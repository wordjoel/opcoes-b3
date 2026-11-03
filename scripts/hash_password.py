"""Gera APP_PASSWORD_HASH e SESSION_SECRET: python -m scripts.hash_password"""

import secrets
from getpass import getpass

from app.auth import hash_password


def main() -> None:
    password = getpass("Senha do app: ")
    if len(password) < 12:
        raise SystemExit("Use pelo menos 12 caracteres.")
    if password != getpass("Repita a senha: "):
        raise SystemExit("As senhas não conferem.")
    print(f"APP_PASSWORD_HASH={hash_password(password)}")
    print(f"SESSION_SECRET={secrets.token_hex(32)}")


if __name__ == "__main__":
    main()
