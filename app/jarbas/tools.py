"""Ferramentas internas que o Jarbas consulta: só leitura, sempre pelo motor existente.

A escolha da ferramenta é feita por regras fixas sobre a pergunta, não pelo modelo de IA:
assim o Jarbas nunca consulta nada fora desta lista e nunca altera dados. Cada dado vai
rotulado como REAL, HISTÓRICO, CALCULADO ou INDISPONÍVEL, para a resposta não confundir
cotação com estimativa.
"""

import re
import time
from collections.abc import Callable, Sequence
from datetime import datetime

from app import carteira, service
from core.clock import market_today
from core.exceptions import DataInsufficientError
from data.providers.base import DataProvider
from db.client import Database
from quant.lab import vertical_ranking

FAMILY = {
    "bull_call_spread": "Trava de alta com call (débito)",
    "bear_call_spread": "Trava de baixa com call (crédito)",
    "bull_put_spread": "Trava de alta com put (crédito)",
    "bear_put_spread": "Trava de baixa com put (débito)",
}

INTENTS = {
    "carteira": re.compile(r"carteira|posi[çc][ãaõo]|caixa|meu resultado|minhas? opera|realizad", re.I),
    "mercado": re.compile(
        r"oportunidad|volatil|vencimento|defasad|ativo|mercado|hoje|aten[çc][ãa]o|\biv\b|scanner|sinal|sinais|regime|grade", re.I
    ),
    "travas": re.compile(r"trava|retorno|risco.?retorno|rent[áa]ve|melhores? (opera|estrut)|spread", re.I),
    "decisoes": re.compile(r"decis|aprovad|reprovad|registro", re.I),
}

MARKET_TTL = 300.0
SPREADS_TTL = 600.0
MARKET_BUDGET = 12.0
SPREADS_BUDGET = 15.0
MAX_SPREAD_SYMBOLS = 6

_cache: dict[str, tuple[float, object]] = {}

STATUS_LABEL = {"REAL": "REAL", "ATRASADO": "REAL, atrasada", "INCOMPLETO": "REAL, incompleta", "INDISPONIVEL": "INDISPONÍVEL"}
REGIME = {"BULL": "alta", "BEAR": "baixa", "SIDEWAYS": "lateral", "HIGH_VOL": "volatilidade alta"}


def _cached(key: str, ttl: float, load: Callable[[], object], clock: Callable[[], float]) -> object:
    hit = _cache.get(key)
    if hit and clock() - hit[0] < ttl:
        return hit[1]
    value = load()
    _cache[key] = (clock(), value)
    return value


def _pct(value: float | None, digits: int = 1) -> str:
    return "indisponível" if value is None else f"{value * 100:.{digits}f}%".replace(".", ",")


def _num(value: float | None, digits: int = 2) -> str:
    return "indisponível" if value is None else f"{value:.{digits}f}".replace(".", ",")


def intents_of(question: str, has_context: bool) -> list[str]:
    found = [name for name, pattern in INTENTS.items() if pattern.search(question)]
    # Pergunta genérica sem estrutura na tela: o panorama do mercado ajuda a responder.
    if not found and not has_context:
        found = ["mercado"]
    return found


def symbols_in(question: str, watchlist: Sequence[str]) -> list[str]:
    upper = question.upper()
    return [symbol for symbol in watchlist if re.search(rf"\b{symbol}\b", upper) or re.search(rf"\b{symbol[:4]}\b", upper)]


