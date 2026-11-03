from datetime import date, timedelta

import pytest

from core.exceptions import DataInsufficientError
from core.types import ExerciseStyle, LegAction, MarketRegime, OptionKind, PriceBar
from data.validators import validate_bars, validate_chain
from quant.greeks import position_greeks
from quant.payoff import net_premium, payoff_curve, position_pnl
from quant.regime import classify_regime
from quant.risk import RiskLimits, assess_risk, leg_liquidity, position_pop
from quant.strategies import STRUCTURES, PriceBasis, build_candidates, execution_price, fits_regime
from tests.helpers import EXPIRY, NOW, chain, leg, provenance, quote, snapshot

SPOT = 40.0


def full_grid(**changes):
    """Calls e puts de 2 em 2 reais em torno do ativo, com preço só de fechamento."""
    quotes = []
    for strike in range(30, 52, 2):
        for kind, prefix in ((OptionKind.CALL, "C"), (OptionKind.PUT, "P")):
            intrinsic = max(SPOT - strike, 0) if kind is OptionKind.CALL else max(strike - SPOT, 0)
            values = dict(
                symbol=f"TEST{prefix}{strike}",
                kind=kind,
                strike=float(strike),
                bid=None,
                ask=None,
                close=intrinsic + 1.0,
                open_interest=2_000_000,
                volume=200_000,
                trades=200,
                iv=0.3,
            )
            quotes.append(quote(**{**values, **changes}))
    return quotes


def candidates_by_key(quotes=None):
    built, unavailable = build_candidates(quotes if quotes is not None else full_grid(), SPOT)
    return {item.key: item for item in built}, unavailable


class TestBuilder:
    def test_full_grid_builds_all_eleven(self):
        built, unavailable = candidates_by_key()
        assert len(STRUCTURES) == 11
        assert set(built) == {structure.key for structure in STRUCTURES}
        assert unavailable == []

    def test_bull_call_spread_shape_and_numbers(self):
        spread = candidates_by_key()[0]["bull_call_spread"].proposal
        buy, sell = spread.legs
        assert (buy.action, buy.strike, sell.action, sell.strike) == (LegAction.BUY, 40.0, LegAction.SELL, 42.0)
        # Débito de 1,00 por opção e largura de 2,00, em 100 opções.
        assert net_premium(spread.legs) == pytest.approx(0.0)
        assert spread.max_loss == pytest.approx(0.0)

    def test_iron_condor_strikes_are_ordered(self):
        legs = candidates_by_key()[0]["iron_condor"].proposal.legs
        assert [item.strike for item in legs] == [36.0, 38.0, 42.0, 44.0]
        assert [item.action for item in legs] == [LegAction.BUY, LegAction.SELL, LegAction.SELL, LegAction.BUY]

    def test_butterfly_doubles_the_center(self):
        legs = candidates_by_key()[0]["call_butterfly"].proposal.legs
        assert [item.quantity for item in legs] == [100, 200, 100]

    def test_missing_strike_is_reported_not_substituted(self):
        grid = [item for item in full_grid() if item.strike < 40]
        built, unavailable = candidates_by_key(grid)
        reasons = {item.key: item.reason for item in unavailable}
        assert "bear_call_spread" in reasons and "bear_call_spread" not in built
        assert "long_call" in reasons

    def test_straddle_refuses_different_center_strikes(self):
        # Com o ativo em 41, sem a call 40, a call central cai em 42 e a put, em 40.
        grid = [item for item in full_grid() if not (item.kind is OptionKind.CALL and item.strike == 40)]
        built, unavailable = build_candidates(grid, 41.0)
        assert "long_straddle" not in {item.key for item in built}
        assert any(item.key == "long_straddle" and "strikes diferentes" in item.reason for item in unavailable)

    def test_refuses_two_expiries(self):
        with pytest.raises(ValueError):
            build_candidates([quote(strike=40.0), quote(strike=42.0, expiry=date(2027, 1, 15))], SPOT)

    def test_execution_uses_unfavorable_side_of_book(self):
        item = quote(bid=1.0, ask=1.2, close=1.1)
        assert execution_price(item, LegAction.BUY) == (1.2, PriceBasis.BOOK)
        assert execution_price(item, LegAction.SELL) == (1.0, PriceBasis.BOOK)

    def test_execution_falls_back_to_close_and_says_so(self):
        item = quote(bid=None, ask=0.0, close=1.1)
        assert execution_price(item, LegAction.BUY) == (1.1, PriceBasis.CLOSE)
        spread = candidates_by_key()[0]["long_call"]
        assert spread.bases == (PriceBasis.CLOSE,)
        assert any("indicativos" in text for text in spread.proposal.assumptions)

    def test_end_of_day_ignores_leftover_book(self):
        item = quote(bid=0.25, ask=18.5, close=6.77)
        assert execution_price(item, LegAction.BUY, use_book=False) == (6.77, PriceBasis.CLOSE)

    def test_execution_without_any_price_raises(self):
        with pytest.raises(ValueError):
            execution_price(quote(bid=None, ask=None, close=None), LegAction.BUY)


