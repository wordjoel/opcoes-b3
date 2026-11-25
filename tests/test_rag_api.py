"""HTTP das rotas documentais do RAG: autenticação, limites, busca e degradação.

Todos os bancos são SQLite temporários; nenhum banco de produção é tocado e a
migration 0010 não é aplicada a qualquer ambiente real.
"""

import base64

from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, create_session, hash_password
from app.main import Settings, create_app
from db.client import Database, MIGRATIONS, migrate
from tests.test_api import NOW, PASSWORD, SECRET, FakeProvider
from tests.test_rag import tiny_pdf

PDF = tiny_pdf("Manual PETR4: hedge com borboleta de call protege a posição contra queda moderada.")
CONTENT = base64.b64encode(PDF).decode("ascii")
DOCUMENT = {"name": "manual.pdf", "content_base64": CONTENT, "source": "teste"}


def client_for(db: Database, authenticated: bool = True) -> TestClient:
    config = Settings(hash_password(PASSWORD), SECRET, True, insecure_cookie=True)
    app = create_app(config, lambda: db, lambda _: FakeProvider(), now=lambda: NOW)
    client = TestClient(app, base_url="https://testserver")
    if authenticated:
        client.cookies.set(COOKIE_NAME, create_session(SECRET, NOW), path="/api")
    return client


def migrated_db(tmp_path) -> Database:
    db = Database(str(tmp_path / "rag-api.db"))
    migrate(db)
    return db


def db_without_rag(tmp_path) -> Database:
    """Banco com as tabelas de autenticação, mas sem a migration documental."""
    db = Database(str(tmp_path / "sem-rag.db"))
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.stem.startswith("0010"):
            continue
        db.run_script(path.read_text(encoding="utf-8"))
    return db


class TestDocumentRoutes:
    def test_unauthenticated_requests_are_refused(self, tmp_path):
        client = client_for(migrated_db(tmp_path), authenticated=False)
        assert client.post("/api/jarbas/documents", json=DOCUMENT).status_code == 401
        assert client.get("/api/jarbas/documents/search", params={"q": "PETR4"}).status_code == 401

    def test_invalid_documents_are_refused(self, tmp_path):
        client = client_for(migrated_db(tmp_path))
        cases = [
            {**DOCUMENT, "name": "../malware.exe"},
            {**DOCUMENT, "name": "sem-extensao"},
            {**DOCUMENT, "content_base64": "%%%"},
            {**DOCUMENT, "content_base64": ""},
        ]
        for body in cases:
            assert client.post("/api/jarbas/documents", json=body).status_code == 422

    def test_document_above_limit_is_refused(self, tmp_path):
        client = client_for(migrated_db(tmp_path))
        huge = base64.b64encode(b"x" * 4_000_001).decode("ascii")
        response = client.post("/api/jarbas/documents", json={**DOCUMENT, "content_base64": huge})
        assert response.status_code == 413
        assert "4 MB" in response.json()["detail"]

    def test_valid_document_is_indexed_and_deduplicated(self, tmp_path):
        client = client_for(migrated_db(tmp_path))
        first = client.post("/api/jarbas/documents", json=DOCUMENT)
        assert first.status_code == 200
        body = first.json()
        assert set(body) == {"document_id", "name", "pages", "chunks", "updated"}
        assert body["name"] == "manual.pdf" and body["pages"] == 1 and body["chunks"] >= 1 and body["updated"] is True
        second = client.post("/api/jarbas/documents", json=DOCUMENT).json()
        assert second["document_id"] == body["document_id"] and second["updated"] is False

    def test_search_returns_indexed_content_only(self, tmp_path):
        client = client_for(migrated_db(tmp_path))
        assert client.get("/api/jarbas/documents/search", params={"q": "hedge PETR4 borboleta"}).json() == {"chunks": []}
        assert client.post("/api/jarbas/documents", json=DOCUMENT).status_code == 200
        found = client.get("/api/jarbas/documents/search", params={"q": "hedge PETR4 borboleta"}).json()["chunks"]
        assert found and found[0]["name"] == "manual.pdf"
        assert "PETR4" in found[0]["content"] and found[0]["page"] == 1
        assert client.get("/api/jarbas/documents/search").status_code == 422

    def test_processing_failure_is_safe(self, tmp_path, monkeypatch):
        from app import main

        def fail(*_args, **_kwargs):
            raise RuntimeError("falha interna que nunca deve vazar")

        monkeypatch.setattr(main, "ingest_bytes", fail)
        client = client_for(migrated_db(tmp_path))
        response = client.post("/api/jarbas/documents", json=DOCUMENT)
        assert response.status_code == 503
        assert "falha interna" not in response.text
        assert response.json()["detail"] == "Não foi possível indexar este documento agora."

    def test_missing_migration_degrades_without_inventing_results(self, tmp_path):
        client = client_for(db_without_rag(tmp_path))
        upload = client.post("/api/jarbas/documents", json=DOCUMENT)
        assert upload.status_code == 503
        assert upload.json()["detail"] == "Não foi possível indexar este documento agora."
        found = client.get("/api/jarbas/documents/search", params={"q": "PETR4"})
        assert found.status_code == 200 and found.json() == {"chunks": []}

    def test_query_validation_refuses_empty_and_too_long(self, tmp_path):
        client = client_for(migrated_db(tmp_path))
        assert client.get("/api/jarbas/documents/search", params={"q": ""}).status_code == 422
        assert client.get("/api/jarbas/documents/search", params={"q": "x" * 501}).status_code == 422
