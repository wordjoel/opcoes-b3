"""Convenções e limites globais. Não guarda segredos."""

from dataclasses import dataclass

BUSINESS_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class DataQualityLimits:
    """Limites a partir dos quais um dado deixa de servir para análise."""

    # Idade máxima do dado frente ao relógio de referência.
    max_age_seconds: float = 20 * 60
    # Diferença máxima de horário entre o ativo e as opções de uma mesma análise.
    max_time_skew_seconds: float = 120
    # Tolerância de relógio para horários no futuro.
    max_future_seconds: float = 5
    # Diferença relativa máxima de preço entre duas fontes.
    max_source_divergence: float = 0.005
    # Intervalo em dias corridos entre barras que merece aviso.
    max_bar_gap_days: int = 5
