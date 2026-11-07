from datetime import date

import pytest

from core.types import LegAction, OptionKind, OptionLeg
from quant.costs import CostSchedule, net_of_costs, premium_notional, round_trip_cost

EXPIRY = date(2026, 12, 18)


def leg(action, premium, strike=30.0, kind=OptionKind.CALL):
    return OptionLeg(symbol=f"X{strike}", kind=kind, action=action, strike=strike, expiry=EXPIRY, premium=premium, quantity=100)


SPREAD = [leg(LegAction.BUY, 1.20, 30.0), leg(LegAction.SELL, 0.40, 32.0)]


def test_notional_ignores_direction():
    assert premium_notional(SPREAD) == pytest.approx(160.0)


def test_round_trip_counts_orders_once_and_fees_per_lot():
    schedule = CostSchedule(per_order_brl=2.5, fee_pct=0.1, income_tax_pct=15)
    # 4 ordens de R$ 2,50 + 0,1% de R$ 160 x 3 lotes nas duas pontas.
    assert round_trip_cost(SPREAD, schedule, lots=3) == pytest.approx(10.0 + 0.96)


def test_zero_schedule_costs_nothing():
    assert round_trip_cost(SPREAD, CostSchedule(0, 0, 0)) == 0


def test_net_taxes_only_gains():
    schedule = CostSchedule(0, 0, 15)
    assert net_of_costs(100.0, 20.0, schedule) == pytest.approx(68.0)
    assert net_of_costs(10.0, 20.0, schedule) == pytest.approx(-10.0)
    assert net_of_costs(None, 20.0, schedule) is None


@pytest.mark.parametrize("args", [(-1, 0, 0), (0, 6, 0), (0, 0, 101)])
def test_invalid_schedule(args):
    with pytest.raises(ValueError):
        CostSchedule(*args)


def test_invalid_lots():
    with pytest.raises(ValueError):
        round_trip_cost(SPREAD, CostSchedule(0, 0, 0), lots=0)
