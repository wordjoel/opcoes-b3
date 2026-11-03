"""Laboratório. As grades aqui são fixtures de teste, nunca resultados apresentados como reais."""

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import lab
from app.auth import COOKIE_NAME, create_session, hash_password
from app.cache import CachingProvider
from app.main import Settings, create_app
from core.exceptions import DataInsufficientError
from core.types import LegAction, MarketSnapshot, OptionChain, OptionKind, OptionQuote, Provenance, SourceKind
from data.providers.brapi import BrapiProvider
from db.client import Database, migrate
from quant.lab import evaluate_path, expected_pnl, mark_pnl, rank_groups, returns_summary, settlement_pnl, size_position, vertical_scan
from quant.pricing.black_scholes import option_price
from tests.helpers import leg
from tests.test_api import FakeProvider, PASSWORD, SECRET

NOW = datetime(2026, 11, 3, 22, 0, tzinfo=timezone.utc)
EXPIRY = date(2026, 12, 18)


def history_chain(symbol, expiry, day, spot, price_of, traded=lambda s, d: True):
    prov = Provenance(source="fixture", kind=SourceKind.EOD, collected_at=NOW, market_time=datetime(day.year, day.month, day.day, 21, tzinfo=timezone.utc))
    quotes = []
    for strike in range(30, 52):
        for kind, tag in ((OptionKind.CALL, "C"), (OptionKind.PUT, "P")):
            name = f"T{tag}{strike}"
            sign = 1 if kind is OptionKind.CALL else -1
            base = 0.9 - (strike - 32) * 0.05 if kind is OptionKind.CALL else 0.9 - (strike - 32) * 0.05 - 1
            quotes.append(
                OptionQuote(
                    symbol=name, underlying=symbol, kind=kind, strike=float(strike), expiry=expiry, bid=None, ask=None,
                    close=price_of(kind, strike, spot), open_interest=50_000, volume=20_000, trades=50,
                    last_trade_date=day if traded(name, day) else day - timedelta(days=9), iv=0.3,
                    delta=max(-0.98, min(0.98, base)) * 1 if sign else 0, provenance=prov,
                )
            )
    return OptionChain(underlying=MarketSnapshot(symbol=symbol, price=spot, provenance=prov), quotes=quotes, market_date=day, risk_free_rate=0.1, time_to_expiry_years=0.15)


def model_price(kind, strike, spot):
    return max(round(option_price(kind, spot, float(strike), 0.15, 0.1, 0.3), 2), 0.01)


class HistoryProvider(FakeProvider):
    """Ativo em 40 até `move_day`; depois em `after`. Registra os pregões consultados."""

    def __init__(self, after=44.0, move_day=date(2026, 1, 1), traded=lambda s, d: True, live=40.0):
        super().__init__(live_price=live)
        self.after, self.move_day, self.traded, self.requested = after, move_day, traded, []

    def get_expirations(self, underlying):
        return [EXPIRY]

    def _spot(self, day):
        return self.after if day >= self.move_day else 40.0

    def get_option_chain_on(self, underlying, expiry, day):
        self.requested.append(day)
        if day.weekday() >= 5:
            return None
        return history_chain(underlying, expiry, day, self._spot(day), model_price, self.traded)

    def get_option_chain(self, underlying, expiry):
        day = date(2026, 11, 3)
        return history_chain(underlying, expiry, day, 40.0, model_price, self.traded)


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "lab.db"))
    migrate(database)
    return database


