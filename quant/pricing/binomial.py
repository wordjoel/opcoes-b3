"""Preço de opção americana por árvore binomial (Cox-Ross-Rubinstein).

Sem dividendos (q = 0) e com juros não negativos, nunca vale a pena exercer uma call
antes do vencimento: ela vale o mesmo que a europeia, e a função usa a fórmula exata.
Como a fonte informa dividendYield 0 nas grades observadas, a diferença real aparece em
puts americanas. Dividendo discreto perto do vencimento não é modelado, e nele a call
americana também pode valer mais: essa limitação fica registrada nos avisos da análise.
"""

from math import exp, sqrt

import numpy as np

from core.types import ExerciseStyle, OptionKind
from quant.pricing.black_scholes import check_inputs, option_price

DEFAULT_STEPS = 200


def american_price(
    kind: OptionKind, s: float, k: float, t: float, r: float, sigma: float, q: float = 0.0, steps: int = DEFAULT_STEPS
) -> float:
    check_inputs(s, k, sigma)
    sign = 1 if kind is OptionKind.CALL else -1
    if t <= 0 or sigma == 0:
        return max(option_price(kind, s, k, t, r, sigma, q), max(sign * (s - k), 0.0))
    if kind is OptionKind.CALL and q == 0 and r >= 0:
        return option_price(kind, s, k, t, r, sigma, q)

    dt = t / steps
    up = exp(sigma * sqrt(dt))
    down = 1 / up
    p = (exp((r - q) * dt) - down) / (up - down)
    discount = exp(-r * dt)
    powers = up ** np.arange(steps, -steps - 1, -2.0)
    values = np.maximum(sign * (s * powers - k), 0.0)
    for step in range(steps - 1, -1, -1):
        values = discount * (p * values[:-1] + (1 - p) * values[1:])
        prices = s * up ** np.arange(step, -step - 1, -2.0)
        values = np.maximum(values, sign * (prices - k))
    return float(values[0])


def model_value(
    kind: OptionKind, style: ExerciseStyle | None, s: float, k: float, t: float, r: float, sigma: float, q: float = 0.0
) -> float:
    """Usa o modelo do estilo informado. Sem estilo informado, o europeu, com aviso na análise."""
    if style is ExerciseStyle.AMERICAN:
        return american_price(kind, s, k, t, r, sigma, q)
    return option_price(kind, s, k, t, r, sigma, q)