class TestRegimeFit:
    def test_long_vol_needs_cheap_iv(self):
        assert fits_regime("long_straddle", MarketRegime.BULL, 0.7)
        assert not fits_regime("long_straddle", MarketRegime.HIGH_VOL, 1.5)
        assert not fits_regime("long_straddle", None, None)

    def test_condor_fits_expensive_vol_and_sideways(self):
        assert fits_regime("iron_condor", MarketRegime.HIGH_VOL, 1.5)
        assert fits_regime("iron_condor", MarketRegime.SIDEWAYS, None)
        assert not fits_regime("iron_condor", MarketRegime.BULL, None)

    def test_classify(self):
        rising = [100 + index for index in range(60)]
        assert classify_regime(rising) is MarketRegime.BULL
        assert classify_regime(list(reversed(rising))) is MarketRegime.BEAR
        assert classify_regime([100.0] * 60) is MarketRegime.SIDEWAYS
        assert classify_regime([100.0] * 60, iv_ratio=1.4) is MarketRegime.HIGH_VOL

    def test_short_series_is_insufficient(self):
        with pytest.raises(DataInsufficientError):
            classify_regime([100.0] * 49)


class TestRisk:
    def assess(self, proposal_quotes=None, key="long_call", drift=0.0, limits=RiskLimits()):
        candidate = candidates_by_key(proposal_quotes)[0][key]
        return assess_risk(candidate.proposal, candidate.quotes, SPOT, 0.12, 0.1375, drift, limits)

    def test_liquid_long_call_is_approved(self):
        result = self.assess()
        assert result.is_approved
        assert result.liquidity_score == pytest.approx(1.0)
        assert "Ativo -20% no vencimento" in result.stress_test_results
        assert "Vol +10 pontos hoje" in result.stress_test_results

    def test_stress_at_expiry_matches_payoff(self):
        # Call 40 comprada a 1,00: com o ativo em 48, ganha 8 - 1 por opção.
        assert self.assess().stress_test_results["Ativo +20% no vencimento"] == pytest.approx(700.0)

    def test_spot_drift_rejects(self):
        result = self.assess(drift=-0.0546)
        assert not result.is_approved
        assert "-5,5%" in result.rejection_reason and "defasados" in result.rejection_reason

    def test_unmeasured_drift_only_warns(self):
        result = self.assess(drift=None)
        assert result.is_approved
        assert any("comparar" in text for text in result.warnings)

    def test_illiquid_rejects(self):
        result = self.assess(full_grid(open_interest=5, volume=1, trades=1))
        assert not result.is_approved
        assert "liquidez" in result.rejection_reason

    def test_unmeasured_liquidity_is_not_approved(self):
        result = self.assess(full_grid(open_interest=None))
        assert not result.is_approved
        assert result.liquidity_score is None
        assert "não medida" in result.rejection_reason

    def test_zero_loss_from_unsynced_closes_rejects(self):
        # Na grade de teste, comprar e vender a 1,00 zera a perda: preço suspeito.
        result = self.assess(key="bull_call_spread")
        assert not result.is_approved
        assert "sincronizados" in result.rejection_reason

    def test_wide_spread_reduces_liquidity(self):
        depth = dict(open_interest=2_000_000, volume=200_000, trades=200)
        assert leg_liquidity(quote(bid=1.0, ask=1.5, **depth)) == 0.0
        assert leg_liquidity(quote(bid=1.0, ask=1.02, **depth)) > 0.9

    def test_end_of_day_leftover_book_does_not_affect_liquidity(self):
        # Caso real: PETRL497, muito negociada, com sobra de ofertas de 0,25 x 18,50.
        real = quote(bid=0.25, ask=18.5, open_interest=266_700, volume=607_600, trades=162)
        assert leg_liquidity(real) == 0.0
        assert leg_liquidity(real, use_book=False) > 0.7

    def test_thinly_traded_series_stays_below_minimum(self):
        # Caso real: PETRK498, com um único negócio em 30/10.
        thin = quote(open_interest=600, volume=600, trades=1)
        assert leg_liquidity(thin, use_book=False) < RiskLimits().min_liquidity

    def test_american_short_leg_warns(self):
        grid = full_grid(style=ExerciseStyle.AMERICAN)
        result = self.assess(grid, key="bear_call_spread")
        assert any("americanas" in text for text in result.warnings)

    def test_missing_iv_skips_vol_shock_and_warns(self):
        result = self.assess(full_grid(iv=None))
        assert "Vol +10 pontos hoje" not in result.stress_test_results
        assert any("volatilidade implícita" in text for text in result.warnings)

    def test_pop_needs_every_iv(self):
        legs = [leg("BUY", "CALL", 40.0, 1.0)]
        assert position_pop(legs, [None], SPOT, 0.1, 0.1) is None
        assert 0 < position_pop(legs, [0.3], SPOT, 0.1, 0.1) < 1


