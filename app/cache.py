"""Guarda as respostas da fonte no banco, para poupar a cota do plano da brapi.

A procedência original fica dentro do payload, então um dado em cache continua com o
horário real de mercado e passa pelos mesmos validadores de idade. Erros não são guardados.
"""

import json
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

from pydantic import TypeAdapter

from core.types import CorporateEvent, MarketSnapshot, OptionChain, PriceBar
from data.providers.base import AtmIvSample, DataProvider
from db.client import Database

_SNAPSHOT_TTL = timedelta(minutes=5)
# A grade do pregão entra por volta das 21h: uma hora limita o atraso em vê-la.
_CHAIN_TTL = timedelta(hours=1)
_EXPIRATIONS_TTL = timedelta(hours=6)
_HISTORY_TTL = timedelta(hours=6)

_BARS = TypeAdapter(list[PriceBar])
_EVENTS = TypeAdapter(list[CorporateEvent])
_DATES = TypeAdapter(list[date])


class CachingProvider(DataProvider):
    def __init__(
        self,
        inner: DataProvider,
        database: Database,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._inner = inner
        self._database = database
        self._now = now

    def _read(self, key: str, ttl: timedelta) -> str | None:
        rows = self._database.fetch("SELECT payload, fetched_at FROM provider_cache WHERE key = ?", (key,))
        if not rows or self._now() - datetime.fromisoformat(rows[0][1]) > ttl:
            return None
        return rows[0][0]

    def _load(self, key: str, ttl: timedelta, parse):
        """Entrada que o formato atual não entende vale como ausente: busca de novo, sem erro 500."""
        try:
            cached = self._read(key, ttl)
            return parse(cached) if cached else None
        except ValueError:
            return None

    def _write(self, key: str, payload: str) -> None:
        self._database.run(
            "INSERT INTO provider_cache (key, payload, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT (key) DO UPDATE SET payload = excluded.payload, fetched_at = excluded.fetched_at",
            (key, payload, self._now().isoformat()),
        )

    def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        key = f"snapshot:{symbol}"
        cached = self._load(key, _SNAPSHOT_TTL, MarketSnapshot.model_validate_json)
        if cached:
            return cached
        fresh = self._inner.get_market_snapshot(symbol)
        self._write(key, fresh.model_dump_json())
        return fresh

    def get_option_chain(self, underlying: str, expiry: date) -> OptionChain:
        key = f"chain:{underlying}:{expiry.isoformat()}"
        cached = self._load(key, _CHAIN_TTL, OptionChain.model_validate_json)
        if cached:
            return cached
        fresh = self._inner.get_option_chain(underlying, expiry)
        self._write(key, fresh.model_dump_json())
        return fresh

    def get_expirations(self, underlying: str) -> list[date]:
        key = f"expirations:{underlying}"
        cached = self._load(key, _EXPIRATIONS_TTL, _DATES.validate_json)
        if cached:
            return cached
        fresh = self._inner.get_expirations(underlying)
        self._write(key, json.dumps([day.isoformat() for day in fresh]))
        return fresh

    def get_historical_prices(self, symbol: str, lookback: str = "1y") -> list[PriceBar]:
        key = f"history:{symbol}:{lookback}"
        cached = self._load(key, _HISTORY_TTL, _BARS.validate_json)
        if cached:
            return cached
        fresh = self._inner.get_historical_prices(symbol, lookback)
        self._write(key, _BARS.dump_json(fresh).decode())
        return fresh

    def get_atm_iv_on(self, underlying: str, day: date) -> AtmIvSample | None:
        rows = self._database.fetch(
            "SELECT iv, expiry FROM iv_history WHERE symbol = ? AND day = ?", (underlying, day.isoformat())
        )
        if rows:
            iv, expiry = rows[0]
            return None if iv is None else AtmIvSample(day, iv, date.fromisoformat(expiry))
        fresh = self._inner.get_atm_iv_on(underlying, day)
        self._database.run(
            "INSERT INTO iv_history (symbol, day, iv, expiry, fetched_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (symbol, day) DO NOTHING",
            (
                underlying,
                day.isoformat(),
                fresh.iv if fresh else None,
                fresh.expiry.isoformat() if fresh else None,
                self._now().isoformat(),
            ),
        )
        return fresh

    def get_upcoming_events(self, symbol: str, today: date) -> list[CorporateEvent]:
        key = f"events:{symbol}:{today.isoformat()}"
        # Lista vazia também é resposta válida da fonte.
        cached = self._load(key, _HISTORY_TTL, _EVENTS.validate_json)
        if cached is not None:
            return cached
        fresh = self._inner.get_upcoming_events(symbol, today)
        self._write(key, _EVENTS.dump_json(fresh).decode())
        # A chave leva a data: sem isto, cada dia deixaria uma linha para sempre.
        self._database.run(
            "DELETE FROM provider_cache WHERE key LIKE ? AND key <> ?", (f"events:{symbol}:%", key)
        )
        return fresh
