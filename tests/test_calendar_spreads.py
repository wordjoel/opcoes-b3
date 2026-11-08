"""Trava calendário e diagonal: resultado no vencimento curto, perda limitada ao débito e API."""

from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, create_session, hash_password
from app.main import Settings, create_app
from core.types import MarketSnapshot, OptionChain, OptionKind, OptionQuote
from quant.calendar_spreads import analyze_calendar, bs_value, build_calendars
from tests.test_api import EXPIRY, NOW, PASSWORD, SECRET, SESSION_DAY, SPOT, FakeProvider, _provenance

R = 0.1
SIGMA = 0.3
T_NEAR, T_FAR = 0.1, 0.35


def quotes(expiry: date, t: float, sigma: float = SIGMA, strikes=range(30, 52, 2)) -> list[OptionQuote]:
    """Grade com prêmios justos de Black-Scholes, para isolar a matemática."""
    result = []
    for strike in strikes:
        for kind, prefix in ((OptionKind.CALL, "C"), (OptionKind.PUT, "P")):
            price = float(bs_value(kind, SPOT, strike, t, R, sigma))
            result.append(
                OptionQuote(
                    symbol=f"T{prefix}{strike}{expiry:%m}",
                    underlying="PETR4",
                    kind=kind,
                    strike=float(strike),
                    expiry=expiry,
                    close=round(max(price, 0.01), 4),
                    iv=sigma,
                    volume=200_000,
                    open_interest=2_000_000,
                    trades=200,
                    last_trade_date=SESSION_DAY,
                    provenance=_provenance(),
                )
            )
    return result


NEAR, FAR = date(2026, 11, 20), EXPIRY


def built():
    candidates, missing = build_calendars(quotes(NEAR, T_NEAR), quotes(FAR, T_FAR), SPOT, T_NEAR, T_FAR)
    return {item.key: item for item in candidates}, missing


class TestBuild:
    def test_builds_the_four_structures(self):
        by_key, missing = built()
        assert set(by_key) == {"call_calendar", "put_calendar", "call_diagonal", "put_diagonal"} and not missing
        calendar = by_key["call_calendar"]
        assert calendar.short.leg.strike == calendar.long.leg.strike == SPOT
        assert calendar.short.leg.expiry == NEAR and calendar.long.leg.expiry == FAR
        assert calendar.legs[0].leg.action.value == "BUY"
        assert by_key["call_diagonal"].short.leg.strike > by_key["call_diagonal"].long.leg.strike
        assert by_key["put_diagonal"].short.leg.strike < by_key["put_diagonal"].long.leg.strike

    def test_calendar_is_a_debit(self):
        by_key, _ = built()
        assert by_key["call_calendar"].net_premium() > 0

    def test_missing_common_strike_is_declared(self):
        far = quotes(FAR, T_FAR, strikes=range(31, 52, 2))
        candidates, missing = build_calendars(quotes(NEAR, T_NEAR), far, SPOT, T_NEAR, T_FAR)
        reasons = {key: reason for key, _, reason in missing}
        assert "call_calendar" in reasons and "mesmo strike" in reasons["call_calendar"]

    def test_invalid_times_are_refused(self):
        with pytest.raises(ValueError):
            build_calendars(quotes(NEAR, T_NEAR), quotes(FAR, T_FAR), SPOT, T_FAR, T_NEAR)


class TestAnalysis:
    def test_value_at_short_expiry_matches_black_scholes(self):
        by_key, _ = built()
        calendar = by_key["call_calendar"]
        price = 43.0
        expected = (float(bs_value(OptionKind.CALL, price, SPOT, T_FAR - T_NEAR, R, SIGMA)) - calendar.long.leg.premium) * 100 - (
            max(price - SPOT, 0) - calendar.short.leg.premium
        ) * 100
        assert float(calendar.pnl_at_short_expiry(price, R)) == pytest.approx(expected)

    def test_loss_is_bounded_by_the_debit_and_peak_is_at_the_strike(self):
        by_key, _ = built()
        calendar = by_key["call_calendar"]
        analysis = analyze_calendar(calendar, SPOT, R)
        assert analysis.max_loss <= analysis.net_premium + 1e-6
        assert analysis.max_profit_estimate is not None and analysis.max_profit_estimate > 0
        peak = max(analysis.curve, key=lambda point: point[1])[0]
        assert abs(peak - SPOT) < SPOT * 0.03
        low, high = analysis.breakevens
        assert low < SPOT < high
        for value in analysis.breakevens:
            assert float(calendar.pnl_at_short_expiry(value, R)) == pytest.approx(0, abs=1e-4)
        assert 0 < analysis.probability_of_profit < 1

    def test_more_long_volatility_raises_the_curve(self):
        by_key, _ = built()
        calendar = by_key["call_calendar"]
        prices = np.array([36.0, 40.0, 44.0])
        assert np.all(calendar.pnl_at_short_expiry(prices, R, 0.05) > calendar.pnl_at_short_expiry(prices, R))


class CalendarProvider(FakeProvider):
    """Prazos e séries distintos por vencimento, como na fonte real."""

    def get_option_chain(self, underlying, expiry):
        t = T_NEAR if expiry < EXPIRY else T_FAR
        return OptionChain(
            underlying=MarketSnapshot(symbol=underlying, price=SPOT, provenance=_provenance()),
            quotes=quotes(expiry, t),
            market_date=SESSION_DAY,
            risk_free_rate=R,
            time_to_expiry_years=t,
        )


@pytest.fixture
def client(tmp_path):
    from db.client import Database, migrate

    db = Database(str(tmp_path / "cal.db"))
    migrate(db)
    app = create_app(Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True), lambda: db, lambda _: CalendarProvider(), now=lambda: NOW)
    test_client = TestClient(app, base_url="https://testserver")
    test_client.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
    return test_client


class TestApi:
    URL = f"/api/assets/PETR4/calendars?near={date(2026, 11, 6)}&far={EXPIRY}"

    def test_lists_calendars_never_approved(self, client):
        body = client.get(self.URL).json()
        assert body["near"] == "2026-11-06" and body["far"] == EXPIRY.isoformat()
        assert {row["key"] for row in body["candidates"]} == {"call_calendar", "put_calendar", "call_diagonal", "put_diagonal"}
        for row in body["candidates"]:
            assert row["decision"]["status"] == "INCOMPLETA"
            assert "vol futura" in row["decision"]["missing"][0]
            assert {leg["expiry"] for leg in row["legs"]} == {"2026-11-06", EXPIRY.isoformat()}
            assert row["legs"][0]["action"] == "BUY" and row["legs"][0]["t"] > row["legs"][1]["t"]
            assert row["payoff"] and row["max_loss"] > 0

    def test_far_must_come_after_near(self, client):
        response = client.get(f"/api/assets/PETR4/calendars?near={EXPIRY}&far={date(2026, 11, 6)}")
        assert response.status_code == 422

    def test_requires_session(self, client):
        client.cookies.clear()
        assert client.get(self.URL).status_code == 401