class TestMath:
    def test_size_uses_loss_and_refuses_too_small_capital(self):
        size = size_position(150.0, 150.0, 1000.0)
        assert (size.lots, size.employed, size.max_risk) == (6, 900.0, 900.0)
        assert size_position(1500.0, 1500.0, 1000.0) is None
        assert size_position(0.0, -10.0, 1000.0) is None

    def test_mark_needs_every_leg(self):
        legs = [leg("BUY", "CALL", 40.0, 2.0), leg("SELL", "CALL", 44.0, 1.0)]
        legs = [legs[0].model_copy(update={"symbol": "A"}), legs[1].model_copy(update={"symbol": "B"})]
        assert mark_pnl(legs, {"A": 3.0, "B": 1.5}) == pytest.approx(100 - 50)
        assert mark_pnl(legs, {"A": 3.0}) is None

    def test_settlement_is_intrinsic(self):
        assert settlement_pnl([leg("BUY", "CALL", 40.0, 2.0)], 45.0) == pytest.approx(300.0)

    def test_expected_value_matches_black_scholes_forward(self):
        price = option_price(OptionKind.CALL, 40.0, 42.0, 0.5, 0.1, 0.3)
        ev = expected_pnl([leg("BUY", "CALL", 42.0, 0.0, quantity=1)], 40.0, 0.3, 0.5, 0.1)
        assert ev == pytest.approx(price * 2.718281828 ** (0.1 * 0.5), rel=1e-3)

    def test_path_target_stops_at_first_hit_and_ignores_later(self):
        marks = [("d1", 10.0), ("d2", 60.0), ("d3", -90.0)]
        path = evaluate_path(marks, 100.0, 50.0, 50.0)
        assert (path.exit_reason, path.exit_day, path.final_pnl_unit, path.marks_used) == ("ALVO", "d2", 60.0, 2)
        assert path.worst_unit == 10.0

    def test_path_stop_and_drawdown(self):
        path = evaluate_path([("d1", 30.0), ("d2", -60.0)], 100.0, None, 50.0)
        assert path.exit_reason == "STOP"
        assert path.max_drawdown_unit == pytest.approx(90.0)

    def test_empty_path_has_no_result(self):
        path = evaluate_path([], 100.0, 50.0, 50.0)
        assert path.final_pnl_unit is None and path.exit_reason == "SEM_MARCACAO"

    def test_returns_include_costs(self):
        result = returns_summary(50.0, 2, 1000.0, 300.0, 200.0, 10.0)
        assert result["pnl_brl"] == 90.0
        assert result["return_on_capital"] == pytest.approx(0.09)
        assert result["return_on_employed"] == pytest.approx(0.3)
        assert result["return_on_risk"] == pytest.approx(0.45)

    def test_missing_result_is_not_zero(self):
        assert returns_summary(None, 1, 1000, 100, 100, 0)["pnl_brl"] is None


class TestRanking:
    def row(self, agent, value, symbol="PETR4", horizon=5, regime="BULL"):
        return {"agent": agent, "return_on_risk": value, "max_risk_brl": 100.0, "symbol": symbol, "horizon_days": horizon, "regime": regime}

    def test_one_exceptional_trade_does_not_win(self):
        lucky = [self.row("sorte", 50.0)] + [self.row("sorte", -0.5) for _ in range(24)]
        steady = [self.row("consistente", 0.1) for _ in range(25)]
        ranked = rank_groups(lucky + steady, "agent")
        assert ranked[0]["agent"] == "consistente" and ranked[0]["position"] == 1
        assert ranked[1]["mean_return"] > ranked[0]["mean_return"]

    def test_small_sample_gets_no_position(self):
        ranked = rank_groups([self.row("pouco", 5.0) for _ in range(3)] + [self.row("muito", 0.01) for _ in range(20)], "agent")
        by = {item["agent"]: item for item in ranked}
        assert by["muito"]["position"] == 1
        assert by["pouco"]["position"] is None and not by["pouco"]["sufficient_sample"]

    def test_breakdown_by_symbol_horizon_and_regime(self):
        ranked = rank_groups([self.row("a", 1.0, "PETR4", 5, "BULL"), self.row("a", -1.0, "VALE3", 10, "BEAR")], "agent")[0]
        assert set(ranked["by_symbol"]) == {"PETR4", "VALE3"}
        assert set(ranked["by_horizon"]) == {"5", "10"}
        assert ranked["by_regime"]["BEAR"]["hit_rate"] == 0.0

    def test_unmeasured_results_are_ignored(self):
        assert rank_groups([self.row("a", None)], "agent") == []


