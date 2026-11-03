"""Barramento, carteira, risco e supervisor. Valores só de teste, sem rede."""

import asyncio
from datetime import date

import pytest

from agents.orchestrator.supervisor import IntelligenceSupervisor
from agents.risk_manager import RiskConfig, RiskManager
from core.bus import B3Bus
from core.exceptions import DataInsufficientError
from quant.portfolio import PortfolioState

EXPIRY = date(2026, 12, 18)


def leg(symbol, action, kind, strike, premium, quantity=100):
    return dict(symbol=symbol, action=action, kind=kind, strike=strike, premium=premium, quantity=quantity, expiry=EXPIRY)


IRON_CONDOR = [
    leg("TESTP90", "BUY", "PUT", 90.0, 0.5),
    leg("TESTP95", "SELL", "PUT", 95.0, 1.5),
    leg("TESTC105", "SELL", "CALL", 105.0, 1.5),
    leg("TESTC110", "BUY", "CALL", 110.0, 0.5),
]


def setup(cash=100_000.0, limit=1_000, timeout=1.0):
    bus = B3Bus()
    portfolio = PortfolioState(cash=cash)
    RiskManager(bus, portfolio, RiskConfig(max_position_size=limit))
    return bus, portfolio, IntelligenceSupervisor(bus, timeout)


def propose(supervisor, legs):
    return asyncio.run(supervisor.propose_strategy("TEST4", "TESTE", legs))


class TestBus:
    def test_delivers_sync_and_async_handlers_to_topic_only(self):
        async def run():
            bus, got = B3Bus(), []

            async def later(event):
                got.append(("async", event["data"]["n"]))

            bus.subscribe("a", lambda event: got.append(("sync", event["data"]["n"])))
            bus.subscribe("a", later)
            bus.subscribe("b", lambda event: got.append(("b", 0)))
            await bus.publish("a", {"n": 1})
            return got

        assert sorted(asyncio.run(run())) == [("async", 1), ("sync", 1)]

    def test_failing_handler_does_not_stop_others(self):
        async def run():
            bus, got = B3Bus(), []

            def bad(_):
                raise RuntimeError("falha")

            bus.subscribe("a", bad)
            bus.subscribe("a", got.append)
            await bus.publish("a", {})
            return got

        assert len(asyncio.run(run())) == 1

    def test_log_is_bounded_and_filterable(self):
        async def run():
            bus = B3Bus(max_log_size=2)
            for topic in ("market.A", "market.B", "risk.C"):
                await bus.publish(topic, {})
            return bus

        bus = asyncio.run(run())
        assert [e["topic"] for e in bus.get_replay_stream()] == ["market.B", "risk.C"]
        assert [e["topic"] for e in bus.get_replay_stream("risk.")] == ["risk.C"]

    def test_unsubscribe(self):
        async def run():
            bus, got = B3Bus(), []
            bus.subscribe("a", got.append)
            bus.unsubscribe("a", got.append)
            await bus.publish("a", {})
            return got

        assert asyncio.run(run()) == []


class TestPortfolio:
    def test_buy_sets_cash_and_position_without_extra_multiplier(self):
        p = PortfolioState(cash=1_000.0)
        p.apply_fill("X", 100, 2.0, True)
        assert p.cash == 800.0
        assert p.positions["X"].quantity == 100

    def test_first_sell_opens_short(self):
        p = PortfolioState(cash=0.0)
        result = p.apply_fill("X", 100, 2.0, False)
        assert result.new_quantity == -100
        assert p.positions["X"].quantity == -100
        assert p.cash == 200.0

    def test_average_price_when_adding(self):
        p = PortfolioState(cash=0.0)
        p.apply_fill("X", 100, 2.0, True)
        p.apply_fill("X", 300, 4.0, True)
        assert p.positions["X"].avg_entry_price == pytest.approx(3.5)

    def test_partial_close_realizes_and_keeps_average(self):
        p = PortfolioState(cash=0.0)
        p.apply_fill("X", 100, 2.0, True)
        result = p.apply_fill("X", 40, 3.0, False)
        assert result.realized_pnl == pytest.approx(40.0)
        assert result.new_quantity == 60
        assert p.positions["X"].avg_entry_price == 2.0

    def test_closing_short_with_loss(self):
        p = PortfolioState(cash=0.0)
        p.apply_fill("X", 100, 2.0, False)
        result = p.apply_fill("X", 100, 3.0, True)
        assert result.realized_pnl == pytest.approx(-100.0)
        assert "X" not in p.positions
        assert p.realized_pnl == pytest.approx(-100.0)
        assert p.cash == pytest.approx(-100.0)

    def test_crossing_zero_realizes_part_and_opens_at_fill_price(self):
        p = PortfolioState(cash=0.0)
        p.apply_fill("X", 100, 2.0, True)
        result = p.apply_fill("X", 150, 3.0, False)
        assert result.realized_pnl == pytest.approx(100.0)
        assert p.positions["X"].quantity == -50
        assert p.positions["X"].avg_entry_price == 3.0

    def test_invalid_fill_changes_nothing(self):
        p = PortfolioState(cash=10.0)
        for quantity, price in ((0, 1.0), (-1, 1.0), (1, -1.0)):
            with pytest.raises(ValueError):
                p.apply_fill("X", quantity, price, True)
        assert p.cash == 10.0 and p.positions == {}

    def test_equity_marks_long_and_short_to_market(self):
        p = PortfolioState(cash=1_000.0)
        p.apply_fill("L", 100, 2.0, True)
        p.apply_fill("S", 100, 2.0, False)
        assert p.equity({"L": 3.0, "S": 1.0}) == pytest.approx(1_200.0)

    def test_equity_without_price_is_insufficient(self):
        p = PortfolioState(cash=0.0)
        p.apply_fill("X", 100, 2.0, True)
        with pytest.raises(DataInsufficientError):
            p.equity({})


