"""Proventos e eventos em ações publicados pela B3, para ajustar o histórico do COTAHIST.

Fonte: a página de empresas listadas da B3 (gratuita, sem chave). Cada empresa é consultada
pelo código de emissor, os quatro primeiros caracteres do ticker, e os eventos são filtrados
pelo ISIN do papel.

Ajuste, do mais recente para o mais antigo, sobre os preços anteriores à data ex (o pregão
seguinte à data com):
- dividendo, JCP e rendimento: fator 1 - valor / fechamento da data com (valor bruto);
- desdobramento e bonificação: a B3 informa o percentual de ações novas; preço / (1 + f/100);
- grupamento: a B3 informa ações novas por ação antiga; preço / f.
Direitos de subscrição não são ajustados.
"""

import base64
import json
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from core.calendario_b3 import next_trading_day
from core.exceptions import DataInsufficientError
from core.types import PriceBar

_URL = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (B3 Opcoes Pro)"}
_TIMEOUT_SECONDS = 10.0
_FRESH_SECONDS = 12 * 3600
# Depois de uma falha, espera antes de tentar de novo: a consulta está no caminho da requisição.
_RETRY_SECONDS = 1800

_CASH_LABELS = {"DIVIDENDO", "JRS CAP PROPRIO", "RENDIMENTO"}
_SPLIT_LABELS = {"DESDOBRAMENTO", "BONIFICACAO"}
_REVERSE_LABELS = {"GRUPAMENTO"}


@dataclass(frozen=True)
class CashEvent:
    isin: str
    last_day_with: date
    amount: float
    label: str


@dataclass(frozen=True)
class ShareEvent:
    isin: str
    last_day_with: date
    # Ações depois do evento para cada ação antes dele.
    multiplier: float
    label: str


def _number(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def _day(text: str) -> date:
    return datetime.strptime(text, "%d/%m/%Y").date()


def parse_company(payload: list | dict) -> tuple[list[CashEvent], list[ShareEvent]]:
    company = payload[0] if isinstance(payload, list) else payload
    cash, shares = [], []
    # A B3 repete eventos idênticos; parcelas com pagamentos em datas diferentes são distintas.
    seen: set[tuple] = set()
    for item in company.get("cashDividends") or []:
        label = (item.get("label") or "").strip().upper()
        if label not in _CASH_LABELS:
            continue
        try:
            event = CashEvent(item["isinCode"], _day(item["lastDatePrior"]), _number(item["rate"]), label)
        except (KeyError, ValueError):
            continue
        key = (event, item.get("paymentDate"))
        if key not in seen:
            seen.add(key)
            cash.append(event)
    for item in company.get("stockDividends") or []:
        label = (item.get("label") or "").strip().upper()
        try:
            factor, day = _number(item["factor"]), _day(item["lastDatePrior"])
        except (KeyError, ValueError):
            continue
        if label in _SPLIT_LABELS:
            multiplier = 1 + factor / 100
        elif label in _REVERSE_LABELS:
            multiplier = factor
        else:
            continue
        event = ShareEvent(item["isinCode"], day, multiplier, label)
        if multiplier > 0 and event not in seen:
            seen.add(event)
            shares.append(event)
    return cash, shares


class B3CorporateActions:
    def __init__(self, get: Callable[..., httpx.Response] = httpx.get, clock: Callable[[], float] = time.monotonic) -> None:
        self._get = get
        self._clock = clock
        self._lock = threading.Lock()
        self._known: dict[str, tuple[float, tuple[list[CashEvent], list[ShareEvent]]]] = {}
        self._failed: dict[str, float] = {}

    def events(self, issuer: str) -> tuple[list[CashEvent], list[ShareEvent]]:
        issuer = issuer.upper()
        now = self._clock()
        with self._lock:
            known = self._known.get(issuer)
            if known and now - known[0] < _FRESH_SECONDS:
                return known[1]
            failed = self._failed.get(issuer)
            if failed is not None and now - failed < _RETRY_SECONDS:
                raise DataInsufficientError(f"B3 sem eventos de {issuer} (falha recente)")
        query = base64.b64encode(json.dumps({"issuingCompany": issuer, "language": "pt-br"}).encode()).decode()
        try:
            response = self._get(_URL + query, headers=_HEADERS, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            parsed = parse_company(response.json())
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as error:
            with self._lock:
                self._failed[issuer] = now
            raise DataInsufficientError(f"B3 sem eventos de {issuer} ({type(error).__name__})") from None
        with self._lock:
            self._known[issuer] = (now, parsed)
            self._failed.pop(issuer, None)
        return parsed


SHARED_ACTIONS = B3CorporateActions()


def adjust_bars(bars: Sequence[PriceBar], isin: str, cash: Sequence[CashEvent], shares: Sequence[ShareEvent]) -> list[PriceBar]:
    """Devolve as barras ajustadas e marcadas como `adjusted`. Volume é ajustado só por eventos em ações."""
    ordered = sorted(bars, key=lambda bar: bar.day)
    if not ordered:
        return []
    closes = {bar.day: bar.close for bar in ordered}
    first, last = ordered[0].day, ordered[-1].day
    # (data ex, fator de preço, fator de volume)
    factors: list[tuple[date, float, float]] = []
    for event in shares:
        ex = next_trading_day(event.last_day_with)
        if event.isin == isin and first < ex <= last:
            factors.append((ex, 1 / event.multiplier, event.multiplier))
    for event in cash:
        ex = next_trading_day(event.last_day_with)
        if event.isin != isin or not first < ex <= last:
            continue
        reference = closes.get(event.last_day_with)
        if reference is None:
            prior = [bar.close for bar in ordered if bar.day <= event.last_day_with]
            reference = prior[-1] if prior else None
        if reference and 0 < event.amount < reference:
            factors.append((ex, 1 - event.amount / reference, 1.0))
    adjusted = []
    for bar in ordered:
        price_factor = volume_factor = 1.0
        for ex, price, volume in factors:
            if bar.day < ex:
                price_factor *= price
                volume_factor *= volume
        adjusted.append(
            bar.model_copy(
                update={
                    "open": bar.open * price_factor,
                    "high": bar.high * price_factor,
                    "low": bar.low * price_factor,
                    "close": bar.close * price_factor,
                    "volume": round(bar.volume * volume_factor) if bar.volume is not None else None,
                    "adjusted": True,
                }
            )
        )
    return adjusted
