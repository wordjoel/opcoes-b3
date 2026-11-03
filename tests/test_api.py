"""API de ponta a ponta com banco SQLite temporário e fonte falsa, sem rede."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, create_session, hash_password
from app.cache import CachingProvider
from app.main import Settings, create_app
from core.exceptions import DataInsufficientError
from core.types import CorporateEvent, MarketSnapshot, OptionChain, OptionKind, OptionQuote, PriceBar, Provenance, SourceKind
from data.providers.base import AtmIvSample, DataProvider
from db.client import Database, DatabaseError, migrate, pending_migrations

NOW = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)
SESSION_DAY = date(2026, 11, 3)
EXPIRY = date(2026, 12, 18)
PASSWORD = "senha-de-teste-123"
SECRET = "s" * 40
SPOT = 40.0


def _provenance(kind=SourceKind.EOD, moment=NOW - timedelta(hours=1)):
    return Provenance(source="fixture", kind=kind, collected_at=NOW, market_time=moment)


class FakeProvider(DataProvider):
    def __init__(self, live_price=SPOT):
        self.live_price = live_price
        self.calls = {"snapshot": 0, "chain": 0, "expirations": 0, "history": 0}

    def get_market_snapshot(self, symbol):
        self.calls["snapshot"] += 1
        if symbol == "SEMD3":
            raise DataInsufficientError("sem dados")
        return MarketSnapshot(
            symbol=symbol,
            price=self.live_price,
            name="Teste",
            change_percent=self.live_price / SPOT * 100 - 100,
            provenance=_provenance(SourceKind.DELAYED, NOW - timedelta(minutes=1)),
        )

    def get_expirations(self, underlying):
        self.calls["expirations"] += 1
        if underlying == "SEMD3":
            raise DataInsufficientError("sem dados")
        return [date(2026, 10, 1), date(2026, 11, 6), EXPIRY]

    def get_option_chain(self, underlying, expiry):
        self.calls["chain"] += 1
        provenance = _provenance()
        quotes = []
        for strike in range(30, 52, 2):
            for kind, prefix in ((OptionKind.CALL, "C"), (OptionKind.PUT, "P")):
                intrinsic = max(SPOT - strike, 0) if kind is OptionKind.CALL else max(strike - SPOT, 0)
                quotes.append(
                    OptionQuote(
                        symbol=f"TEST{prefix}{strike}",
                        underlying=underlying,
                        kind=kind,
                        strike=float(strike),
                        expiry=expiry,
                        bid=0.0,
                        ask=0.0,
                        close=intrinsic + 2.0 / (1 + abs(strike - SPOT)),
                        open_interest=2_000_000,
                        volume=200_000,
                        trades=200,
                        last_trade_date=SESSION_DAY,
                        iv=0.3,
                        delta=0.5,
                        provenance=provenance,
                    )
                )
        return OptionChain(
            underlying=MarketSnapshot(symbol=underlying, price=SPOT, provenance=provenance),
            quotes=quotes,
            market_date=SESSION_DAY,
            risk_free_rate=0.1375,
            time_to_expiry_years=0.12,
        )

    def get_upcoming_events(self, symbol, today):
        return [CorporateEvent(kind="RESULTADO", day=date(2026, 11, 5), label="Resultado Q3/2026", confirmed=True)]

    def get_atm_iv_on(self, underlying, day):
        return AtmIvSample(day, 0.2 + (day.toordinal() % 7) / 10 + (day.toordinal() % 11) / 100, EXPIRY)

    def get_historical_prices(self, symbol, lookback="1y"):
        self.calls["history"] += 1
        if symbol == "SEMD3":
            raise DataInsufficientError("sem dados")
        bars = []
        for index in range(80):
            close = 30 + index * 0.1 + (index % 2) * 0.3
            bars.append(
                PriceBar(
                    symbol=symbol,
                    day=date(2026, 7, 1) + timedelta(days=index),
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    adjusted=True,
                    provenance=_provenance(),
                )
            )
        return bars


@pytest.fixture
def database(tmp_path):
    db = Database(str(tmp_path / "teste.db"))
    migrate(db)
    return db


def make_client(database, provider=None, settings=None):
    source = provider or FakeProvider()
    config = settings or Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True)
    app = create_app(config, lambda: database, lambda _: source, now=lambda: NOW)
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def client(database):
    logged = make_client(database)
    logged.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
    return logged


class TestAuth:
    def test_every_data_route_requires_session(self, database):
        anonymous = make_client(database)
        for path in (
            "/api/status",
            "/api/watchlist",
            "/api/scanner",
            "/api/assets/PETR4",
            "/api/assets/PETR4/expirations",
            f"/api/assets/PETR4/chain?expiry={EXPIRY}",
            f"/api/assets/PETR4/strategies?expiry={EXPIRY}",
        ):
            assert anonymous.get(path).status_code == 401, path

    def test_login_flow_sets_protected_cookie(self, database):
        anonymous = make_client(database)
        response = anonymous.post("/api/login", json={"password": PASSWORD})
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert anonymous.get("/api/session").json()["authenticated"] is True
        assert anonymous.get("/api/status").status_code == 200

    def test_cookie_is_secure_by_default(self, database):
        settings = Settings(hash_password(PASSWORD), SECRET, True)
        response = make_client(database, settings=settings).post("/api/login", json={"password": PASSWORD})
        assert "secure" in response.headers["set-cookie"].lower()

    def test_wrong_password_and_throttle(self, database):
        anonymous = make_client(database)
        for _ in range(5):
            assert anonymous.post("/api/login", json={"password": "errada"}).status_code == 401
        assert anonymous.post("/api/login", json={"password": PASSWORD}).status_code == 429

    def test_forged_and_expired_cookies_fail(self, database):
        anonymous = make_client(database)
        anonymous.cookies.set(COOKIE_NAME, "9999999999.assinatura-falsa", path="/api")
        assert anonymous.get("/api/status").status_code == 401
        anonymous.cookies.set(COOKIE_NAME, create_session(SECRET, NOW - timedelta(days=30)), path="/api")
        assert anonymous.get("/api/status").status_code == 401

    def test_non_ascii_cookie_is_refused_without_error(self, database):
        anonymous = make_client(database)
        response = anonymous.get("/api/status", headers={"Cookie": f"{COOKIE_NAME}=1.\u00e9".encode("latin-1")})
        assert response.status_code == 401

    def test_unconfigured_login_fails_closed(self, database):
        anonymous = make_client(database, settings=Settings(None, None, False))
        assert anonymous.post("/api/login", json={"password": "x"}).status_code == 503
        assert anonymous.get("/api/status").status_code == 503
        assert anonymous.get("/api/session").json() == {"authenticated": False, "login_ready": False}

    def test_short_secret_is_not_accepted(self, database):
        settings = Settings(hash_password(PASSWORD), "curto", True)
        assert make_client(database, settings=settings).post("/api/login", json={"password": PASSWORD}).status_code == 503

    def test_no_order_route_exists(self, client):
        for path in ("/api/orders", "/api/ordens", "/api/order"):
            assert client.post(path, json={}).status_code == 404
        assert client.get("/api/status").json()["order_routing"] is False


class TestData:
    def test_responses_are_not_cacheable(self, client):
        assert client.get("/api/status").headers["cache-control"] == "no-store"

    def test_invalid_symbol(self, client):
        assert client.get("/api/assets/x$y").status_code == 400

    def test_asset_overview(self, client):
        body = client.get("/api/assets/PETR4").json()
        assert body["quote"]["price"] == SPOT
        assert body["quote"]["provenance"]["source"] == "fixture"
        assert body["historical_volatility"] > 0
        assert len(body["history"]) == 80
        assert body["history"][0]["bb_upper"] is None and body["history"][-1]["bb_upper"] is not None
        assert body["history"][-1]["hv_20d"] > 0 and body["history"][-1]["open"] > 0

    def test_expirations_hide_past_dates(self, client):
        assert client.get("/api/assets/PETR4/expirations").json()["expirations"] == ["2026-11-06", "2026-12-18"]

    def test_chain_hides_zero_book_as_missing(self, client):
        body = client.get(f"/api/assets/PETR4/chain?expiry={EXPIRY}").json()
        assert body["market_date"] == "2026-11-03"
        assert body["quotes"][0]["bid"] is None
        assert "CLOSE_ONLY" in {issue["code"] for issue in body["quality"]["issues"]}

    def test_strategies_are_calculated_and_sorted(self, client):
        body = client.get(f"/api/assets/PETR4/strategies?expiry={EXPIRY}").json()
        assert len(body["candidates"]) == 11
        flags = [row["risk"]["is_approved"] for row in body["candidates"]]
        assert any(flags) and flags == sorted(flags, reverse=True)
        call = next(row for row in body["candidates"] if row["key"] == "long_call")
        assert call["max_profit"] is None
        assert call["max_loss"] == pytest.approx(200.0)
        assert call["legs"][0]["price_basis"] == "CLOSE"
        assert call["greeks"]["delta"] > 0
        assert 0 < call["probability_of_profit"] < 1
        assert call["payoff"]
        assert len(call["heatmap"]["pnl"]) == 5
        assert 0 < call["legs"][0]["probability_itm"] < 1
        assert any("Resultado Q3/2026" in text for text in call["risk"]["warnings"])
        assert body["events"][0]["label"] == "Resultado Q3/2026"
        assert body["iv_rank"] is not None

    def test_profile_is_validated_and_applied(self, client):
        assert client.get(f"/api/assets/PETR4/strategies?expiry={EXPIRY}&profile=OUTRO").status_code == 422
        body = client.get(f"/api/assets/PETR4/strategies?expiry={EXPIRY}&profile=MODERATE").json()
        assert body["profile"] == "MODERATE"

    def test_chain_reports_open_interest(self, client):
        summary = client.get(f"/api/assets/PETR4/chain?expiry={EXPIRY}").json()["open_interest"]
        assert summary["calls"] > 0 and summary["put_call_ratio"] == 1.0
        assert summary["calls_change"] is None

    def test_moved_spot_rejects_every_structure(self, database):
        logged = make_client(database, FakeProvider(live_price=SPOT * 0.94))
        logged.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
        body = logged.get(f"/api/assets/PETR4/strategies?expiry={EXPIRY}").json()
        assert body["spot_drift"] == pytest.approx(-0.06)
        assert not any(row["risk"]["is_approved"] for row in body["candidates"])

    def test_insufficient_data_has_label(self, client):
        response = client.get("/api/assets/SEMD3")
        assert response.status_code == 422
        assert response.json()["label"] == "DADOS INSUFICIENTES"


class TestScanner:
    def test_one_symbol_without_data_does_not_break_the_rest(self, client):
        client.post("/api/watchlist", json={"symbol": "semd3"})
        rows = {row["symbol"]: row for row in client.get("/api/scanner").json()["rows"]}
        assert len(rows) == 9
        assert rows["PETR4"]["iv_ratio"] > 0
        assert rows["PETR4"]["expiry"] == "2026-12-18"
        assert rows["PETR4"]["missing"] == []
        assert rows["PETR4"]["iv_samples"] == 52
        assert 0 <= rows["PETR4"]["iv_rank"] <= 100
        assert rows["SEMD3"]["iv_rank"] is None
        assert rows["SEMD3"]["price"] is None
        assert len(rows["SEMD3"]["missing"]) == 3

    def test_signals_for_moved_spot(self, database):
        logged = make_client(database, FakeProvider(live_price=SPOT * 0.94))
        logged.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
        row = logged.get("/api/scanner").json()["rows"][0]
        details = {signal["type"]: signal["detail"] for signal in row["signals"]}
        assert details["MOVIMENTO"] == "Ativo -6,00% no dia."
        assert details["GRADE_DEFASADA"] == "Ativo -6,0% desde o pregão da grade."


class TestCron:
    SECRET = "c" * 40

    def client(self, database, cron_secret="c" * 40):
        settings = Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True, cron_secret=cron_secret)
        return make_client(database, settings=settings)

    def test_runs_with_the_secret_and_needs_no_session(self, database):
        response = self.client(database).get("/api/cron/scan", headers={"Authorization": f"Bearer {self.SECRET}"})
        assert response.status_code == 200
        assert response.json() == {
            "symbols": 8,
            "complete": 8,
            "iv_samples": 416,
            "scan_complete": True,
            "b3": {"sessions": [], "bars": 0},
            "lab": {"active": 0, "marked": 0, "closed": 0, "not_reached": 0},
        }

    def test_refuses_missing_or_wrong_secret(self, database):
        client = self.client(database)
        assert client.get("/api/cron/scan").status_code == 401
        assert client.get("/api/cron/scan", headers={"Authorization": "Bearer errado"}).status_code == 401
        assert client.get("/api/cron/scan", headers={"Authorization": self.SECRET}).status_code == 401

    def test_user_session_does_not_open_it(self, database):
        client = self.client(database)
        client.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
        assert client.get("/api/cron/scan").status_code == 401

    def test_unconfigured_or_short_secret_fails_closed(self, database):
        for secret in (None, "curto"):
            client = self.client(database, cron_secret=secret)
            assert client.get("/api/cron/scan", headers={"Authorization": f"Bearer {secret}"}).status_code == 503

    def test_response_has_no_market_data(self, database):
        response = self.client(database).get("/api/cron/scan", headers={"Authorization": f"Bearer {self.SECRET}"})
        assert set(response.json()) == {"symbols", "complete", "iv_samples", "scan_complete", "b3", "lab"}

    def test_failed_b3_download_does_not_stop_the_scan(self, database):
        def failing(_db, _moment):
            raise DataInsufficientError("B3 indisponível")

        settings = Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True, cron_secret="c" * 40)
        app = create_app(settings, lambda: database, lambda _: FakeProvider(), now=lambda: NOW, market_ingest=failing)
        response = TestClient(app, base_url="https://testserver").get(
            "/api/cron/scan", headers={"Authorization": f"Bearer {self.SECRET}"}
        )
        assert response.status_code == 200
        assert response.json()["b3"]["error"] == "B3 indisponível"
        assert response.json()["symbols"] == 8


class TestIvRankErrors:
    def test_source_limit_keeps_chain_data_and_counts_samples(self, database):
        class Limited(FakeProvider):
            def __init__(self):
                super().__init__()
                self.iv_calls = 0

            def get_atm_iv_on(self, underlying, day):
                self.iv_calls += 1
                if self.iv_calls > 5:
                    raise DataInsufficientError("limite de requisições")
                return super().get_atm_iv_on(underlying, day)

        logged = make_client(database, Limited())
        logged.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
        logged.delete("/api/watchlist/VALE3")
        for symbol in ("ITUB4", "BBAS3", "BBDC4", "MGLU3", "WEGE3", "B3SA3"):
            logged.delete(f"/api/watchlist/{symbol}")
        row = logged.get("/api/scanner").json()["rows"][0]
        assert row["atm_iv"] is not None
        assert row["iv_samples"] == 4
        assert row["iv_rank"] is None
        assert row["missing"] == ["IV Rank: limite de requisições"]


class TestWatchlist:
    def test_add_normalizes_and_remove(self, client):
        assert "KLBN11" in client.post("/api/watchlist", json={"symbol": " klbn11 "}).json()["symbols"]
        assert "KLBN11" not in client.delete("/api/watchlist/KLBN11").json()["symbols"]

    def test_add_twice_keeps_one(self, client):
        client.post("/api/watchlist", json={"symbol": "KLBN11"})
        symbols = client.post("/api/watchlist", json={"symbol": "KLBN11"}).json()["symbols"]
        assert symbols.count("KLBN11") == 1

    def test_add_rejects_garbage(self, client):
        assert client.post("/api/watchlist", json={"symbol": "ABC; DROP"}).status_code == 400


class TestDatabase:
    def test_migrate_is_idempotent(self, database):
        assert pending_migrations(database) == []
        assert migrate(database) == []

    def test_seed_has_only_symbols(self, database):
        assert len(database.fetch("SELECT symbol FROM watchlist")) == 8

    def test_failure_message_does_not_leak_url(self, database):
        with pytest.raises(DatabaseError) as error:
            database.fetch("SELECT * FROM tabela_inexistente")
        assert "teste.db" not in str(error.value)
        assert "tabela_inexistente" not in str(error.value)

    def test_vercel_without_url_refuses_local_file(self, monkeypatch):
        monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
        monkeypatch.setenv("VERCEL", "1")
        with pytest.raises(DatabaseError):
            Database.from_env()


class TestCache:
    def setup_provider(self, database):
        self.moment = NOW
        self.inner = FakeProvider()
        return CachingProvider(self.inner, database, now=lambda: self.moment)

    def test_second_read_uses_cache_and_keeps_provenance(self, database):
        cached = self.setup_provider(database)
        first = cached.get_option_chain("PETR4", EXPIRY)
        second = cached.get_option_chain("PETR4", EXPIRY)
        assert self.inner.calls["chain"] == 1
        assert second == first
        assert second.underlying.provenance.kind is SourceKind.EOD

    def test_expired_entry_is_fetched_again(self, database):
        cached = self.setup_provider(database)
        cached.get_market_snapshot("PETR4")
        self.moment = NOW + timedelta(minutes=6)
        cached.get_market_snapshot("PETR4")
        assert self.inner.calls["snapshot"] == 2

    def test_all_types_round_trip(self, database):
        cached = self.setup_provider(database)
        for _ in range(2):
            days = cached.get_expirations("PETR4")
            bars = cached.get_historical_prices("PETR4")
        assert days[-1] == EXPIRY and len(bars) == 80
        assert self.inner.calls["expirations"] == 1 and self.inner.calls["history"] == 1

    def test_errors_are_not_cached(self, database):
        cached = self.setup_provider(database)
        for _ in range(2):
            with pytest.raises(DataInsufficientError):
                cached.get_market_snapshot("SEMD3")
        assert self.inner.calls["snapshot"] == 2
