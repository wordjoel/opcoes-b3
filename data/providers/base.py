"""Contrato de qualquer fonte de mercado.

Devolve modelos tipados em vez de DataFrames ou dicts, para que a origem de cada
dado acompanhe o valor. Se a fonte não tiver a informação, deve levantar
DataInsufficientError em vez de preencher um valor.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from core.exceptions import DataInsufficientError
from core.types import CorporateEvent, MarketSnapshot, OptionChain, PriceBar


@dataclass(frozen=True)
class AtmIvSample:
    """Vol implícita no dinheiro em um pregão, com o vencimento usado na medida."""

    day: date
    iv: float
    expiry: date


class DataProvider(ABC):
    @abstractmethod
    def get_market_snapshot(self, symbol: str) -> MarketSnapshot: ...

    @abstractmethod
    def get_option_chain(self, underlying: str, expiry: date) -> OptionChain: ...

    @abstractmethod
    def get_expirations(self, underlying: str) -> list[date]: ...

    @abstractmethod
    def get_historical_prices(self, symbol: str, lookback: str = "1y") -> list[PriceBar]: ...

    @abstractmethod
    def get_atm_iv_on(self, underlying: str, day: date) -> AtmIvSample | None:
        """None = a fonte não tem dado suficiente nesse pregão. Erro de acesso levanta exceção."""

    @abstractmethod
    def get_upcoming_events(self, symbol: str, today: date) -> list[CorporateEvent]:
        """Resultados, proventos e eventos societários a partir de hoje, em ordem de data."""

    def get_option_chain_on(self, underlying: str, expiry: date, day: date) -> OptionChain | None:
        """Grade de um pregão passado. None = a fonte não tem esse pregão ou vencimento."""
        raise DataInsufficientError("esta fonte não oferece histórico de opções")
