"""Gregas de Black-Scholes-Merton."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp, pi, sqrt

from scipy.special import ndtr

from core.config import BUSINESS_DAYS_PER_YEAR
from core.types import LegAction, OptionKind, OptionLeg
from quant.pricing.black_scholes import check_inputs, d1_d2


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    # Por ano de passagem do tempo.
    theta: float
    # Por 1,00 (100 pontos) de volatilidade.
    vega: float
    # Por 1,00 (100 pontos) de taxa.
    rho: float

    @property
    def theta_per_business_day(self) -> float:
        return self.theta / BUSINESS_DAYS_PER_YEAR

    @property
    def vega_per_vol_point(self) -> float:
        return self.vega / 100

    @property
    def rho_per_rate_point(self) -> float:
        return self.rho / 100


@dataclass(frozen=True)
class PositionGreeks:
    """Da posição inteira, em R$: delta por R$ 1,00 no ativo, theta por dia útil, vega por ponto."""

    delta: float
    gamma: float
    theta_per_business_day: float
    vega_per_vol_point: float


def option_greeks(kind: OptionKind, s: float, k: float, t: float, r: float, sigma: float, q: float = 0.0) -> Greeks:
    check_inputs(s, k, sigma)
    sign = 1 if kind is OptionKind.CALL else -1
    if t <= 0 or sigma == 0:
        # No limite, resta a sensibilidade do valor intrínseco.
        in_the_money = sign * (s - k) > 0
        return Greeks(sign * 1.0 if in_the_money else 0.0, 0.0, 0.0, 0.0, 0.0)

    d1, d2 = d1_d2(s, k, t, r, sigma, q)
    root = sqrt(t)
    eq = exp(-q * t)
    er = exp(-r * t)
    pdf = exp(-d1 * d1 / 2) / sqrt(2 * pi)
    return Greeks(
        delta=sign * eq * float(ndtr(sign * d1)),
        gamma=eq * pdf / (s * sigma * root),
        theta=(
            -s * eq * pdf * sigma / (2 * root)
            - sign * r * k * er * float(ndtr(sign * d2))
            + sign * q * s * eq * float(ndtr(sign * d1))
        ),
        vega=s * eq * pdf * root,
        rho=sign * k * t * er * float(ndtr(sign * d2)),
    )


def position_greeks(
    legs: Sequence[OptionLeg], ivs: Sequence[float | None], s: float, t: float, r: float, q: float = 0.0
) -> PositionGreeks | None:
    """Soma das pernas com sinal e quantidade. None se faltar a volatilidade de alguma perna."""
    if len(legs) != len(ivs):
        raise ValueError("Uma volatilidade por perna")
    delta = gamma = theta = vega = 0.0
    for leg, iv in zip(legs, ivs):
        if iv is None or iv <= 0:
            return None
        size = leg.quantity * (1 if leg.action is LegAction.BUY else -1)
        greeks = option_greeks(leg.kind, s, leg.strike, t, r, iv, q)
        delta += size * greeks.delta
        gamma += size * greeks.gamma
        theta += size * greeks.theta_per_business_day
        vega += size * greeks.vega_per_vol_point
    return PositionGreeks(delta, gamma, theta, vega)
