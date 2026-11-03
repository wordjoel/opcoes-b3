"""Regime de mercado medido por médias móveis e pela razão entre vol implícita e histórica."""

from collections.abc import Sequence

import numpy as np

from core.exceptions import DataInsufficientError
from core.types import MarketRegime
from quant.strategies import RICH_IV_RATIO

_SHORT = 20
_LONG = 50
# Diferença entre as médias a partir da qual há tendência.
_TREND_THRESHOLD = 0.02


def classify_regime(closes: Sequence[float], iv_ratio: float | None = None) -> MarketRegime:
    if len(closes) < _LONG:
        raise DataInsufficientError(f"{len(closes)} fechamentos; o regime exige {_LONG}")
    if iv_ratio is not None and iv_ratio >= RICH_IV_RATIO:
        return MarketRegime.HIGH_VOL
    prices = np.asarray(closes, dtype=float)
    short = float(prices[-_SHORT:].mean())
    long = float(prices[-_LONG:].mean())
    gap = short / long - 1
    last = float(prices[-1])
    if abs(gap) < _TREND_THRESHOLD:
        return MarketRegime.SIDEWAYS
    if gap > 0 and last > short:
        return MarketRegime.BULL
    if gap < 0 and last < short:
        return MarketRegime.BEAR
    # As médias apontam para um lado e o preço já está do outro.
    return MarketRegime.UNCERTAIN