class TestVerticalScan:
    def test_returns_valid_structures_with_defined_risk(self):
        chain = history_chain("TEST4", EXPIRY, date(2026, 11, 3), 40.0, model_price)
        found = vertical_scan(chain.quotes, 40.0, 0.15, 0.1)
        assert {item.key for item in found} == {"varredura_alta_call", "varredura_baixa_call", "varredura_alta_put", "varredura_baixa_put"}
        for item in found:
            assert item.proposal.max_loss > 0 and item.proposal.max_profit > 0
            assert {leg_.action for leg_ in item.proposal.legs} == {LegAction.BUY, LegAction.SELL}

    def test_ignores_illiquid_series(self):
        chain = history_chain("TEST4", EXPIRY, date(2026, 11, 3), 40.0, model_price)
        thin = [quote.model_copy(update={"open_interest": 5}) for quote in chain.quotes]
        assert vertical_scan(thin, 40.0, 0.15, 0.1) == []

    def test_impossible_prices_are_not_presented_as_free_profit(self):
        chain = history_chain("TEST4", EXPIRY, date(2026, 11, 3), 40.0, lambda kind, strike, spot: 1.0)
        for item in vertical_scan(chain.quotes, 40.0, 0.15, 0.1):
            assert item.proposal.max_loss > 0


class TestDiscover:
    def test_all_agents_propose_and_nothing_is_approved_without_capital(self):
        result = lab.discover(HistoryProvider(), ["PETR4"], NOW)
        assert {item["agent"] for item in result["opportunities"]} == set(lab.AGENTS)
        assert result["assets"][0]["status"] == "ANALISADO"
        assert all(item["decision"]["status"] != "APROVADA" for item in result["opportunities"])
        first = result["opportunities"][0]
        for field in ("legs", "max_profit", "max_loss", "breakevens", "risk_reward", "days_to_expiry", "potential_return", "theoretical_return"):
            assert field in first

    def test_failure_in_one_asset_does_not_stop_others(self):
        class Partial(HistoryProvider):
            def get_expirations(self, underlying):
                if underlying == "VALE3":
                    raise DataInsufficientError("sem token")
                return super().get_expirations(underlying)

        assets = {item["symbol"]: item for item in lab.discover(Partial(), ["VALE3", "PETR4"], NOW)["assets"]}
        assert assets["VALE3"]["status"] == "DADOS_INSUFICIENTES"
        assert assets["PETR4"]["status"] == "ANALISADO"

    def test_flags_asset_without_liquidity(self):
        class Thin(HistoryProvider):
            def get_option_chain(self, underlying, expiry):
                chain = super().get_option_chain(underlying, expiry)
                return chain.model_copy(update={"quotes": [q.model_copy(update={"volume": 1}) for q in chain.quotes]})

        assert lab.discover(Thin(), ["PETR4"], NOW)["assets"][0]["status"] == "SEM_LIQUIDEZ"

    def test_out_of_budget_is_reported(self):
        assert lab.discover(HistoryProvider(), ["PETR4"], NOW, budget_seconds=0)["assets"][0]["status"] == "NAO_ANALISADO"


PLAN = lab.LabPlan(capital_brl=10_000.0, period_days=5, target_pct=50.0, stop_pct=50.0)


def start(provider, db, plan=PLAN, agent="regra_5pct", key="bull_call_spread", now=NOW):
    return lab.start_forward(provider, db, "PETR4", agent, key, plan, now)


