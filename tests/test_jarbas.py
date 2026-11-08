"""Jarbas IA: fallback entre provedores, contexto da estrutura, limites e segurança das chaves.

Os provedores são simulados com httpx.MockTransport: nenhum teste chama a rede.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, create_session, hash_password
from app.jarbas.assistant import StrategyContext, describe, recent_turns, system_prompt
from app.jarbas.providers import (
    AllProvidersFailed,
    ChatMessage,
    GeminiProvider,
    OpenAICompatibleProvider,
    ProviderManager,
    providers_from_env,
)
from app.main import Settings, create_app
from db.client import Database, migrate
from tests.test_api import NOW, PASSWORD, SECRET, FakeProvider

GEMINI_KEY = "gem-segredo-123"
GROQ_KEY = "groq-segredo-456"
ROUTER_KEY = "or-segredo-789"


def gemini_ok(text="Resposta do Gemini."):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def openai_ok(text):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


class Router:
    """Responde conforme o host e guarda as requisições recebidas."""

    def __init__(self, gemini=None, groq=None, openrouter=None):
        self.handlers = {"generativelanguage.googleapis.com": gemini, "api.groq.com": groq, "openrouter.ai": openrouter}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        handler = self.handlers[request.url.host]
        if isinstance(handler, Exception):
            raise handler
        return handler if isinstance(handler, httpx.Response) else handler(request)

    def hosts(self):
        return [request.url.host for request in self.requests]


def all_providers(order=("gemini", "groq", "openrouter")):
    """Ordem fixa nos testes de fallback; a ordem padrão (OpenRouter primeiro) tem teste próprio."""
    found = providers_from_env({"GEMINI_API_KEY": GEMINI_KEY, "GROQ_API_KEY": GROQ_KEY, "OPENROUTER_API_KEY": ROUTER_KEY})
    return sorted(found, key=lambda provider: order.index(provider.name))


def ask(manager, router, text="Como monto?"):
    with httpx.Client(transport=httpx.MockTransport(router)) as client:
        return manager.complete("sistema", [ChatMessage("user", text)], client)


class TestProviders:
    def test_order_follows_priority_and_only_configured(self):
        assert [p.name for p in providers_from_env({"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q", "OPENROUTER_API_KEY": "o"})] == ["openrouter", "gemini", "groq"]
        assert [p.name for p in providers_from_env({"OPENROUTER_API_KEY": "x"})] == ["openrouter"]
        assert providers_from_env({}) == []

    def test_models_are_configurable(self):
        found = providers_from_env({"GEMINI_API_KEY": "x", "JARBAS_GEMINI_MODEL": "gemini-outro"})
        assert found[0].model == "gemini-outro"

    def test_gemini_answers_first_with_key_in_header(self):
        router = Router(gemini=gemini_ok())
        result = ask(ProviderManager(all_providers()), router)
        assert result.provider == "gemini" and result.text == "Resposta do Gemini."
        request = router.requests[0]
        assert request.headers["x-goog-api-key"] == GEMINI_KEY
        assert GEMINI_KEY not in str(request.url)
        body = json.loads(request.content)
        assert body["systemInstruction"]["parts"][0]["text"] == "sistema"
        assert body["contents"][0] == {"role": "user", "parts": [{"text": "Como monto?"}]}

    def test_quota_on_gemini_falls_back_to_groq(self):
        router = Router(gemini=httpx.Response(429, json={}), groq=openai_ok("Resposta do Groq."))
        manager = ProviderManager(all_providers())
        result = ask(manager, router)
        assert result.provider == "groq"
        assert [(a.provider, a.error) for a in result.attempts] == [("gemini", "cota ou limite de requisições atingido"), ("groq", None)]
        assert router.requests[1].headers["authorization"] == f"Bearer {GROQ_KEY}"
        # Em pausa depois da cota: a próxima pergunta nem tenta o Gemini.
        ask(manager, router)
        assert router.hosts()[2:] == ["api.groq.com"]

    def test_groq_failure_falls_back_to_openrouter(self):
        router = Router(gemini=httpx.Response(500), groq=httpx.ConnectTimeout("t"), openrouter=openai_ok("Resposta do OpenRouter."))
        result = ask(ProviderManager(all_providers()), router)
        assert result.provider == "openrouter" and result.label == "OpenRouter"
        assert router.requests[2].url.path == "/api/v1/chat/completions"
        assert json.loads(router.requests[2].content)["model"].endswith(":free")

    def test_openrouter_tries_the_next_free_model(self):
        seen = []

        def handler(request):
            model = json.loads(request.content)["model"]
            seen.append(model)
            return httpx.Response(429) if model == "a:free" else httpx.Response(404) if model == "b:free" else openai_ok(f"pelo {model}")

        providers = providers_from_env({"OPENROUTER_API_KEY": ROUTER_KEY, "JARBAS_OPENROUTER_MODEL": "a:free, b:free ,c:free"})
        result = ask(ProviderManager(providers), Router(openrouter=handler))
        assert seen == ["a:free", "b:free", "c:free"] and result.text == "pelo c:free"

    def test_rejected_key_does_not_try_other_models(self):
        seen = []

        def handler(request):
            seen.append(json.loads(request.content)["model"])
            return httpx.Response(401)

        providers = providers_from_env({"OPENROUTER_API_KEY": ROUTER_KEY, "JARBAS_OPENROUTER_MODEL": "a:free,b:free"})
        with pytest.raises(AllProvidersFailed):
            ask(ProviderManager(providers), Router(openrouter=handler))
        assert seen == ["a:free"]

    def test_truncated_answer_is_marked(self):
        cut = httpx.Response(200, json={"choices": [{"message": {"content": "1. Compre"}, "finish_reason": "length"}]})
        result = ask(ProviderManager(providers_from_env({"GROQ_API_KEY": "x"})), Router(groq=cut))
        assert result.text.startswith("1. Compre") and "cortada" in result.text

    def test_timeout_in_one_model_tries_the_next(self):
        def handler(request):
            if json.loads(request.content)["model"] == "lento:free":
                raise httpx.ReadTimeout("lento")
            return openai_ok("pelo rápido")

        providers = providers_from_env({"OPENROUTER_API_KEY": ROUTER_KEY, "JARBAS_OPENROUTER_MODEL": "lento:free,rapido:free"})
        assert ask(ProviderManager(providers), Router(openrouter=handler)).text == "pelo rápido"

    def test_openrouter_asks_for_short_hidden_reasoning(self):
        router = openrouter_router()
        ask(ProviderManager(providers_from_env({"OPENROUTER_API_KEY": ROUTER_KEY})), router)
        sent = [json.loads(r.content) for r in router.requests if r.method == "POST"][0]
        assert sent["reasoning"] == {"effort": "low", "exclude": True}

    def test_deadline_stops_trying_more_models(self):
        import time as clock

        seen = []

        def handler(request):
            seen.append(json.loads(request.content)["model"])
            return httpx.Response(429)

        provider = providers_from_env({"OPENROUTER_API_KEY": ROUTER_KEY, "JARBAS_OPENROUTER_MODEL": "a:free,b:free"})[0]
        provider.deadline = clock.monotonic() + 1  # menos que o mínimo por chamada
        with httpx.Client(transport=httpx.MockTransport(Router(openrouter=handler))) as client:
            with pytest.raises(Exception):
                provider.complete("s", [ChatMessage("user", "x")], client)
        assert seen == []

    def test_consecutive_questions_are_merged(self):
        turns = recent_turns([ChatMessage("user", "a"), ChatMessage("user", "b"), ChatMessage("assistant", "c"), ChatMessage("user", "d")])
        assert [(t.role, t.content) for t in turns] == [("user", "a\nb"), ("assistant", "c"), ("user", "d")]

    def test_catalog_skips_models_that_do_not_chat(self):
        from app.jarbas.catalog import parse_models

        models = parse_models({"data": [
            {"id": "musica:free", "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["audio"]}},
            {"id": "texto:free", "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["text"]}},
            {"id": "imagem", "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"modality": "text->image"}},
        ]})
        assert [m["id"] for m in models] == ["texto:free"]

    def test_bad_key_and_empty_answers_are_failures(self):
        router = Router(gemini=httpx.Response(403), groq=openai_ok(""), openrouter=httpx.Response(200, json={"choices": []}))
        with pytest.raises(AllProvidersFailed) as failure:
            ask(ProviderManager(all_providers()), router)
        assert [a.error for a in failure.value.attempts] == ["chave recusada pelo provedor", "resposta vazia", "resposta vazia"]

    def test_blocked_gemini_answer_is_reported(self):
        router = Router(gemini=httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}), groq=openai_ok("ok"))
        result = ask(ProviderManager(all_providers()), router)
        assert "bloqueada" in result.attempts[0].error and result.provider == "groq"

    def test_retry_after_sets_the_pause(self):
        clock = [0.0]
        manager = ProviderManager(all_providers(), clock=lambda: clock[0])
        ask(manager, Router(gemini=httpx.Response(429, headers={"retry-after": "5"}), groq=openai_ok("ok")))
        assert manager.status()[0]["paused"] is True
        clock[0] = 6.0
        assert manager.status()[0]["paused"] is False

    def test_paused_providers_are_still_tried_when_all_are_paused(self):
        manager = ProviderManager([GeminiProvider(api_key="x")])
        with pytest.raises(AllProvidersFailed):
            ask(manager, Router(gemini=httpx.Response(429)))
        assert ask(manager, Router(gemini=gemini_ok("voltou"))).text == "voltou"

    def test_network_details_never_leak(self):
        provider = OpenAICompatibleProvider(api_key="k", model="m", base_url="https://api.groq.com/openai/v1", name="groq", label="Groq")
        with pytest.raises(AllProvidersFailed) as failure:
            ask(ProviderManager([provider]), Router(groq=httpx.ConnectError("https://api.groq.com/segredo")))
        assert failure.value.attempts[0].error == "falha de rede ou resposta fora do formato"


CONTEXT = {
    "symbol": "PETR4",
    "structure_key": "call_butterfly",
    "structure_name": "Borboleta com call",
    "market_date": "2026-11-03",
    "spot": 40.0,
    "expiry": "2026-12-18",
    "business_days_to_expiry": 31,
    "net_premium": 50.0,
    "max_profit": 150.0,
    "max_loss": 50.0,
    "breakevens": [38.5, 41.5],
    "probability_of_profit": 0.31,
    "decision_status": "INCOMPLETA",
    "decision_missing": ["custos operacionais não informados"],
    "warnings": ["Prêmios pelo fechamento do pregão."],
    "legs": [
        {"symbol": "PETRL420", "action": "SELL", "kind": "CALL", "strike": 40, "quantity": 200, "premium": 1.0, "style": "AMERICAN"},
        {"symbol": "PETRL380", "action": "BUY", "kind": "CALL", "strike": 38, "quantity": 100, "premium": 2.25},
        {"symbol": "PETRL440", "action": "BUY", "kind": "CALL", "strike": 42, "quantity": 100, "premium": 0.25},
    ],
}


class TestContext:
    def test_describes_real_data_in_assembly_order(self):
        text = describe(StrategyContext(**CONTEXT))
        assert text.index("1. Comprar 100 PETRL380") < text.index("2. Comprar 100 PETRL440") < text.index("3. Vender 200 PETRL420")
        assert "débito (o usuário paga) de R$ 50,00" in text
        assert "R$ 38,50, R$ 41,50" in text
        assert "americana" in text
        assert "Falta para decidir: custos operacionais não informados." in text
        assert "31,0%" in text

    def test_stale_grid_is_flagged(self):
        text = describe(StrategyContext(**{**CONTEXT, "spot_drift": 0.05}))
        assert "defasados" in text

    def test_prompt_states_the_rules_and_isolates_data(self):
        prompt = system_prompt(StrategyContext(**CONTEXT))
        assert "Nunca invente preço" in prompt and "não envia ordens" in prompt and "Nunca prometa lucro" in prompt
        assert prompt.index("<<<") < prompt.index("PETRL380") < prompt.index(">>>")
        assert "nenhuma estrutura selecionada" in system_prompt(None)

    def test_recent_turns_start_with_user_and_are_capped(self):
        turns = [ChatMessage("assistant", "oi")] + [ChatMessage("user" if i % 2 == 0 else "assistant", f"m{i}") for i in range(40)]
        kept = recent_turns(turns)
        assert kept[0].role == "user" and len(kept) <= 16


@pytest.fixture(autouse=True)
def fresh_caches():
    from app.jarbas import catalog, tools

    catalog._cache.update(at=None, models=[])
    tools._cache.clear()
    yield


def make_client(tmp_path, router=None, env=None, db=None):
    db = db or Database(str(tmp_path / "jarbas.db"))
    migrate(db)
    manager = ProviderManager(providers_from_env(env if env is not None else {"GEMINI_API_KEY": GEMINI_KEY, "GROQ_API_KEY": GROQ_KEY}))
    app = create_app(
        Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True),
        lambda: db,
        lambda _: FakeProvider(),
        now=lambda: NOW,
        ai_manager=manager,
        ai_transport=httpx.MockTransport(router or Router(gemini=gemini_ok("Compre primeiro as pontas."))),
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
    client.db = db
    return client


def chat(client, question="Como monto essa operação?", context=CONTEXT, conversation=None):
    body = {"question": question, "context": context}
    if conversation:
        body["conversation_id"] = conversation
    return client.post("/api/jarbas/chat", json=body)


def sent_prompt(router, index=-1):
    return json.loads(router.requests[index].content)["systemInstruction"]["parts"][0]["text"]


CATALOG = {
    "data": [
        {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "Nemotron", "context_length": 1000000, "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "google/gemma-4-31b-it:free", "name": "Gemma", "context_length": 262144, "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "openai/gpt-pago", "name": "Pago", "context_length": 128000, "pricing": {"prompt": "0.000002", "completion": "0.000008"}},
    ]
}


def openrouter_router(reply="Pelo OpenRouter."):
    seen = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=CATALOG)
        seen.append(json.loads(request.content)["model"])
        return openai_ok(reply)

    router = Router(openrouter=handler)
    router.models_seen = seen
    return router


class TestApi:
    def test_answers_with_provider_and_sends_context(self, tmp_path):
        router = Router(gemini=gemini_ok("Compre primeiro as pontas."))
        client = make_client(tmp_path, router)
        response = chat(client)
        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "Compre primeiro as pontas." and body["provider"] == "Gemini"
        assert len(body["conversation_id"]) == 32
        sent = sent_prompt(router)
        assert "PETRL380" in sent and "Borboleta com call" in sent

    def test_fallback_through_the_api(self, tmp_path):
        client = make_client(tmp_path, Router(gemini=httpx.Response(429), groq=openai_ok("Pelo Groq.")))
        client.put("/api/jarbas/settings", json={**SETTINGS, "provider_order": ["gemini", "groq"]})
        body = chat(client).json()
        assert body["provider"] == "Groq" and body["attempts"][0]["provider"] == "gemini"
        usage = client.get("/api/jarbas/status").json()["usage"]
        assert usage["requests"] == 2 and usage["failures"] == 1

    def test_all_failing_is_503_without_secrets(self, tmp_path):
        client = make_client(tmp_path, Router(gemini=httpx.Response(500), groq=httpx.Response(401)))
        client.put("/api/jarbas/settings", json={**SETTINGS, "provider_order": ["gemini", "groq"]})
        response = chat(client)
        assert response.status_code == 503
        assert GEMINI_KEY not in response.text and GROQ_KEY not in response.text
        assert response.json()["detail"]["attempts"][1]["error"] == "chave recusada pelo provedor"

    def test_without_providers_is_503(self, tmp_path):
        client = make_client(tmp_path, env={})
        assert chat(client).status_code == 503
        assert client.get("/api/jarbas/status").json()["available"] is False

    def test_status_never_shows_keys(self, tmp_path):
        client = make_client(tmp_path)
        status = client.get("/api/jarbas/status").json()
        assert {p["label"] for p in status["providers"]} == {"Gemini", "Groq"}
        assert GEMINI_KEY not in json.dumps(status) and GROQ_KEY not in json.dumps(status)
        assert status["usage"]["daily_limit"] == 200

    def test_requires_session(self, tmp_path):
        client = make_client(tmp_path)
        client.cookies.clear()
        for method, path in [("post", "/api/jarbas/chat"), ("get", "/api/jarbas/status"), ("get", "/api/jarbas/settings"),
                             ("get", "/api/jarbas/models"), ("get", "/api/jarbas/conversations")]:
            assert getattr(client, method)(path, **({"json": {"question": "x"}} if method == "post" else {})).status_code == 401

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"question": ""},
            {"question": "x" * 2001},
            {"question": "x", "conversation_id": "nao-e-hex"},
            {"question": "x", "context": {**CONTEXT, "legs": []}},
            {"question": "x", "context": {**CONTEXT, "spot": -1}},
        ],
    )
    def test_invalid_input_is_refused(self, tmp_path, body):
        assert make_client(tmp_path).post("/api/jarbas/chat", json=body).status_code == 422

    def test_rate_limit_protects_the_free_quota(self, tmp_path):
        client = make_client(tmp_path)
        codes = [chat(client).status_code for _ in range(21)]
        assert codes[:20] == [200] * 20 and codes[20] == 429


SETTINGS = {
    "provider_order": ["openrouter", "gemini", "groq"],
    "openrouter_model": None,
    "allow_paid": False,
    "daily_limit": 200,
    "retention_days": 90,
    "speak_replies": True,
    "voice_name": None,
    "voice_rate": 1.0,
}


class TestHistory:
    def test_conversation_is_persisted_and_continued(self, tmp_path):
        router = Router(gemini=gemini_ok("Resposta."))
        client = make_client(tmp_path, router)
        first = chat(client, "Como monto essa operação?").json()
        second = chat(client, "E quando devo sair?", conversation=first["conversation_id"]).json()
        assert second["conversation_id"] == first["conversation_id"]
        # A segunda pergunta leva a conversa anterior ao modelo.
        contents = json.loads(router.requests[-1].content)["contents"]
        assert [c["parts"][0]["text"] for c in contents] == ["Como monto essa operação?", "Resposta.", "E quando devo sair?"]
        listed = client.get("/api/jarbas/conversations").json()["conversations"]
        assert listed[0]["title"] == "Como monto essa operação?" and listed[0]["messages"] == 4
        detail = client.get(f"/api/jarbas/conversations/{first['conversation_id']}").json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
        assert detail["messages"][1]["provider"] == "Gemini"

    def test_history_survives_another_instance(self, tmp_path):
        client = make_client(tmp_path)
        identity = chat(client).json()["conversation_id"]
        other = make_client(tmp_path, db=client.db)
        assert other.get(f"/api/jarbas/conversations/{identity}").status_code == 200

    def test_delete_and_unknown(self, tmp_path):
        client = make_client(tmp_path)
        identity = chat(client).json()["conversation_id"]
        assert client.delete(f"/api/jarbas/conversations/{identity}").json() == {"deleted": True}
        assert client.get(f"/api/jarbas/conversations/{identity}").status_code == 404
        assert client.delete(f"/api/jarbas/conversations/{'0' * 32}").status_code == 404

    def test_unknown_conversation_starts_a_new_one(self, tmp_path):
        client = make_client(tmp_path)
        body = chat(client, conversation="a" * 32).json()
        assert body["conversation_id"] != "a" * 32

    def test_daily_limit_is_enforced_from_the_database(self, tmp_path):
        client = make_client(tmp_path)
        client.put("/api/jarbas/settings", json={**SETTINGS, "daily_limit": 2})
        assert [chat(client).status_code for _ in range(3)] == [200, 200, 429]
        assert "Limite diário" in chat(client).json()["detail"]

    def test_retention_purges_old_messages(self, tmp_path):
        from datetime import timedelta

        from app.jarbas import store

        client = make_client(tmp_path)
        identity = chat(client).json()["conversation_id"]
        store.purge(client.db, 1, NOW + timedelta(days=3))
        assert store.get_conversation(client.db, identity) is None
        assert client.db.fetch("SELECT COUNT(*) FROM jarbas_usage")[0][0] == 0

    def test_no_api_key_is_stored(self, tmp_path):
        client = make_client(tmp_path)
        chat(client)
        client.put("/api/jarbas/settings", json=SETTINGS)
        dump = json.dumps([client.db.fetch(f"SELECT * FROM {t}") for t in ("jarbas_settings", "jarbas_conversations", "jarbas_messages", "jarbas_usage")])
        assert GEMINI_KEY not in dump and GROQ_KEY not in dump


class TestSettingsAndModels:
    def test_defaults_and_save(self, tmp_path):
        client = make_client(tmp_path)
        assert client.get("/api/jarbas/settings").json()["provider_order"][0] == "openrouter"
        saved = client.put("/api/jarbas/settings", json={**SETTINGS, "voice_rate": 1.2, "speak_replies": False}).json()
        assert saved["voice_rate"] == 1.2 and saved["speak_replies"] is False and saved["updated_at"]
        assert client.get("/api/jarbas/status").json()["voice"]["speak_replies"] is False

    @pytest.mark.parametrize(
        "change",
        [{"provider_order": ["gemini", "gemini"]}, {"provider_order": ["outro"]}, {"daily_limit": 0}, {"voice_rate": 3}, {"openrouter_model": "x y"}],
    )
    def test_invalid_settings(self, tmp_path, change):
        assert make_client(tmp_path).put("/api/jarbas/settings", json={**SETTINGS, **change}).status_code == 422

    def test_catalog_marks_free_and_paid_and_blocks_paid_without_authorization(self, tmp_path):
        router = openrouter_router()
        client = make_client(tmp_path, router, env={"OPENROUTER_API_KEY": ROUTER_KEY})
        listed = client.get("/api/jarbas/models").json()
        assert listed["configured"] is True
        assert [m["free"] for m in listed["models"]] == [True, True, False]
        assert listed["chain"] == ["nvidia/nemotron-3-ultra-550b-a55b:free", "google/gemma-4-31b-it:free"]
        refused = client.put("/api/jarbas/settings", json={**SETTINGS, "openrouter_model": "openai/gpt-pago"})
        assert refused.status_code == 422 and "cobrança" in refused.json()["detail"]
        assert client.put("/api/jarbas/settings", json={**SETTINGS, "openrouter_model": "inexistente/x:free"}).status_code == 422
        assert client.put("/api/jarbas/settings", json={**SETTINGS, "openrouter_model": "openai/gpt-pago", "allow_paid": True}).status_code == 200

    def test_selected_model_goes_first_and_paid_only_when_allowed(self, tmp_path):
        router = openrouter_router()
        client = make_client(tmp_path, router, env={"OPENROUTER_API_KEY": ROUTER_KEY})
        client.put("/api/jarbas/settings", json={**SETTINGS, "openrouter_model": "google/gemma-4-31b-it:free"})
        assert chat(client).json()["model"] == "google/gemma-4-31b-it:free"
        assert router.models_seen[-1] == "google/gemma-4-31b-it:free"
        client.put("/api/jarbas/settings", json={**SETTINGS, "openrouter_model": "openai/gpt-pago", "allow_paid": True})
        chat(client)
        assert router.models_seen[-1] == "openai/gpt-pago"

    def test_models_without_openrouter(self, tmp_path):
        assert make_client(tmp_path).get("/api/jarbas/models").json() == {"configured": False, "models": [], "chain": []}


class TestSystemTools:
    def test_portfolio_question_reads_the_real_portfolio(self, tmp_path):
        router = Router(gemini=gemini_ok("ok"))
        client = make_client(tmp_path, router)
        client.put("/api/portfolio/settings", json={"initial_cash_brl": 1000, "max_position_size": 500})
        client.post("/api/portfolio/fills", json={"symbol": "PETRL500", "side": "BUY", "quantity": 100, "price": 1.5, "fees_brl": 2.0, "trade_day": "2026-11-03"})
        body = chat(client, "Como está minha carteira?", context=None).json()
        assert body["tools"] == ["carteira"]
        prompt = sent_prompt(router)
        assert "Caixa: R$ 848,00" in prompt and "PETRL500: 100 opções" in prompt
        assert "não calcula margem, resultado em aberto" in prompt

    def test_market_question_reads_the_scanner_with_labels(self, tmp_path):
        router = Router(gemini=gemini_ok("ok"))
        client = make_client(tmp_path, router)
        body = chat(client, "Quais ativos apresentam volatilidade interessante hoje?", context=None).json()
        assert "mercado" in body["tools"]
        prompt = sent_prompt(router)
        assert "PANORAMA DOS ATIVOS" in prompt and "PETR4: preço" in prompt
        assert "[CALCULADO" in prompt and "[HISTÓRICO]" in prompt
        assert "Só está DEFASADA a grade marcada como GRADE DEFASADA" in prompt

    def test_spread_question_ranks_real_chain(self, tmp_path):
        router = Router(gemini=gemini_ok("ok"))
        client = make_client(tmp_path, router)
        body = chat(client, "Quais travas de PETR4 apresentam melhor retorno?", context=None).json()
        assert "travas" in body["tools"]
        prompt = sent_prompt(router)
        assert "TRAVAS COM MELHOR ESTIMATIVA" in prompt and "PETR4 vencimento" in prompt and "ainda não passaram pela decisão" in prompt
        assert "Trava de" in prompt and "_spread" not in prompt

    def test_question_about_the_structure_does_not_scan_the_market(self, tmp_path):
        router = Router(gemini=gemini_ok("ok"))
        client = make_client(tmp_path, router)
        assert chat(client, "Como monto essa operação?").json()["tools"] == []
        assert "DADOS DO SISTEMA (consultados" not in sent_prompt(router)

    def test_failing_source_becomes_unavailable_not_invented(self, tmp_path, monkeypatch):
        from app import service

        def broken(*_args, **_kwargs):
            raise RuntimeError("fonte fora")

        monkeypatch.setattr(service, "scanner", broken)
        router = Router(gemini=gemini_ok("ok"))
        client = make_client(tmp_path, router)
        chat(client, "Quais oportunidades merecem atenção hoje?", context=None)
        assert "PANORAMA DOS ATIVOS: INDISPONÍVEL" in sent_prompt(router)
