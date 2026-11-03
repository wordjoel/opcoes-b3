"""Delta por perfil, probabilidade, eventos, estrutura e contratos em aberto. Valores só de teste."""

from datetime import date, timedelta

import httpx
import pytest

from core.types import CorporateEvent, OptionKind, PriceBar
from data.providers.brapi import BrapiProvider
from quant.open_interest import summarize_open_interest
from quant.pricing.black_scholes import option_price
from quant.probability import probability_itm
from quant.risk import assess_risk
from quant.strategies import PROFILES, build_candidates
from quant.structure import analyze_structure
from tests.helpers import EXPIRY, leg, provenance, quote

SPOT = 40.0


def grid(**changes):
    """Delta cai 0,05 por real acima de 36: calls de 0,70 a 0,05."""
    quotes = []
    for strike in range(32, 54):
        base = max(0.02, min(0.98, 0.90 - (strike - 32) * 0.05))
        for kind, sign, delta in ((OptionKind.CALL, "C", base), (OptionKind.PUT, "P", base - 1)):
            values = dict(
                symbol=f"T{sign}{strike}",
                kind=kind,
                strike=float(strike),
                bid=None,
                ask=None,
                close=1.0,
                delta=delta,
                iv=0.3,
                open_interest=50_000,
                volume=20_000,
                trades=50,
            )
            quotes.append(quote(**{**values, **changes}))
    return quotes


def build(quotes=None, profile="MODERATE"):
    built, unavailable = build_candidates(quotes or grid(), SPOT, use_book=False, profile=profile)
    return {item.key: item for item in built}, {item.key: item.reason for item in unavailable}


class TestDeltaSelection:
    def strikes(self, key, profile):
        return [item.strike for item in build(profile=profile)[0][key].proposal.legs]

    def test_bull_call_uses_profile_targets(self):
        # Delta = 0,90 - (K - 32) x 0,05.
        assert self.strikes("bull_call_spread", "CONSERVATIVE") == [42.0, 46.0]
        assert self.strikes("bull_call_spread", "MODERATE") == [41.0, 45.0]
        assert self.strikes("bull_call_spread", "AGGRESSIVE") == [40.0, 44.0]

    def test_put_side_uses_absolute_delta(self):
        buy, sell = build(profile="MODERATE")[0]["bear_put_spread"].proposal.legs
        assert buy.strike > sell.strike
        assert buy.kind is OptionKind.PUT

    def test_condor_has_ordered_strikes(self):
        strikes = self.strikes("iron_condor", "CONSERVATIVE")
        assert strikes == sorted(strikes)

    def test_without_profile_keeps_distance_rule(self):
        built = build(profile=None)[0]
        assert built["bull_call_spread"].proposal.legs[0].strike == 40.0

    def test_illiquid_series_are_not_chosen(self):
        # 5.000 opções = 50 contratos; 10.000 = 100 contratos.
        thin = grid(open_interest=9_999)
        built, reasons = build(thin)
        assert "bull_call_spread" not in built
        assert "delta" in reasons["bull_call_spread"]

    def test_series_without_delta_is_not_chosen(self):
        assert "bull_call_spread" not in build(grid(delta=None))[0]

    def test_no_delta_near_target_is_reported(self):
        far = [item for item in grid() if not 0.1 <= abs(item.delta) <= 0.6]
        assert "alvo" in build(far)[1]["bull_call_spread"]

    def test_invalid_profile(self):
        assert set(PROFILES) == {"CONSERVATIVE", "MODERATE", "AGGRESSIVE"}
        with pytest.raises(ValueError):
            build_candidates(grid(), SPOT, profile="OUTRO")