class TestForward:
    def test_records_entry_and_prevents_duplicates(self, db):
        provider = HistoryProvider()
        first = start(provider, db)
        again = start(provider, db)
        assert first["created"] and not again["created"] and first["id"] == again["id"]
        assert db.fetch("SELECT count(*) FROM lab_strategies")[0][0] == 1
        assert first["end_day"] == "2026-11-08"

    def test_stale_grid_is_refused(self, db):
        with pytest.raises(DataInsufficientError, match="defasada"):
            start(HistoryProvider(live=44.0), db)

    def test_capital_too_small_is_refused(self, db):
        with pytest.raises(DataInsufficientError, match="capital"):
            start(HistoryProvider(), db, lab.LabPlan(1.0, 5))

    def test_unknown_agent_is_refused(self, db):
        with pytest.raises(DataInsufficientError):
            start(HistoryProvider(), db, agent="inventado")

    def test_same_session_is_not_marked_as_evolution(self, db):
        provider = HistoryProvider()
        start(provider, db)
        assert lab.monitor(provider, db, NOW)["marked"] == 0

    def chain_provider(self, day, spot, traded=lambda s, d: True):
        provider = HistoryProvider(traded=traded)
        provider.get_option_chain = lambda u, e: history_chain(u, e, day, spot, model_price, traded)
        return provider

    def test_new_session_marks_with_real_prices_and_keeps_active(self, db):
        identity = start(HistoryProvider(), db)["id"]
        next_day = date(2026, 11, 4)
        summary = lab.monitor(self.chain_provider(next_day, 40.2), db, NOW + timedelta(days=1))
        assert summary["marked"] == 1
        detail = lab.strategy_detail(db, identity)
        assert detail["status"] == "ATIVA" and detail["marks"][0]["complete"]
        assert detail["returns"]["measured_label"] == "OBSERVADO"

    def test_target_closes(self, db):
        identity = start(HistoryProvider(), db)["id"]
        lab.monitor(self.chain_provider(date(2026, 11, 4), 50.0), db, NOW + timedelta(days=1))
        detail = lab.strategy_detail(db, identity)
        assert detail["status"] == "ENCERRADA" and detail["close_reason"] == "ALVO" and detail["pnl_brl"] > 0

    def test_stop_closes(self, db):
        identity = start(HistoryProvider(), db)["id"]
        lab.monitor(self.chain_provider(date(2026, 11, 4), 30.0), db, NOW + timedelta(days=1))
        detail = lab.strategy_detail(db, identity)
        assert detail["close_reason"] == "STOP" and detail["pnl_brl"] < 0

    def test_untraded_leg_gives_incomplete_mark_not_a_price(self, db):
        identity = start(HistoryProvider(), db)["id"]
        provider = self.chain_provider(date(2026, 11, 4), 50.0, traded=lambda s, d: False)
        lab.monitor(provider, db, NOW + timedelta(days=1))
        detail = lab.strategy_detail(db, identity)
        assert detail["marks"][0]["complete"] is False and detail["marks"][0]["pnl_brl"] is None
        assert detail["pnl_brl"] is None and detail["status"] == "ATIVA"

    def test_period_end_closes(self, db):
        identity = start(HistoryProvider(), db, lab.LabPlan(10_000.0, 1))["id"]
        lab.monitor(self.chain_provider(date(2026, 11, 4), 40.1), db, NOW + timedelta(days=1))
        assert lab.strategy_detail(db, identity)["close_reason"] == "FIM_DO_PERIODO"

    def test_expiry_settles_by_underlying(self, db):
        identity = start(HistoryProvider(), db, lab.LabPlan(10_000.0, 365))["id"]
        provider = self.chain_provider(EXPIRY, 45.0, traded=lambda s, d: False)
        lab.monitor(provider, db, datetime(2026, 12, 18, 22, tzinfo=timezone.utc))
        detail = lab.strategy_detail(db, identity)
        assert detail["close_reason"] == "VENCIMENTO" and detail["marks"][-1]["settlement"] is True
        assert detail["pnl_brl"] is not None

    def test_failure_is_reported_without_closing(self, db):
        identity = start(HistoryProvider(), db)["id"]

        class Down(HistoryProvider):
            def get_option_chain(self, underlying, expiry):
                raise DataInsufficientError("limite")

        summary = lab.monitor(Down(), db, NOW + timedelta(days=1))
        assert summary["failed"][0]["reason"] == "limite"
        assert lab.strategy_detail(db, identity)["status"] == "ATIVA"

    def test_costs_reduce_the_result_and_absence_is_marked(self, db):
        plan = lab.LabPlan(10_000.0, 30, cost_brl=20.0)
        with_cost = start(HistoryProvider(), db, plan)["id"]
        no_cost = start(HistoryProvider(), db, lab.LabPlan(10_001.0, 30))["id"]
        provider = self.chain_provider(date(2026, 11, 4), 41.0)
        lab.monitor(provider, db, NOW + timedelta(days=1))
        a, b = lab.strategy_detail(db, with_cost), lab.strategy_detail(db, no_cost)
        assert a["cost_informed"] == 1 and b["cost_informed"] == 0
        unit = db.fetch("SELECT pnl_unit FROM lab_marks WHERE strategy_id = ?", (with_cost,))[0][0]
        assert a["pnl_brl"] == pytest.approx(unit * a["lots"] - 20.0)


