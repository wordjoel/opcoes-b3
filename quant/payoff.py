"""Resultado no vencimento e probabilidade de lucro de uma posição.

O P&L é linear por partes, com quebras só nos strikes, então os extremos e os
breakevens são exatos. Estruturas com mais de um vencimento (calendário, diagonal)
não têm payoff definido só pelo vencimento e são recusadas aqui.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import log, sqrt

import numpy as np
from numpy.typing import NDArray
from scipy.special import ndtr

from core.types import LegAction, OptionKind, OptionLeg

_EPSILON = 1e-9


@dataclass(frozen=True)
class PayoffAnalysis:
    # Em R$. None = ilimitado. Pode ser <= 0 se os preços impedirem qualquer ganho.
    max_profit: float | None
    # Em R$, como valor positivo. None = ilimitada.
    max_loss: float | None
    breakevens: tuple[float, ...]

    @property
    def risk_reward_ratio(self) -> float | None:
        """Ganho máximo por real de perda máxima. None se um dos lados não tem limite."""
        if self.max_profit is None or self.max_loss is None or self.max_loss == 0:
            return None
        return max(self.max_profit, 0.0) / self.max_loss


def _direction(leg: OptionLeg) -> int:
    return 1 if leg.action is LegAction.BUY else -1


def _check_legs(legs: Sequence[OptionLeg]) -> None:
    if not legs:
        raise ValueError("Posição sem pernas")
    if len({leg.expiry for leg in legs}) > 1:
        raise ValueError("Payoff no vencimento exige um único vencimento")


def position_pnl(legs: Sequence[OptionLeg], prices: NDArray[np.float64] | float) -> NDArray[np.float64]:
    """P&L total em R$ para cada preço do ativo no vencimento."""
    _check_legs(legs)
    at = np.asarray(prices, dtype=float)
    total = np.zeros_like(at)
    for leg in legs:
        intrinsic = np.maximum(at - leg.strike, 0) if leg.kind is OptionKind.CALL else np.maximum(leg.strike - at, 0)
        total = total + _direction(leg) * (intrinsic - leg.premium) * leg.quantity
    return total


def net_premium(legs: Sequence[OptionLeg]) -> float:
    """Valor líquido na montagem, em R$. Positivo = débito; negativo = crédito."""
    return float(sum(_direction(leg) * leg.premium * leg.quantity for leg in legs))


def analyze_payoff(legs: Sequence[OptionLeg]) -> PayoffAnalysis:
    _check_legs(legs)
    pnl = lambda price: float(position_pnl(legs, price))  # noqa: E731
    points = [0.0, *sorted({leg.strike for leg in legs})]
    values = [pnl(point) for point in points]
    # Acima do maior strike, só as calls continuam variando.
    slope = sum(_direction(leg) * leg.quantity for leg in legs if leg.kind is OptionKind.CALL)

    candidates: list[float] = []
    for (low, a), (high, b) in zip(zip(points, values), zip(points[1:], values[1:])):
        if abs(b) < _EPSILON:
            candidates.append(high)
        elif a * b < 0:
            candidates.append(low + (high - low) * -a / (b - a))
    if slope != 0 and values[-1] * slope < 0:
        candidates.append(points[-1] - values[-1] / slope)

    # Um zero só é breakeven se o P&L realmente trocar de sinal nele.
    breakevens = sorted({c for c in candidates if pnl(c - 1e-6) * pnl(c + 1e-6) < 0})
    return PayoffAnalysis(
        max_profit=None if slope > 0 else max(values),
        max_loss=None if slope < 0 else max(-min(values), 0.0),
        breakevens=tuple(breakevens),
    )


def probability_of_profit(
    legs: Sequence[OptionLeg], spot: float, sigma: float, t: float, r: float, q: float = 0.0
) -> float:
    """Probabilidade de P&L positivo no vencimento, com preço lognormal neutro ao risco.

    É o que os parâmetros informados implicam, não uma previsão do mercado.
    """
    if spot <= 0 or sigma <= 0 or t <= 0:
        raise ValueError("spot, sigma e t precisam ser positivos")
    analysis = analyze_payoff(legs)
    root = sigma * sqrt(t)
    drift = (r - q - sigma * sigma / 2) * t

    def cdf(price: float) -> float:
        return 0.0 if price <= 0 else float(ndtr((log(price / spot) - drift) / root))

    edges = [0.0, *sorted({*(leg.strike for leg in legs), *analysis.breakevens})]
    probability = 0.0
    for index, low in enumerate(edges):
        high = edges[index + 1] if index + 1 < len(edges) else None
        sample = low * 1.5 + 1 if high is None else (low + high) / 2
        if float(position_pnl(legs, sample)) > _EPSILON:
            probability += (1.0 if high is None else cdf(high)) - cdf(low)
    return probability
