"""Conector da brapi (https://brapi.dev/docs).

Regras aprendidas com as respostas reais:
- A grade de opções é de fim de dia e o pregão do dia entra por volta das 21h.
- `regularMarketTime` não é o horário do último negócio, então a grade nunca usa a
  cotação corrente: o preço do ativo vem de `underlyingPrice`, do mesmo pregão.
- Bid e ask dessa grade são sobras após o fechamento, muitas vezes zeradas (em 03/11/2026,
  só 63 de 176 séries negociadas de PETR4 tinham os dois, com spread mediano de 77%).
  Zero significa "sem oferta". O preço que serve para análise é o fechamento.
- Sem token, as opções só respondem para PETR4. O token vai apenas no header.
"""

from calendar import FRIDAY, monthcalendar
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from statistics import median

import httpx

from core.exceptions import DataInsufficientError
from core.types import (
    CorporateEvent,
    ExerciseStyle,
    MarketSnapshot,
    OptionChain,
    OptionKind,
    OptionQuote,
    PriceBar,
    Provenance,
    SourceKind,
)
from data.normalizer import normalize_symbol
from data.providers.base import AtmIvSample, DataProvider

BASE_URL = "https://brapi.dev/api/v2"
SOURCE = "brapi"
# Fuso fixo: o Brasil não tem horário de verão desde 2019.
_BRT = timezone(timedelta(hours=-3))
_SESSION_CLOSE_HOUR = 18


# Vencimento mensal mais próximo a pelo menos esta distância, para evitar o gama do fim.
_MIN_DAYS_TO_EXPIRY = 20
# Distância do ativo e confiança aceitas na medida da vol no dinheiro.
_ATM_BAND = 0.05
_TRUSTED_CONFIDENCE = {"high", "medium"}
_MIN_ATM_VALUES = 2
_EVENTS_HORIZON_DAYS = 180


# Depois de um 429, não insiste: cada nova chamada só gastaria a cota.
_RATE_LIMIT_PAUSE_SECONDS = 60.0
_TIMEOUT_SECONDS = 10.0


def _guarded(method):
    """Resposta fora do formato esperado vira falta de dado declarada, nunca um valor parcial."""

    @wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except DataInsufficientError:
            raise
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
            raise DataInsufficientError(f"brapi com resposta inesperada ({type(error).__name__})") from None

    return wrapper


class _NotFound(DataInsufficientError):
    """A fonte respondeu 404: não há esse dado, o que é diferente de falta de acesso."""


def candidate_expiries(day: date) -> list[date]:
    """Terceira sexta do primeiro mês possível e a véspera, usada quando a sexta é feriado."""
    year, month = day.year, day.month
    while True:
        fridays = [week[FRIDAY] for week in monthcalendar(year, month) if week[FRIDAY]]
        third = date(year, month, fridays[2])
        if (third - day).days >= _MIN_DAYS_TO_EXPIRY:
            return [third, third - timedelta(days=1)]
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def _session_close(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, _SESSION_CLOSE_HOUR, tzinfo=_BRT)