BT_PLAN = lab.LabPlan(capital_brl=100_000.0, period_days=5)


class TestBacktest:
    def test_runs_and_labels_as_simulated(self, db):
        summary = lab.run_backtest(HistoryProvider(), db, "PETR4", BT_PLAN, 2, NOW)
        assert summary["entries"] == 2 and summary["complete"] and summary["created"] > 0
        rows = lab.list_strategies(db, "BACKTEST")
        assert rows and all(row["returns"]["measured_label"] == "SIMULADO" for row in rows)
        assert all(row["status"] == "ENCERRADA" for row in rows)

    def test_entry_uses_only_the_session_of_entry(self, tmp_path):
        """Grades posteriores totalmente diferentes não alteram as pernas escolhidas."""

        class Later(HistoryProvider):
            def __init__(self, later_spot):
                super().__init__()
                self.later_spot = later_spot
                self.entry = None

            def get_option_chain_on(self, underlying, expiry, day):
                self.requested.append(day)
                if day.weekday() >= 5:
                    return None
                if self.entry is None:
                    self.entry = day
                spot = 40.0 if day == self.entry else self.later_spot
                return history_chain(underlying, expiry, day, spot, model_price)

        def run(later_spot, name):
            db = Database(str(tmp_path / name))
            migrate(db)
            lab.run_backtest(Later(later_spot), db, "PETR4", BT_PLAN, 1, NOW)
            return db

        low, high = run(30.0, "low.db"), run(50.0, "high.db")
        query = "SELECT agent, structure_key, legs_json FROM lab_strategies ORDER BY id"
        assert low.fetch(query) == high.fetch(query)
        assert low.fetch("SELECT sum(pnl_unit) FROM lab_marks")[0][0] != high.fetch("SELECT sum(pnl_unit) FROM lab_marks")[0][0]

    def test_resumes_without_duplicates(self, db):
        lab.run_backtest(HistoryProvider(), db, "PETR4", BT_PLAN, 2, NOW)
        before = db.fetch("SELECT count(*) FROM lab_strategies")[0][0], db.fetch("SELECT count(*) FROM lab_marks")[0][0]
        lab.run_backtest(HistoryProvider(), db, "PETR4", BT_PLAN, 2, NOW)
        assert (db.fetch("SELECT count(*) FROM lab_strategies")[0][0], db.fetch("SELECT count(*) FROM lab_marks")[0][0]) == before

    def test_out_of_budget_reports_incomplete(self, db):
        assert lab.run_backtest(HistoryProvider(), db, "PETR4", BT_PLAN, 2, NOW, budget_seconds=0)["complete"] is False

    def test_source_limit_stops_and_is_reported(self, db):
        class Limited(HistoryProvider):
            def get_option_chain_on(self, underlying, expiry, day):
                raise DataInsufficientError("limite de requisições")

        summary = lab.run_backtest(Limited(), db, "PETR4", BT_PLAN, 2, NOW)
        assert summary["complete"] is False and summary["skipped"][0]["reason"] == "limite de requisições"

    def test_missing_session_is_skipped(self, db):
        class Holiday(HistoryProvider):
            def get_option_chain_on(self, underlying, expiry, day):
                return None

        summary = lab.run_backtest(Holiday(), db, "PETR4", BT_PLAN, 1, NOW)
        assert summary["entries"] == 0 and summary["skipped"]

    def test_uses_no_entry_after_the_period_fits(self, db):
        provider = HistoryProvider()
        lab.run_backtest(provider, db, "PETR4", BT_PLAN, 1, NOW)
        assert max(provider.requested) <= date(2026, 11, 3)

    def test_ranking_never_mixes_modes_and_is_labelled(self, db):
        lab.run_backtest(HistoryProvider(), db, "PETR4", BT_PLAN, 2, NOW)
        simulated = lab.ranking(db, "BACKTEST")
        assert simulated["label"] == "SIMULADO" and simulated["closed"] > 0
        assert simulated["agents"][0]["position"] is None or simulated["agents"][0]["count"] >= 20
        assert lab.ranking(db, "FORWARD")["closed"] == 0


