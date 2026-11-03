"""Combina fontes em ordem: a seguinte só responde quando a anterior declara falta de dado."""

from datetime import date

from core.exceptions import DataInsufficientError
from core.types import CorporateEvent, MarketSnapshot, OptionChain, PriceBar
from data.providers.base import AtmIvSample, DataProvider


class SourceChain(DataProvider):
    def __init__(self, market: list[DataProvider], events: DataProvider, quotes: list[DataProvider] | None = None) -> None:
        if not market:
            raise ValueError("é preciso ao menos uma fonte de mercado")
        self._market = market
        self._events = events
        # A cotação pode ter fonte própria: é ela que mede quanto o ativo andou desde a grade.
        self._quotes = quotes or market

    def _first(self, call, sources: list[DataProvider] | None = None):
        failures: list[str] = []
        for source in sources or self._market:
            try:
                return call(source)
            except DataInsufficientError as error:
                failures.append(error.detail)
        raise DataInsufficientError(" | ".join(failures))

    def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        return self._first(lambda source: source.get_market_snapshot(symbol), self._quotes)

    def get_option_chain(self, underlying: str, expiry: date) -> OptionChain:
        return self._first(lambda source: source.get_option_chain(underlying, expiry))

    def get_expirations(self, underlying: str) -> list[date]:
        return self._first(lambda source: source.get_expirations(underlying))

    def get_historical_prices(self, symbol: str, lookback: str = "1y") -> list[PriceBar]:
        return self._first(lambda source: source.get_historical_prices(symbol, lookback))

    def _dated(self, call):
        """None só vale se todas as fontes responderam: falha de acesso não pode virar "sem dado",
        porque o cache guarda a ausência de um pregão para sempre."""
        failures: list[str] = []
        for source in self._market:
            try:
                found = call(source)
            except DataInsufficientError as error:
                failures.append(error.detail)
                continue
            if found is not None:
                return found
        if failures:
            raise DataInsufficientError(" | ".join(failures))
        return None

    def get_atm_iv_on(self, underlying: str, day: date) -> AtmIvSample | None:
        return self._dated(lambda source: source.get_atm_iv_on(underlying, day))

    def get_option_chain_on(self, underlying: str, expiry: date, day: date) -> OptionChain | None:
        return self._dated(lambda source: source.get_option_chain_on(underlying, expiry, day))

    def get_upcoming_events(self, symbol: str, today: date) -> list[CorporateEvent]:
        return self._events.get_upcoming_events(symbol, today)
