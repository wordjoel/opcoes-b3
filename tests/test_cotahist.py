"""Fonte oficial da B3. As linhas seguem o layout do arquivo real, com valores de teste."""

import io
import zipfile
from datetime import date, datetime, timezone

import httpx
import pytest

from app import lab, service
from core.clock import grid_still_current
from core.exceptions import DataInsufficientError
from core.types import ExerciseStyle, OptionKind, SourceKind
from data.providers.base import DataProvider
from data.providers.composite import SourceChain
from data.providers.cotahist import (
    CotahistFiles,
    CotahistProvider,
    SelicRates,
    atm_iv_sample,
    ingest_recent,
    parse_daily_file,
    parse_line,
)
from db.client import Database, migrate
from quant.lab import meets_scan_liquidity

DAY = date(2026, 10, 30)
NOW = datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc)
ISIN = "BRPETRACNPR6"


def _money(value: float, width: int = 13) -> str:
    return f"{round(value * 100):0{width}d}"


def stock_line(symbol="PETR4", close=50.0, isin=ISIN, day="20261030", bdi="02", name="PETROBRAS") -> str:
    prices = _money(close) * 5  # abertura, máxima, mínima, média, último
    line = "01" + day + bdi + f"{symbol:<12}" + "010" + f"{name:<12}" + f"{'PN      N2':<10}" + "000" + "R$  "
    line += prices + _money(0) + _money(0) + "00100" + f"{5000:018d}" + f"{250000 * 100:018d}"
    line += _money(0) + "0" + "99991231" + "0000001" + _money(0) + isin + "230"
    assert len(line) == 245
    return line


def option_line(
    symbol="PETRK500", market="070", name="PETRE", strike=50.0, close=2.0, expiry="20261218", isin=ISIN,
    bid=1.9, ask=2.1, volume=10000, trades=20,
) -> str:
    prices = _money(close) * 5
    line = "01" + "20261030" + "78" + f"{symbol:<12}" + market + f"{name:<12}" + f"{'PN      N2':<10}" + "000" + "R$  "
    line += prices + _money(bid) + _money(ask) + f"{trades:05d}" + f"{volume:018d}" + f"{0:018d}"
    line += _money(strike) + "0" + expiry + "0000001" + _money(0) + isin + "230"
    assert len(line) == 245
    return line


def zipped(lines: list[str], stamp="20261030", trailer=True) -> bytes:
    rows = [f"00COTAHIST.2026BOVESPA {stamp}".ljust(245), *lines]
    if trailer:
        rows.append("99COTAHIST".ljust(245))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("COTAHIST.TXT", "\r\n".join(rows).encode("latin-1"))
    return buffer.getvalue()


class FakeHttp:
    def __init__(self, files: dict[str, bytes] | None = None, status: int | None = None) -> None:
        self.files, self.status, self.calls = files or {}, status, 0

    def __call__(self, url, **_):
        self.calls += 1
        if self.status:
            return httpx.Response(self.status, request=httpx.Request("GET", url))
        for stamp, content in self.files.items():
            if stamp in url:
                return httpx.Response(200, content=content, request=httpx.Request("GET", url))
        return httpx.Response(404, request=httpx.Request("GET", url))


def selic(value="13.75"):
    def get(url, params=None, **_):
        return httpx.Response(200, json=[{"data": params["dataInicial"], "valor": value}], request=httpx.Request("GET", url))
    return SelicRates(get)


GRID = [
    stock_line(),
    stock_line("PETR3", close=48.0, isin="BRPETRACNOR9"),
    option_line(),
    option_line("PETRW500", market="080", name="PETR", close=2.5),
    option_line("PETRX490", market="080", name="PETRE  FM", strike=49.0, close=1.8),
    option_line("PETRK510", strike=51.0, close=1.6),
    option_line("PETRK550W1", strike=50.0, close=0.5, expiry="20261106"),
    option_line("PETRK499", isin="BRPETRACNOR9", strike=49.9, close=1.5),
]


