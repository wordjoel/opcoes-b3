"""IV Rank, histórico de vol da brapi, bandas e mapa de resultado. Valores só de teste."""

from datetime import date

import httpx
import pytest

from app.cache import CachingProvider
from core.exceptions import DataInsufficientError
from data.providers.base import AtmIvSample, DataProvider
from data.providers.brapi import BrapiProvider, candidate_expiries
from db.client import Database, migrate
from quant.iv_rank import iv_rank
from quant.pricing.black_scholes import option_price
from quant.risk import pnl_heatmap
from quant.volatility import bollinger_bands, historical_volatility, rolling_volatility
from core.types import OptionKind
from tests.helpers import leg


class TestIvRank:
    def test_position_and_percentile(self):
        result = iv_rank(0.40, [0.20] * 13 + [0.60] * 13)
        assert result.rank == pytest.approx(50.0)
        assert result.percentile == pytest.approx(50.0)
        assert result.samples == 26

    def test_new_extreme_stays_in_range(self):
        assert iv_rank(0.90, [0.2, 0.6] * 13).rank == 100.0
        assert iv_rank(0.10, [0.2, 0.6] * 13).rank == 0.0

    def test_short_history_is_insufficient(self):
        with pytest.raises(DataInsufficientError):
            iv_rank(0.3, [0.2] * 25)

    def test_flat_history_is_insufficient(self):
        with pytest.raises(DataInsufficientError):
            iv_rank(0.2, [0.2] * 30)


def row(strike, iv=0.3, confidence="high", spot=50.0):
    return {"strike": strike, "impliedVolatility": iv, "confidence": confidence, "underlyingPrice": spot}


def provider(routes):
    """`routes`: expiração -> resposta (dict) ou status HTTP."""

    def handler(request):
        answer = routes.get(request.url.params["expirationDate"], 404)
        return httpx.Response(answer, json={}) if isinstance(answer, int) else httpx.Response(200, json=answer)

    return BrapiProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))


class TestBrapiHistory:
    DAY = date(2026, 10, 14)

    def test_holiday_friday_moves_expiry_to_thursday(self):
        # 20/11/2026 é sexta e feriado nacional: o vencimento é a quinta, 19/11.
        assert candidate_expiries(self.DAY) == [date(2026, 11, 19), date(2026, 11, 20)]

    def test_candidates_are_third_friday_then_thursday(self):
        assert candidate_expiries(date(2026, 9, 1)) == [date(2026, 10, 16), date(2026, 10, 15)]

    def test_candidates_respect_minimum_distance(self):
        assert candidate_expiries(date(2026, 11, 1))[0] == date(2026, 12, 18)

    def test_median_of_near_money_with_confidence(self):
        rows = [row(49, 0.2), row(50, 0.3), row(51, 0.9), row(50, 5.0, "none"), row(50, 5.0, "low"), row(70, 5.0)]
        sample = provider({"2026-11-20": {"date": "2026-10-14", "analytics": rows}}).get_atm_iv_on("PETR4", self.DAY)
        assert sample == AtmIvSample(self.DAY, 0.3, date(2026, 11, 20))

    def test_holiday_expiry_falls_back_to_thursday(self):
        routes = {"2026-11-19": {"date": "2026-10-14", "analytics": [row(50), row(51)]}}
        assert provider(routes).get_atm_iv_on("PETR4", self.DAY).expiry == date(2026, 11, 19)

    def test_response_for_another_session_is_not_used(self):
        # Caso real: pedir um feriado devolve o pregão anterior sem aviso.
        routes = {"2026-11-20": {"date": "2026-10-13", "analytics": [row(50), row(51)]}}
        assert provider(routes).get_atm_iv_on("PETR4", self.DAY) is None

    def test_too_few_values_gives_no_sample(self):
        routes = {"2026-11-20": {"date": "2026-10-14", "analytics": [row(50)]}}
        assert provider(routes).get_atm_iv_on("PETR4", self.DAY) is None

    def test_access_errors_are_not_treated_as_no_data(self):
        for status in (401, 403, 429):
            with pytest.raises(DataInsufficientError):
                provider({"2026-11-20": status}).get_atm_iv_on("VALE3", self.DAY)