class TestDecision:
    def test_defined_risk_within_limits_is_approved(self):
        assert propose(setup()[2], IRON_CONDOR)["decision"] == "APPROVED"

    def test_risk_veto_is_respected(self):
        # No código de origem, a espera pelo veredito sempre devolvia APPROVED.
        result = propose(setup(limit=50)[2], IRON_CONDOR)
        assert result["decision"] == "REJECTED"
        assert any(reason.startswith("EXPOSURE_LIMIT") for reason in result["reasons"])

    def test_no_risk_manager_means_rejected(self):
        result = propose(IntelligenceSupervisor(B3Bus(), 1.0), IRON_CONDOR)
        assert result["decision"] == "REJECTED"
        assert result["reasons"][0].startswith("NO_VERDICT")

    def test_crashing_risk_manager_means_rejected(self):
        bus = B3Bus()

        def crash(_):
            raise RuntimeError("falha")

        bus.subscribe("intent.STRATEGY", crash)
        assert propose(IntelligenceSupervisor(bus, 1.0), IRON_CONDOR)["decision"] == "REJECTED"

    def test_slow_risk_manager_means_rejected(self):
        bus = B3Bus()

        async def slow(_):
            await asyncio.sleep(5)

        bus.subscribe("intent.STRATEGY", slow)
        result = propose(IntelligenceSupervisor(bus, 0.01), IRON_CONDOR)
        assert result["decision"] == "REJECTED"
        assert result["reasons"][0].startswith("RISK_TIMEOUT")

    def test_unlimited_loss_is_rejected(self):
        result = propose(setup()[2], [leg("TESTC105", "SELL", "CALL", 105.0, 1.5)])
        assert "UNLIMITED_LOSS" in result["reasons"]

    def test_loss_above_cash_is_rejected_even_without_limit_price_trick(self):
        result = propose(setup(cash=100.0)[2], IRON_CONDOR)
        assert result["reasons"][0].startswith("INSUFFICIENT_CASH")

    def test_malformed_intents_are_rejected(self):
        for legs in ([], [{"symbol": "X"}], "lixo"):
            assert propose(setup()[2], legs)["decision"] == "REJECTED"

    def test_two_expiries_are_rejected(self):
        legs = [IRON_CONDOR[0], {**IRON_CONDOR[1], "expiry": date(2027, 1, 15)}]
        assert propose(setup()[2], legs)["reasons"][0].startswith("INVALID_INTENT")

    def test_flow_never_publishes_an_execution_topic(self):
        bus, _, supervisor = setup()
        propose(supervisor, IRON_CONDOR)
        topics = {event["topic"] for event in bus.get_replay_stream()}
        assert topics == {"intent.STRATEGY", "risk.VERDICT", "decision.RESULT"}

    def test_informed_fill_updates_portfolio_and_exposure_check(self):
        bus, portfolio, supervisor = setup(limit=150)

        async def run():
            await bus.publish("portfolio.FILL", {"symbol": "TESTP90", "quantity": 100, "price": 0.5, "side": "BUY"})
            return await supervisor.propose_strategy("TEST4", "TESTE", IRON_CONDOR)

        result = asyncio.run(run())
        assert portfolio.positions["TESTP90"].quantity == 100
        assert any("TESTP90 iria a 200" in reason for reason in result["reasons"])
        states = bus.get_replay_stream("portfolio.STATE")
        assert states[0]["data"]["cash"] == pytest.approx(99_950.0)

    def test_bad_fill_side_changes_nothing(self):
        bus, portfolio, _ = setup()
        asyncio.run(bus.publish("portfolio.FILL", {"symbol": "X", "quantity": 1, "price": 1.0, "side": "?"}))
        assert portfolio.positions == {}
