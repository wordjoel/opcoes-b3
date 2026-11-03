"""O script de configuração não troca valores existentes nem mostra segredos."""

import pytest

from app.auth import verify_password
from scripts.configurar_vercel import VARIABLES, brapi_status, prepare, push, read_values


def test_creates_only_what_is_missing(tmp_path):
    env = tmp_path / ".env.turso"
    env.write_text("TURSO_AUTH_TOKEN=existente\n", encoding="utf-8")
    values = prepare(env, password=lambda: "senha-de-teste-12", brapi=lambda: "chave")
    assert values["TURSO_AUTH_TOKEN"] == "existente"
    assert verify_password("senha-de-teste-12", values["APP_PASSWORD_HASH"])
    assert len(values["SESSION_SECRET"]) == 64 and len(values["CRON_SECRET"]) == 64
    assert read_values(env) == values


def test_running_again_changes_nothing(tmp_path):
    env = tmp_path / ".env.turso"
    prepare(env, password=lambda: "senha-de-teste-12", brapi=lambda: "chave")
    before = env.read_text(encoding="utf-8")

    def must_not_ask():
        raise AssertionError("não deveria pedir de novo")

    prepare(env, password=must_not_ask, brapi=must_not_ask)
    assert env.read_text(encoding="utf-8") == before


def test_plain_password_never_reaches_the_file(tmp_path):
    env = tmp_path / ".env.turso"
    prepare(env, password=lambda: "senha-de-teste-12", brapi=lambda: "")
    assert "senha-de-teste-12" not in env.read_text(encoding="utf-8")
    assert "BRAPI_API_KEY" not in read_values(env)


def test_push_reports_failures_and_never_prints_values(capsys):
    values = {name: f"valor-secreto-{name}" for name in VARIABLES}
    failed = push(values, ["preview"], add=lambda name, value, target: name != "CRON_SECRET")
    assert failed == ["CRON_SECRET/preview"]
    assert "valor-secreto" not in capsys.readouterr().out


def test_push_skips_absent_values(capsys):
    calls = []
    push({"TURSO_AUTH_TOKEN": "x"}, ["preview", "production"], add=lambda *args: calls.append(args[0::2]) or True)
    assert calls == [("TURSO_AUTH_TOKEN", "preview"), ("TURSO_AUTH_TOKEN", "production")]
    assert "BRAPI_API_KEY: ausente" in capsys.readouterr().out


def test_no_key_is_explained():
    assert "sem chave" in brapi_status(None)


@pytest.mark.parametrize("name", ["APP_PASSWORD_HASH", "SESSION_SECRET", "CRON_SECRET", "BRAPI_API_KEY", "TURSO_AUTH_TOKEN"])
def test_all_required_variables_are_covered(name):
    assert name in VARIABLES
