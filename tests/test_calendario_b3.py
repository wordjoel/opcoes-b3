from datetime import date, timedelta

import pytest

from core.calendario_b3 import (
    add_trading_days,
    easter,
    holidays,
    is_trading_day,
    monthly_option_expiry,
    next_trading_day,
    previous_trading_day,
    trading_days_between,
)


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))],
)
def test_easter(year, expected):
    assert easter(year) == expected


def test_holidays_2026():
    # Calendário divulgado pela B3 para 2026.
    expected = {
        date(2026, 1, 1),
        date(2026, 2, 16),
        date(2026, 2, 17),
        date(2026, 4, 3),
        date(2026, 4, 21),
        date(2026, 5, 1),
        date(2026, 6, 4),
        date(2026, 9, 7),
        date(2026, 10, 12),
        date(2026, 11, 2),
        date(2026, 11, 15),
        date(2026, 11, 20),
        date(2026, 12, 24),
        date(2026, 12, 25),
        date(2026, 12, 31),
    }
    assert holidays(2026) == expected


def test_sao_paulo_dates_by_era():
    assert not is_trading_day(date(2021, 1, 25))
    assert is_trading_day(date(2023, 1, 25))
    assert is_trading_day(date(2023, 11, 20))
    assert not is_trading_day(date(2024, 11, 20))


def test_ash_wednesday_is_a_session():
    assert is_trading_day(date(2026, 2, 18))


def test_next_and_previous_skip_holidays_and_weekends():
    assert next_trading_day(date(2026, 10, 30)) == date(2026, 11, 3)
    assert previous_trading_day(date(2026, 11, 3)) == date(2026, 10, 30)


def test_add_trading_days():
    assert add_trading_days(date(2026, 10, 30), 0) == date(2026, 10, 30)
    assert add_trading_days(date(2026, 10, 30), 1) == date(2026, 11, 3)
    assert add_trading_days(date(2026, 11, 13), 5) == date(2026, 11, 23)
    with pytest.raises(ValueError):
        add_trading_days(date(2026, 1, 2), -1)


def test_trading_days_between():
    assert trading_days_between(date(2026, 11, 13), date(2026, 11, 19)) == 4
    assert trading_days_between(date(2026, 11, 19), date(2026, 11, 13)) == 0
    assert trading_days_between(date(2026, 1, 1), date(2026, 12, 31)) == 247


def test_monthly_expiry():
    assert monthly_option_expiry(2026, 10) == date(2026, 10, 16)
    assert monthly_option_expiry(2026, 11) == date(2026, 11, 19)
    # Terceira sexta de abril de 2025 é 18/04, Sexta-feira Santa.
    assert monthly_option_expiry(2025, 4) == date(2025, 4, 17)


def test_near_expiry_warning_counts_sessions():
    from quant.risk import assess_risk
    from tests.test_capital_american import SPOT, candidate

    item = candidate("long_call")
    expiry = item.proposal.legs[0].expiry
    near = assess_risk(item.proposal, item.quotes, SPOT, 0.12, 0.1375, 0.0, use_book=False,
                       today=previous_trading_day(previous_trading_day(expiry)))
    far = assess_risk(item.proposal, item.quotes, SPOT, 0.12, 0.1375, 0.0, use_book=False,
                      today=expiry - timedelta(days=30))
    assert any("pregões até o vencimento" in text for text in near.warnings)
    assert not any("pregões até o vencimento" in text for text in far.warnings)
