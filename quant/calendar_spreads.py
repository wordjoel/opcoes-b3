"""Trava calendário (horizontal) e diagonal: vende no vencimento curto e compra no longo.

O resultado é medido no vencimento curto. Nesse dia a perna vendida vale o intrínseco e a
comprada ainda tem prazo, então vale pelo modelo (Black-Scholes europeu com a vol que ela
tem hoje). Por isso o ganho máximo é uma estimativa: depende da vol que o mercado der à
perna longa naquele dia. A perda máxima, para débito com a longa cobrindo a curta, é o
débito pago, salvo exercício antecipado da vendida americana.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import exp, log, sqrt

import numpy as np
from scipy.special import ndtr

from core.types import LegAction, OptionKind, OptionLeg, OptionQuote
from quant.strategies import DEFAULT_LOT, DEFAULT_WIDTH, PriceBasis, execution_price

BUY, SELL = LegAction.BUY, LegAction.SELL
CALL, PUT = OptionKind.CALL, OptionKind.PUT


@dataclass(frozen=True)
class _Spec:
    key: str
    name: str
    kind: OptionKind
    # Strike da vendida (curta) em larguras a partir do ativo; a comprada (longa) fica no dinheiro.
    short_offset: int
    rationale: str


SPECS: tuple[_Spec, ...] = (
    _Spec("call_calendar", "Trava calendário com call", CALL, 0,
          "Ganha com o ativo parado perto do strike: a call curta perde valor mais rápido que a longa."),
    _Spec("put_calendar", "Trava calendário com put", PUT, 0,
          "Igual à calendário com call, montada com puts: ganha com o ativo parado perto do strike."),
    _Spec("call_diagonal", "Trava diagonal de alta com call", CALL, 1,
          "Alta lenta até o strike vendido: a call curta acima do ativo financia a call longa."),
    _Spec("put_diagonal", "Trava diagonal de baixa com put", PUT, -1,
          "Queda lenta até o strike vendido: a put curta abaixo do ativo financia a put longa."),
)


def bs_value(kind: OptionKind, spot: float | np.ndarray, strike: float, t: float, r: float, sigma: float) -> np.ndarray:
    """Black-Scholes europeu vetorizado; no vencimento, o intrínseco."""
    s = np.asarray(spot, dtype=float)
    if t <= 0:
        return np.maximum(s - strike, 0) if kind is CALL else np.maximum(strike - s, 0)
    safe = np.maximum(s, 1e-9)
    root = sigma * sqrt(t)
    d1 = (np.log(safe / strike) + (r + sigma * sigma / 2) * t) / root
    d2 = d1 - root
    if kind is CALL:
        return safe * ndtr(d1) - strike * exp(-r * t) * ndtr(d2)
    return strike * exp(-r * t) * ndtr(-d2) - safe * ndtr(-d1)


@dataclass(frozen=True)
class CalendarLeg:
    leg: OptionLeg
    quote: OptionQuote
    basis: PriceBasis
    # Anos até o vencimento desta perna, contados do pregão da grade.
    t: float


@dataclass(frozen=True)
class CalendarCandidate:
    key: str
    name: str
    rationale: str
    short: CalendarLeg
    long: CalendarLeg

    @property
    def legs(self) -> tuple[CalendarLeg, CalendarLeg]:
        # Ordem de montagem: a compra primeiro.
        return (self.long, self.short)

    def net_premium(self) -> float:
        """Positivo = débito."""
        return sum((1 if item.leg.action is BUY else -1) * item.leg.premium * item.leg.quantity for item in self.legs)

    def pnl_at_short_expiry(self, prices: np.ndarray | float, r: float, vol_shift: float = 0.0) -> np.ndarray:
        """R$ no vencimento curto: curta pelo intrínseco, longa pelo modelo com o prazo que sobra."""
        remaining = self.long.t - self.short.t
        short_value = bs_value(self.short.leg.kind, prices, self.short.leg.strike, 0.0, r, 1.0)
        sigma = max((self.long.quote.iv or 0) + vol_shift, 0.01)
        long_value = bs_value(self.long.leg.kind, prices, self.long.leg.strike, remaining, r, sigma)
        return (long_value - self.long.leg.premium) * self.long.leg.quantity - (short_value - self.short.leg.premium) * self.short.leg.quantity


def _nearest(quotes: Sequence[OptionQuote], kind: OptionKind, target: float) -> OptionQuote | None:
    return min((q for q in quotes if q.kind is kind and q.iv), key=lambda q: (abs(q.strike - target), q.strike), default=None)


def build_calendars(
    near: Sequence[OptionQuote],
    far: Sequence[OptionQuote],
    spot: float,
    t_near: float,
    t_far: float,
    lot: int = DEFAULT_LOT,
    width: float = DEFAULT_WIDTH,
) -> tuple[list[CalendarCandidate], list[tuple[str, str, str]]]:
    """`near` e `far` são as cotações utilizáveis de cada vencimento. Devolve as estruturas e as
    indisponíveis (chave, nome, motivo). Só monta com vol implícita nas duas pernas."""
    if spot <= 0 or lot <= 0 or not 0 < t_near < t_far:
        raise ValueError("Parâmetros de calendário inválidos")
    built: list[CalendarCandidate] = []
    missing: list[tuple[str, str, str]] = []
    for spec in SPECS:
        long_quote = _nearest(far, spec.kind, spot)
        if long_quote is None:
            missing.append((spec.key, spec.name, "o vencimento longo não tem série com vol implícita"))
            continue
        short_target = long_quote.strike if spec.short_offset == 0 else spot * (1 + spec.short_offset * width)
        short_quote = _nearest(near, spec.kind, short_target)
        if short_quote is None:
            missing.append((spec.key, spec.name, "o vencimento curto não tem série com vol implícita"))
            continue
        if spec.short_offset == 0 and short_quote.strike != long_quote.strike:
            missing.append((spec.key, spec.name, "os dois vencimentos não têm o mesmo strike perto do ativo"))
            continue
        # Na diagonal, a vendida precisa ficar do lado do movimento esperado.
        if spec.short_offset > 0 and short_quote.strike <= long_quote.strike or spec.short_offset < 0 and short_quote.strike >= long_quote.strike:
            missing.append((spec.key, spec.name, "a grade curta não tem strike além do ativo para a vendida"))
            continue
        legs = []
        for quote, action, t in ((short_quote, SELL, t_near), (long_quote, BUY, t_far)):
            price, basis = execution_price(quote, action, use_book=False)
            leg = OptionLeg(symbol=quote.symbol, strike=quote.strike, expiry=quote.expiry, kind=spec.kind, action=action, quantity=lot, premium=price)
            legs.append(CalendarLeg(leg, quote, basis, t))
        built.append(CalendarCandidate(spec.key, spec.name, spec.rationale, short=legs[0], long=legs[1]))
    return built, missing


@dataclass(frozen=True)
class CalendarAnalysis:
    net_premium: float
    # Estimativa pelo modelo no vencimento curto. None se o ganho não tiver teto na faixa.
    max_profit_estimate: float | None
    # Pior resultado na faixa varrida (preço de 0 a 4x o ativo), positivo.
    max_loss: float
    breakevens: tuple[float, ...]
    probability_of_profit: float
    expected_pnl: float
    curve: list[tuple[float, float]]


def _zeros(fn: Callable[[float], float], grid: np.ndarray, values: np.ndarray) -> list[float]:
    found = []
    for low, high, a, b in zip(grid, grid[1:], values, values[1:]):
        if a == 0 or a * b < 0:
            lo, hi = float(low), float(high)
            for _ in range(60):
                mid = (lo + hi) / 2
                if (fn(lo) < 0) == (fn(mid) < 0):
                    lo = mid
                else:
                    hi = mid
            found.append((lo + hi) / 2)
    return found


def analyze_calendar(candidate: CalendarCandidate, spot: float, r: float, points: int = 121) -> CalendarAnalysis:
    """Resultado no vencimento curto, com a distribuição lognormal da vol da perna curta."""
    sigma = candidate.short.quote.iv
    t = candidate.short.t
    if not sigma or sigma <= 0 or t <= 0:
        raise ValueError("A perna curta precisa de vol implícita e prazo positivos")
    fn = lambda price: float(candidate.pnl_at_short_expiry(price, r))  # noqa: E731

    wide = np.linspace(spot * 0.01, spot * 4, 4000)
    wide_values = candidate.pnl_at_short_expiry(wide, r)
    max_loss = max(-float(wide_values.min()), 0.0)
    # Se o resultado ainda sobe na ponta, o ganho não tem teto na faixa: não estima.
    rising = wide_values[-1] > wide_values[-2] + 1e-6 and wide_values[-1] >= wide_values.max() - 1e-6
    max_profit = None if rising else float(wide_values.max())

    root = sigma * sqrt(t)
    mean = log(spot) + (r - sigma * sigma / 2) * t
    z = np.linspace(-6, 6, 6001)
    prices = np.exp(mean + root * z)
    density = np.exp(-(z**2) / 2) / sqrt(2 * np.pi)
    values = candidate.pnl_at_short_expiry(prices, r)
    expected = float(np.trapezoid(values * density, z))
    probability = float(np.trapezoid((values > 0) * density, z))

    span = min(max(3 * root, 0.15), 0.6)
    grid = np.linspace(spot * (1 - span), spot * (1 + span), points)
    curve_values = candidate.pnl_at_short_expiry(grid, r)
    breakevens = tuple(_zeros(fn, wide, wide_values))
    return CalendarAnalysis(
        net_premium=candidate.net_premium(),
        max_profit_estimate=max_profit,
        max_loss=max_loss,
        breakevens=breakevens,
        probability_of_profit=probability,
        expected_pnl=expected,
        curve=[(float(price), float(value)) for price, value in zip(grid, curve_values)],
    )
