"""Carteira persistida e rastreabilidade das decisões.

O estado nunca fica em memória entre requisições: a cada uso, a carteira é refeita a partir
das operações gravadas, na ordem em que aconteceram. Assim o gestor de risco e o supervisor
rodam iguais em qualquer instância da Vercel, e o barramento serve só a esta requisição.

Nada aqui envia ordens. O fluxo termina em decision.RESULT, que é gravado em decision_log.
"""

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from agents.orchestrator.supervisor import IntelligenceSupervisor
from agents.risk_manager import RiskConfig, RiskManager
from core.bus import B3Bus
from db.client import Database
from quant.portfolio import PortfolioState

_FILL_COLUMNS = "id, symbol, side, quantity, price, fees_brl, trade_day, note, created_at, voided_at"


def read_settings(db: Database) -> dict | None:
    rows = db.fetch("SELECT initial_cash_brl, max_position_size, updated_at FROM portfolio_settings WHERE id = 1")
    if not rows:
        return None
    return {"initial_cash_brl": rows[0][0], "max_position_size": rows[0][1], "updated_at": rows[0][2]}


def save_settings(db: Database, initial_cash_brl: float, max_position_size: int, now: datetime) -> dict:
    db.run(
        "INSERT INTO portfolio_settings (id, initial_cash_brl, max_position_size, updated_at) VALUES (1, ?, ?, ?) "
        "ON CONFLICT (id) DO UPDATE SET initial_cash_brl = excluded.initial_cash_brl, "
        "max_position_size = excluded.max_position_size, updated_at = excluded.updated_at",
        (initial_cash_brl, max_position_size, now.isoformat()),
    )
    return read_settings(db)  # type: ignore[return-value]


def _fill_view(row: tuple) -> dict:
    keys = [name.strip() for name in _FILL_COLUMNS.split(",")]
    return dict(zip(keys, row))


def list_fills(db: Database) -> list[dict]:
    return [_fill_view(row) for row in db.fetch(f"SELECT {_FILL_COLUMNS} FROM portfolio_fills ORDER BY trade_day, id")]


def add_fill(
    db: Database, symbol: str, side: str, quantity: int, price: float, fees_brl: float, trade_day: date, note: str | None, now: datetime
) -> dict:
    """Valida contra a carteira atual antes de gravar: dado inválido não entra."""
    state, _ = rebuild(db)
    probe = PortfolioState(state.cash, dict(state.positions), state.realized_pnl)
    probe.apply_fill(symbol, quantity, price, side == "BUY")
    db.run(
        "INSERT INTO portfolio_fills (symbol, side, quantity, price, fees_brl, trade_day, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (symbol, side, quantity, price, fees_brl, trade_day.isoformat(), note, now.isoformat()),
    )
    rows = db.fetch(f"SELECT {_FILL_COLUMNS} FROM portfolio_fills ORDER BY id DESC LIMIT 1")
    return _fill_view(rows[0])


def void_fill(db: Database, identity: int, now: datetime) -> dict | None:
    rows = db.fetch(f"SELECT {_FILL_COLUMNS} FROM portfolio_fills WHERE id = ?", (identity,))
    if not rows:
        return None
    if rows[0][-1] is None:
        db.run("UPDATE portfolio_fills SET voided_at = ? WHERE id = ?", (now.isoformat(), identity))
    return _fill_view(db.fetch(f"SELECT {_FILL_COLUMNS} FROM portfolio_fills WHERE id = ?", (identity,))[0])


def rebuild(db: Database) -> tuple[PortfolioState, float]:
    """Carteira refeita das operações válidas. Devolve o estado e o total de custos informados.
    Os custos saem do caixa; o resultado realizado de `PortfolioState` continua bruto."""
    settings = read_settings(db)
    state = PortfolioState(cash=settings["initial_cash_brl"] if settings else 0.0)
    fees = 0.0
    for fill in list_fills(db):
        if fill["voided_at"]:
            continue
        state.apply_fill(fill["symbol"], fill["quantity"], fill["price"], fill["side"] == "BUY")
        state.cash -= fill["fees_brl"]
        fees += fill["fees_brl"]
    return state, fees


def portfolio_view(db: Database) -> dict:
    settings = read_settings(db)
    state, fees = rebuild(db)
    return {
        "settings": settings,
        "cash_brl": state.cash,
        "realized_pnl_brl": state.realized_pnl,
        "fees_brl": fees,
        "realized_net_brl": state.realized_pnl - fees,
        "positions": [asdict(position) for position in sorted(state.positions.values(), key=lambda p: p.symbol)],
        "fills": list_fills(db),
    }


