"""Tempo de negociação. Datas de pregão e de vencimento são sempre as de São Paulo."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/Sao_Paulo")


def market_today(now: datetime) -> date:
    """Depois das 21h em São Paulo, a data em UTC já é a do dia seguinte: esta não."""
    return now.astimezone(MARKET_TZ).date()
