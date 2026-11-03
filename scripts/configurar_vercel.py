"""Configura os segredos do app sem mostrar nenhum valor.

Rode em um terminal próprio, na pasta do projeto:

    .venv/Scripts/python -m scripts.configurar_vercel            (cadastra em preview)
    .venv/Scripts/python -m scripts.configurar_vercel --producao (cadastra também em produção)

Pede a senha do app e a chave da brapi só se ainda não estiverem em .env.turso.
"""

import secrets
import subprocess
import sys
from collections.abc import Callable
from getpass import getpass
from pathlib import Path

import httpx

from app.auth import hash_password

ENV_FILE = Path(".env.turso")
MIN_PASSWORD = 12
VARIABLES = (
    "TURSO_DATABASE_URL",
    "TURSO_AUTH_TOKEN",
    "APP_PASSWORD_HASH",
    "SESSION_SECRET",
    "CRON_SECRET",
    "BRAPI_API_KEY",
)


def read_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#"))


def ask_password() -> str:
    password = getpass("Crie a senha do app (mínimo de 12 caracteres): ")
    if len(password) < MIN_PASSWORD:
        raise SystemExit("Senha curta demais. Nada foi alterado.")
    if password != getpass("Repita a senha: "):
        raise SystemExit("As senhas não conferem. Nada foi alterado.")
    return password


def prepare(
    path: Path,
    password: Callable[[], str] = ask_password,
    brapi: Callable[[], str] = lambda: getpass("Chave da brapi (Enter para deixar sem): ").strip(),
) -> dict[str, str]:
    """Completa o arquivo local sem nunca trocar um valor que já existe."""
    values = read_values(path)
    added: dict[str, str] = {}
    if not values.get("APP_PASSWORD_HASH"):
        added["APP_PASSWORD_HASH"] = hash_password(password())
    for name in ("SESSION_SECRET", "CRON_SECRET"):
        if not values.get(name):
            added[name] = secrets.token_hex(32)
    if not values.get("BRAPI_API_KEY"):
        key = brapi()
        if key:
            added["BRAPI_API_KEY"] = key
    if added:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        separator = "" if not text or text.endswith("\n") else "\n"
        path.write_text(text + separator + "".join(f"{name}={value}\n" for name, value in added.items()), encoding="utf-8")
    return {**values, **added}


def brapi_status(key: str | None) -> str:
    """Testa com um ativo fora do acesso livre: só responde 200 se a chave incluir opções."""
    if not key:
        return "sem chave: só a PETR4 terá opções"
    try:
        expirations = httpx.get(
            "https://brapi.dev/api/v2/options/expirations",
            params={"underlying": "VALE3"},
            headers={"Authorization": f"Bearer {key}"},
            timeout=20,
        )
    except httpx.HTTPError as error:
        return f"não testada ({type(error).__name__})"
    return {200: "válida, com opções", 401: "RECUSADA: chave inválida", 403: "RECUSADA: o plano não inclui opções"}.get(
        expirations.status_code, f"resposta {expirations.status_code}"
    )


def vercel_add(name: str, value: str, target: str) -> bool:
    result = subprocess.run(
        f"npx vercel env add {name} {target} --force --yes --sensitive",
        input=value,
        text=True,
        capture_output=True,
        shell=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0


def push(values: dict[str, str], targets: list[str], add: Callable[[str, str, str], bool] = vercel_add) -> list[str]:
    """Devolve o que falhou. A saída só traz nomes de variáveis."""
    failed = []
    for name in VARIABLES:
        if not values.get(name):
            print(f"{name}: ausente, não cadastrada")
            continue
        for target in targets:
            success = add(name, values[name], target)
            print(f"{name} em {target}: {'ok' if success else 'FALHOU'}")
            if not success:
                failed.append(f"{name}/{target}")
    return failed


def main() -> None:
    targets = ["preview", "production"] if "--producao" in sys.argv else ["preview"]
    values = prepare(ENV_FILE)
    print(f"brapi: {brapi_status(values.get('BRAPI_API_KEY'))}")
    failed = push(values, targets)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
