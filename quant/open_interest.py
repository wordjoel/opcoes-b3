"""Contratos em aberto de um vencimento.

Mostra quanto mudou, não quem mudou: a variação não informa quem abriu ou fechou posição,
então conclusões como "squeeze" ou "a massa está presa" não saem destes números.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from core.types import OptionKind, OptionQuote


@dataclass(frozen=True)
class OpenInterestSummary:
    calls: int
    puts: int
    # Puts por call. None sem calls em aberto.
    put_call_ratio: float | None
    # None se a fonte não informou a variação de nenhuma série.
    calls_change: int | None
    puts_change: int | None


def _change(quotes: list[OptionQuote]) -> int | None:
    known = [quote.open_interest_change for quote in quotes if quote.open_interest_change is not None]
    return sum(known) if known else None


def summarize_open_interest(quotes: Sequence[OptionQuote]) -> OpenInterestSummary:
    calls = [quote for quote in quotes if quote.kind is OptionKind.CALL]
    puts = [quote for quote in quotes if quote.kind is OptionKind.PUT]
    call_total = sum(quote.open_interest or 0 for quote in calls)
    put_total = sum(quote.open_interest or 0 for quote in puts)
    return OpenInterestSummary(
        calls=call_total,
        puts=put_total,
        put_call_ratio=put_total / call_total if call_total else None,
        calls_change=_change(calls),
        puts_change=_change(puts),
    )