class BrapiProvider(DataProvider):
    def __init__(
        self,
        token: str | None = None,
        client: httpx.Client | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._client = client or httpx.Client(timeout=_TIMEOUT_SECONDS)
        self._blocked_until = 0.0
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._now = now

    def _get(self, path: str, params: dict[str, str]) -> dict:
        if time.monotonic() < self._blocked_until:
            raise DataInsufficientError("limite de requisições da brapi atingido")
        response = None
        for attempt in range(2):
            try:
                response = self._client.get(f"{BASE_URL}{path}", params=params, headers=self._headers)
            except httpx.HTTPError as error:
                if attempt == 1:
                    raise DataInsufficientError(f"brapi inacessível ({type(error).__name__})") from None
                continue
            if response.status_code < 500:
                break
        assert response is not None
        if response.status_code == 401:
            raise DataInsufficientError("brapi recusou o acesso: token ausente ou inválido")
        if response.status_code == 403:
            raise DataInsufficientError("o plano da brapi não inclui este recurso")
        if response.status_code == 429:
            self._blocked_until = time.monotonic() + _RATE_LIMIT_PAUSE_SECONDS
            raise DataInsufficientError("limite de requisições da brapi atingido")
        if response.status_code == 404:
            raise _NotFound(f"brapi não encontrou {params}")
        if response.status_code != 200:
            raise DataInsufficientError(f"brapi respondeu {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("resposta sem objeto")
        return payload

    def _provenance(self, kind: SourceKind, market_time: datetime) -> Provenance:
        return Provenance(source=SOURCE, kind=kind, collected_at=self._now(), market_time=market_time)

    @_guarded
    def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        symbol = normalize_symbol(symbol)
        results = self._get("/stocks/quote", {"symbols": symbol}).get("results") or []
        data = results[0].get("data") if results else None
        if not data or not data.get("regularMarketPrice"):
            raise DataInsufficientError(f"brapi sem cotação para {symbol}")
        return MarketSnapshot(
            symbol=symbol,
            price=data["regularMarketPrice"],
            volume=data.get("regularMarketVolume"),
            name=data.get("longName") or data.get("shortName"),
            change_percent=data.get("regularMarketChangePercent"),
            provenance=self._provenance(
                SourceKind.DELAYED, datetime.fromisoformat(data["regularMarketTime"].replace("Z", "+00:00"))
            ),
        )

    @_guarded
    def get_expirations(self, underlying: str) -> list[date]:
        payload = self._get("/options/expirations", {"underlying": normalize_symbol(underlying)})
        return [date.fromisoformat(day) for day in payload.get("expirations", [])]

    @_guarded
    def get_option_chain(self, underlying: str, expiry: date) -> OptionChain:
        symbol = normalize_symbol(underlying)
        params = {"underlying": symbol, "expirationDate": expiry.isoformat()}
        chain = self._get("/options/chain", params)
        analytics = self._get("/options/analytics", params)
        series = chain.get("series") or []
        rows = analytics.get("analytics") or []
        if not series or not rows or not chain.get("date"):
            raise DataInsufficientError(f"brapi sem grade para {symbol} em {expiry}")
        if analytics.get("date") != chain["date"]:
            # Misturar pregões daria gregas de um dia sobre preços de outro.
            raise DataInsufficientError(f"grade de {chain['date']} e gregas de {analytics.get('date')}")

        market_date = date.fromisoformat(chain["date"])
        spots = {row["underlyingPrice"] for row in rows if row.get("underlyingPrice")}
        rates = {row["riskFreeRate"] for row in rows if row.get("riskFreeRate") is not None}
        times = {row["timeToExpirationYears"] for row in rows if row.get("timeToExpirationYears")}
        if len(spots) != 1 or len(rates) != 1 or len(times) != 1:
            raise DataInsufficientError(f"brapi com parâmetros divergentes para {symbol} em {expiry}")

        provenance = self._provenance(SourceKind.EOD, _session_close(market_date))
        by_symbol = {row["symbol"]: row for row in rows}
        return OptionChain(
            underlying=MarketSnapshot(symbol=symbol, price=spots.pop(), provenance=provenance),
            quotes=[self._quote(item, by_symbol.get(item["symbol"], {}), symbol, provenance) for item in series],
            market_date=market_date,
            risk_free_rate=rates.pop(),
            time_to_expiry_years=times.pop(),
        )

    @staticmethod
    def _quote(item: dict, greeks: dict, underlying: str, provenance: Provenance) -> OptionQuote:
        last_trade = item.get("lastTradeDate")
        style = {"european": ExerciseStyle.EUROPEAN, "american": ExerciseStyle.AMERICAN}.get(item.get("optionStyle"))
        return OptionQuote(
            symbol=item["symbol"],
            underlying=underlying,
            kind=OptionKind.CALL if item["side"] == "call" else OptionKind.PUT,
            strike=item["strike"],
            expiry=date.fromisoformat(item["expirationDate"]),
            style=style,
            bid=item.get("bid"),
            ask=item.get("ask"),
            open_interest=item.get("openInterest"),
            volume=item.get("volume"),
            trades=item.get("trades"),
            open_interest_change=item.get("openInterestChange"),
            close=item.get("close"),
            last_trade_date=date.fromisoformat(last_trade) if last_trade else None,
            iv=greeks.get("impliedVolatility"),
            delta=greeks.get("delta"),
            provenance=provenance,
        )

    @_guarded
    def get_upcoming_events(self, symbol: str, today: date) -> list[CorporateEvent]:
        symbol = normalize_symbol(symbol)
        events: list[CorporateEvent] = []
        limit = today + timedelta(days=_EVENTS_HORIZON_DAYS)
        try:
            earnings = self._get(
                "/stocks/earnings-calendar", {"symbols": symbol, "from": today.isoformat(), "to": limit.isoformat()}
            )
        except _NotFound:
            earnings = {}
        for item in earnings.get("results") or []:
            if item.get("status") == "scheduled" and item.get("date"):
                events.append(
                    CorporateEvent(
                        kind="RESULTADO",
                        day=date.fromisoformat(item["date"][:10]),
                        label=f"Resultado {item.get('fiscalPeriod')}/{item.get('fiscalYear')}",
                        confirmed=item.get("dateStatus") == "confirmed",
                    )
                )
        try:
            dividends = self._get("/stocks/dividends", {"symbols": symbol})
        except _NotFound:
            dividends = {}
        results = dividends.get("results") or []
        data = (results[0].get("data") or {}) if results else {}
        groups = (("PROVENTO", data.get("cashDividends")), ("EVENTO_SOCIETARIO", data.get("stockDividends")))
        for kind, items in groups:
            for item in items or []:
                moment = item.get("exDate") or item.get("lastDatePrior")
                if moment:
                    day = datetime.fromisoformat(moment.replace("Z", "+00:00")).astimezone(_BRT).date()
                    if today <= day <= limit:
                        confirmed = item.get("verified", True) is not False
                        events.append(CorporateEvent(kind=kind, day=day, label=item.get("label") or kind, confirmed=confirmed))
        return sorted(events, key=lambda event: event.day)

    @_guarded
    def get_atm_iv_on(self, underlying: str, day: date) -> AtmIvSample | None:
        """Mediana das vols perto do ativo. Em datas passadas, lastTradeDate é o último negócio
        geral da série, não o daquele dia: por isso o filtro é pela confiança da própria fonte."""
        symbol = normalize_symbol(underlying)
        for expiry in candidate_expiries(day):
            try:
                payload = self._get(
                    "/options/analytics",
                    {"underlying": symbol, "expirationDate": expiry.isoformat(), "date": day.isoformat()},
                )
            except _NotFound:
                continue
            # Em feriado, a fonte devolve o pregão anterior sem avisar.
            if payload.get("date") != day.isoformat():
                return None
            values = [
                row["impliedVolatility"]
                for row in payload.get("analytics") or []
                if row.get("impliedVolatility")
                and row.get("confidence") in _TRUSTED_CONFIDENCE
                and row.get("underlyingPrice")
                and abs(row["strike"] / row["underlyingPrice"] - 1) <= _ATM_BAND
            ]
            return AtmIvSample(day, median(values), expiry) if len(values) >= _MIN_ATM_VALUES else None
        return None

    @_guarded
    def get_historical_prices(self, symbol: str, lookback: str = "1y") -> list[PriceBar]:
        symbol = normalize_symbol(symbol)
        params = {"symbols": symbol, "range": lookback, "interval": "1d"}
        results = self._get("/stocks/historical", params).get("results") or []
        points = (results[0].get("data") or {}).get("historicalDataPrice") if results else None
        if not points:
            raise DataInsufficientError(f"brapi sem histórico para {symbol}")
        bars = []
        for point in sorted(points, key=lambda item: item["date"]):
            close, adjusted = point.get("close"), point.get("adjustedClose")
            if not close or not adjusted or not point.get("open") or not point.get("high") or not point.get("low"):
                continue
            # Ajusta o OHLC inteiro: só o fechamento ajustado deixaria a barra incoerente.
            factor = adjusted / close
            moment = datetime.fromtimestamp(point["date"], _BRT)
            bars.append(
                PriceBar(
                    symbol=symbol,
                    day=moment.date(),
                    open=point["open"] * factor,
                    high=point["high"] * factor,
                    low=point["low"] * factor,
                    close=adjusted,
                    volume=point.get("volume"),
                    adjusted=True,
                    provenance=self._provenance(SourceKind.EOD, _session_close(moment.date())),
                )
            )
        return bars
