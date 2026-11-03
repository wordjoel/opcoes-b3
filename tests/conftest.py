import pytest

from app import auth


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    """O custo real leva mais de 1 s por senha. Um teste específico confere o custo de produção."""
    monkeypatch.setattr(auth, "_SCRYPT_N", 2**10)
