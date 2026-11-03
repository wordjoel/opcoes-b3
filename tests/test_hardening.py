"""Login, sessão, tempo de mercado, cache e falhas da fonte."""

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.auth import COOKIE_NAME, create_session, hash_password, session_is_valid, verify_password
from app.cache import CachingProvider
from app.main import Settings, create_app
from core.clock import market_today
from core.exceptions import DataInsufficientError
from data.providers.brapi import BrapiProvider
from db.client import Database, migrate
from tests.test_api import NOW, PASSWORD, SECRET, FakeProvider


@pytest.fixture
def database(tmp_path):
    db = Database(str(tmp_path / "h.db"))
    migrate(db)
    return db


def client_from(database, ip="1.1.1.1", settings=None, provider=None, clock=lambda: NOW):
    config = settings or Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True, trust_proxy=True)
    source = provider or FakeProvider()
    app = create_app(config, lambda: database, lambda _: source, now=clock)
    return TestClient(app, base_url="https://testserver", headers={"x-vercel-forwarded-for": ip})


class TestPassword:
    def test_production_cost_and_legacy_format(self, monkeypatch):
        monkeypatch.undo()
        stored = hash_password("senha")
        assert stored.split("$")[1] == str(2**17)
        assert verify_password("senha", stored)
        assert not verify_password("outra", stored)

    def test_legacy_hash_still_verifies(self):
        salt = bytes(16)
        derived = auth.hashlib.scrypt(b"senha", salt=salt, n=2**14, r=8, p=1, dklen=32)
        assert verify_password("senha", f"scrypt${salt.hex()}${derived.hex()}")

    @pytest.mark.parametrize("stored", ["", "scrypt", "md5$a$b", "scrypt$zz$zz", "scrypt$a$b$c$d$e"])
    def test_malformed_hash_is_refused(self, stored):
        assert not verify_password("x", stored)


class TestLoginLimits:
    def test_third_party_cannot_lock_the_owner_out(self, database):
        attacker = client_from(database, ip="6.6.6.6")
        for _ in range(5):
            assert attacker.post("/api/login", json={"password": "errada"}).status_code == 401
        assert attacker.post("/api/login", json={"password": PASSWORD}).status_code == 429
        owner = client_from(database, ip="2.2.2.2")
        assert owner.post("/api/login", json={"password": PASSWORD}).status_code == 200

    def test_correct_login_only_clears_its_own_origin(self, database):
        attacker = client_from(database, ip="6.6.6.6")
        for _ in range(5):
            attacker.post("/api/login", json={"password": "errada"})
        client_from(database, ip="2.2.2.2").post("/api/login", json={"password": PASSWORD})
        assert attacker.post("/api/login", json={"password": PASSWORD}).status_code == 429

    def test_block_expires_after_the_window(self, database):
        moment = {"now": NOW}
        client = client_from(database, clock=lambda: moment["now"])
        for _ in range(5):
            client.post("/api/login", json={"password": "errada"})
        moment["now"] = NOW + timedelta(minutes=16)
        assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200

    def test_distributed_attack_hits_the_global_limit(self, database):
        for index in range(100):
            auth.record_failure(database, NOW, f"origem-{index}")
        assert client_from(database, ip="9.9.9.9").post("/api/login", json={"password": PASSWORD}).status_code == 429

    def test_ip_is_not_stored_in_clear(self, database):
        client_from(database, ip="6.6.6.6").post("/api/login", json={"password": "errada"})
        assert "6.6.6.6" not in str(database.fetch("SELECT * FROM login_failures"))

    def test_forwarded_header_is_ignored_outside_the_proxy(self, database):
        settings = Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True, trust_proxy=False)
        for index in range(5):
            client_from(database, ip=f"3.3.3.{index}", settings=settings).post("/api/login", json={"password": "errada"})
        blocked = client_from(database, ip="4.4.4.4", settings=settings)
        assert blocked.post("/api/login", json={"password": PASSWORD}).status_code == 429