def market_overview(rows: list[dict], limits_drift: float) -> str:
    lines = []
    for row in rows:
        status = STATUS_LABEL.get(row.get("data_status") or "", "INDISPONÍVEL")
        parts = [f"{row['symbol']}: preço {_num(row.get('price'))} [{status}, mercado {row.get('market_time') or 'sem horário'}]"]
        if row.get("change_percent") is not None:
            parts.append(f"variação no dia {_num(row['change_percent'])}%")
        parts.append(f"vol implícita no dinheiro {_pct(row.get('atm_iv'))} [CALCULADO da grade de {row.get('market_date') or 'data indisponível'}]")
        parts.append(f"vol histórica 1 ano {_pct(row.get('historical_volatility'))} [HISTÓRICO]")
        if row.get("iv_ratio") is not None:
            parts.append(f"implícita/histórica {_num(row['iv_ratio'])} [CALCULADO]")
        if row.get("iv_rank") is not None:
            parts.append(f"IV Rank {_num(row['iv_rank'], 0)} [HISTÓRICO]")
        else:
            parts.append(f"IV Rank indisponível ({row.get('iv_samples', 0)} amostras)")
        if row.get("regime"):
            parts.append(f"regime {REGIME.get(row['regime'], row['regime'])} [CALCULADO]")
        if row.get("expiry"):
            parts.append(f"vencimento de referência {row['expiry']}")
        drift = row.get("spot_drift")
        if drift is not None and abs(drift) > limits_drift:
            parts.append(f"GRADE DEFASADA: ativo andou {_pct(drift)} desde a grade")
        for signal in row.get("signals") or []:
            parts.append(f"sinal {signal['type']}: {signal['detail']}")
        for event in (row.get("events") or [])[:2]:
            parts.append(f"evento {event.get('day')}: {event.get('label')}")
        if row.get("missing"):
            parts.append("INDISPONÍVEL: " + "; ".join(row["missing"][:3]))
        lines.append("- " + ", ".join(parts) + ".")
    return "\n".join(lines) or "Nenhum ativo na lista de acompanhamento."


def spread_ranking(provider: DataProvider, symbols: Sequence[str], now: datetime, clock: Callable[[], float]) -> str:
    """As 2 melhores travas de cada tipo por ativo, no vencimento de referência. Sem decisão de risco."""
    deadline = clock() + SPREADS_BUDGET
    lines = []
    for symbol in symbols[:MAX_SPREAD_SYMBOLS]:
        if clock() > deadline:
            lines.append(f"- {symbol}: INDISPONÍVEL (tempo de consulta esgotado).")
            continue
        try:
            today = market_today(now)
            expiry = service._reference_expiry([day for day in provider.get_expirations(symbol) if day >= today], today)
            if expiry is None:
                lines.append(f"- {symbol}: INDISPONÍVEL (sem vencimento futuro).")
                continue
            chain, report = service._load_chain(provider, symbol, expiry, now)
            if chain.time_to_expiry_years is None or chain.risk_free_rate is None:
                lines.append(f"- {symbol}: INDISPONÍVEL (fonte sem prazo ou juros).")
                continue
            ranked = vertical_ranking(report.usable_quotes, chain.underlying.price, chain.time_to_expiry_years, chain.risk_free_rate, top=2)
        except DataInsufficientError as error:
            lines.append(f"- {symbol}: INDISPONÍVEL ({error.detail}).")
            continue
        if not ranked:
            lines.append(f"- {symbol} (vencimento {expiry}): nenhum par de séries passou nos filtros de liquidez.")
            continue
        ranked.sort(key=lambda item: -item.expected_return_on_risk)
        for item in ranked[:4]:
            proposal = item.candidate.proposal
            legs = " e ".join(
                f"{'compra' if leg.action.value == 'BUY' else 'venda'} {leg.symbol} strike {_num(leg.strike)} a {_num(leg.premium)}"
                for leg in proposal.legs
            )
            lines.append(
                f"- {symbol} vencimento {expiry}, grade de {chain.market_date}: {FAMILY.get(item.family, item.family)}, por lote de 100 ({legs}); "
                f"ganho máx R$ {_num(proposal.max_profit)}, perda máx R$ {_num(proposal.max_loss)}, "
                f"estimativa média R$ {_num(item.expected_pnl)} ({_pct(item.expected_return_on_risk)} do risco) [CALCULADO pelo modelo, prêmios de fechamento]."
            )
    lines.append("Estas travas ainda não passaram pela decisão de risco do app: a decisão aparece na tela Estratégias > Travas mais rentáveis.")
    return "\n".join(lines)


