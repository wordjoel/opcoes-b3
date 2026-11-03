"""Avaliação de risco. Sem aprovação explícita daqui, uma estrutura não é apresentável.

Aprovar significa apenas passar nestas regras; não é recomendação de operar. Os limites
são escolhas iniciais do projeto, não padrões de mercado, e estão reunidos em RiskLimits.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import log1p
from statistics import mean

from core.text import decimal_comma
from core.types import CorporateEvent, LegAction, OptionLeg, OptionQuote, RiskAssessment, StrategyProposal
from quant.payoff import net_premium, position_pnl, probability_of_profit
from quant.pricing.black_scholes import option_price

_SPOT_SHOCKS = (-0.20, -0.10, -0.05, 0.05, 0.10, 0.20)
_VOL_SHOCKS = (-0.10, 0.10)
_HEATMAP_SPOT_SHOCKS = (-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20)
_HEATMAP_VOL_SHOCKS = (0.10, 0.05, 0.0, -0.05, -0.10)


@dataclass(frozen=True)
class RiskLimits:
    min_liquidity: float = 0.5
    # Diferença máxima entre bid e ask, como fração do preço médio.
    max_spread: float = 0.25
    # Referências em que cada componente da liquidez chega à nota máxima.
    # A B3 conta em opções: uma série líquida da PETR4 tem milhões em aberto.
    full_open_interest: int = 1_000_000
    full_volume: int = 100_000
    full_trades: int = 100
    # Abaixo disto, o preço de fechamento informa pouco.
    min_trades: int = 3
    # Movimento do ativo desde o pregão da grade que invalida os prêmios.
    max_spot_drift: float = 0.03
    # Cerca de 5 dias úteis.
    near_expiry_years: float = 5 / 252
    low_pop: float = 0.25
    # Venda de crédito abaixo disto recebe aviso.
    min_credit_pop: float = 0.65
    # Com resultado antes do vencimento, prazo abaixo disto reprova.
    min_days_with_earnings: int = 7


def leg_liquidity(quote: OptionQuote, limits: RiskLimits = RiskLimits(), use_book: bool = True) -> float | None:
    """Nota de 0 a 1. None = não medida, o que é diferente de liquidez zero.

    `use_book=False` em grade de fim de dia: o spread final não mede a liquidez do pregão.
    """
    if quote.open_interest is None or quote.volume is None or quote.trades is None:
        return None
    depth = (
        0.4 * min(1.0, log1p(quote.open_interest) / log1p(limits.full_open_interest))
        + 0.4 * min(1.0, log1p(quote.volume) / log1p(limits.full_volume))
        + 0.2 * min(1.0, quote.trades / limits.full_trades)
    )
    if use_book and quote.bid and quote.ask:
        spread = (quote.ask - quote.bid) / ((quote.ask + quote.bid) / 2)
        depth *= max(0.0, 1 - spread / limits.max_spread)
    return depth


def position_pop(
    legs: Sequence[OptionLeg], ivs: Sequence[float | None], spot: float, t: float, r: float
) -> float | None:
    """Usa a média das vols das pernas. None se faltar alguma."""
    if any(iv is None or iv <= 0 for iv in ivs):
        return None
    return probability_of_profit(legs, spot, mean(ivs), t, r)


def stress_tests(
    legs: Sequence[OptionLeg], ivs: Sequence[float | None], spot: float, t: float, r: float
) -> dict[str, float]:
    """P&L em R$: choques no ativo no vencimento e na vol hoje, ambos pelo modelo europeu."""
    results = {
        f"Ativo {shock:+.0%} no vencimento": float(position_pnl(legs, spot * (1 + shock))) for shock in _SPOT_SHOCKS
    }
    if all(iv is not None and iv > 0 for iv in ivs):
        for shock in _VOL_SHOCKS:
            total = 0.0
            for leg, iv in zip(legs, ivs):
                sigma = max(iv + shock, 0.01)
                value = option_price(leg.kind, spot, leg.strike, t, r, sigma)
                total += (1 if leg.action is LegAction.BUY else -1) * (value - leg.premium) * leg.quantity
            results[f"Vol {shock * 100:+.0f} pontos hoje"] = total
    return results


def pnl_heatmap(
    legs: Sequence[OptionLeg], ivs: Sequence[float | None], spot: float, t: float, r: float
) -> dict | None:
    """Resultado hoje, em R$, para cada par de choque no ativo e na vol. None se faltar vol de alguma perna."""
    if any(iv is None or iv <= 0 for iv in ivs):
        return None
    pnl = []
    for vol_shock in _HEATMAP_VOL_SHOCKS:
        line = []
        for spot_shock in _HEATMAP_SPOT_SHOCKS:
            total = 0.0
            for leg, iv in zip(legs, ivs):
                value = option_price(leg.kind, spot * (1 + spot_shock), leg.strike, t, r, max(iv + vol_shock, 0.01))
                total += (1 if leg.action is LegAction.BUY else -1) * (value - leg.premium) * leg.quantity
            line.append(total)
        pnl.append(line)
    return {"spot_shocks": list(_HEATMAP_SPOT_SHOCKS), "vol_shocks": list(_HEATMAP_VOL_SHOCKS), "pnl": pnl}


def assess_risk(
    proposal: StrategyProposal,
    quotes: Sequence[OptionQuote],
    spot: float,
    t: float,
    r: float,
    spot_drift: float | None,
    limits: RiskLimits = RiskLimits(),
    use_book: bool = True,
    events: Sequence[CorporateEvent] = (),
    today: date | None = None,
) -> RiskAssessment:
    """`spot_drift`: variação relativa do ativo desde o pregão da grade. None = não medida."""
    legs = proposal.legs
    ivs = [quote.iv for quote in quotes]
    rejections: list[str] = []
    warnings: list[str] = []

    if proposal.max_loss is None:
        rejections.append("perda máxima ilimitada")
    elif proposal.max_loss == 0:
        rejections.append("perda máxima zero: os prêmios não estão sincronizados entre si")
    if proposal.max_profit is not None and proposal.max_profit <= 0:
        rejections.append("nenhum preço no vencimento dá lucro com estes prêmios")

    scores = [leg_liquidity(quote, limits, use_book) for quote in quotes]
    liquidity = None if any(score is None for score in scores) else min(scores)
    if liquidity is None:
        rejections.append("liquidez não medida: faltam contratos em aberto, volume ou negócios")
    elif liquidity < limits.min_liquidity:
        rejections.append(
            decimal_comma(f"liquidez {liquidity:.2f} abaixo do mínimo de {limits.min_liquidity:.2f}")
        )

    if spot_drift is None:
        warnings.append("Não foi possível comparar o ativo agora com o pregão da grade.")
    elif abs(spot_drift) > limits.max_spot_drift:
        moved = decimal_comma(f"{spot_drift:+.1%}")
        rejections.append(f"o ativo já se moveu {moved} desde o pregão da grade: os prêmios estão defasados")

    thin = sorted(quote.symbol for quote in quotes if quote.trades is not None and quote.trades < limits.min_trades)
    if thin:
        warnings.append(f"Fechamento formado por poucos negócios: {', '.join(thin)}.")
    if t < limits.near_expiry_years:
        warnings.append("Menos de 5 dias úteis até o vencimento: o risco de gama é alto.")
    american_short = [
        quote.symbol
        for leg, quote in zip(legs, quotes)
        if leg.action is LegAction.SELL and quote.style is not None and quote.style.value == "AMERICAN"
    ]
    if american_short:
        warnings.append(f"Pernas vendidas americanas podem ser exercidas antes: {', '.join(american_short)}.")
    if any(leg.action is LegAction.SELL for leg in legs):
        warnings.append("A margem exigida pela corretora não foi calculada.")
    if any(iv is None or iv <= 0 for iv in ivs):
        warnings.append("Falta volatilidade implícita: gregas, probabilidade e choque de vol não foram calculados.")
    else:
        pop = position_pop(legs, ivs, spot, t, r)
        if pop is not None and pop < limits.low_pop:
            warnings.append(f"Probabilidade de lucro baixa: {pop:.0%}.")
        if pop is not None and net_premium(legs) < 0 and pop < limits.min_credit_pop:
            warnings.append(f"Venda de crédito com probabilidade de lucro de {pop:.0%}, abaixo de {limits.min_credit_pop:.0%}.")

    expiry = legs[0].expiry
    for event in events:
        if event.day <= expiry:
            status = "" if event.confirmed else " (data estimada)"
            warnings.append(f"{event.label} em {event.day.strftime('%d/%m/%Y')}{status}, antes do vencimento.")
            if (
                event.kind == "RESULTADO"
                and today is not None
                and (expiry - today).days < limits.min_days_with_earnings
            ):
                rejections.append(f"{event.label} antes de um vencimento a menos de {limits.min_days_with_earnings} dias")

    approved = not rejections
    return RiskAssessment(
        is_approved=approved,
        liquidity_score=liquidity,
        stress_test_results=stress_tests(legs, ivs, spot, t, r),
        warnings=warnings,
        final_verdict="Passou nas regras de risco; não é recomendação." if approved else "Reprovada nas regras de risco.",
        rejection_reason=None if approved else "; ".join(rejections),
    )
