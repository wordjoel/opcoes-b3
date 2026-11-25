"""Ferramentas dos agentes: adaptação tipada sobre os motores já existentes.

Arquitetura: um ``AgentTool`` recebe um ``AgentContext`` imutável e devolve um
``ToolResult`` rotulado. O orquestrador escolhe quais ferramentas rodam, mas
nenhuma delas escreve no mercado, envia ordens ou inventa dado ausente. O caso
de hedge (por exemplo, PETR4) reutiliza ``service.strategies_view`` e
``carteira.review_candidates``, que já passam as estruturas pelo ``RiskManager``
com a carteira real do proprietário.
"""

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from app import carteira, service
from app.jarbas import tools as jarbas_tools
from core.clock import market_today
from core.exceptions import DataInsufficientError
from data.normalizer import is_stock_symbol, normalize_symbol
from data.providers.base import DataProvider
from db.client import Database
from quant.risk import RiskLimits

ProviderFactory = Callable[[], DataProvider]


@dataclass(frozen=True)
class AgentContext:
    """Entrada compartilhada por todas as ferramentas e especialistas."""

    question: str
    db: Database
    provider_factory: ProviderFactory
    watchlist: Sequence[str]
    now: datetime
    clock: Callable[[], float] = time.monotonic
    has_context: bool = False
    context_symbol: str | None = None
    max_drift: float = RiskLimits().max_spot_drift
    memory_text: str = ""
    rag_text: str = ""
    _provider: DataProvider | None = field(default=None, repr=False, compare=False)

    def source(self) -> DataProvider:
        """Uma instância de fonte por pergunta, compartilhada entre ferramentas."""
        if self._provider is None:
            object.__setattr__(self, "_provider", self.provider_factory())
        return self._provider

    def with_extras(self, **changes: object) -> "AgentContext":
        values = {key: getattr(self, key) for key in self.__dataclass_fields__}
        values.update(changes)
        return AgentContext(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ToolResult:
    name: str
    text: str
    ok: bool = True
    attempts: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    run: Callable[[AgentContext], ToolResult]


def _unavailable(name: str, reason: str) -> ToolResult:
    detail = reason.strip() or "motivo não informado"
    # A mensagem de uma fonte externa pode conter URL ou credencial: nunca repassar.
    if any(mark in detail.lower() for mark in ("http", "sk-", "token", "chave", "authorization")):
        detail = "a fonte de dados falhou"
    return ToolResult(name, f"INDISPONÍVEL ({detail}).", ok=False)


def _symbols_in(question: str, watchlist: Sequence[str]) -> list[str]:
    return jarbas_tools.symbols_in(question, watchlist)


def _reference_expiry(context: AgentContext, symbol: str) -> date | None:
    today = market_today(context.now)
    expiries = [day for day in context.source().get_expirations(symbol) if day >= today]
    return service._reference_expiry(expiries, today)


def scan_market(context: AgentContext) -> ToolResult:
    """Panorama do Scanner, com procedência e aviso de grade defasada."""
    try:
        result = service.scanner(
            context.source(),
            list(context.watchlist),
            context.now,
            budget_seconds=jarbas_tools.MARKET_BUDGET,
        )
    except Exception:  # noqa: BLE001 — falha de fonte vira dado indisponível
        return ToolResult("mercado", "PANORAMA DOS ATIVOS: INDISPONÍVEL (a fonte de mercado falhou).", ok=False)
    note = "" if result["complete"] else " (varredura incompleta: alguns ativos sem todos os dados)"
    rule = (
        "Regra do app: a grade é sempre a do último pregão disponível. "
        f"Só está DEFASADA a grade marcada como GRADE DEFASADA, quando o ativo andou mais de {context.max_drift * 100:.0f}% desde ela."
    )
    text = (
        f"PANORAMA DOS ATIVOS ACOMPANHADOS, gerado em {result['generated_at'][:16]}{note}. {rule}\n"
        + jarbas_tools.market_overview(result["rows"], context.max_drift)
    )
    return ToolResult("mercado", text)


def rank_spreads(context: AgentContext) -> ToolResult:
    """As melhores travas por retorno sobre risco, sem substituir a decisão do app."""
    targets = _symbols_in(context.question, context.watchlist) or (
        [context.context_symbol] if context.context_symbol else list(context.watchlist)
    )
    try:
        text = jarbas_tools.spread_ranking(context.source(), targets, context.now, context.clock)
    except Exception:  # noqa: BLE001
        return _unavailable("travas", "a fonte de cadeias falhou")
    return ToolResult("travas", "TRAVAS COM MELHOR ESTIMATIVA MÉDIA POR REAL DE RISCO:\n" + text)


def portfolio_summary(context: AgentContext) -> ToolResult:
    """Carteira informada pelo proprietário, com os limites do que o app calcula."""
    return ToolResult("carteira", "CARTEIRA DO PROPRIETÁRIO:\n" + jarbas_tools.portfolio_summary(context.db))


def decisions_summary(context: AgentContext) -> ToolResult:
    """Últimas decisões gravadas pelas regras fixas do app."""
    return ToolResult("decisoes", "ÚLTIMAS DECISÕES REGISTRADAS PELO APP:\n" + jarbas_tools.decisions_summary(context.db))


_HEDGE = re.compile(r"\bhedge\b|prote[çc][ãa]o|proteger|cobertura", re.I)


def hedge_and_risk(context: AgentContext) -> ToolResult:
    """Scanner + decisão de risco + RiskManager para o ativo pedido.

    É a ferramenta usada quando o usuário pede um hedge (por exemplo, PETR4):
    ``strategies_view`` monta as estruturas a partir da grade; ``review_candidates``
    passa cada uma pelo ``RiskManager`` com a carteira real. A resposta mostra o
    veredito do app, nunca uma recomendação do modelo.
    """
    mentioned = _symbols_in(context.question, context.watchlist)
    candidate = next(
        (symbol for symbol in mentioned if is_stock_symbol(normalize_symbol(symbol))),
        None,
    )
    if candidate is None and context.context_symbol:
        candidate = normalize_symbol(context.context_symbol)
    if candidate is None and _HEDGE.search(context.question) and context.watchlist:
        candidate = normalize_symbol(context.watchlist[0])
    if candidate is None or not is_stock_symbol(candidate):
        return ToolResult("hedge_risco", "HEDGE: INDISPONÍVEL (ativo não identificado).", ok=False)

    attempts: list[str] = []
    try:
        expiry = _reference_expiry(context, candidate)
        if expiry is None:
            return ToolResult("hedge_risco", f"HEDGE de {candidate}: INDISPONÍVEL (sem vencimento futuro).", ok=False)
        view = service.strategies_view(
            context.source(), candidate, expiry, context.now, limits=RiskLimits(max_spot_drift=context.max_drift)
        )
        attempts.append("scanner")
        verdicts = carteira.review_candidates(context.db, view)
        carteira.apply_review(view, verdicts)
        attempts.append("risk_manager")
    except (DataInsufficientError, ValueError, KeyError, TypeError):
        return _unavailable("hedge_risco", "a grade não tinha dados suficientes para avaliar o hedge")
    except Exception:  # noqa: BLE001
        return _unavailable("hedge_risco", "a fonte de dados falhou")

    lines = [
        f"HEDGE de {candidate}, vencimento de referência {expiry}, grade de {view.get('market_date') or 'data indisponível'}.",
        "Os vereditos abaixo são das regras fixas do app e do RiskManager com a carteira informada; o modelo não pode mudá-los.",
    ]
    rows = sorted(
        view["candidates"],
        key=lambda row: (row["decision"]["status"] != "APROVADA", -(row.get("ranking") or {}).get("expected_return_on_risk", 0)),
    )[:5]
    for row in rows:
        decision = row["decision"]
        portfolio = row.get("portfolio") or {}
        reasons = list(decision.get("reasons") or []) + [f"carteira: {r}" for r in portfolio.get("reasons") or []]
        lines.append(
            f"- {row.get('name') or row['key']}: decisão {decision['status']}"
            + (f"; motivos: {'; '.join(reasons[:3])}" if reasons else "")
            + (f"; falta: {'; '.join(decision.get('missing', [])[:2])}" if decision.get("missing") else "")
            + "."
        )
    if not rows:
        lines.append("Nenhuma estrutura passou nos filtros de liquidez da grade.")
    if not verdicts:
        lines.append("Carteira não configurada: o RiskManager não pôde avaliar exposição nem caixa.")
    return ToolResult("hedge_risco", "\n".join(lines), attempts=tuple(attempts))


def rag_context(context: AgentContext) -> ToolResult:
    """Trechos de documentos locais, já recuperados pelo retriever do RAG."""
    if not context.rag_text:
        return ToolResult("rag", "", ok=True)
    return ToolResult("rag", "DOCUMENTOS LOCAIS CONSULTADOS (só leitura):\n" + context.rag_text)


def memory_context(context: AgentContext) -> ToolResult:
    """Lembretes da memória de longo prazo, separados dos dados de mercado."""
    if not context.memory_text:
        return ToolResult("memoria", "", ok=True)
    return ToolResult("memoria", "LEMBRETES DE CONVERSAS ANTERIORES:\n" + context.memory_text)


DEFAULT_TOOLS = (
    AgentTool("mercado", "Panorama de mercado e sinais do Scanner.", scan_market),
    AgentTool("travas", "Ranking de travas por retorno sobre risco.", rank_spreads),
    AgentTool("carteira", "Posições e caixa informados pelo proprietário.", portfolio_summary),
    AgentTool("decisoes", "Últimas decisões gravadas pelas regras do app.", decisions_summary),
    AgentTool("hedge_risco", "Hedge com Scanner, decisão do app e RiskManager.", hedge_and_risk),
    AgentTool("rag", "Trechos de documentos locais indexados.", rag_context),
    AgentTool("memoria", "Memória de longo prazo do proprietário.", memory_context),
)


def default_tools() -> list[AgentTool]:
    return list(DEFAULT_TOOLS)


def tools_by_name(names: Sequence[str], tools: Sequence[AgentTool] | None = None) -> list[AgentTool]:
    available = {tool.name: tool for tool in (tools or DEFAULT_TOOLS)}
    return [available[name] for name in names if name in available]
