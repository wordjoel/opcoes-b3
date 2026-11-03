"""Probabilidade neutra ao risco de uma opção terminar dentro do dinheiro. Não é previsão."""

from scipy.special import ndtr

from core.types import OptionKind
from quant.pricing.black_scholes import d1_d2


def probability_itm(kind: OptionKind, s: float, k: float, t: float, r: float, sigma: float | None) -> float | None:
    """None sem volatilidade ou prazo positivos."""
    if sigma is None or sigma <= 0 or t <= 0:
        return None
    _, d2 = d1_d2(s, k, t, r, sigma)
    call = float(ndtr(d2))
    return call if kind is OptionKind.CALL else 1 - call