def brapi_with(handler):
    return BrapiProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))


class TestBrapiHistory:
    DAY = date(2026, 1, 14)

    def responses(self, chain_date="2026-01-14", analytics_date="2026-01-14"):
        ts_day = int(datetime(2026, 1, 14, 3, tzinfo=timezone.utc).timestamp())
        ts_old = int(datetime(2026, 1, 9, 3, tzinfo=timezone.utc).timestamp())
        base = {"underlyingSymbol": "PETR4", "side": "call", "optionStyle": "american", "strike": 31.65, "expirationDate": "2026-02-20", "close": 1.26, "lastTradeDate": "2026-02-20", "trades": 5, "volume": 100, "openInterest": 1000}

        def handler(request):
            if request.url.path.endswith("/chain"):
                return httpx.Response(200, json={"date": chain_date, "series": [{**base, "symbol": "A", "date": ts_day}, {**base, "symbol": "B", "date": ts_old}]})
            return httpx.Response(200, json={"date": analytics_date, "analytics": [{"symbol": "A", "underlyingPrice": 31.99, "riskFreeRate": 0.15, "timeToExpirationYears": 0.1, "impliedVolatility": 0.2, "delta": 0.5}]})

        return handler

    def test_traded_date_comes_from_the_session_not_the_future(self):
        chain = brapi_with(self.responses()).get_option_chain_on("PETR4", date(2026, 2, 20), self.DAY)
        by = {quote.symbol: quote for quote in chain.quotes}
        assert by["A"].last_trade_date == self.DAY
        assert by["B"].last_trade_date == date(2026, 1, 9)
        assert chain.underlying.price == 31.99

    def test_other_session_returned_by_source_is_refused(self):
        assert brapi_with(self.responses(chain_date="2026-01-13")).get_option_chain_on("PETR4", date(2026, 2, 20), self.DAY) is None

    def test_not_found_means_none(self):
        provider = brapi_with(lambda request: httpx.Response(404, json={}))
        assert provider.get_option_chain_on("PETR4", date(2026, 2, 20), self.DAY) is None

    def test_rate_limit_raises(self):
        provider = brapi_with(lambda request: httpx.Response(429, json={}))
        with pytest.raises(DataInsufficientError):
            provider.get_option_chain_on("PETR4", date(2026, 2, 20), self.DAY)


class TestHistoryCache:
    def test_stored_forever_and_absence_too(self, db):
        inner = HistoryProvider()
        cached = CachingProvider(inner, db, now=lambda: NOW)
        day = date(2026, 1, 14)
        assert cached.get_option_chain_on("PETR4", EXPIRY, day) == cached.get_option_chain_on("PETR4", EXPIRY, day)
        saturday = date(2026, 1, 17)
        assert cached.get_option_chain_on("PETR4", EXPIRY, saturday) is None
        assert cached.get_option_chain_on("PETR4", EXPIRY, saturday) is None
        assert inner.requested == [day, saturday]

    def test_corrupt_entry_is_fetched_again(self, db):
        inner = HistoryProvider()
        cached = CachingProvider(inner, db, now=lambda: NOW)
        day = date(2026, 1, 14)
        db.run("INSERT INTO option_history VALUES ('PETR4', ?, ?, 'lixo', ?)", (EXPIRY.isoformat(), day.isoformat(), NOW.isoformat()))
        assert cached.get_option_chain_on("PETR4", EXPIRY, day).quotes
        assert inner.requested == [day]

    def test_errors_are_not_stored(self, db):
        class Down(HistoryProvider):
            def get_option_chain_on(self, underlying, expiry, day):
                raise DataInsufficientError("limite")

        cached = CachingProvider(Down(), db, now=lambda: NOW)
        with pytest.raises(DataInsufficientError):
            cached.get_option_chain_on("PETR4", EXPIRY, date(2026, 1, 14))
        assert db.fetch("SELECT count(*) FROM option_history")[0][0] == 0