class TestProbability:
    def test_call_and_put_sum_to_one(self):
        call = probability_itm(OptionKind.CALL, 40.0, 42.0, 0.2, 0.1, 0.3)
        put = probability_itm(OptionKind.PUT, 40.0, 42.0, 0.2, 0.1, 0.3)
        assert call + put == pytest.approx(1.0)

    def test_matches_digital_price_derivative(self):
        step = 1e-3
        slope = option_price(OptionKind.CALL, 40.0, 42.0 - step, 0.2, 0.1, 0.3) - option_price(
            OptionKind.CALL, 40.0, 42.0 + step, 0.2, 0.1, 0.3
        )
        discounted = slope / (2 * step)
        expected = probability_itm(OptionKind.CALL, 40.0, 42.0, 0.2, 0.1, 0.3) * 2.718281828 ** (-0.1 * 0.2)
        assert discounted == pytest.approx(expected, abs=1e-4)

    def test_missing_inputs_give_none(self):
        assert probability_itm(OptionKind.CALL, 40.0, 42.0, 0.2, 0.1, None) is None
        assert probability_itm(OptionKind.CALL, 40.0, 42.0, 0.0, 0.1, 0.3) is None


def event(day, kind="RESULTADO", label="Resultado Q3/2026", confirmed=True):
    return CorporateEvent(kind=kind, day=day, label=label, confirmed=confirmed)


class TestEventsInRisk:
    def assess(self, events, today=date(2026, 11, 3), expiry=EXPIRY):
        candidate = build_candidates(grid(expiry=expiry), SPOT, use_book=False)[0][0]
        return assess_risk(candidate.proposal, candidate.quotes, SPOT, 0.1, 0.1, 0.0, use_book=False, events=events, today=today)

    def test_event_before_expiry_warns(self):
        result = self.assess([event(date(2026, 11, 10))])
        assert any("Resultado Q3/2026 em 10/11/2026" in text for text in result.warnings)

    def test_estimated_date_says_so(self):
        result = self.assess([event(date(2026, 11, 10), confirmed=False)])
        assert any("data estimada" in text for text in result.warnings)

    def test_event_after_expiry_is_ignored(self):
        result = self.assess([event(EXPIRY + timedelta(days=1))])
        assert not any("Resultado" in text for text in result.warnings)

    def test_earnings_with_short_expiry_rejects(self):
        result = self.assess([event(date(2026, 11, 6))], expiry=date(2026, 11, 7))
        assert not result.is_approved
        assert "menos de 7 dias" in result.rejection_reason

    def test_dividend_with_short_expiry_only_warns(self):
        result = self.assess([event(date(2026, 11, 6), "PROVENTO", "JCP")], expiry=date(2026, 11, 7))
        assert result.is_approved
        assert any("JCP" in text for text in result.warnings)

    def test_low_pop_credit_warns(self):
        legs = [leg("SELL", "PUT", 41.0, 0.5), leg("BUY", "PUT", 38.0, 0.1)]
        candidate = build_candidates(grid(), SPOT, use_book=False)[0][0]
        proposal = candidate.proposal.model_copy(update={"legs": legs, "max_loss": 260.0, "max_profit": 40.0})
        quotes = [quote(strike=41.0, iv=0.3, open_interest=2_000_000, volume=200_000, trades=200)] * 2
        result = assess_risk(proposal, quotes, SPOT, 0.1, 0.1, 0.0, use_book=False)
        assert any("65%" in text for text in result.warnings)


def provider(routes):
    def handler(request):
        answer = routes.get(request.url.path.rsplit("/", 1)[-1], 404)
        return httpx.Response(answer, json={}) if isinstance(answer, int) else httpx.Response(200, json=answer)

    return BrapiProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))