async def _review(state: PortfolioState, config: RiskConfig, symbol: str, intents: list[tuple[str, list[dict]]]) -> dict[str, dict]:
    bus = B3Bus(max_log_size=1000)
    RiskManager(bus, state, config)
    supervisor = IntelligenceSupervisor(bus)
    results = {}
    for key, legs in intents:
        results[key] = await supervisor.propose_strategy(symbol, key, legs)
    return results


def review_candidates(db: Database, view: dict) -> dict[str, dict] | None:
    """Passa cada estrutura pelo supervisor e pelo gestor de risco com a carteira real.
    None = carteira não configurada: a análise segue sem essa etapa."""
    settings = read_settings(db)
    if settings is None:
        return None
    state, _ = rebuild(db)
    config = RiskConfig(max_position_size=settings["max_position_size"])
    intents = [
        (
            row["key"],
            [
                {
                    "symbol": leg["symbol"],
                    "strike": leg["strike"],
                    "expiry": view["expiry"],
                    "kind": leg["kind"],
                    "action": leg["action"],
                    "quantity": leg["quantity"],
                    "premium": leg["premium"],
                }
                for leg in row["legs"]
            ],
        )
        for row in view["candidates"]
    ]
    return asyncio.run(_review(state, config, view["symbol"], intents))


def apply_review(view: dict, verdicts: dict[str, dict] | None) -> None:
    """Reprovação da carteira reprova a estrutura; aprovação dela não aprova nada sozinha."""
    view["portfolio_configured"] = verdicts is not None
    for row in view["candidates"]:
        verdict = verdicts.get(row["key"]) if verdicts is not None else None
        row["portfolio"] = {"decision": verdict["decision"], "reasons": verdict["reasons"]} if verdict else None
        if verdict and verdict["decision"] != "APPROVED":
            decision = row["decision"]
            decision["reasons"] = [*decision["reasons"], *(f"carteira: {reason}" for reason in verdict["reasons"])]
            decision["status"] = "REPROVADA"


def _inputs(view: dict, row: dict) -> dict[str, Any]:
    return {
        "market_date": view.get("market_date"),
        "source": view.get("source"),
        "spot": view.get("spot"),
        "live_price": view.get("live_price"),
        "spot_drift": view.get("spot_drift"),
        "risk_free_rate": view.get("risk_free_rate"),
        "time_to_expiry_years": view.get("time_to_expiry_years"),
        "profile": view.get("profile"),
        "legs": [
            {key: leg.get(key) for key in ("symbol", "action", "kind", "strike", "quantity", "premium", "price_basis", "iv")}
            for leg in row["legs"]
        ],
        "max_profit": row.get("max_profit"),
        "max_loss": row.get("max_loss"),
        "liquidity_score": row["risk"].get("liquidity_score"),
        "warnings": row["risk"].get("warnings"),
        "capital": {key: row["decision"].get(key) for key in ("limit_brl", "capital_required", "costs_brl", "max_risk")},
        "portfolio": row.get("portfolio"),
    }


def record_decisions(db: Database, view: dict, now: datetime) -> int:
    """Grava cada decisão com os dados de entrada. Devolve quantas são novas."""
    created = 0
    for row in view["candidates"]:
        decision = row["decision"]
        inputs = _inputs(view, row)
        content = json.dumps(
            [view["symbol"], view["expiry"], row["key"], decision["status"], decision["reasons"], decision["missing"], inputs],
            sort_keys=True,
            default=str,
        )
        identity = hashlib.sha256(content.encode()).hexdigest()[:32]
        if db.fetch("SELECT 1 FROM decision_log WHERE id = ?", (identity,)):
            continue
        db.run(
            "INSERT INTO decision_log (id, created_at, symbol, expiry, structure_key, status, reasons_json, missing_json, inputs_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING",
            (
                identity, now.isoformat(), view["symbol"], view["expiry"], row["key"], decision["status"],
                json.dumps(decision["reasons"], ensure_ascii=False), json.dumps(decision["missing"], ensure_ascii=False),
                json.dumps(inputs, ensure_ascii=False, default=str),
            ),
        )
        created += 1
    return created


def list_decisions(db: Database, symbol: str | None = None, limit: int = 100) -> list[dict]:
    where, params = ("WHERE symbol = ?", (symbol, limit)) if symbol else ("", (limit,))
    rows = db.fetch(
        "SELECT id, created_at, symbol, expiry, structure_key, status, reasons_json, missing_json, inputs_json"
        f" FROM decision_log {where} ORDER BY created_at DESC, id LIMIT ?",
        params,
    )
    return [
        {
            "id": row[0],
            "created_at": row[1],
            "symbol": row[2],
            "expiry": row[3],
            "structure_key": row[4],
            "status": row[5],
            "reasons": json.loads(row[6]),
            "missing": json.loads(row[7]),
            "inputs": json.loads(row[8]),
        }
        for row in rows
    ]