def provider(database, grid=GRID, rates=None) -> CotahistProvider:
    files = CotahistFiles(FakeHttp({"D30102026": zipped(grid)}))
    return CotahistProvider(database, files, rates or selic(), now=lambda: NOW)


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "t.db"))
    migrate(database)
    return database


def test_style_compares_with_root_not_last_letter():
    """VALE e WEGE terminam em E, mas só VALEE é europeia."""
    american = parse_line(option_line("VALEK620", name="VALE", isin="BRVALEACNOR0"))[1]
    european = parse_line(option_line("VALEK621", name="VALEE", isin="BRVALEACNOR0"))[1]
    formador = parse_line(option_line("VALEK622", name="VALEE  FM", isin="BRVALEACNOR0"))[1]
    assert american.style is ExerciseStyle.AMERICAN
    assert european.style is ExerciseStyle.EUROPEAN
    assert formador.style is ExerciseStyle.EUROPEAN


def test_parses_prices_and_ignores_other_markets():
    assert parse_line(stock_line(bdi="96")) is None
    assert parse_line("00COTAHIST".ljust(245)) is None
    day, row = parse_line(option_line(strike=50.5, close=2.34, bid=2.1, ask=2.5))
    assert (day, row.strike, row.close, row.bid, row.ask) == (DAY, 50.5, 2.34, 2.1, 2.5)
    assert row.kind is OptionKind.CALL and row.volume == 10000 and row.trades == 20


def test_price_factor_is_applied():
    line = option_line(close=200.0).replace("0000001" + _money(0), "0001000" + _money(0))
    assert parse_line(line)[1].close == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("content", "reason"),
    [(zipped([stock_line()], stamp="20261029"), "outra data"), (zipped([stock_line()], trailer=False), "incompleto"), (b"<html>", "ilegível")],
)
def test_wrong_or_truncated_file_is_refused(content, reason):
    with pytest.raises(DataInsufficientError, match=reason):
        parse_daily_file(content, DAY)


def test_absent_day_is_none_and_not_downloaded_again():
    http = FakeHttp()
    files = CotahistFiles(http)
    assert files.session(DAY) is None
    assert files.session(DAY) is None
    assert http.calls == 1


def test_server_failure_is_error_not_absence():
    with pytest.raises(DataInsufficientError, match="503"):
        CotahistFiles(FakeHttp(status=503)).session(DAY)


def test_same_file_is_downloaded_once():
    http = FakeHttp({"D30102026": zipped(GRID)})
    files = CotahistFiles(http)
    assert files.session(DAY) is files.session(DAY)
    assert http.calls == 1


def test_latest_walks_back_over_holiday_and_weekend():
    files = CotahistFiles(FakeHttp({"D30102026": zipped(GRID)}))
    assert files.latest(date(2026, 11, 3)).day == DAY


def test_chain_separates_on_and_pn_by_isin(db):
    chain = provider(db).get_option_chain("PETR4", date(2026, 12, 18))
    assert {quote.symbol for quote in chain.quotes} == {"PETRK500", "PETRW500", "PETRX490", "PETRK510"}
    assert chain.underlying.price == 50.0 and chain.market_date == DAY
    assert chain.risk_free_rate == pytest.approx(0.1375)
    assert chain.time_to_expiry_years == pytest.approx(49 / 365)
    quote = next(q for q in chain.quotes if q.symbol == "PETRK500")
    assert quote.iv and 0 < quote.delta < 1
    assert quote.last_trade_date == DAY
    assert quote.provenance.source == "B3 COTAHIST" and quote.provenance.kind.value == "EOD"


def test_open_interest_is_unknown_never_zero(db):
    chain = provider(db).get_option_chain("PETR4", date(2026, 12, 18))
    assert all(quote.open_interest is None for quote in chain.quotes)


def test_liquidity_filter_keeps_volume_rule_when_open_interest_is_unknown(db):
    quote = provider(db).get_option_chain("PETR4", date(2026, 12, 18)).quotes[0]
    assert meets_scan_liquidity(quote)
    assert not meets_scan_liquidity(quote.model_copy(update={"volume": 10}))
    assert not meets_scan_liquidity(quote.model_copy(update={"open_interest": 5}))


