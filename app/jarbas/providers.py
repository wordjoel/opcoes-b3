"""Provedores de IA do Jarbas, intercambiáveis e com fallback automático.

Cada provedor só existe se a sua chave estiver em variável de ambiente do servidor; nada
vai ao navegador. Nenhum provedor é tratado como gratuito e ilimitado: cota esgotada (429),
falta de saldo (402) ou falha deixam o provedor de lado por um tempo e a pergunta segue
para o próximo. Cada pergunta faz no máximo uma tentativa por modelo: não há laço de repetição.
"""

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import httpx

# Tempo máximo de cada chamada: o total cabe nos 60 s da função na Vercel.
PROVIDER_TIMEOUT = 25.0
# Prazo total de uma pergunta, somando todas as tentativas.
TOTAL_BUDGET = 45.0
# Modelos que raciocinam antes de responder gastam parte deste limite pensando.
MAX_OUTPUT_TOKENS = 2500
# Menos que isto não dá tempo de um modelo responder: melhor parar e avisar.
MIN_CALL_SECONDS = 4.0
# Modelos gratuitos do OpenRouter mudam e ficam congestionados: a lista é tentada em ordem.
OPENROUTER_FREE_MODELS = "nvidia/nemotron-3-ultra-550b-a55b:free,google/gemma-4-31b-it:free,nvidia/nemotron-3.5-super-vl:free"
TRUNCATED_NOTE = " […resposta cortada pelo limite de tamanho; peça para eu continuar.]"
TEMPERATURE = 0.3
DEFAULT_ORDER = ("openrouter", "gemini", "groq", "custom")

# Quanto tempo um provedor fica de lado depois de cada tipo de falha.
COOLDOWN_QUOTA = 60.0
COOLDOWN_ERROR = 30.0
COOLDOWN_AUTH = 600.0


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user" ou "assistant"
    content: str


@dataclass(frozen=True)
class ProviderReply:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ProviderError(Exception):
    def __init__(self, reason: str, cooldown: float = COOLDOWN_ERROR, fatal: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.cooldown = cooldown
        # Falha da conta (chave ou saldo): não adianta tentar outro modelo do mesmo provedor.
        self.fatal = fatal


def _classify(response: httpx.Response) -> ProviderError:
    status = response.status_code
    if status == 429:
        retry = response.headers.get("retry-after")
        wait = float(retry) if retry and retry.replace(".", "", 1).isdigit() else COOLDOWN_QUOTA
        return ProviderError("cota ou limite de requisições atingido", max(wait, 1.0))
    if status == 402:
        return ProviderError("sem saldo ou crédito no provedor", COOLDOWN_AUTH, fatal=True)
    if status in (401, 403):
        return ProviderError("chave recusada pelo provedor", COOLDOWN_AUTH, fatal=True)
    if status == 404:
        return ProviderError("modelo não encontrado no provedor", COOLDOWN_AUTH)
    if status >= 500:
        return ProviderError(f"provedor fora do ar (erro {status})")
    return ProviderError(f"erro {status} no provedor")


def _tokens(value) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


class Provider:
    name: str
    label: str
    model: str

    def complete(self, system: str, messages: Sequence[ChatMessage], client: httpx.Client) -> ProviderReply:
        raise NotImplementedError


@dataclass
class GeminiProvider(Provider):
    api_key: str
    model: str = "gemini-2.5-flash"
    name: str = "gemini"
    label: str = "Gemini"

    def complete(self, system: str, messages: Sequence[ChatMessage], client: httpx.Client) -> ProviderReply:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "model" if message.role == "assistant" else "user", "parts": [{"text": message.content}]}
                for message in messages
            ],
            "generationConfig": {"temperature": TEMPERATURE, "maxOutputTokens": MAX_OUTPUT_TOKENS},
        }
        response = client.post(url, json=body, headers={"x-goog-api-key": self.api_key}, timeout=PROVIDER_TIMEOUT)
        if response.status_code != 200:
            raise _classify(response)
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise ProviderError(f"resposta bloqueada pelo provedor ({reason})" if reason else "resposta vazia")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise ProviderError("resposta vazia")
        if candidates[0].get("finishReason") == "MAX_TOKENS":
            text += TRUNCATED_NOTE
        usage = data.get("usageMetadata") or {}
        return ProviderReply(text, self.model, _tokens(usage.get("promptTokenCount")), _tokens(usage.get("candidatesTokenCount")))