class TestRoutes:
    @pytest.fixture
    def client(self, db):
        provider = HistoryProvider()
        app = create_app(Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True), lambda: db, lambda _: provider, now=lambda: NOW)
        logged = TestClient(app, base_url="https://testserver")
        logged.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
        return logged

    def test_all_require_session(self, db):
        app = create_app(Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True), lambda: db, lambda _: HistoryProvider(), now=lambda: NOW)
        anonymous = TestClient(app, base_url="https://testserver")
        assert anonymous.get("/api/lab/opportunities").status_code == 401
        assert anonymous.get("/api/lab/strategies").status_code == 401
        assert anonymous.get("/api/lab/strategies/x").status_code == 401
        assert anonymous.get("/api/lab/ranking?mode=BACKTEST").status_code == 401
        assert anonymous.post("/api/lab/monitor").status_code == 401
        assert anonymous.post("/api/lab/strategies", json={}).status_code == 401
        assert anonymous.post("/api/lab/backtests", json={}).status_code == 401

    def test_flow(self, client):
        assert client.get("/api/lab/opportunities").json()["opportunities"]
        body = {"symbol": "petr4", "agent": "regra_5pct", "key": "bull_call_spread", "capital_brl": 1000, "period_days": 5, "target_pct": 50, "stop_pct": 50}
        created = client.post("/api/lab/strategies", json=body)
        assert created.status_code == 200
        identity = created.json()["id"]
        listed = client.get("/api/lab/strategies?mode=FORWARD").json()["strategies"]
        assert listed[0]["id"] == identity and listed[0]["returns"]["measured"] is None
        assert client.get(f"/api/lab/strategies/{identity}").json()["marks"] == []
        assert client.get("/api/lab/strategies/inexistente").status_code == 404
        assert client.post("/api/lab/monitor").json()["active"] == 1
        run = client.post("/api/lab/backtests", json={"symbol": "PETR4", "capital_brl": 100000, "period_days": 5, "weeks": 1})
        assert run.status_code == 200
        assert client.get("/api/lab/ranking?mode=BACKTEST").json()["label"] == "SIMULADO"

    @pytest.mark.parametrize(
        "body",
        [
            {"symbol": "PETR4", "agent": "regra_5pct", "key": "x", "capital_brl": 0, "period_days": 5},
            {"symbol": "PETR4", "agent": "regra_5pct", "key": "x", "capital_brl": 10, "period_days": 0},
            {"symbol": "PETR4", "agent": "regra_5pct", "key": "x", "capital_brl": 10, "period_days": 5, "stop_pct": 500},
        ],
    )
    def test_invalid_plans_are_refused(self, client, body):
        assert client.post("/api/lab/strategies", json=body).status_code == 422

    def test_client_cannot_inject_prices(self, client):
        body = {"symbol": "PETR4", "agent": "regra_5pct", "key": "bull_call_spread", "capital_brl": 1000, "period_days": 5, "premium": 0.01}
        identity = client.post("/api/lab/strategies", json=body).json()["id"]
        assert all(leg_["premium"] > 0.01 for leg_ in client.get(f"/api/lab/strategies/{identity}").json()["legs"])

    def test_no_order_route_in_the_lab(self, client):
        for path in ("/api/lab/orders", "/api/lab/execute", "/api/lab/ordens"):
            assert client.post(path, json={}).status_code == 404
