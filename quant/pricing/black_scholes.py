"""Preço pelo modelo de Black-Scholes-Merton (opção europeia, dividendo contínuo).

t em anos; r, q e sigma em decimal. r não tem valor padrão de propósito: a taxa
precisa vir da análise, com sua fonte. Convenções e limitações em
docs/quant-convencoes.md.
"""

from math import exp, log, sqrt

from scipy.special import ndtr

from core.types import OptionKind


def check_inputs(s: float, k: float, sigma: float) -> None:
    if s <= 0 or k <= 0:
        raise ValueError("Preço do ativo e strike precisam ser positivos")
    if sigma < 0:
        raise ValueError("Volatilidade não pode ser negativa")


def d1_d2(s: float, k: float, t: float, r: float, sigma: float, q: float = 0.0) -> tuple[float, float]:
    """Só definido para t > 0 e sigma > 0."""
    vol_root = sigma * sqrt(t)
    d1 = (log(s / k) + (r - q + sigma * sigma / 2) * t) / vol_root
    return d1, d1 - vol_root


def option_price(kind: OptionKind, s: float, k: float, t: float, r: float, sigma: float, q: float = 0.0) -> float:
    check_inputs(s, k, sigma)
    sign = 1 if kind is OptionKind.CALL else -1
    if t <= 0:
        return max(sign * (s - k), 0.0)
    disc_s = s * exp(-q * t)
    disc_k = k * exp(-r * t)
    if sigma == 0:
        return max(sign * (disc_s - disc_k), 0.0)
    d1, d2 = d1_d2(s, k, t, r, sigma, q)
    return sign * (disc_s * float(ndtr(sign * d1)) - disc_k * float(ndtr(sign * d2)))
