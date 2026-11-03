"""Login de um único usuário, por senha, com sessão em cookie assinado.

Sair invalida todas as sessões emitidas até aquele instante. Trocar SESSION_SECRET também.
O limite por origem impede que terceiros bloqueiem o proprietário; o limite global, bem
mais alto e também temporário, contém ataques distribuídos.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from db.client import Database

COOKIE_NAME = "b3_session"
SESSION_SECONDS = 7 * 86400
MIN_SECRET_LENGTH = 32
MAX_FAILURES_PER_ORIGIN = 5
MAX_FAILURES_GLOBAL = 100
FAILURE_WINDOW = timedelta(minutes=15)
_SCRYPT_N = 2**17
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32
# Parâmetros do formato antigo: "scrypt$sal$hash".
_LEGACY_N = 2**14


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=_DKLEN, maxmem=2 * 128 * n * r)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = _derive(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        parts = stored.split("$")
        if parts[0] != "scrypt":
            return False
        if len(parts) == 3:
            n, r, p, salt, expected = _LEGACY_N, 8, 1, parts[1], parts[2]
        elif len(parts) == 6:
            n, r, p, salt, expected = int(parts[1]), int(parts[2]), int(parts[3]), parts[4], parts[5]
        else:
            return False
        return hmac.compare_digest(_derive(password, bytes.fromhex(salt), n, r, p), bytes.fromhex(expected))
    except ValueError:
        return False


def _signature(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session(secret: str, now: datetime) -> str:
    issued = int(now.timestamp())
    payload = f"{issued + SESSION_SECONDS}.{issued}"
    return f"{payload}.{_signature(payload, secret)}"


def session_is_valid(token: str | None, secret: str, now: datetime, revoked_before: int = 0) -> bool:
    if not token or token.count(".") != 2:
        return False
    expires, issued, signature = token.split(".")
    if not hmac.compare_digest(signature.encode(), _signature(f"{expires}.{issued}", secret).encode()):
        return False
    if not expires.isdigit() or not issued.isdigit():
        return False
    return int(expires) > now.timestamp() and int(issued) >= revoked_before


def revoked_before(database: Database) -> int:
    rows = database.fetch("SELECT revoked_before FROM auth_state WHERE id = 1")
    return rows[0][0] if rows else 0


def revoke_sessions(database: Database, now: datetime) -> None:
    # +1: a sessão emitida neste mesmo segundo também cai.
    moment = int(now.timestamp()) + 1
    database.run(
        "INSERT INTO auth_state (id, revoked_before) VALUES (1, ?) "
        "ON CONFLICT (id) DO UPDATE SET revoked_before = excluded.revoked_before",
        (moment,),
    )


def origin_key(ip: str, secret: str) -> str:
    """O banco não guarda o IP em claro."""
    return _signature(f"login-origin:{ip}", secret)[:32]


def too_many_failures(database: Database, now: datetime, key: str) -> bool:
    since = (now - FAILURE_WINDOW).isoformat()
    database.run("DELETE FROM login_failures WHERE at < ?", (since,))
    per_origin = database.fetch("SELECT COUNT(*) FROM login_failures WHERE ip_key = ?", (key,))[0][0]
    if per_origin >= MAX_FAILURES_PER_ORIGIN:
        return True
    return database.fetch("SELECT COUNT(*) FROM login_failures")[0][0] >= MAX_FAILURES_GLOBAL


def record_failure(database: Database, now: datetime, key: str) -> None:
    database.run("INSERT INTO login_failures (at, ip_key) VALUES (?, ?)", (now.isoformat(), key))


def clear_failures(database: Database, key: str) -> None:
    """Só a origem que acertou a senha: o erro de outras continua contando."""
    database.run("DELETE FROM login_failures WHERE ip_key = ?", (key,))
