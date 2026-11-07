"""Tempo de negociação. Datas de pregão e de vencimento são sempre as de São Paulo."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from core.calendario_b3 import next_trading_day

MARKET_TZ = ZoneInfo("America/Sao_Paulo")


def market_today(now: datetime) -> date:
    """Depois das 21h em São Paulo, a data em UTC já é a do dia seguinte: esta não."""
    return now.astimezone(MARKET_TZ).date()


def grid_still_current(market_date: date, now: datetime, open_hour: int = 10) -> bool:
    """True até a abertura do pregão seguinte, pelo calendário da B3: depois dela o preço pode ter mudado."""
    following = next_trading_day(market_date)
    opening = datetime(following.year, following.month, following.day, open_hour, tzinfo=MARKET_TZ)
    return now < opening
