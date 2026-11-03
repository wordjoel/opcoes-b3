"""Posição da volatilidade implícita atual dentro do próprio histórico do ativo."""

from collections.abc import Sequence
from dataclasses import dataclass

from core.exceptions import DataInsufficientError

# Meio ano de amostras semanais: com menos, o intervalo ainda não representa o ativo.
MIN_SAMPLES = 26
HIGH_RANK = 80.0
LOW_RANK = 20.0


@dataclass(frozen=True)
class IvRank:
    # 0 a 100: posição entre a menor e a maior vol do período.
    rank: float
    # 0 a 100: parcela das amostras abaixo da vol atual.
    percentile: float
    low: float
    high: float
    samples: int


def iv_rank(current: float, history: Sequence[float], min_samples: int = MIN_SAMPLES) -> IvRank:
    if len(history) < min_samples:
        raise DataInsufficientError(f"{len(history)} amostras de vol implícita; o mínimo é {min_samples}")
    # A vol atual pode ser um novo extremo: entra no intervalo.
    low = min(*history, current)
    high = max(*history, current)
    if high == low:
        raise DataInsufficientError("vol implícita sem variação no período")
    return IvRank(
        rank=(current - low) / (high - low) * 100,
        percentile=sum(value < current for value in history) / len(history) * 100,
        low=low,
        high=high,
        samples=len(history),
    )
