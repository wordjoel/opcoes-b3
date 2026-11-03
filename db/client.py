"""Acesso ao banco: Turso em produção, arquivo SQLite local em desenvolvimento.

Cada operação abre a própria conexão: a do libsql não é segura entre threads, e o
FastAPI atende rotas síncronas em um pool delas.
"""

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import libsql

LOCAL_DATABASE = Path(__file__).resolve().parent.parent / ".b3-local.db"
MIGRATIONS = Path(__file__).resolve().parent / "migrations"


class DatabaseError(Exception):
    """Banco indisponível ou com erro. A mensagem é segura para a interface."""


class Database:
    def __init__(self, url: str, auth_token: str | None = None) -> None:
        self._url = url
        self._auth_token = auth_token

    @classmethod
    def from_env(cls) -> "Database":
        url = os.environ.get("TURSO_DATABASE_URL")
        if url:
            return cls(url, os.environ.get("TURSO_AUTH_TOKEN"))
        if os.environ.get("VERCEL"):
            # Na Vercel o disco é efêmero: um arquivo local perderia tudo em silêncio.
            raise DatabaseError("TURSO_DATABASE_URL não configurada")
        return cls(str(LOCAL_DATABASE))

    @contextmanager
    def _connection(self) -> Iterator[libsql.Connection]:
        try:
            options = {"auth_token": self._auth_token} if self._auth_token else {}
            connection = libsql.connect(self._url, **options)
            try:
                yield connection
            finally:
                connection.close()
        except DatabaseError:
            raise
        except Exception as error:
            # O texto original pode conter a URL do banco.
            raise DatabaseError(f"falha no banco ({type(error).__name__})") from None

    def fetch(self, sql: str, params: Sequence = ()) -> list[tuple]:
        with self._connection() as connection:
            return list(connection.execute(sql, tuple(params)).fetchall())

    def run(self, sql: str, params: Sequence = ()) -> None:
        with self._connection() as connection:
            connection.execute(sql, tuple(params))
            connection.commit()

    def run_script(self, script: str) -> None:
        with self._connection() as connection:
            connection.executescript(script)
            connection.commit()


def _available() -> dict[str, str]:
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.sql"))}


def pending_migrations(database: Database) -> list[str]:
    database.run("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    applied = {row[0] for row in database.fetch("SELECT version FROM schema_migrations")}
    return [version for version in _available() if version not in applied]


def migrate(database: Database) -> list[str]:
    """Aplica as migrations pendentes, em ordem. Devolve as aplicadas."""
    scripts = _available()
    pending = pending_migrations(database)
    for version in pending:
        database.run_script(scripts[version])
        database.run(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )
    return pending
