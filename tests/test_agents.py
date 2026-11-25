"""Agentes do Jarbas: plano, ferramentas, memória e decisão de risco.

Nenhum teste chama rede. O provedor e a fonte de mercado são simulados, e as
funções reais de estratégia/RiskManager são substituídas por espiões quando o
objetivo é verificar a composição da ferramenta de hedge.
"""

from collections.abc import Sequence
from datetime import date, datetime, timezone

from app import carteira, service
from app.agents.memory_manager import MemoryManager
from app.agents.orchestrator import Orchestrator
from app.agents.specialists import specialists_for, tools_for
from app.agents.tools import AgentContext, AgentTool, ToolResult, hedge_and_risk
from app.jarbas.providers import ChatMessage, Provider, ProviderManager, ProviderReply
from db.client import Database, migrate

NOW = datetime(2026, 11, 25, 13, 0, tzinfo=timezone.utc)


class RecordingProvider(Provider):
    name = "fake"
    label = "Fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.systems: list[str] = []
        self.turns: list[Sequence[ChatMessage]] = []

    def complete(self, system: str, messages: Sequence[ChatMessage], client) -> ProviderReply:
        self.systems.append(system)
        self.turns.append(messages)
        return ProviderReply("Resposta do orquestrador.", self.model, 12, 7)


class FakeSource:
    def get_expirations(self, symbol: str) -> list[date]:
        return [date(2026, 12, 15), date(2026, 12, 22)]


def agent_context(question: str, db: Database, watchlist: Sequence[str] = ("PETR4",)) -> AgentContext:
    return AgentContext(
        question=question,
        db=db,
        provider_factory=FakeSource,
        watchlist=watchlist,
        now=NOW,
        clock=lambda: 0.0,
    )


class TestSpecialists:
    def test_hedge_selects_scanner_and_risk_tools(self):
        found = specialists_for("Como faço hedge de PETR4?", False)
        names = [specialist.name for specialist in found]
        tools = tools_for(found)
        assert names == ["scanner", "risco"]
        assert "mercado" in tools and "hedge_risco" in tools

    def test_conceptual_question_with_structure_activates_no_tool(self):
        found = specialists_for("Explique esta estratégia", True)
        assert found == [] and tools_for(found) == []

    def test_generic_question_without_structure_uses_scanner(self):
        assert [s.name for s in specialists_for("Quais oportunidades hoje?", False)] == ["scanner"]


class TestMemory:
    def test_recall_ranks_terms_and_never_stores_secrets(self, tmp_path):
        db = Database(str(tmp_path / "memory.db"))
        migrate(db)
        manager = MemoryManager()
        assert manager.remember(db, "abc", "user", "Prefiro hedge de PETR4 em borboleta.", NOW)
        assert manager.remember(db, "abc", "assistant", "Anotei sua preferência.", NOW)
        assert not manager.remember(db, "abc", "user", "sk-abcdefgh12345678", NOW)
        assert not manager.remember(db, "abc", "user", "senha: muito-secreta", NOW)
        records = manager.recall(db, "hedge PETR4")
        assert records and "PETR4" in records[0].content
        assert "sk-abcdefgh12345678" not in str(db.fetch("SELECT content FROM jarbas_memory"))
        assert manager.recall(db, "xyz") == []


class TestHedgeTool:
    def test_combines_scanner_and_risk_manager_verdict(self, tmp_path, monkeypatch):
        db = Database(str(tmp_path / "hedge.db"))
        migrate(db)
        view = {
            "symbol": "PETR4",
            "expiry": "2026-12-15",
            "market_date": "2026-11-25",
            "candidates": [
                {
                    "key": "bull_call_spread#1",
                    "name": "Trava de alta 38/42",
                    "decision": {"status": "REPROVADA", "reasons": ["grade defasada"], "missing": []},
                    "ranking": {"expected_return_on_risk": 0.4},
                }
            ],
        }
        seen: dict[str, object] = {}

        def fake_view(*args, **kwargs):
            seen["strategies_view"] = args[1]
            return view

        def fake_review(database, received):
            seen["review"] = True
            return {"bull_call_spread#1": {"decision": "REJECTED", "reasons": ["EXPOSURE_LIMIT"]}}

        def fake_apply(received, verdicts):
            received["candidates"][0]["portfolio"] = {"decision": "REJECTED", "reasons": ["EXPOSURE_LIMIT"]}

        monkeypatch.setattr(service, "strategies_view", fake_view)
        monkeypatch.setattr(carteira, "review_candidates", fake_review)
        monkeypatch.setattr(carteira, "apply_review", fake_apply)

        result = hedge_and_risk(agent_context("Faça hedge de PETR4", db))
        assert result.ok
        assert seen["strategies_view"] == "PETR4" and seen["review"] is True
        assert result.attempts == ("scanner", "risk_manager")
        assert "decisão REPROVADA" in result.text
        assert "carteira: EXPOSURE_LIMIT" in result.text

    def test_unknown_symbol_is_unavailable(self, tmp_path):
        result = hedge_and_risk(agent_context("Faça hedge", Database(str(tmp_path / "empty.db")), ()))
        assert result.ok is False and "INDISPONÍVEL" in result.text


class TestOrchestrator:
    def test_plan_and_prompt_reach_the_provider(self, tmp_path):
        db = Database(str(tmp_path / "orchestrator.db"))
        migrate(db)
        provider = RecordingProvider()
        tools = [
            AgentTool("mercado", "", lambda ctx: ToolResult("mercado", "PETR4: preço REAL 40,00")),
            AgentTool(
                "hedge_risco",
                "",
                lambda ctx: ToolResult(
                    "hedge_risco", "HEDGE: decisão REPROVADA pelo RiskManager", attempts=("scanner", "risk_manager")
                ),
            ),
        ]
        orchestrator = Orchestrator(ProviderManager([provider]), tools=tools)
        result = orchestrator.run(
            question="Como faço hedge de PETR4?",
            context=None,
            history=[],
            db=db,
            client=None,  # type: ignore[arg-type]
            provider_factory=FakeSource,
            watchlist=["PETR4"],
            now=NOW,
        )
        assert result.provider == "fake" and result.text == "Resposta do orquestrador."
        assert "mercado" in result.tools and "hedge_risco" in result.tools
        assert result.specialists == ("scanner", "risco")
        assert "ferramenta:hedge_risco" in result.plan
        prompt = provider.systems[-1]
        assert "ÁREA scanner" in prompt and "ÁREA risco" in prompt
        assert "PETR4: preço REAL 40,00" in prompt
        assert "HEDGE: decisão REPROVADA" in prompt
