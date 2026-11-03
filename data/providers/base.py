"""Contrato de qualquer fonte de mercado.

Devolve modelos tipados em vez de DataFrames ou dicts, para que a origem de cada
dado acompanhe o valor. Se a fonte não tiver a informação, deve levantar
DataInsufficientError em vez de preencher um valor.
"""

from abc import ABC, abstractmethod
from datetime import date

from core.types import MarketSnapshot, OptionChain, PriceBar


class DataProvider(ABC):
    @abstractmethod
    def get_market_snapshot(self, symbol: str) -> MarketSnapshot: ...

    @abstractmethod
    def get_option_chain(self, underlying: str, expiry: date) -> OptionChain: ...

    @abstractmethod
    def get_expirations(self, underlying: str) -> list[date]: ...

    @abstractmethod
    def get_historical_prices(self, symbol: str, lookback: str = "1y") -> list[PriceBar]: ...