class TestPositionMath:
    def test_position_greeks_cancel_on_opposite_legs(self):
        legs = [leg("BUY", "CALL", 40.0, 1.0), leg("SELL", "CALL", 40.0, 1.0)]
        greeks = position_greeks(legs, [0.3, 0.3], SPOT, 0.1, 0.1)
        assert greeks.delta == pytest.approx(0.0)
        assert greeks.vega_per_vol_point == pytest.approx(0.0)

    def test_position_greeks_none_without_iv(self):
        assert position_greeks([leg("BUY", "CALL", 40.0, 1.0)], [None], SPOT, 0.1, 0.1) is None

    def test_payoff_curve_includes_strikes_and_matches_pnl(self):
        legs = [leg("BUY", "CALL", 41.37, 1.0)]
        curve = dict(payoff_curve(legs, SPOT))
        assert 41.37 in curve
        assert curve[41.37] == pytest.approx(float(position_pnl(legs, 41.37)))
        assert list(curve) == sorted(curve)


class TestLargeJump:
    def bars(self, *closes):
        return [
            PriceBar(
                symbol="TEST4",
                day=date(2026, 10, 1) + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                adjusted=True,
                provenance=provenance(),
            )
            for index, close in enumerate(closes)
        ]

    def test_real_case_warns_without_rejecting_the_series(self):
        # Caso real da brapi: MGLU3 em 26/10/2026.
        report = validate_bars(self.bars(12.69, 5.30))
        assert report.is_valid
        assert "LARGE_JUMP" in report.codes
        detail = next(issue.detail for issue in report.issues if issue.code == "LARGE_JUMP")
        assert "fechamento de 12,69 para 5,30 (-58%) em um pregão. Confira" in detail

    def test_normal_move_does_not_warn(self):
        assert "LARGE_JUMP" not in validate_bars(self.bars(58.68, 53.88)).codes


class TestCloseOnlyValidation:
    def eod_chain(self, *quotes):
        base = chain(*quotes)
        return base.model_copy(update={"market_date": NOW.date()})

    def traded(self, **changes):
        return quote(bid=0.0, ask=0.0, close=1.1, last_trade_date=NOW.date(), **changes)

    def test_eod_quote_with_close_is_usable_with_notice(self):
        report = validate_chain(self.eod_chain(self.traded()), NOW, allow_test=True)
        assert len(report.usable_quotes) == 1
        assert "CLOSE_ONLY" in report.codes

    def test_eod_without_close_is_excluded(self):
        item = quote(bid=0.0, ask=0.0, close=None, last_trade_date=NOW.date())
        report = validate_chain(self.eod_chain(item), NOW, allow_test=True)
        assert report.usable_quotes == ()
        assert "MISSING_QUOTE" in report.codes

    def test_untraded_is_still_excluded(self):
        item = quote(bid=0.0, ask=0.0, close=1.1, last_trade_date=date(2026, 10, 1))
        report = validate_chain(self.eod_chain(item), NOW, allow_test=True)
        assert report.usable_quotes == ()
        assert "NOT_TRADED" in report.codes

    def test_close_above_spot_is_outlier(self):
        item = quote(bid=0.0, ask=0.0, close=50.0, last_trade_date=NOW.date())
        report = validate_chain(self.eod_chain(item), NOW, allow_test=True)
        assert "PRICE_OUTLIER" in report.codes

    def test_eod_leftover_book_does_not_exclude(self):
        crossed = quote(bid=5.0, ask=1.0, close=1.1, last_trade_date=NOW.date())
        wide = quote(strike=42.0, bid=0.25, ask=18.5, close=1.1, last_trade_date=NOW.date())
        report = validate_chain(self.eod_chain(crossed, wide), NOW, allow_test=True)
        assert len(report.usable_quotes) == 2

    def test_chain_without_market_date_still_needs_book(self):
        item = quote(bid=0.0, ask=0.0, close=1.1)
        report = validate_chain(chain(item), NOW, allow_test=True)
        assert report.usable_quotes == ()
