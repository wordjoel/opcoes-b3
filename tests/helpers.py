"""Dados de teste. Todos marcados como SourceKind.TEST, que a validação recusa por padrão."""

from datetime import date, datetime, timedelta, timezone

from core.types import (
    LegAction,
    MarketSnapshot,
    OptionChain,
    OptionKind,
    OptionLeg,
    OptionQuote,
    Provenance,
    SourceKind,
)

NOW = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)
EXPIRY = date(2026, 12, 18)


def provenance(age_seconds: float = 0, source: str = "fixture", kind: SourceKind = SourceKind.TEST) -> Provenance:
    moment = NOW - timedelta(seconds=age_seconds)
    return Provenance(source=source, kind=kind, collected_at=NOW, market_time=moment)


def snapshot(price: float = 40.0, age_seconds: float = 0, source: str = "fixture") -> MarketSnapshot:
    return MarketSnapshot(symbol="TEST4", price=price, provenance=provenance(age_seconds, source))


def quote(strike: float = 40.0, bid: float | None = 1.0, ask: float | None = 1.1, age_seconds: float = 0, **changes) -> OptionQuote:
    values = dict(
        symbol=f"TESTL{int(strike * 10)}",
        underlying="TEST4",
        kind=OptionKind.CALL,
        strike=strike,
        expiry=EXPIRY,
        bid=bid,
        ask=ask,
        provenance=provenance(age_seconds),
    )
    return OptionQuote(**{**values, **changes})


def chain(*quotes: OptionQuote, spot: MarketSnapshot | None = None) -> OptionChain:
    return OptionChain(underlying=spot or snapshot(), quotes=list(quotes))


def leg(action: str, kind: str, strike: float, premium: float, quantity: int = 100, expiry: date = EXPIRY) -> OptionLeg:
    return OptionLeg(
        symbol=f"TEST{kind[0]}{int(strike)}",
        strike=strike,
        expiry=expiry,
        kind=OptionKind(kind),
        action=LegAction(action),
        quantity=quantity,
        premium=premium,
    )
