"""Decisão com capital e margem, e modelo americano. Valores só de teste."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, create_session, hash_password
from app.main import Settings, create_app
from core.types import ExerciseStyle, OptionKind
from db.client import Database, migrate
from quant.pricing.binomial import american_price, model_value
from quant.pricing.black_scholes import option_price
from quant.costs import CostSchedule
from quant.risk import CapitalLimits, assess_risk, decide, pnl_heatmap, stress_tests
from quant.strategies import build_candidates
from tests.helpers import leg, quote
from tests.test_api import EXPIRY, NOW, PASSWORD, SECRET, FakeProvider
from tests.test_strategies_risk import SPOT, full_grid


def candidate(key):
    built, _ = build_candidates(full_grid(), SPOT, use_book=False)
    return next(item for item in built if item.key == key)


ZERO_COSTS = CostSchedule(0.0, 0.0, 0.0)


def evaluate(key, capital, drift=0.0, quotes=None, costs=ZERO_COSTS):
    item = candidate(key)
    rules = assess_risk(item.proposal, quotes or item.quotes, SPOT, 0.12, 0.1375, drift, use_book=False)
    return decide(item.proposal, rules, capital, drift, costs)


CAPITAL = CapitalLimits(capital_brl=10_000.0, max_loss_pct=5.0)


class TestDecision:
    def test_long_option_within_limits_is_approved(self):
        result = evaluate("long_call", CAPITAL)
        assert result["status"] == "APROVADA"
        assert result["capital_required"] == pytest.approx(100.0)
        assert result["max_risk"] == pytest.approx(100.0)
        assert result["max_risk_pct"] == pytest.approx(1.0)
        assert result["limit_brl"] == pytest.approx(500.0)

    def test_without_costs_is_never_approved(self):
        result = evaluate("long_call", CAPITAL, costs=None)
        assert result["status"] == "INCOMPLETA"
        assert "custos operacionais não informados" in result["missing"]

    def test_costs_enter_the_loss_and_the_profit(self):
        # 2 ordens de R$ 5, 0,5% sobre R$ 100 nas duas pontas = R$ 11; imposto de 15% sobre o ganho.
        result = evaluate("long_call", CAPITAL, costs=CostSchedule(5.0, 0.5, 15.0))
        assert result["costs_brl"] == pytest.approx(11.0)
        assert result["max_risk"] == pytest.approx(111.0)
        assert result["capital_required"] == pytest.approx(105.5)
        assert result["max_profit_net"] is None  # call comprada: ganho ilimitado

    def test_costs_can_push_loss_over_the_limit(self):
        result = evaluate("long_call", CapitalLimits(capital_brl=10_000.0, max_loss_pct=1.05), costs=CostSchedule(5.0, 0.0, 0.0))
        assert result["status"] == "REPROVADA"
        assert any("com custos" in reason for reason in result["reasons"])

    def test_without_capital_is_never_approved(self):
        result = evaluate("long_call", None)
        assert result["status"] == "INCOMPLETA"
        assert any("capital" in text.lower() for text in result["missing"])

    def test_loss_above_limit_rejects(self):
        result = evaluate("long_call", CapitalLimits(10_000.0, 0.5))
        assert result["status"] == "REPROVADA"
        assert any("limite" in text for text in result["reasons"])

    def test_cost_above_capital_rejects(self):
        result = evaluate("long_call", CapitalLimits(50.0, 100.0))
        assert result["status"] == "REPROVADA"
        assert any("capital" in text for text in result["reasons"])

    @pytest.mark.parametrize("key", ["bear_call_spread", "bull_put_spread", "iron_condor", "iron_butterfly", "call_butterfly"])
    def test_sold_leg_without_broker_margin_is_not_approved(self, key):
        result = evaluate(key, CapitalLimits(1_000_000.0, 100.0))
        assert result["status"] != "APROVADA"
        assert result["capital_required"] is None

    def test_sold_leg_says_margin_is_missing(self):
        result = evaluate("iron_condor", CapitalLimits(1_000_000.0, 100.0))
        assert any("margem" in text for text in result["missing"])

    def test_rule_rejection_prevails_over_missing_data(self):
        assert evaluate("long_call", None, drift=-0.10)["status"] == "REPROVADA"

    def test_unmeasured_drift_is_not_approved(self):
        assert evaluate("long_call", CAPITAL, drift=None)["status"] == "INCOMPLETA"

    def test_missing_iv_is_not_approved(self):
        grid = full_grid(iv=None)
        built, _ = build_candidates(grid, SPOT, use_book=False)
        item = next(entry for entry in built if entry.key == "long_call")
        rules = assess_risk(item.proposal, item.quotes, SPOT, 0.12, 0.1375, 0.0, use_book=False)
        result = decide(item.proposal, rules, CAPITAL, 0.0)
        assert result["status"] == "INCOMPLETA"

    def test_unmeasured_liquidity_is_incomplete_not_rejected(self):
        grid = full_grid(open_interest=None)
        built, _ = build_candidates(grid, SPOT, use_book=False)
        item = next(entry for entry in built if entry.key == "long_call")
        rules = assess_risk(item.proposal, item.quotes, SPOT, 0.12, 0.1375, 0.0, use_book=False)
        assert decide(item.proposal, rules, CAPITAL, 0.0)["status"] == "INCOMPLETA"

    def test_unlimited_loss_is_rejected(self):
        item = candidate("long_call")
        naked = item.proposal.model_copy(update={"legs": [leg("SELL", "CALL", 40.0, 1.0)], "max_loss": None, "max_profit": 100.0})
        rules = assess_risk(naked, item.quotes, SPOT, 0.12, 0.1375, 0.0, use_book=False)
        assert decide(naked, rules, CAPITAL, 0.0)["status"] == "REPROVADA"

    @pytest.mark.parametrize("values", [(0.0, 5.0), (-1.0, 5.0), (100.0, 0.0), (100.0, 101.0)])
    def test_invalid_limits_are_refused(self, values):
        with pytest.raises(ValueError):
            CapitalLimits(*values)


class TestAmerican:
    def test_put_value_converges_to_reference(self):
        # Hull: S=50, K=50, r=10%, sigma=40%, T=5 meses, put americana perto de 4,28.
        assert american_price(OptionKind.PUT, 50, 50, 5 / 12, 0.1, 0.4, steps=500) == pytest.approx(4.28, abs=0.02)

    def test_american_put_is_worth_at_least_european(self):
        american = american_price(OptionKind.PUT, 40, 44, 0.5, 0.1375, 0.3)
        assert american > option_price(OptionKind.PUT, 40, 44, 0.5, 0.1375, 0.3)

    def test_deep_put_never_below_intrinsic(self):
        assert american_price(OptionKind.PUT, 20, 44, 0.5, 0.1375, 0.3) >= 24.0

    def test_call_without_dividend_equals_european(self):
        assert american_price(OptionKind.CALL, 40, 42, 0.5, 0.1375, 0.3) == option_price(OptionKind.CALL, 40, 42, 0.5, 0.1375, 0.3)

    def test_call_with_dividend_can_be_worth_more(self):
        assert american_price(OptionKind.CALL, 60, 40, 1.0, 0.05, 0.3, q=0.10) > option_price(OptionKind.CALL, 60, 40, 1.0, 0.05, 0.3, q=0.10)

    def test_expired_is_intrinsic(self):
        assert american_price(OptionKind.PUT, 40, 44, 0.0, 0.1, 0.3) == 4.0

    def test_style_selects_the_model(self):
        args = (OptionKind.PUT, 40.0, 44.0, 0.5, 0.1375, 0.3)
        assert model_value(args[0], ExerciseStyle.AMERICAN, *args[1:]) > model_value(args[0], ExerciseStyle.EUROPEAN, *args[1:])
        assert model_value(args[0], None, *args[1:]) == option_price(*args)

    def test_stress_and_heatmap_use_the_style(self):
        legs = [leg("BUY", "PUT", 44.0, 4.0)]
        european = stress_tests(legs, [0.3], 40.0, 0.5, 0.1375)
        american = stress_tests(legs, [0.3], 40.0, 0.5, 0.1375, [ExerciseStyle.AMERICAN])
        assert american["Vol +10 pontos hoje"] > european["Vol +10 pontos hoje"]
        map_e = pnl_heatmap(legs, [0.3], 40.0, 0.5, 0.1375)["pnl"][2][3]
        map_a = pnl_heatmap(legs, [0.3], 40.0, 0.5, 0.1375, [ExerciseStyle.AMERICAN])["pnl"][2][3]
        assert map_a > map_e

    def test_analysis_declares_the_model_limit(self):
        item = candidate("long_call")
        quotes = [quote(strike=40.0, style=ExerciseStyle.AMERICAN, iv=0.3, open_interest=2_000_000, volume=200_000, trades=200)]
        rules = assess_risk(item.proposal, quotes, SPOT, 0.12, 0.1375, 0.0, use_book=False)
        assert any("modelo europeu" in text for text in rules.warnings)

    def test_unknown_style_is_declared(self):
        item = candidate("long_call")
        rules = assess_risk(item.proposal, item.quotes, SPOT, 0.12, 0.1375, 0.0, use_book=False)
        assert any("estilo" in text for text in rules.warnings)


@pytest.fixture
def client(tmp_path):
    db = Database(str(tmp_path / "c.db"))
    migrate(db)
    app = create_app(Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True), lambda: db, lambda _: FakeProvider(), now=lambda: NOW)
    logged = TestClient(app, base_url="https://testserver")
    logged.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
    return logged


class TestRiskSettingsRoutes:
    def test_starts_without_settings(self, client):
        assert client.get("/api/settings/risk").json() == {"capital_brl": None, "max_loss_pct": None, "updated_at": None}

    def test_save_and_apply_to_analysis(self, client):
        before = client.get(f"/api/assets/PETR4/strategies?expiry={EXPIRY}").json()
        assert {row["decision"]["status"] for row in before["candidates"]} <= {"INCOMPLETA", "REPROVADA"}
        saved = client.put("/api/settings/risk", json={"capital_brl": 10_000, "max_loss_pct": 5})
        assert saved.status_code == 200 and saved.json()["capital_brl"] == 10_000
        still = client.get(f"/api/assets/PETR4/strategies?expiry={EXPIRY}").json()
        assert {row["decision"]["status"] for row in still["candidates"]} <= {"INCOMPLETA", "REPROVADA"}
        costs = client.put("/api/settings/costs", json={"per_order_brl": 0, "fee_pct": 0, "income_tax_pct": 15})
        assert costs.status_code == 200 and costs.json()["income_tax_pct"] == 15
        after = client.get(f"/api/assets/PETR4/strategies?expiry={EXPIRY}").json()
        by_key = {row["key"]: row for row in after["candidates"]}
        assert by_key["long_call"]["decision"]["status"] == "APROVADA"
        assert by_key["iron_condor"]["decision"]["status"] != "APROVADA"

    @pytest.mark.parametrize("body", [{"capital_brl": 0, "max_loss_pct": 5}, {"capital_brl": 100, "max_loss_pct": 0}, {"capital_brl": 100, "max_loss_pct": 101}, {"capital_brl": 100}])
    def test_invalid_values_are_refused(self, client, body):
        assert client.put("/api/settings/risk", json=body).status_code == 422

    @pytest.mark.parametrize("body", [{"per_order_brl": -1, "fee_pct": 0, "income_tax_pct": 15}, {"per_order_brl": 0, "fee_pct": 6, "income_tax_pct": 15}, {"per_order_brl": 0, "fee_pct": 0}])
    def test_invalid_costs_are_refused(self, client, body):
        assert client.put("/api/settings/costs", json=body).status_code == 422

    def test_costs_start_empty(self, client):
        assert client.get("/api/settings/costs").json()["per_order_brl"] is None

    def test_requires_session(self, tmp_path):
        db = Database(str(tmp_path / "d.db"))
        migrate(db)
        app = create_app(Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True), lambda: db, lambda _: FakeProvider(), now=lambda: NOW)
        anonymous = TestClient(app, base_url="https://testserver")
        assert anonymous.get("/api/settings/risk").status_code == 401
        assert anonymous.put("/api/settings/risk", json={"capital_brl": 1, "max_loss_pct": 1}).status_code == 401