def portfolio_summary(db: Database) -> str:
    view = carteira.portfolio_view(db)
    limits = "O app não calcula margem, resultado em aberto nem marcação a mercado da carteira."
    if view["settings"] is None and not view["fills"]:
        return "Carteira não configurada: o proprietário ainda não informou caixa nem operações. " + limits + " Para configurar: aba Carteira."
    lines = [
        f"Caixa: R$ {_num(view['cash_brl'])} [CALCULADO das operações informadas].",
        f"Resultado realizado bruto: R$ {_num(view['realized_pnl_brl'])}; custos informados: R$ {_num(view['fees_brl'])}; líquido antes do imposto: R$ {_num(view['realized_net_brl'])}.",
        limits,
    ]
    for position in view["positions"][:12]:
        lines.append(f"- posição {position['symbol']}: {position['quantity']} opções, preço médio R$ {_num(position['avg_entry_price'])}.")
    if not view["positions"]:
        lines.append("Nenhuma posição aberta.")
    return "\n".join(lines)


def decisions_summary(db: Database) -> str:
    items = carteira.list_decisions(db, limit=10)
    if not items:
        return "Nenhuma decisão registrada ainda."
    return "\n".join(
        f"- {item['created_at'][:16]} {item['symbol']} {item['expiry']} {item['structure_key']}: {item['status']}"
        + (f" ({'; '.join((item['reasons'] + item['missing'])[:2])})" if item["reasons"] or item["missing"] else "")
        for item in items
    )


def gather(
    question: str,
    has_context: bool,
    context_symbol: str | None,
    db: Database,
    provider_factory: Callable[[], DataProvider],
    watchlist: Sequence[str],
    now: datetime,
    max_drift: float,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[str, list[str]]:
    """Texto com os dados consultados e a lista de ferramentas usadas."""
    blocks: list[str] = []
    used: list[str] = []
    intents = intents_of(question, has_context)
    provider: DataProvider | None = None

    def source() -> DataProvider:
        nonlocal provider
        provider = provider or provider_factory()
        return provider

    if "mercado" in intents:
        used.append("mercado")
        try:
            result = _cached(
                "mercado:" + ",".join(watchlist),
                MARKET_TTL,
                lambda: service.scanner(source(), list(watchlist), now, budget_seconds=MARKET_BUDGET),
                clock,
            )
            note = "" if result["complete"] else " (varredura incompleta: alguns ativos sem todos os dados)"
            rule = (
                f"Regra do app: a grade é sempre a do último pregão disponível (fins de semana e feriados não têm pregão). "
                f"Só está DEFASADA a grade marcada como GRADE DEFASADA, quando o ativo andou mais de {max_drift * 100:.0f}% desde ela."
            )
            blocks.append(f"PANORAMA DOS ATIVOS ACOMPANHADOS, gerado em {result['generated_at'][:16]}{note}. {rule}\n" + market_overview(result["rows"], max_drift))
        except Exception:  # noqa: BLE001 — falha de fonte vira dado indisponível, nunca invenção
            blocks.append("PANORAMA DOS ATIVOS: INDISPONÍVEL (a fonte de dados falhou agora).")
    if "travas" in intents:
        used.append("travas")
        targets = symbols_in(question, watchlist) or ([context_symbol] if context_symbol else list(watchlist))
        try:
            text = _cached(
                "travas:" + ",".join(targets[:MAX_SPREAD_SYMBOLS]),
                SPREADS_TTL,
                lambda: spread_ranking(source(), targets, now, clock),
                clock,
            )
            blocks.append("TRAVAS COM MELHOR ESTIMATIVA MÉDIA POR REAL DE RISCO:\n" + str(text))
        except Exception:  # noqa: BLE001
            blocks.append("TRAVAS: INDISPONÍVEL (a fonte de dados falhou agora).")
    if "carteira" in intents:
        used.append("carteira")
        blocks.append("CARTEIRA DO PROPRIETÁRIO:\n" + portfolio_summary(db))
    if "decisoes" in intents:
        used.append("decisoes")
        blocks.append("ÚLTIMAS DECISÕES REGISTRADAS PELO APP:\n" + decisions_summary(db))
    return "\n\n".join(blocks), used
