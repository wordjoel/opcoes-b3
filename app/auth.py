"""Login de um único usuário, por senha, com sessão em cookie assinado.

A sessão não fica guardada no servidor: trocar SESSION_SECRET invalida todas.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from db.client import Database

COOKIE_NAME = "b3_session"
SESSION_SECONDS = 7 * 86400
MIN_SECRET_LENGTH = 32
MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=15)
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
        return hmac.compare_digest(derived, bytes.fromhex(expected))
    except ValueError:
        return False


def _signature(expires: str, secret: str) -> str:
    return hmac.new(secret.encode(), expires.encode(), hashlib.sha256).hexdigest()


def create_session(secret: str, now: datetime) -> str:
    expires = str(int(now.timestamp()) + SESSION_SECONDS)
    return f"{expires}.{_signature(expires, secret)}"


def session_is_valid(token: str | None, secret: str, now: datetime) -> bool:
    if not token or "." not in token:
        return False
    expires, signature = token.split(".", 1)
    if not hmac.compare_digest(signature.encode(), _signature(expires, secret).encode()):
        return False
    return expires.isdigit() and int(expires) > now.timestamp()


def too_many_failures(database: Database, now: datetime) -> bool:
    since = (now - FAILURE_WINDOW).isoformat()
    database.run("DELETE FROM login_failures WHERE at < ?", (since,))
    return database.fetch("SELECT COUNT(*) FROM login_failures")[0][0] >= MAX_FAILURES


def record_failure(database: Database, now: datetime) -> None:
    database.run("INSERT INTO login_failures (at) VALUES (?)", (now.isoformat(),))


def clear_failures(database: Database) -> None:
    database.run("DELETE FROM login_failures")