class TestSessions:
    def test_logout_revokes_a_copied_cookie(self, database):
        moment = {"now": NOW}
        client = client_from(database, clock=lambda: moment["now"])
        client.post("/api/login", json={"password": PASSWORD})
        stolen = client.cookies.get(COOKIE_NAME)
        assert client.post("/api/logout").status_code == 200
        copy = client_from(database, clock=lambda: moment["now"])
        copy.cookies.set(COOKIE_NAME, stolen, path="/api")
        assert copy.get("/api/status").status_code == 401

    def test_logout_without_session_revokes_nothing(self, database):
        client = client_from(database)
        client.post("/api/login", json={"password": PASSWORD})
        client_from(database).post("/api/logout")
        assert client.get("/api/status").status_code == 200

    def test_login_works_again_after_logout(self, database):
        moment = {"now": NOW}
        client = client_from(database, clock=lambda: moment["now"])
        client.post("/api/login", json={"password": PASSWORD})
        client.post("/api/logout")
        moment["now"] = NOW + timedelta(seconds=2)
        client.post("/api/login", json={"password": PASSWORD})
        assert client.get("/api/status").status_code == 200

    @pytest.mark.parametrize("token", ["", "a", "a.b", "a.b.c.d", "1.2.3", "9999999999.1.é"])
    def test_malformed_tokens(self, token):
        assert not session_is_valid(token, SECRET, NOW)

    def test_signature_covers_both_times(self):
        token = create_session(SECRET, NOW)
        expires, issued, signature = token.split(".")
        assert not session_is_valid(f"{int(expires) + 999}.{issued}.{signature}", SECRET, NOW)

    def test_unexpected_error_does_not_leak_details(self, database):
        class Broken(FakeProvider):
            def get_market_snapshot(self, symbol):
                raise RuntimeError("detalhe-interno-secreto")

        app = create_app(
            Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True), lambda: database, lambda _: Broken(), now=lambda: NOW
        )
        client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
        client.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
        response = client.get("/api/assets/PETR4")
        assert response.status_code == 500
        assert "detalhe-interno-secreto" not in response.text


class TestMarketTime:
    def test_after_21h_in_sao_paulo_is_still_today(self):
        assert market_today(datetime(2026, 11, 4, 1, 30, tzinfo=timezone.utc)) == date(2026, 11, 3)

    def test_expiring_today_is_listed_at_night(self, database):
        class Today(FakeProvider):
            def get_expirations(self, underlying):
                return [date(2026, 11, 3), date(2026, 12, 18)]

        night = datetime(2026, 11, 4, 1, 30, tzinfo=timezone.utc)
        client = client_from(database, provider=Today(), clock=lambda: night)
        client.cookies.set(COOKIE_NAME, create_session(SECRET, night), path="/api")
        assert client.get("/api/assets/PETR4/expirations").json()["expirations"][0] == "2026-11-03"


def brapi(handler):
    return BrapiProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))


class TestSourceFailures:
    @pytest.mark.parametrize(
        "body", [b"<html>manutencao</html>", b'{"results":[{"data":{"regularMarketPrice":10}}]}', b'{"results":"x"}']
    )
    def test_unexpected_answers_become_insufficient(self, body):
        provider = brapi(lambda request: httpx.Response(200, content=body))
        with pytest.raises(DataInsufficientError):
            provider.get_market_snapshot("PETR4")

    def test_chain_with_missing_fields_becomes_insufficient(self):
        def handler(request):
            return httpx.Response(200, json={"date": "2026-10-30", "series": [{"symbol": "X"}], "analytics": [{"symbol": "X", "underlyingPrice": 1, "riskFreeRate": 0.1, "timeToExpirationYears": 0.1}]})

        with pytest.raises(DataInsufficientError):
            brapi(handler).get_option_chain("PETR4", date(2026, 12, 18))

    def test_rate_limit_stops_further_calls(self):
        calls = []

        def handler(request):
            calls.append(request.url.path)
            return httpx.Response(429, json={})

        provider = brapi(handler)
        for _ in range(3):
            with pytest.raises(DataInsufficientError):
                provider.get_market_snapshot("PETR4")
        assert len(calls) == 1


