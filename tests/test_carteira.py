"""Carteira persistida, supervisor e gestor de risco sobre o banco, e registro das decisões."""

import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, create_session, hash_password
from app.main import Settings, create_app
from db.client import Database, migrate
from tests.test_api import EXPIRY, NOW, PASSWORD, SECRET, FakeProvider


def make_client(db):
    app = create_app(Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True), lambda: db, lambda _: FakeProvider(), now=lambda: NOW)
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
    return client


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "carteira.db"))
    migrate(database)
    return database


@pytest.fixture
def client(db):
    return make_client(db)


FILL = {"symbol": "PETRL500", "side": "BUY", "quantity": 100, "price": 1.5, "fees_brl": 2.0, "trade_day": "2026-11-03"}


class TestPortfolio:
    def test_starts_empty(self, client):
        view = client.get("/api/portfolio").json()
        assert view["settings"] is None and view["positions"] == [] and view["fills"] == []

    def test_fills_rebuild_positions_cash_and_result(self, client):
        client.put("/api/portfolio/settings", json={"initial_cash_brl": 1000, "max_position_size": 500})
        client.post("/api/portfolio/fills", json=FILL)
        view = client.post("/api/portfolio/fills", json={**FILL, "side": "SELL", "quantity": 40, "price": 2.0, "fees_brl": 1.0}).json()
        assert view["positions"] == [{"symbol": "PETRL500", "quantity": 60, "avg_entry_price": 1.5}]
        assert view["realized_pnl_brl"] == pytest.approx(20.0)
        assert view["fees_brl"] == pytest.approx(3.0)
        assert view["realized_net_brl"] == pytest.approx(17.0)
        assert view["cash_brl"] == pytest.approx(1000 - 150 + 80 - 3)

    def test_state_survives_another_instance(self, db, client):
        # Na Vercel cada requisição pode cair em outra instância: o estado vem do banco.
        client.put("/api/portfolio/settings", json={"initial_cash_brl": 1000, "max_position_size": 500})
        client.post("/api/portfolio/fills", json=FILL)
        other = make_client(db).get("/api/portfolio").json()
        assert other["positions"][0]["quantity"] == 100

    def test_void_keeps_the_record_and_removes_the_effect(self, client):
        client.put("/api/portfolio/settings", json={"initial_cash_brl": 1000, "max_position_size": 500})
        identity = client.post("/api/portfolio/fills", json=FILL).json()["fills"][0]["id"]
        view = client.post(f"/api/portfolio/fills/{identity}/void").json()
        assert view["positions"] == [] and view["cash_brl"] == pytest.approx(1000)
        assert view["fills"][0]["voided_at"] is not None
        assert client.post("/api/portfolio/fills/999/void").status_code == 404

    @pytest.mark.parametrize(
        "body",
        [
            {**FILL, "side": "HOLD"},
            {**FILL, "quantity": 0},
            {**FILL, "price": -1},
            {**FILL, "trade_day": "2030-01-01"},
            {**FILL, "symbol": "PETR L500"},
        ],
    )
    def test_invalid_fills_are_refused(self, client, body):
        assert client.post("/api/portfolio/fills", json=body).status_code == 422
        assert client.get("/api/portfolio").json()["fills"] == []

    def test_requires_session(self, db):
        app = create_app(Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True), lambda: db, lambda _: FakeProvider(), now=lambda: NOW)
        anonymous = TestClient(app, base_url="https://testserver")
        assert anonymous.get("/api/portfolio").status_code == 401
        assert anonymous.post("/api/portfolio/fills", json=FILL).status_code == 401
        assert anonymous.get("/api/decisions").status_code == 401


def strategies(client):
    return client.get(f"/api/assets/PETR4/strategies?expiry={EXPIRY}").json()


class TestReviewWithPortfolio:
    def test_without_settings_the_review_is_skipped(self, client):
        view = strategies(client)
        assert view["portfolio_configured"] is False
        assert all(row["portfolio"] is None for row in view["candidates"])

    def test_exposure_limit_rejects_through_supervisor(self, client):
        client.put("/api/settings/risk", json={"capital_brl": 10_000, "max_loss_pct": 5})
        client.put("/api/settings/costs", json={"per_order_brl": 0, "fee_pct": 0, "income_tax_pct": 15})
        client.put("/api/portfolio/settings", json={"initial_cash_brl": 100_000, "max_position_size": 10})
        view = strategies(client)
        assert view["portfolio_configured"] is True
        for row in view["candidates"]:
            assert row["portfolio"]["decision"] == "REJECTED"
            assert row["decision"]["status"] == "REPROVADA"
            assert any(reason.startswith("carteira: EXPOSURE_LIMIT") for reason in row["decision"]["reasons"])

    def test_portfolio_approval_does_not_approve_alone(self, client):
        client.put("/api/portfolio/settings", json={"initial_cash_brl": 100_000, "max_position_size": 100_000})
        view = strategies(client)
        long_call = next(row for row in view["candidates"] if row["key"] == "long_call")
        assert long_call["portfolio"]["decision"] == "APPROVED"
        assert long_call["decision"]["status"] == "INCOMPLETA"


class TestDecisionLog:
    def test_each_decision_is_recorded_once_with_inputs(self, client):
        first = strategies(client)
        strategies(client)
        log = client.get("/api/decisions").json()["decisions"]
        assert len(log) == len(first["candidates"])
        entry = next(item for item in log if item["structure_key"] == "long_call")
        assert entry["symbol"] == "PETR4" and entry["expiry"] == EXPIRY.isoformat()
        assert entry["inputs"]["market_date"] == first["market_date"]
        assert entry["inputs"]["legs"][0]["symbol"]
        assert "capital e limite de perda não informados" in entry["missing"]

    def test_a_new_input_creates_a_new_entry(self, client):
        strategies(client)
        before = len(client.get("/api/decisions").json()["decisions"])
        client.put("/api/settings/risk", json={"capital_brl": 10_000, "max_loss_pct": 5})
        strategies(client)
        assert len(client.get("/api/decisions?symbol=PETR4").json()["decisions"]) > before

    def test_filter_validates_symbol(self, client):
        assert client.get("/api/decisions?symbol=x%20y").status_code == 400
