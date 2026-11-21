import pytest

from app import auth
from core import retry


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    """O custo real leva mais de 1 s por senha. Um teste específico confere o custo de produção."""
    monkeypatch.setattr(auth, "_SCRYPT_N", 2**10)


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    """Os testes não dormem entre tentativas; o intervalo é conferido em test_retry.py."""
    monkeypatch.setattr(retry, "_sleep", lambda _: None)
