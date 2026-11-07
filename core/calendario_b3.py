"""Calendário de pregões da B3.

Feriados por regra, sem lista baixada: os nacionais fixos, os móveis derivados da Páscoa
(Carnaval, Sexta-feira Santa, Corpus Christi) e os dias sem pregão de 24 e 31 de dezembro.

Feriados de São Paulo: até 2021 a B3 fechava em 25/01, 09/07 e 20/11. Desde 2022 abre
nesses dias, e desde 2024 o 20/11 é feriado nacional (Lei 14.759/2023).

Fechamentos extraordinários anunciados pela B3 não entram. Um pregão a mais ou a menos
aqui só muda prazos e janelas: dados de pregão vêm sempre dos arquivos, que são a verdade.
"""

from datetime import date, timedelta
from functools import lru_cache


def easter(year: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


@lru_cache(maxsize=64)
def holidays(year: int) -> frozenset[date]:
    """Dias úteis (segunda a sexta ou não) em que a B3 não abre."""
    pascoa = easter(year)
    days = {
        date(year, 1, 1),
        pascoa - timedelta(days=48),  # segunda de Carnaval
        pascoa - timedelta(days=47),  # terça de Carnaval
        pascoa - timedelta(days=2),  # Sexta-feira Santa
        date(year, 4, 21),
        date(year, 5, 1),
        pascoa + timedelta(days=60),  # Corpus Christi
        date(year, 9, 7),
        date(year, 10, 12),
        date(year, 11, 2),
        date(year, 11, 15),
        date(year, 12, 24),
        date(year, 12, 25),
        date(year, 12, 31),
    }
    if year <= 2021:
        days |= {date(year, 1, 25), date(year, 7, 9), date(year, 11, 20)}
    if year >= 2024:
        days.add(date(year, 11, 20))
    return frozenset(days)


def is_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day not in holidays(day.year)


def next_trading_day(day: date) -> date:
    """Primeiro pregão depois de `day`."""
    following = day + timedelta(days=1)
    while not is_trading_day(following):
        following += timedelta(days=1)
    return following


def previous_trading_day(day: date) -> date:
    """Último pregão antes de `day`."""
    before = day - timedelta(days=1)
    while not is_trading_day(before):
        before -= timedelta(days=1)
    return before


def add_trading_days(start: date, count: int) -> date:
    """O `count`-ésimo pregão depois de `start`. Com `count` 0, devolve `start`."""
    if count < 0:
        raise ValueError("count precisa ser zero ou positivo")
    day = start
    for _ in range(count):
        day = next_trading_day(day)
    return day


def trading_days_between(start: date, end: date) -> int:
    """Pregões depois de `start` até `end`, inclusive: os dias úteis (du) até o vencimento.
    Zero quando `end` não é posterior a `start`."""
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        if is_trading_day(day):
            count += 1
    return count


def monthly_option_expiry(year: int, month: int) -> date:
    """Vencimento mensal de opções de ações: terceira sexta-feira; se não houver pregão,
    o pregão anterior."""
    first = date(year, month, 1)
    third_friday = first + timedelta(days=(4 - first.weekday()) % 7 + 14)
    return third_friday if is_trading_day(third_friday) else previous_trading_day(third_friday)
