"""Volatilidade implícita, histórica e EWMA, em decimal anualizado."""

from collections.abc import Sequence

import numpy as np
from scipy.optimize import brentq

from core.config import BUSINESS_DAYS_PER_YEAR
from core.exceptions import DataInsufficientError
from core.types import OptionKind
from quant.pricing.black_scholes import option_price

_MIN_VOL = 1e-4
_MAX_VOL = 5.0


def implied_volatility(
    kind: OptionKind, price: float, s: float, k: float, t: float, r: float, q: float = 0.0
) -> float | None:
    """None quando nenhuma volatilidade explica o preço (viola limites de arbitragem)."""
    if t <= 0 or price <= 0:
        return None
    low = option_price(kind, s, k, t, r, _MIN_VOL, q)
    high = option_price(kind, s, k, t, r, _MAX_VOL, q)
    if price < low or price > high:
        return None
    if price == low:
        return _MIN_VOL
    return float(brentq(lambda sigma: option_price(kind, s, k, t, r, sigma, q) - price, _MIN_VOL, _MAX_VOL, xtol=1e-8))


def _log_returns(closes: Sequence[float], min_observations: int) -> np.ndarray:
    prices = np.asarray(closes, dtype=float)
    if np.any(~np.isfinite(prices)) or np.any(prices <= 0):
        raise ValueError("Série com preço inválido")
    if prices.size - 1 < min_observations:
        raise DataInsufficientError(f"{prices.size - 1} retornos; o mínimo é {min_observations}")
    return np.diff(np.log(prices))


def historical_volatility(closes: Sequence[float], min_observations: int = 20) -> float:
    """Desvio-padrão amostral dos retornos logarítmicos, anualizado por 252."""
    returns = _log_returns(closes, min_observations)
    return float(np.std(returns, ddof=1) * np.sqrt(BUSINESS_DAYS_PER_YEAR))


def ewma_volatility(closes: Sequence[float], decay: float = 0.94, min_observations: int = 20) -> float:
    """Média exponencial da variância (RiskMetrics), iniciada no primeiro retorno ao quadrado."""
    if not 0 < decay < 1:
        raise ValueError("decay precisa estar entre 0 e 1")
    returns = _log_returns(closes, min_observations)
    variance = float(returns[0] ** 2)
    for value in returns[1:]:
        variance = decay * variance + (1 - decay) * float(value) ** 2
    return float(np.sqrt(variance * BUSINESS_DAYS_PER_YEAR))
