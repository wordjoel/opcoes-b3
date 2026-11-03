"""Tempo de negociação. Datas de pregão e de vencimento são sempre as de São Paulo."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/Sao_Paulo")


def market_today(now: datetime) -> date:
    """Depois das 21h em São Paulo, a data em UTC já é a do dia seguinte: esta não."""
    return now.astimezone(MARKET_TZ).date()


def grid_still_current(market_date: date, now: datetime, open_hour: int = 10) -> bool:
    """True até a abertura do dia útil seguinte ao pregão: depois dela o preço pode ter mudado.
    Sem calendário de feriados, um feriado encurta a janela, o que erra para o lado seguro."""
    following = market_date + timedelta(days=1)
    while following.weekday() >= 5:
        following += timedelta(days=1)
    opening = datetime(following.year, following.month, following.day, open_hour, tzinfo=MARKET_TZ)
    return now < opening