def test_price_below_intrinsic_has_no_vol_instead_of_invented_value(db):
    grid = [stock_line(), option_line(strike=30.0, close=1.0)]
    assert provider(db, grid).get_option_chain("PETR4", date(2026, 12, 18)).quotes[0].iv is None


def test_missing_rate_blocks_chain_instead_of_default(db):
    def failing(url, **_):
        raise httpx.ConnectError("sem rede")

    with pytest.raises(DataInsufficientError, match="Selic"):
        provider(db, rates=SelicRates(failing)).get_option_chain("PETR4", date(2026, 12, 18))


def test_expirations_only_future_and_only_this_underlying(db):
    assert provider(db).get_expirations("PETR4") == [date(2026, 11, 6), date(2026, 12, 18)]
    with pytest.raises(DataInsufficientError):
        provider(db).get_expirations("VALE3")


def test_atm_sample_ignores_weekly_and_short_expiries():
    session = parse_daily_file(zipped(GRID), DAY)
    sample = atm_iv_sample(session, "PETR4", 0.1375)
    assert sample.expiry == date(2026, 12, 18) and sample.iv > 0


def test_atm_sample_for_today_unpublished_raises_so_it_is_not_cached(db):
    source = provider(db)
    with pytest.raises(DataInsufficientError, match="não publicado"):
        source.get_atm_iv_on("PETR4", date(2026, 11, 3))
    assert source.get_atm_iv_on("PETR4", date(2026, 11, 2)) is None


def test_ingest_is_repeatable_and_keeps_only_stocks_with_options(db):
    files = CotahistFiles(FakeHttp({"D30102026": zipped([*GRID, stock_line("XYZW3", isin="BRXYZWACNOR1")])}))
    assert ingest_recent(db, files, NOW)["sessions"] == ["2026-10-30"]
    ingest_recent(db, files, NOW)
    assert db.fetch("SELECT symbol, count(*) FROM b3_daily_bars GROUP BY symbol ORDER BY symbol") == [("PETR3", 1), ("PETR4", 1)]


def test_ingest_only_asks_for_days_after_the_last_stored(db):
    db.run("INSERT INTO b3_daily_bars VALUES ('PETR4', '2026-10-30', 1, 1, 1, 1, 1, 1, 'x')")
    http = FakeHttp()
    ingest_recent(db, CotahistFiles(http), NOW)
    assert http.calls == 2  # 02 e 03/11; 31/10 e 01/11 são fim de semana


def test_ingest_after_long_gap_is_limited(db):
    db.run("INSERT INTO b3_daily_bars VALUES ('PETR4', '2025-01-02', 1, 1, 1, 1, 1, 1, 'x')")
    http = FakeHttp()
    ingest_recent(db, CotahistFiles(http), NOW)
    assert http.calls <= 11


def test_ingest_does_not_overwrite_existing_bar(db):
    db.run("INSERT INTO b3_daily_bars VALUES ('PETR4', '2026-10-30', 1, 1, 1, 1, 1, 1, 'antes')")
    from data.providers.cotahist import optioned_stocks, store_bars

    store_bars(db, DAY, optioned_stocks(parse_daily_file(zipped(GRID), DAY)), NOW)
    assert db.fetch("SELECT close, fetched_at FROM b3_daily_bars WHERE symbol = 'PETR4'") == [(1.0, "antes")]


def test_history_merges_stored_bars_with_latest_session_and_is_marked_unadjusted(db):
    db.run("INSERT INTO b3_daily_bars VALUES ('PETR4', '2026-10-29', 48, 49, 47, 48.5, 1, 1, 'x')")
    bars = provider(db).get_historical_prices("PETR4")
    assert [(bar.day, bar.close) for bar in bars] == [(date(2026, 10, 29), 48.5), (DAY, 50.0)]
    assert not any(bar.adjusted for bar in bars)


