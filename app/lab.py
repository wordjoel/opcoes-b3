"""Laboratório de Estratégias: descobre, acompanha, testa e compara. Exclusivamente analítico.

"Agentes" são as regras que realmente propõem estruturas. Não há personagens: os demais papéis
(risco, monitoramento, backtest, desempenho) são as funções deste módulo. Nada aqui envia ordens.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.service import _try_bars, _regime
from core.clock import market_today
from core.exceptions import DataInsufficientError
from core.types import LegAction, OptionChain, OptionKind, OptionLeg
from data.providers.base import DataProvider
from data.providers.brapi import candidate_expiries
from data.validators import ValidationReport, validate_chain
from db.client import Database
from quant.lab import (
    MIN_LIQUID_SERIES,
    MIN_SCAN_OPEN_INTEREST,
    MIN_SCAN_VOLUME,
    evaluate_path,
    expected_pnl,
    mark_pnl,
    rank_groups,
    returns_summary,
    settlement_pnl,
    size_position,
    vertical_scan,
)
from quant.payoff import net_premium
from quant.risk import CapitalLimits, RiskLimits, assess_risk, decide, leg_liquidity, position_pop
from quant.strategies import Candidate, build_candidates

AGENTS = {
    "regra_5pct": ("Regra de 5% do ativo", None),
    "delta_conservador": ("Delta conservador", "CONSERVATIVE"),
    "delta_moderado": ("Delta moderado", "MODERATE"),
    "delta_agressivo": ("Delta agressivo", "AGGRESSIVE"),
    "varredura_vertical": ("Varredura de travas", "SCAN"),
}
_REFERENCE_DAYS = 14
_DISCOVER_BUDGET_SECONDS = 30.0
_MONITOR_BUDGET_SECONDS = 35.0
_BACKTEST_BUDGET_SECONDS = 40.0
PERIODS = (1, 3, 5, 10, 15, 30)


def agent_proposals(agent: str, chain: OptionChain, quotes, t: float, r: float) -> list[Candidate]:
    profile = AGENTS[agent][1]
    spot = chain.underlying.price
    if profile == "SCAN":
        return vertical_scan(quotes, spot, t, r)
    built, _ = build_candidates(quotes, spot, use_book=False, profile=profile)
    if profile is None:
        return built
    from quant.strategies import PROFILES

    # O perfil só muda as estruturas com alvo de delta; as demais já são da regra de 5%.
    return [candidate for candidate in built if candidate.key in PROFILES[profile]]


def _theoretical(candidate: Candidate, spot: float, t: float, r: float) -> tuple[float | None, float | None]:
    ivs = [quote.iv for quote in candidate.quotes]
    probability = position_pop(candidate.proposal.legs, ivs, spot, t, r)
    if probability is None:
        return None, None
    sigma = sum(ivs) / len(ivs)
    return probability, expected_pnl(candidate.proposal.legs, spot, sigma, t, r)


def _leg_view(leg: OptionLeg, quote) -> dict:
    return {
        "symbol": leg.symbol,
        "action": leg.action.value,
        "kind": leg.kind.value,
        "strike": leg.strike,
        "expiry": leg.expiry.isoformat(),
        "quantity": leg.quantity,
        "premium": leg.premium,
        "bid": quote.bid or None,
        "ask": quote.ask or None,
        "volume": quote.volume,
        "open_interest": quote.open_interest,
        "iv": quote.iv,
        "style": quote.style.value if quote.style else None,
    }


def _reference_expiry(provider: DataProvider, symbol: str, today: date) -> date:
    limit = today + timedelta(days=_REFERENCE_DAYS)
    days = [day for day in provider.get_expirations(symbol) if day >= limit]
    if not days:
        raise DataInsufficientError("sem vencimento a partir de 14 dias")
    return min(days)


def _chain_times(chain: OptionChain) -> tuple[float, float]:
    if chain.risk_free_rate is None or chain.time_to_expiry_years is None:
        raise DataInsufficientError("a fonte não informou juros e prazo da grade")
    return chain.time_to_expiry_years, chain.risk_free_rate


def _liquidity(report: ValidationReport) -> dict:
    liquid = [
        quote
        for quote in report.usable_quotes
        if (quote.volume or 0) >= MIN_SCAN_VOLUME and (quote.open_interest or 0) >= MIN_SCAN_OPEN_INTEREST
    ]
    return {
        "usable_series": len(report.usable_quotes),
        "liquid_series": len(liquid),
        "calls": sum(quote.kind is OptionKind.CALL for quote in liquid),
        "puts": sum(quote.kind is OptionKind.PUT for quote in liquid),
        "sufficient": len(liquid) >= MIN_LIQUID_SERIES,
    }


def discover(
    provider: DataProvider,
    symbols: list[str],
    now: datetime,
    capital: CapitalLimits | None = None,
    budget_seconds: float = _DISCOVER_BUDGET_SECONDS,
) -> dict:
    """Propostas de todos os agentes, com o resultado da avaliação de risco. Nada é aprovado sem dado."""
    today = market_today(now)
    stop_at = time.monotonic() + budget_seconds
    assets, opportunities = [], []
    for symbol in symbols:
        if time.monotonic() >= stop_at:
            assets.append({"symbol": symbol, "status": "NAO_ANALISADO", "reason": "tempo esgotado", "liquidity": None})
            continue
        try:
            expiry = _reference_expiry(provider, symbol, today)
            chain = provider.get_option_chain(symbol, expiry)
            report = validate_chain(chain, now)
            report.require_valid()
            t, r = _chain_times(chain)
        except DataInsufficientError as error:
            assets.append({"symbol": symbol, "status": "DADOS_INSUFICIENTES", "reason": error.detail, "liquidity": None})
            continue
        liquidity = _liquidity(report)
        assets.append(
            {
                "symbol": symbol,
                "status": "ANALISADO" if liquidity["sufficient"] else "SEM_LIQUIDEZ",
                "reason": None if liquidity["sufficient"] else f"menos de {MIN_LIQUID_SERIES} séries líquidas",
                "liquidity": liquidity,
                "market_date": chain.market_date.isoformat() if chain.market_date else None,
                "expiry": expiry.isoformat(),
                "source": chain.underlying.provenance.source,
            }
        )
        try:
            live = provider.get_market_snapshot(symbol)
            drift = live.price / chain.underlying.price - 1
        except DataInsufficientError:
            drift = None
        spot = chain.underlying.price
        for agent, (agent_name, _) in AGENTS.items():
            for candidate in agent_proposals(agent, chain, report.usable_quotes, t, r):
                proposal = candidate.proposal
                if proposal.max_loss is None or proposal.max_loss <= 0:
                    continue
                probability, theoretical = _theoretical(candidate, spot, t, r)
                rules = assess_risk(proposal, candidate.quotes, spot, t, r, drift, use_book=False)
                opportunities.append(
                    {
                        "agent": agent,
                        "agent_name": agent_name,
                        "key": candidate.key,
                        "name": proposal.name,
                        "symbol": symbol,
                        "expiry": expiry.isoformat(),
                        "market_date": chain.market_date.isoformat() if chain.market_date else None,
                        "days_to_expiry": (expiry - today).days,
                        "legs": [_leg_view(leg, quote) for leg, quote in zip(proposal.legs, candidate.quotes)],
                        "net_premium": net_premium(proposal.legs),
                        "max_profit": proposal.max_profit,
                        "max_loss": proposal.max_loss,
                        "breakevens": proposal.breakeven_points,
                        "risk_reward": proposal.risk_reward_ratio,
                        "probability_of_profit": probability,
                        "potential_return": proposal.max_profit / proposal.max_loss if proposal.max_profit is not None else None,
                        "theoretical_return": theoretical / proposal.max_loss if theoretical is not None else None,
                        "liquidity_score": min((leg_liquidity(q, use_book=False) or 0) for q in candidate.quotes),
                        "decision": decide(proposal, rules, capital, drift),
                    }
                )
    opportunities.sort(
        key=lambda item: (
            item["decision"]["status"] == "REPROVADA",
            -(item["theoretical_return"] if item["theoretical_return"] is not None else float("-inf")),
        )
    )
    return {"generated_at": now.isoformat(), "assets": assets, "opportunities": opportunities}


def _strategy_id(mode: str, agent: str, key: str, symbol: str, expiry: date, entry: date, legs, capital, end_day: date) -> str:
    identity = [mode, agent, key, symbol, expiry.isoformat(), entry.isoformat(), [leg.symbol for leg in legs], capital, end_day.isoformat()]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]


@dataclass(frozen=True)
class LabPlan:
    capital_brl: float
    period_days: int
    target_pct: float | None = None
    stop_pct: float | None = None
    # None = o proprietário não informou custos: o resultado fica marcado como "sem custos".
    cost_brl: float | None = None


def _insert_strategy(
    db: Database,
    mode: str,
    agent: str,
    candidate: Candidate,
    symbol: str,
    expiry: date,
    entry: date,
    end_day: date,
    plan: LabPlan,
    probability: float | None,
    theoretical: float | None,
    regime: str | None,
    source: str,
    now: datetime,
) -> tuple[str, bool]:
    """Devolve o id e se foi criada agora. A chave primária impede duplicidade."""
    proposal = candidate.proposal
    size = size_position(proposal.max_loss, net_premium(proposal.legs), plan.capital_brl)
    if size is None:
        raise DataInsufficientError("o capital hipotético não comporta nem um lote desta estrutura")
    identity = _strategy_id(mode, agent, candidate.key, symbol, expiry, entry, proposal.legs, plan.capital_brl, end_day)
    if db.fetch("SELECT 1 FROM lab_strategies WHERE id = ?", (identity,)):
        return identity, False
    db.run(
        "INSERT INTO lab_strategies (id, mode, agent, symbol, structure_key, structure_name, expiry, entry_day, end_day, legs_json,"
        " capital_brl, lots, unit_debit, max_profit, max_loss, breakevens_json, probability, theoretical_pnl, regime, target_pct,"
        " stop_pct, cost_brl, cost_informed, status, source, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING",
        (
            identity, mode, agent, symbol, candidate.key, proposal.name, expiry.isoformat(), entry.isoformat(), end_day.isoformat(),
            json.dumps([leg.model_dump(mode="json") for leg in proposal.legs]), plan.capital_brl, size.lots,
            net_premium(proposal.legs), proposal.max_profit, proposal.max_loss, json.dumps(proposal.breakeven_points), probability,
            theoretical, regime, plan.target_pct, plan.stop_pct, plan.cost_brl or 0.0, 0 if plan.cost_brl is None else 1, "ATIVA", source,
            now.isoformat(),
        ),
    )
    return identity, True


def start_forward(provider: DataProvider, db: Database, symbol: str, agent: str, key: str, plan: LabPlan, now: datetime, limits: RiskLimits = RiskLimits()) -> dict:
    """A estrutura é refeita no servidor com a grade real: o cliente nunca informa preços."""
    if agent not in AGENTS:
        raise DataInsufficientError(f"agente desconhecido: {agent}")
    today = market_today(now)
    expiry = _reference_expiry(provider, symbol, today)
    chain = provider.get_option_chain(symbol, expiry)
    report = validate_chain(chain, now)
    report.require_valid()
    t, r = _chain_times(chain)
    if chain.market_date is None:
        raise DataInsufficientError("grade sem data de pregão")
    spot = chain.underlying.price
    live = provider.get_market_snapshot(symbol)
    drift = live.price / spot - 1
    # Entrar por um preço velho com o ativo já longe daria uma vantagem que não existiu.
    if abs(drift) > limits.max_spot_drift:
        raise DataInsufficientError(f"grade defasada: o ativo já se moveu {drift:+.1%} desde o pregão da grade")
    candidate = next((item for item in agent_proposals(agent, chain, report.usable_quotes, t, r) if item.key == key), None)
    if candidate is None or candidate.proposal.max_loss is None:
        raise DataInsufficientError("esta estrutura não está disponível na grade atual")
    probability, theoretical = _theoretical(candidate, spot, t, r)
    regime = _regime(_try_bars(provider, symbol), None)
    end_day = min(expiry, today + timedelta(days=plan.period_days))
    identity, created = _insert_strategy(
        db, "FORWARD", agent, candidate, symbol, expiry, chain.market_date, end_day, plan, probability, theoretical,
        regime.value if regime else None, chain.underlying.provenance.source, now,
    )
    return {"id": identity, "created": created, "entry_day": chain.market_date.isoformat(), "end_day": end_day.isoformat()}


def _legs_of(row_legs: str) -> list[OptionLeg]:
    return [OptionLeg.model_validate(item) for item in json.loads(row_legs)]


def _prices_on(chain: OptionChain, day: date, legs: list[OptionLeg]) -> dict[str, float]:
    """Só o que negociou naquele pregão: fechamento antigo não vale como preço do dia."""
    wanted = {leg.symbol for leg in legs}
    return {
        quote.symbol: quote.close
        for quote in chain.quotes
        if quote.symbol in wanted and quote.close and quote.last_trade_date == day
    }


def _write_mark(db: Database, identity: str, day: date, legs: list[OptionLeg], expiry: date, chain: OptionChain, now: datetime) -> float | None:
    spot = chain.underlying.price
    settlement = day >= expiry
    prices = _prices_on(chain, day, legs)
    pnl = settlement_pnl(legs, spot) if settlement else mark_pnl(legs, prices)
    db.run(
        "INSERT INTO lab_marks (strategy_id, day, pnl_unit, spot, prices_json, complete, settlement, source, fetched_at)"
        " VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT (strategy_id, day) DO NOTHING",
        (identity, day.isoformat(), pnl, spot, json.dumps(prices), 0 if pnl is None else 1, 1 if settlement else 0,
         chain.underlying.provenance.source, now.isoformat()),
    )
    return pnl


def _complete_marks(db: Database, identity: str) -> list[tuple[str, float]]:
    return [
        (row[0], row[1])
        for row in db.fetch("SELECT day, pnl_unit FROM lab_marks WHERE strategy_id = ? AND complete = 1 ORDER BY day", (identity,))
    ]


def _close(db: Database, identity: str, reason: str, day: str) -> None:
    db.run("UPDATE lab_strategies SET status = 'ENCERRADA', close_reason = ?, closed_day = ? WHERE id = ?", (reason, day, identity))


def monitor(provider: DataProvider, db: Database, now: datetime, budget_seconds: float = _MONITOR_BUDGET_SECONDS) -> dict:
    """Marca cada estratégia ativa com a grade mais recente e encerra pelas regras dela.

    A grade é diária: "contínuo" aqui significa a cada novo pregão, não a cada negócio.
    """
    rows = db.fetch(
        "SELECT id, symbol, expiry, entry_day, end_day, legs_json, max_loss, target_pct, stop_pct FROM lab_strategies"
        " WHERE mode = 'FORWARD' AND status = 'ATIVA'"
    )
    today = market_today(now)
    stop_at = time.monotonic() + budget_seconds
    summary = {"active": len(rows), "marked": 0, "closed": 0, "failed": [], "not_reached": 0}
    for identity, symbol, expiry_text, entry_text, end_text, legs_text, max_loss, target, stop in rows:
        if time.monotonic() >= stop_at:
            summary["not_reached"] += 1
            continue
        expiry, entry, end_day = date.fromisoformat(expiry_text), date.fromisoformat(entry_text), date.fromisoformat(end_text)
        legs = _legs_of(legs_text)
        try:
            chain = provider.get_option_chain_on(symbol, expiry, expiry) if today > expiry else provider.get_option_chain(symbol, expiry)
        except DataInsufficientError as error:
            summary["failed"].append({"id": identity, "reason": error.detail})
            continue
        if chain is None or chain.market_date is None:
            summary["failed"].append({"id": identity, "reason": "a fonte não tem a grade deste vencimento"})
            continue
        day = chain.market_date
        if day > entry and not db.fetch("SELECT 1 FROM lab_marks WHERE strategy_id = ? AND day = ?", (identity, day.isoformat())):
            _write_mark(db, identity, day, legs, expiry, chain, now)
            summary["marked"] += 1
        path = evaluate_path(_complete_marks(db, identity), max_loss, target, stop)
        if path.exit_reason in ("ALVO", "STOP"):
            _close(db, identity, path.exit_reason, path.exit_day)
            summary["closed"] += 1
        elif day >= expiry:
            _close(db, identity, "VENCIMENTO", day.isoformat())
            summary["closed"] += 1
        elif day >= end_day or today > end_day:
            _close(db, identity, "FIM_DO_PERIODO", day.isoformat())
            summary["closed"] += 1
    return summary


def _weekdays_after(start: date, count: int) -> date:
    day = start
    while count > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count -= 1
    return day


def _session_now(day: date) -> datetime:
    """Horário de referência da validação: logo após o pregão, nunca o presente."""
    from data.providers.brapi import _session_close

    return _session_close(day) + timedelta(hours=1)


def run_backtest(
    provider: DataProvider,
    db: Database,
    symbol: str,
    plan: LabPlan,
    weeks: int,
    now: datetime,
    budget_seconds: float = _BACKTEST_BUDGET_SECONDS,
) -> dict:
    """Entradas semanais no passado. Cada proposta usa só a grade do dia da entrada; os preços
    seguintes servem apenas para marcar o resultado. Pode ser chamado de novo: continua de onde parou.

    A entrada e a saída são presumidas no fechamento: o livro desses pregões é sobra de ofertas.
    """
    today = market_today(now)
    last_entry = today - timedelta(days=plan.period_days + 3)
    while last_entry.weekday() != 2:
        last_entry -= timedelta(days=1)
    stop_at = time.monotonic() + budget_seconds
    bars = _try_bars(provider, symbol)
    summary = {"entries": 0, "created": 0, "closed": 0, "skipped": [], "complete": True, "symbol": symbol}
    for week in range(weeks):
        entry = last_entry - timedelta(weeks=week)
        if time.monotonic() >= stop_at:
            summary["complete"] = False
            break
        try:
            expiry = next((day for day in candidate_expiries(entry) if (chain := provider.get_option_chain_on(symbol, day, entry))), None)
        except DataInsufficientError as error:
            summary["complete"] = False
            summary["skipped"].append({"entry": entry.isoformat(), "reason": error.detail})
            break
        if expiry is None:
            summary["skipped"].append({"entry": entry.isoformat(), "reason": "sem grade nesse pregão"})
            continue
        report = validate_chain(chain, _session_now(entry))
        if not report.is_valid:
            summary["skipped"].append({"entry": entry.isoformat(), "reason": "grade recusada na validação"})
            continue
        try:
            t, r = _chain_times(chain)
        except DataInsufficientError as error:
            summary["skipped"].append({"entry": entry.isoformat(), "reason": error.detail})
            continue
        summary["entries"] += 1
        spot = chain.underlying.price
        # Regime medido só com fechamentos até a entrada.
        regime = _regime([bar for bar in bars if bar.day <= entry], None)
        end_day = min(expiry, _weekdays_after(entry, plan.period_days))
        checkpoints = sorted({min(_weekdays_after(entry, n), end_day) for n in PERIODS if n <= plan.period_days} | {end_day})
        created_ids: list[tuple[str, list[OptionLeg], float]] = []
        for agent in AGENTS:
            for candidate in agent_proposals(agent, chain, report.usable_quotes, t, r):
                proposal = candidate.proposal
                if proposal.max_loss is None or proposal.max_loss <= 0 or size_position(proposal.max_loss, net_premium(proposal.legs), plan.capital_brl) is None:
                    continue
                probability, theoretical = _theoretical(candidate, spot, t, r)
                identity, created = _insert_strategy(
                    db, "BACKTEST", agent, candidate, symbol, expiry, entry, end_day, plan, probability, theoretical,
                    regime.value if regime else None, chain.underlying.provenance.source, now,
                )
                summary["created"] += int(created)
                created_ids.append((identity, proposal.legs, proposal.max_loss))
        for checkpoint in checkpoints:
            if time.monotonic() >= stop_at:
                summary["complete"] = False
                break
            try:
                later = provider.get_option_chain_on(symbol, expiry, checkpoint)
            except DataInsufficientError as error:
                summary["complete"] = False
                summary["skipped"].append({"entry": entry.isoformat(), "reason": error.detail})
                break
            if later is None:
                continue
            for identity, legs, _ in created_ids:
                _write_mark(db, identity, checkpoint, legs, expiry, later, now)
        else:
            for identity, legs, max_loss in created_ids:
                row = db.fetch("SELECT target_pct, stop_pct, status FROM lab_strategies WHERE id = ?", (identity,))[0]
                if row[2] != "ATIVA":
                    continue
                path = evaluate_path(_complete_marks(db, identity), max_loss, row[0], row[1])
                _close(db, identity, path.exit_reason, path.exit_day or end_day.isoformat())
                summary["closed"] += 1
            continue
        break
    return summary


_LIST_COLUMNS = (
    "id, mode, agent, symbol, structure_key, structure_name, expiry, entry_day, end_day, legs_json, capital_brl, lots, unit_debit,"
    " max_profit, max_loss, breakevens_json, probability, theoretical_pnl, regime, target_pct, stop_pct, cost_brl, cost_informed,"
    " status, close_reason, closed_day, source, created_at"
)


def _strategy_view(columns: tuple, marks: list[tuple[str, float]], with_marks: list | None = None) -> dict:
    keys = [name.strip() for name in _LIST_COLUMNS.split(",")]
    row = dict(zip(keys, columns))
    lots, capital, max_loss = row["lots"], row["capital_brl"], row["max_loss"]
    employed = max(max_loss, row["unit_debit"]) * lots
    max_risk = max_loss * lots
    path = evaluate_path(marks, max_loss, row["target_pct"], row["stop_pct"])
    result = returns_summary(path.final_pnl_unit, lots, capital, employed, max_risk, row["cost_brl"])
    target_day = path.exit_day if path.exit_reason == "ALVO" else None
    entry = date.fromisoformat(row["entry_day"])
    measured_label = "SIMULADO" if row["mode"] == "BACKTEST" else "OBSERVADO"
    view = {
        **{key: row[key] for key in row if key not in ("legs_json", "breakevens_json")},
        "agent_name": AGENTS.get(row["agent"], (row["agent"],))[0],
        "legs": json.loads(row["legs_json"]),
        "breakevens": json.loads(row["breakevens_json"]),
        "employed_brl": employed,
        "max_risk_brl": max_risk,
        "horizon_days": (date.fromisoformat(row["end_day"]) - entry).days,
        "returns": {
            "potential": row["max_profit"] * lots / capital if row["max_profit"] is not None else None,
            "theoretical": row["theoretical_pnl"] * lots / capital if row["theoretical_pnl"] is not None else None,
            "measured_label": measured_label,
            "measured": result["return_on_capital"],
        },
        **result,
        "best_brl": path.best_unit * lots if path.best_unit is not None else None,
        "worst_brl": path.worst_unit * lots if path.worst_unit is not None else None,
        "max_drawdown_brl": path.max_drawdown_unit * lots,
        "exit_reason": path.exit_reason,
        "marks_used": path.marks_used,
        "days_to_target": (date.fromisoformat(target_day) - entry).days if target_day else None,
    }
    if with_marks is not None:
        view["marks"] = with_marks
    return view


def list_strategies(db: Database, mode: str | None = None, limit: int = 300) -> list[dict]:
    where, params = ("WHERE mode = ?", (mode,)) if mode else ("", ())
    rows = db.fetch(f"SELECT {_LIST_COLUMNS} FROM lab_strategies {where} ORDER BY entry_day DESC, id LIMIT ?", (*params, limit))
    marks: dict[str, list[tuple[str, float]]] = {}
    for strategy, day, pnl in db.fetch(
        f"SELECT m.strategy_id, m.day, m.pnl_unit FROM lab_marks m JOIN lab_strategies s ON s.id = m.strategy_id"
        f" {'WHERE s.mode = ? AND' if mode else 'WHERE'} m.complete = 1 ORDER BY m.day",
        params,
    ):
        marks.setdefault(strategy, []).append((day, pnl))
    return [_strategy_view(row, marks.get(row[0], [])) for row in rows]


def strategy_detail(db: Database, identity: str) -> dict | None:
    rows = db.fetch(f"SELECT {_LIST_COLUMNS} FROM lab_strategies WHERE id = ?", (identity,))
    if not rows:
        return None
    all_marks = db.fetch(
        "SELECT day, pnl_unit, spot, prices_json, complete, settlement, source, fetched_at FROM lab_marks WHERE strategy_id = ? ORDER BY day",
        (identity,),
    )
    lots = rows[0][11]
    details = [
        {
            "day": day,
            "pnl_brl": pnl * lots if pnl is not None else None,
            "spot": spot,
            "prices": json.loads(prices),
            "complete": bool(complete),
            "settlement": bool(settlement),
            "source": source,
            "fetched_at": fetched,
        }
        for day, pnl, spot, prices, complete, settlement, source, fetched in all_marks
    ]
    complete = [(item["day"], all_marks[index][1]) for index, item in enumerate(details) if item["complete"]]
    return _strategy_view(rows[0], complete, details)


def ranking(db: Database, mode: str) -> dict:
    """Backtest e acompanhamento nunca se misturam. Só entra o que foi encerrado com marcação."""
    rows = [row for row in list_strategies(db, mode, limit=5000) if row["status"] == "ENCERRADA" and row["return_on_risk"] is not None]
    agents = rank_groups(rows, "agent")
    for item in agents:
        item["agent_name"] = AGENTS.get(item["agent"], (item["agent"],))[0]
    return {
        "mode": mode,
        "label": "SIMULADO" if mode == "BACKTEST" else "OBSERVADO",
        "closed": len(rows),
        "agents": agents,
        "structures": rank_groups(rows, "structure_name"),
    }