class CountingProvider(DataProvider):
    def __init__(self, result):
        self.result, self.calls = result, 0

    def get_atm_iv_on(self, underlying, day):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def get_market_snapshot(self, symbol): ...
    def get_option_chain(self, underlying, expiry): ...
    def get_expirations(self, underlying): ...
    def get_historical_prices(self, symbol, lookback="1y"): ...
    def get_upcoming_events(self, symbol, today): ...


class TestIvCache:
    @pytest.fixture
    def database(self, tmp_path):
        db = Database(str(tmp_path / "iv.db"))
        migrate(db)
        return db

    def test_sample_is_fetched_once(self, database):
        day = date(2026, 10, 14)
        inner = CountingProvider(AtmIvSample(day, 0.3, date(2026, 11, 20)))
        cached = CachingProvider(inner, database)
        assert cached.get_atm_iv_on("PETR4", day) == cached.get_atm_iv_on("PETR4", day) == inner.result
        assert inner.calls == 1

    def test_absence_is_also_remembered(self, database):
        inner = CountingProvider(None)
        cached = CachingProvider(inner, database)
        for _ in range(2):
            assert cached.get_atm_iv_on("PETR4", date(2026, 10, 14)) is None
        assert inner.calls == 1

    def test_errors_are_not_stored(self, database):
        inner = CountingProvider(DataInsufficientError("limite"))
        cached = CachingProvider(inner, database)
        for _ in range(2):
            with pytest.raises(DataInsufficientError):
                cached.get_atm_iv_on("PETR4", date(2026, 10, 14))
        assert inner.calls == 2


class TestBands:
    CLOSES = [100 + (index % 5) * 1.5 for index in range(40)]

    def test_rolling_matches_full_window(self):
        series = rolling_volatility(self.CLOSES, window=20)
        assert series[:20] == [None] * 20
        assert series[-1] == pytest.approx(historical_volatility(self.CLOSES[-21:], min_observations=20))

    def test_bollinger_is_symmetric_around_mean(self):
        bands = bollinger_bands(self.CLOSES, window=20)
        assert bands[18] is None
        upper, middle, lower = bands[-1]
        assert middle == pytest.approx(sum(self.CLOSES[-20:]) / 20)
        assert upper - middle == pytest.approx(middle - lower)
        assert upper > middle

    def test_flat_series_has_no_width(self):
        upper, middle, lower = bollinger_bands([10.0] * 25)[-1]
        assert upper == middle == lower == 10.0


class TestHeatmap:
    def test_matches_model_and_has_grid_shape(self):
        premium = option_price(OptionKind.CALL, 40.0, 40.0, 0.1, 0.1, 0.3)
        legs = [leg("BUY", "CALL", 40.0, premium)]
        result = pnl_heatmap(legs, [0.3], 40.0, 0.1, 0.1)
        assert len(result["pnl"]) == len(result["vol_shocks"])
        assert all(len(line) == len(result["spot_shocks"]) for line in result["pnl"])
        center = result["pnl"][result["vol_shocks"].index(0.0)][result["spot_shocks"].index(0.0)]
        # Sem choque, o valor pelo modelo é o próprio prêmio pago.
        assert center == pytest.approx(0.0)
        up = result["pnl"][result["vol_shocks"].index(0.0)][result["spot_shocks"].index(0.1)]
        expected = (option_price(OptionKind.CALL, 44.0, 40.0, 0.1, 0.1, 0.3) - premium) * 100
        assert up == pytest.approx(expected)

    def test_long_option_gains_with_vol(self):
        result = pnl_heatmap([leg("BUY", "CALL", 40.0, 2.0)], [0.3], 40.0, 0.1, 0.1)
        column = result["spot_shocks"].index(0.0)
        values = [line[column] for line in result["pnl"]]
        # A grade vem da maior vol para a menor.
        assert values == sorted(values, reverse=True)

    def test_missing_iv_gives_nothing(self):
        assert pnl_heatmap([leg("BUY", "CALL", 40.0, 2.0)], [None], 40.0, 0.1, 0.1) is None