class TestCacheRobustness:
    def test_incompatible_entry_is_treated_as_missing(self, database):
        inner = FakeProvider()
        cached = CachingProvider(inner, database, now=lambda: NOW)
        for key, payload in (("snapshot:PETR4", '{"campo_antigo":1}'), ("chain:PETR4:2026-12-18", "lixo")):
            database.run("INSERT INTO provider_cache (key,payload,fetched_at) VALUES (?,?,?)", (key, payload, NOW.isoformat()))
        assert cached.get_market_snapshot("PETR4").price > 0
        assert cached.get_option_chain("PETR4", date(2026, 12, 18)).quotes
        assert inner.calls["snapshot"] == 1 and inner.calls["chain"] == 1

    def test_old_event_entries_are_cleaned(self, database):
        moment = {"now": NOW}
        cached = CachingProvider(FakeProvider(), database, now=lambda: moment["now"])
        for day in (date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)):
            cached.get_upcoming_events("PETR4", day)
        cached.get_upcoming_events("VALE3", date(2026, 11, 5))
        keys = sorted(row[0] for row in database.fetch("SELECT key FROM provider_cache WHERE key LIKE 'events:%'"))
        assert keys == ["events:PETR4:2026-11-05", "events:VALE3:2026-11-05"]

    def test_cron_purges_old_cache_and_keeps_iv_history(self, database):
        old = (NOW - timedelta(days=30)).isoformat()
        database.run("INSERT INTO provider_cache (key,payload,fetched_at) VALUES ('chain:X:2025-01-01','{}',?)", (old,))
        database.run("INSERT INTO iv_history (symbol,day,iv,expiry,fetched_at) VALUES ('X','2025-01-01',0.3,'2025-02-01',?)", (old,))
        settings = Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True, cron_secret="c" * 40)
        client = client_from(database, settings=settings)
        assert client.get("/api/cron/scan", headers={"Authorization": "Bearer " + "c" * 40}).status_code == 200
        assert database.fetch("SELECT count(*) FROM provider_cache WHERE key = 'chain:X:2025-01-01'")[0][0] == 0
        assert database.fetch("SELECT count(*) FROM iv_history WHERE symbol = 'X'")[0][0] == 1


class TestScanBudget:
    def test_expired_deadline_reports_incomplete_without_calling_source(self, database):
        from app import service

        source = FakeProvider()
        result = service.scanner(source, ["PETR4", "VALE3"], NOW, budget_seconds=0)
        assert result["complete"] is False
        assert result["incomplete_symbols"] == ["PETR4", "VALE3"]
        assert source.calls["snapshot"] == 0
        assert all(row["data_status"] == "INDISPONIVEL" for row in result["rows"])

    def test_one_failure_does_not_invalidate_the_rest(self, database):
        from app import service

        class Partial(FakeProvider):
            def get_market_snapshot(self, symbol):
                if symbol == "VALE3":
                    raise RuntimeError("falha inesperada")
                return super().get_market_snapshot(symbol)

        result = service.scanner(Partial(), ["PETR4", "VALE3"], NOW)
        rows = {row["symbol"]: row for row in result["rows"]}
        assert rows["PETR4"]["price"] is not None
        assert rows["VALE3"]["data_status"] == "INDISPONIVEL"
        assert result["complete"] is False


class TestDataStatus:
    def test_each_state(self):
        from app.service import data_status

        now = NOW
        fresh = (now - timedelta(minutes=2)).isoformat()
        stale = (now - timedelta(hours=3)).isoformat()
        assert data_status(10.0, fresh, [], now) == "REAL"
        assert data_status(10.0, stale, [], now) == "ATRASADO"
        assert data_status(10.0, fresh, ["Opções: sem token"], now) == "INCOMPLETO"
        assert data_status(None, None, ["Cotação: erro"], now) == "INDISPONIVEL"
