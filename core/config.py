"""Convenções e limites globais. Não guarda segredos."""

import os
from dataclasses import dataclass
from pathlib import Path

BUSINESS_DAYS_PER_YEAR = 252
LOCAL_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.turso"


def load_local_env(path: Path = LOCAL_ENV_FILE) -> None:
    """Lê o arquivo local de credenciais, sem sobrescrever o ambiente. Na Vercel, ele não existe."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class DataQualityLimits:
    """Limites a partir dos quais um dado deixa de servir para análise."""

    # Idade máxima do dado frente ao relógio de referência.
    max_age_seconds: float = 20 * 60
    # Dados de fim de dia: cobre fim de semana com feriado prolongado.
    max_eod_age_seconds: float = 5 * 86400
    # Diferença máxima de horário entre o ativo e as opções de uma mesma análise.
    max_time_skew_seconds: float = 120
    # Tolerância de relógio para horários no futuro.
    max_future_seconds: float = 5
    # Diferença relativa máxima de preço entre duas fontes.
    max_source_divergence: float = 0.005
    # Intervalo em dias corridos entre barras que merece aviso.
    max_bar_gap_days: int = 5
    # Variação de um dia que pede conferência: pode ser fato de mercado ou erro da fonte.
    max_daily_move: float = 0.30
