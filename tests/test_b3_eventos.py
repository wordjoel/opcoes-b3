import base64
import json
from datetime import date, datetime, timezone

import httpx
import pytest

from core.exceptions import DataInsufficientError
from core.types import PriceBar, Provenance, SourceKind
from data.providers.b3_eventos import B3CorporateActions, CashEvent, ShareEvent, adjust_bars, parse_company
from data.providers.cotahist import CotahistFiles, CotahistProvider
from tests.test_cotahist import DAY, GRID, ISIN, NOW, FakeHttp, db, selic, zipped  # noqa: F401

_T = datetime(2026, 11, 1, tzinfo=timezone.utc)
PROV = Provenance(source="t", kind=SourceKind.EOD, collected_at=_T, market_time=_T)


def bar(day, close, volume=1000):
    return PriceBar(symbol="X", day=day, open=close, high=close, low=close, close=close, volume=volume, adjusted=False, provenance=PROV)


PAYLOAD = [
    {
        "code": "PETR",
        "cashDividends": [
            {"isinCode": ISIN, "label": "DIVIDENDO", "rate": "1,00000000000", "lastDatePrior": "21/10/2026", "paymentDate": "21/12/2026"},
            {"isinCode": ISIN, "label": "DIVIDENDO", "rate": "1,00000000000", "lastDatePrior": "21/10/2026", "paymentDate": "21/12/2026"},
            {"isinCode": ISIN, "label": "JRS CAP PROPRIO", "rate": "0,50000000000", "lastDatePrior": "21/10/2026", "paymentDate": "20/01/2027"},
            {"isinCode": "OUTRO", "label": "DIVIDENDO", "rate": "9,0", "lastDatePrior": "21/10/2026"},
            {"isinCode": ISIN, "label": "SUBSCRICAO", "rate": "1,0", "lastDatePrior": "21/10/2026"},
        ],
        "stockDividends": [
            {"isinCode": ISIN, "label": "DESDOBRAMENTO", "factor": "100,00000000000", "lastDatePrior": "23/10/2026"},
            {"isinCode": ISIN, "label": "GRUPAMENTO", "factor": "0,10000000000", "lastDatePrior": "01/01/2020"},
            {"isinCode": ISIN, "label": "BONIFICACAO", "factor": "5,00000000000", "lastDatePrior": "02/01/2020"},
        ],
    }
]


def test_parse_reads_brazilian_numbers_and_drops_duplicates():
    cash, shares = parse_company(PAYLOAD)
    assert [(event.label, event.amount) for event in cash if event.isin == ISIN] == [("DIVIDENDO", 1.0), ("JRS CAP PROPRIO", 0.5)]
    assert [(event.label, event.multiplier) for event in shares] == [("DESDOBRAMENTO", 2.0), ("GRUPAMENTO", 0.1), ("BONIFICACAO", 1.05)]


def test_split_halves_prices_before_ex_date_and_doubles_volume():
    _, shares = parse_company(PAYLOAD)
    bars = [bar(date(2026, 10, 23), 40.0), bar(date(2026, 10, 26), 20.0)]
    adjusted = adjust_bars(bars, ISIN, [], shares)
    assert [b.close for b in adjusted] == [20.0, 20.0]
    assert [b.volume for b in adjusted] == [2000, 1000]
    assert all(b.adjusted for b in adjusted)


def test_cash_uses_close_of_last_day_with():
    cash = [CashEvent(ISIN, date(2026, 10, 21), 2.0, "DIVIDENDO")]
    bars = [bar(date(2026, 10, 20), 40.0), bar(date(2026, 10, 21), 50.0), bar(date(2026, 10, 22), 48.0)]
    adjusted = adjust_bars(bars, ISIN, cash, [])
    assert [round(b.close, 6) for b in adjusted] == [38.4, 48.0, 48.0]
    assert adjusted[0].volume == 1000


def test_events_outside_range_or_other_isin_change_nothing():
    cash = [CashEvent("OUTRO", date(2026, 10, 21), 2.0, "DIVIDENDO"), CashEvent(ISIN, date(2020, 1, 2), 2.0, "DIVIDENDO")]
    shares = [ShareEvent(ISIN, date(2026, 12, 1), 2.0, "DESDOBRAMENTO")]
    bars = [bar(date(2026, 10, 20), 40.0), bar(date(2026, 10, 22), 48.0)]
    assert [b.close for b in adjust_bars(bars, ISIN, cash, shares)] == [40.0, 48.0]


def test_client_caches_and_backs_off_after_failure():
    calls = []
    clock = [0.0]

    def get(url, **_):
        calls.append(url)
        query = json.loads(base64.b64decode(url.rsplit("/", 1)[1]))
        if query["issuingCompany"] == "FAIL":
            return httpx.Response(500, request=httpx.Request("GET", url))
        return httpx.Response(200, json=PAYLOAD, request=httpx.Request("GET", url))

    actions = B3CorporateActions(get, clock=lambda: clock[0])
    actions.events("petr")
    actions.events("PETR")
    assert len(calls) == 1
    for _ in range(2):
        with pytest.raises(DataInsufficientError):
            actions.events("FAIL")
    assert len(calls) == 2
    clock[0] = 13 * 3600
    actions.events("PETR")
    assert len(calls) == 3


class _Actions:
    def __init__(self, payload=PAYLOAD, error=False):
        self.payload, self.error = payload, error

    def events(self, issuer):
        if self.error:
            raise DataInsufficientError("fora")
        return parse_company(self.payload)


def provider(db, actions):
    files = CotahistFiles(FakeHttp({"D30102026": zipped(GRID)}))
    return CotahistProvider(db, files, selic(), now=lambda: NOW, actions=actions)


def test_provider_adjusts_history_with_b3_events(db):
    db.run("INSERT INTO b3_daily_bars VALUES ('PETR4', '2026-10-21', 100, 100, 100, 100, 10, 1, 'x')")
    bars = provider(db, _Actions()).get_historical_prices("PETR4")
    # Dividendo 1,00 + JCP 0,50 sobre 100 e desdobramento 2x antes de 26/10.
    assert bars[0].close == pytest.approx(100 * 0.99 * 0.995 / 2)
    assert bars[-1].day == DAY and bars[-1].close == 50.0
    assert all(b.adjusted for b in bars)


def test_provider_falls_back_to_unadjusted(db):
    db.run("INSERT INTO b3_daily_bars VALUES ('PETR4', '2026-10-21', 100, 100, 100, 100, 10, 1, 'x')")
    assert not any(b.adjusted for b in provider(db, _Actions(error=True)).get_historical_prices("PETR4"))
    no_events_for_isin = [{"cashDividends": [], "stockDividends": []}]
    assert not any(b.adjusted for b in provider(db, _Actions(no_events_for_isin)).get_historical_prices("PETR4"))