class TestBrapiEvents:
    TODAY = date(2026, 11, 3)

    def test_parses_real_shapes_and_drops_past(self):
        routes = {
            "earnings-calendar": {
                "results": [
                    {"status": "scheduled", "date": "2026-11-10", "dateStatus": "confirmed", "fiscalPeriod": "Q3", "fiscalYear": 2026},
                    {"status": "published", "date": "2026-08-06", "dateStatus": "confirmed", "fiscalPeriod": "Q2", "fiscalYear": 2026},
                ]
            },
            "dividends": {
                "results": [
                    {
                        "data": {
                            "cashDividends": [
                                {"label": "JCP", "exDate": "2026-08-24T03:00:00.000Z", "verified": True},
                                {"label": "DIVIDENDO", "exDate": "2026-11-20T03:00:00.000Z", "verified": False},
                            ],
                            "stockDividends": [{"label": "GRUPAMENTO", "exDate": None, "lastDatePrior": "2026-12-01T03:00:00.000Z"}],
                        }
                    }
                ]
            },
        }
        events = provider(routes).get_upcoming_events("PETR4", self.TODAY)
        assert [(e.kind, e.day, e.confirmed) for e in events] == [
            ("RESULTADO", date(2026, 11, 10), True),
            ("PROVENTO", date(2026, 11, 20), False),
            ("EVENTO_SOCIETARIO", date(2026, 12, 1), True),
        ]
        assert events[0].label == "Resultado Q3/2026"

    def test_not_found_means_no_events(self):
        assert provider({}).get_upcoming_events("PETR4", self.TODAY) == []


def bar(index, high, low, close):
    return PriceBar(
        symbol="TEST4",
        day=date(2026, 1, 1) + timedelta(days=index),
        open=close,
        high=high,
        low=low,
        close=close,
        adjusted=True,
        provenance=provenance(),
    )


def series(closes):
    return [bar(i, c + 0.5, c - 0.5, c) for i, c in enumerate(closes)]


class TestStructure:
    # Sobe até 15, recua até 10, sobe até 20, recua até 12.
    UP = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 11, 12, 13, 14, 15.2, 17, 18, 19, 20, 19, 18, 17, 16, 15, 14, 13]

    def test_first_break_is_bos_up_at_prior_high(self):
        result = analyze_structure(series(self.UP), pivot=3)
        first = result.events[0]
        assert (first.kind, first.direction) == ("BOS", "UP")
        assert first.level == pytest.approx(15.5)
        assert result.trend == "UP"

    def test_break_against_trend_is_choch(self):
        down = self.UP + [12, 11, 10, 9, 8, 7, 6]
        result = analyze_structure(series(down), pivot=3)
        last = result.events[-1]
        assert (last.kind, last.direction) == ("CHOCH", "DOWN")
        assert result.trend == "DOWN"

    def test_swing_needs_bars_after_it(self):
        # O topo só é conhecido depois das barras seguintes: nenhum rompimento sem elas.
        assert analyze_structure(series([10, 11, 12, 13]), pivot=3).events == []

    def test_new_high_alone_is_not_a_break(self):
        assert analyze_structure(series(list(range(10, 40))), pivot=3).events == []

    def test_reading_never_changes_with_future_bars(self):
        full = analyze_structure(series(self.UP), pivot=3).events
        for size in range(len(self.UP)):
            partial = analyze_structure(series(self.UP[:size]), pivot=3).events
            assert partial == [item for item in full if item.bar_index < size]


class TestOpenInterest:
    def test_totals_ratio_and_change(self):
        result = summarize_open_interest(
            [
                quote(kind=OptionKind.CALL, open_interest=100, open_interest_change=10),
                quote(kind=OptionKind.PUT, open_interest=300, open_interest_change=-40),
                quote(kind=OptionKind.PUT, open_interest=None, open_interest_change=None),
            ]
        )
        assert (result.calls, result.puts, result.put_call_ratio) == (100, 300, 3.0)
        assert (result.calls_change, result.puts_change) == (10, -40)

    def test_unknown_change_is_not_zero(self):
        result = summarize_open_interest([quote(kind=OptionKind.CALL, open_interest=100)])
        assert result.calls_change is None
        assert result.put_call_ratio == 0.0

    def test_no_calls_has_no_ratio(self):
        assert summarize_open_interest([quote(kind=OptionKind.PUT, open_interest=5)]).put_call_ratio is None
