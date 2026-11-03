"""Carrega no Turso o histórico oficial da B3, de graça. Só acrescenta; pode repetir sem efeito.

    .venv/Scripts/python -m scripts.carregar_historico_b3

Baixa os arquivos anuais (cerca de 90 MB cada), guarda barras diárias das ações com opções e a vol
no dinheiro de cada pregão dos ativos acompanhados. O que já existe no banco não é alterado.
"""

import sys
import tempfile
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from core.config import load_local_env
from data.providers.cotahist import (
    SelicRates,
    Session,
    atm_iv_sample,
    optioned_stocks,
    parse_line,
    store_bars,
    store_iv_samples,
)
from db.client import Database, migrate

_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
_HEADERS = {"User-Agent": "Mozilla/5.0 (B3 Opcoes Pro)"}
_DAYS_BACK = 380


def _download(year: int, folder: Path) -> Path:
    target = folder / f"A{year}.zip"
    with httpx.stream("GET", _URL.format(year=year), headers=_HEADERS, timeout=300, follow_redirects=True) as response:
        response.raise_for_status()
        with target.open("wb") as output:
            for chunk in response.iter_bytes(1 << 20):
                output.write(chunk)
    return target


def _read_sessions(path: Path, start: date, sessions: dict[date, Session]) -> None:
    with zipfile.ZipFile(path) as archive, archive.open(archive.namelist()[0]) as source:
        for raw in source:
            if raw[24:27] not in (b"010", b"070", b"080"):
                continue
            parsed = parse_line(raw.decode("latin-1").rstrip("\r\n"))
            if parsed and parsed[0] >= start:
                sessions.setdefault(parsed[0], Session(parsed[0])).add(parsed[1])


def main() -> int:
    load_local_env()
    now = datetime.now(timezone.utc)
    start = now.date() - timedelta(days=_DAYS_BACK)
    database = Database.from_env()
    print("migrações aplicadas:", migrate(database))
    watchlist = [row[0] for row in database.fetch("SELECT symbol FROM watchlist")]
    sessions: dict[date, Session] = {}
    with tempfile.TemporaryDirectory() as folder:
        for year in range(start.year, now.year + 1):
            print(f"baixando {year}...", flush=True)
            _read_sessions(_download(year, Path(folder)), start, sessions)
    days = sorted(sessions)
    print(f"{len(days)} pregões, de {days[0]} a {days[-1]}", flush=True)
    rates = SelicRates()
    rates.load_range(days[0], days[-1])
    bars = samples = 0
    for day in days:
        session = sessions[day]
        bars += store_bars(database, day, optioned_stocks(session), now)
        rate = rates.rate_on(day)
        found = [(symbol, sample) for symbol in watchlist if (sample := atm_iv_sample(session, symbol, rate))]
        samples += store_iv_samples(database, found, now)
    print(f"barras enviadas: {bars}; amostras de vol enviadas: {samples}")
    print("no banco:", database.fetch("SELECT count(*), count(DISTINCT symbol), max(day) FROM b3_daily_bars")[0])
    print("vol por ativo:", database.fetch("SELECT symbol, count(iv) FROM iv_history GROUP BY symbol"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