class _Empty(DataProvider):
    def __init__(self, error=None, value=None):
        self.error, self.value = error, value

    def _answer(self, *_):
        if self.error:
            raise DataInsufficientError(self.error)
        return self.value

    get_market_snapshot = get_option_chain = get_expirations = get_historical_prices = _answer
    get_atm_iv_on = get_upcoming_events = get_option_chain_on = _answer


def test_chain_falls_through_only_on_declared_failure():
    chain = SourceChain([_Empty("sem token"), _Empty(value="b3")], events=_Empty(value=[]))
    assert chain.get_market_snapshot("PETR4") == "b3"
    assert chain.get_upcoming_events("PETR4", DAY) == []


def test_chain_reports_every_failure():
    with pytest.raises(DataInsufficientError, match="a | b"):
        SourceChain([_Empty("a"), _Empty("b")], events=_Empty()).get_expirations("PETR4")


def test_access_failure_is_not_turned_into_absence():
    """O cache guarda a ausência para sempre: 401 da primeira fonte não pode virar "sem pregão"."""
    chain = SourceChain([_Empty("401"), _Empty(value=None)], events=_Empty())
    with pytest.raises(DataInsufficientError, match="401"):
        chain.get_option_chain_on("PETR4", date(2026, 12, 18), DAY)
    assert SourceChain([_Empty(value=None)], events=_Empty()).get_atm_iv_on("PETR4", DAY) is None


def test_scan_reports_real_data_and_warns_about_unadjusted_history(db):
    for day in range(1, 30):
        db.run(
            "INSERT INTO b3_daily_bars VALUES ('PETR4', ?, 50, 60, 45, ?, 1, 1, 'x')",
            (f"2026-09-{day:02d}", 50 + day % 3),
        )
    chain = SourceChain([provider(db)], events=_Empty("brapi recusou o acesso"))
    row = service.scan_symbol(chain, "PETR4", NOW)
    assert row["source"] == "B3 COTAHIST" and row["price"] == 50.0
    assert row["spot_drift"] is None  # mesma fonte e mesmo pregão: não mede movimento
    assert row["market_date"] == "2026-10-30" and row["atm_iv"] > 0
    assert row["missing"] == ["Eventos: brapi recusou o acesso"]
    assert any("proventos" in warning for warning in row["history_warnings"])


def test_day_quote_from_another_source_measures_drift(db):
    grid = provider(db)
    moved = grid.get_market_snapshot("PETR4").model_copy(deep=True)
    fresh = moved.model_copy(update={
        "price": 47.5,
        "provenance": moved.provenance.model_copy(update={"kind": SourceKind.DELAYED, "market_time": NOW}),
    })
    chain = grid.get_option_chain("PETR4", date(2026, 12, 18))
    assert service.spot_drift(chain, fresh) == pytest.approx(-0.05)
    assert service.spot_drift(chain, moved) is None


def test_quote_uses_its_own_source_order():
    chain = SourceChain([_Empty(value="grade")], events=_Empty(), quotes=[_Empty("401"), _Empty(value="b3")])
    assert chain.get_market_snapshot("PETR4") == "b3"
    assert chain.get_expirations("PETR4") == "grade"


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        # Grade de sexta, 30/10: segunda, 02/11, é Finados; vale até a abertura de terça.
        (datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc), True),
        (datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc), True),
        (datetime(2026, 11, 3, 12, 59, tzinfo=timezone.utc), True),
        (datetime(2026, 11, 3, 13, 0, tzinfo=timezone.utc), False),
    ],
)
def test_grid_is_current_only_until_next_opening(moment, expected):
    assert grid_still_current(DAY, moment) is expected


def test_forward_entry_refused_when_drift_cannot_be_measured(db):
    chain = SourceChain([provider(db)], events=_Empty("sem"))
    with pytest.raises(DataInsufficientError, match="sem cotação do dia"):
        lab.start_forward(chain, db, "PETR4", "regra_5pct", "qualquer", lab.LabPlan(10000, 10, None, None, None), NOW)