@dataclass
class OpenAICompatibleProvider(Provider):
    """Groq, OpenRouter e qualquer servidor no formato de chat da OpenAI.

    `model` aceita vários nomes separados por vírgula: se um estiver sem cota, fora do ar
    ou não existir mais, o próximo é tentado antes de passar para outro provedor.
    """

    api_key: str
    model: str
    base_url: str
    name: str
    label: str
    extra_headers: dict = field(default_factory=dict)
    # Campos a mais no corpo, como o raciocínio curto e oculto do OpenRouter.
    extra_body: dict = field(default_factory=dict)
    # Instante (time.monotonic) em que a pergunta precisa terminar; definido pelo gerenciador.
    deadline: float | None = None

    @property
    def models(self) -> list[str]:
        return [item.strip() for item in self.model.split(",") if item.strip()]

    def complete(self, system: str, messages: Sequence[ChatMessage], client: httpx.Client) -> ProviderReply:
        last: ProviderError | None = None
        for model in self.models:
            timeout = PROVIDER_TIMEOUT
            if self.deadline is not None:
                timeout = min(timeout, self.deadline - time.monotonic())
                if timeout < MIN_CALL_SECONDS:
                    last = last or ProviderError("tempo total da pergunta esgotado")
                    break
            try:
                return self._complete_with(model, system, messages, client, timeout)
            except ProviderError as error:
                if error.fatal:
                    raise
                last = error
            except httpx.TimeoutException:
                last = ProviderError("tempo de resposta esgotado")
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                last = ProviderError("falha de rede ou resposta fora do formato")
        raise last or ProviderError("nenhum modelo configurado")

    def _complete_with(
        self, model: str, system: str, messages: Sequence[ChatMessage], client: httpx.Client, timeout: float = PROVIDER_TIMEOUT
    ) -> ProviderReply:
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}]
            + [{"role": message.role, "content": message.content} for message in messages],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_OUTPUT_TOKENS,
            **self.extra_body,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", **self.extra_headers}
        response = client.post(f"{self.base_url.rstrip('/')}/chat/completions", json=body, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise _classify(response)
        data = response.json()
        if data.get("error"):
            code = (data["error"] or {}).get("code") if isinstance(data["error"], dict) else None
            if code in (401, 402, 403, 429) or (isinstance(code, int) and code >= 500):
                raise _classify(httpx.Response(code))
            raise ProviderError("erro informado pelo provedor")
        choices = data.get("choices") or []
        text = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
        if not text:
            raise ProviderError("resposta vazia")
        if choices[0].get("finish_reason") == "length":
            text += TRUNCATED_NOTE
        usage = data.get("usage") or {}
        return ProviderReply(text, data.get("model") or model, _tokens(usage.get("prompt_tokens")), _tokens(usage.get("completion_tokens")))


def providers_from_env(env: dict | None = None) -> list[Provider]:
    """Provedores com chave configurada, na ordem padrão: OpenRouter, Gemini, Groq, personalizado."""
    env = os.environ if env is None else env
    found: list[Provider] = []
    if env.get("OPENROUTER_API_KEY"):
        found.append(
            OpenAICompatibleProvider(
                api_key=env["OPENROUTER_API_KEY"],
                model=env.get("JARBAS_OPENROUTER_MODEL") or OPENROUTER_FREE_MODELS,
                base_url="https://openrouter.ai/api/v1",
                name="openrouter",
                label="OpenRouter",
                extra_headers={"X-Title": "B3 Opcoes Pro - Jarbas"},
                # Modelos que raciocinam: pouco raciocínio e fora da resposta, para sobrar espaço ao texto.
                extra_body={"reasoning": {"effort": "low", "exclude": True}},
            )
        )
    if env.get("GEMINI_API_KEY"):
        found.append(GeminiProvider(api_key=env["GEMINI_API_KEY"], model=env.get("JARBAS_GEMINI_MODEL") or "gemini-2.5-flash"))
    if env.get("GROQ_API_KEY"):
        found.append(
            OpenAICompatibleProvider(
                api_key=env["GROQ_API_KEY"],
                model=env.get("JARBAS_GROQ_MODEL") or "llama-3.3-70b-versatile",
                base_url="https://api.groq.com/openai/v1",
                name="groq",
                label="Groq",
            )
        )
    # Ex.: um agente próprio exposto num endpoint compatível com a OpenAI.
    if env.get("JARBAS_CUSTOM_BASE_URL") and env.get("JARBAS_CUSTOM_MODEL"):
        found.append(
            OpenAICompatibleProvider(
                api_key=env.get("JARBAS_CUSTOM_API_KEY", ""),
                model=env["JARBAS_CUSTOM_MODEL"],
                base_url=env["JARBAS_CUSTOM_BASE_URL"],
                name="custom",
                label=env.get("JARBAS_CUSTOM_LABEL") or "Personalizado",
            )
        )
    return found


@dataclass(frozen=True)
class Attempt:
    provider: str
    error: str | None


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    label: str
    model: str
    attempts: tuple[Attempt, ...]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int = 0


class AllProvidersFailed(Exception):
    def __init__(self, attempts: Sequence[Attempt]):
        super().__init__("nenhum provedor respondeu")
        self.attempts = tuple(attempts)


class ProviderManager:
    """Tenta os provedores em ordem, pulando os que estão em pausa por falha recente."""

    def __init__(self, providers: Sequence[Provider], clock: Callable[[], float] = time.monotonic):
        self.providers = list(providers)
        self.clock = clock
        self._paused_until: dict[str, float] = {}

    def apply(self, order: Sequence[str] | None = None, openrouter_models: str | None = None) -> None:
        """Aplica a configuração gravada pelo proprietário, sem perder as pausas em curso."""
        rank = {name: index for index, name in enumerate(order or DEFAULT_ORDER)}
        self.providers.sort(key=lambda provider: rank.get(provider.name, len(rank)))
        if openrouter_models:
            for provider in self.providers:
                if provider.name == "openrouter" and isinstance(provider, OpenAICompatibleProvider):
                    provider.model = openrouter_models

    def status(self) -> list[dict]:
        now = self.clock()
        return [
            {"name": p.name, "label": p.label, "model": p.model.split(",")[0], "paused": self._paused_until.get(p.name, 0) > now}
            for p in self.providers
        ]

    def complete(self, system: str, messages: Sequence[ChatMessage], client: httpx.Client) -> Completion:
        attempts: list[Attempt] = []
        started = self.clock()
        ready = [p for p in self.providers if self._paused_until.get(p.name, 0) <= started]
        # Se todos estiverem em pausa, tenta mesmo assim: a pausa é só uma economia de tempo.
        for provider in ready or self.providers:
            if self.clock() - started > TOTAL_BUDGET:
                attempts.append(Attempt(provider.name, "tempo total da pergunta esgotado"))
                break
            if isinstance(provider, OpenAICompatibleProvider):
                # O provedor mede no relógio real; o gerenciador pode usar outro nos testes.
                provider.deadline = time.monotonic() + TOTAL_BUDGET - (self.clock() - started)
            try:
                reply = provider.complete(system, messages, client)
            except ProviderError as error:
                self._paused_until[provider.name] = self.clock() + error.cooldown
                attempts.append(Attempt(provider.name, error.reason))
                continue
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                # Rede, timeout ou JSON fora do formato: nunca repassa o detalhe, que pode citar a URL.
                self._paused_until[provider.name] = self.clock() + COOLDOWN_ERROR
                attempts.append(Attempt(provider.name, "falha de rede ou resposta fora do formato"))
                continue
            attempts.append(Attempt(provider.name, None))
            return Completion(
                reply.text,
                provider.name,
                provider.label,
                reply.model,
                tuple(attempts),
                reply.prompt_tokens,
                reply.completion_tokens,
                int((self.clock() - started) * 1000),
            )
        raise AllProvidersFailed(attempts)
