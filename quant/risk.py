"""Avaliação de risco. Sem aprovação explícita daqui, uma estrutura não é apresentável.

Aprovar significa apenas passar nestas regras; não é recomendação de operar. Os limites
são escolhas iniciais do projeto, não padrões de mercado, e estão reunidos em RiskLimits.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import log1p
from statistics import mean

from core.calendario_b3 import trading_days_between
from core.text import decimal_comma
from core.types import CorporateEvent, ExerciseStyle, LegAction, OptionLeg, OptionQuote, RiskAssessment, StrategyProposal
from quant.payoff import net_premium, position_pnl, probability_of_profit
from quant.pricing.binomial import model_value

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
    # Pregões até o vencimento abaixo dos quais o risco de gama recebe aviso.
    near_expiry_sessions: int = 5
    low_pop: float = 0.25
    # Venda de crédito abaixo disto recebe aviso.
    min_credit_pop: float = 0.65
    # Com resultado antes do vencimento, prazo abaixo disto reprova.
    min_days_with_earnings: int = 7


@dataclass(frozen=True)
class CapitalLimits:
    """Definidos pelo proprietário: o sistema não presume capital nem limite."""

    capital_brl: float
    # Perda máxima por estrutura, em % do capital.
    max_loss_pct: float

    def __post_init__(self) -> None:
        if self.capital_brl <= 0:
            raise ValueError("Capital precisa ser positivo")
        if not 0 < self.max_loss_pct <= 100:
            raise ValueError("Limite de perda precisa estar entre 0 e 100%")


def decide(
    proposal: StrategyProposal, rules: RiskAssessment, capital: CapitalLimits | None, spot_drift: float | None
) -> dict:
    """APROVADA só com regras cumpridas, capital e limite informados, e todos os dados presentes.

    Perna vendida exige margem, calculada pela B3 e pela corretora, que não temos: nesse caso o
    capital necessário fica desconhecido e a estrutura nunca é aprovada. A perda máxima continua
    informada, mas não substitui a margem.
    """
    legs = proposal.legs
    has_sold_leg = any(leg.action is LegAction.SELL for leg in legs)
    debit = sum(leg.premium * leg.quantity * (1 if leg.action is LegAction.BUY else -1) for leg in legs)
    required = None if has_sold_leg else debit

    reasons: list[str] = []
    missing: list[str] = []
    for reason in (rules.rejection_reason or "").split("; "):
        if "não medida" in reason:
            missing.append(reason)
        elif reason:
            reasons.append(reason)

    if capital is None:
        missing.append("capital e limite de perda não informados")
    else:
        limit = capital.capital_brl * capital.max_loss_pct / 100
        if proposal.max_loss is not None and proposal.max_loss > limit:
            reasons.append(decimal_comma(f"perda máxima de R$ {proposal.max_loss:.2f} acima do limite de R$ {limit:.2f}"))
        if required is not None and required > capital.capital_brl:
            reasons.append(decimal_comma(f"custo de R$ {required:.2f} acima do capital de R$ {capital.capital_brl:.2f}"))
    if has_sold_leg:
        missing.append("margem da corretora não disponível para perna vendida")
    if spot_drift is None:
        missing.append("não foi possível comparar o ativo com o pregão da grade")
    if any("volatilidade implícita" in warning for warning in rules.warnings):
        missing.append("falta volatilidade implícita em alguma perna")

    status = "REPROVADA" if reasons else "INCOMPLETA" if missing else "APROVADA"
    limit_brl = capital.capital_brl * capital.max_loss_pct / 100 if capital else None
    max_risk_pct = proposal.max_loss / capital.capital_brl * 100 if capital and proposal.max_loss is not None else None
    return {
        "status": status,
        "reasons": reasons,
        "missing": missing,
        "capital_required": required,
        "max_risk": proposal.max_loss,
        "max_risk_pct": max_risk_pct,
        "limit_brl": limit_brl,
        "risk_reward": proposal.risk_reward_ratio,
    }


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
    legs: Sequence[OptionLeg],
    ivs: Sequence[float | None],
    spot: float,
    t: float,
    r: float,
    styles: Sequence[ExerciseStyle | None] | None = None,
) -> dict[str, float]:
    """P&L em R$: choques no ativo no vencimento e na vol hoje, pelo modelo do estilo de cada perna."""
    styles = styles or [None] * len(legs)
    results = {
        f"Ativo {shock:+.0%} no vencimento": float(position_pnl(legs, spot * (1 + shock))) for shock in _SPOT_SHOCKS
    }
    if all(iv is not None and iv > 0 for iv in ivs):
        for shock in _VOL_SHOCKS:
            total = 0.0
            for leg, iv, style in zip(legs, ivs, styles):
                sigma = max(iv + shock, 0.01)
                value = model_value(leg.kind, style, spot, leg.strike, t, r, sigma)
                total += (1 if leg.action is LegAction.BUY else -1) * (value - leg.premium) * leg.quantity
            results[f"Vol {shock * 100:+.0f} pontos hoje"] = total
    return results


def pnl_heatmap(
    legs: Sequence[OptionLeg],
    ivs: Sequence[float | None],
    spot: float,
    t: float,
    r: float,
    styles: Sequence[ExerciseStyle | None] | None = None,
) -> dict | None:
    """Resultado hoje, em R$, para cada par de choque no ativo e na vol. None se faltar vol de alguma perna."""
    if any(iv is None or iv <= 0 for iv in ivs):
        return None
    styles = styles or [None] * len(legs)
    pnl = []
    for vol_shock in _HEATMAP_VOL_SHOCKS:
        line = []
        for spot_shock in _HEATMAP_SPOT_SHOCKS:
            total = 0.0
            for leg, iv, style in zip(legs, ivs, styles):
                value = model_value(leg.kind, style, spot * (1 + spot_shock), leg.strike, t, r, max(iv + vol_shock, 0.01))
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
    expiries = {leg.expiry for leg in legs}
    if today is not None and len(expiries) == 1:
        sessions_left = trading_days_between(today, expiries.pop())
    else:
        # Sem data de referência, estima pelos dias corridos do prazo da grade.
        sessions_left = int(t * 365 * 5 / 7)
    if sessions_left < limits.near_expiry_sessions:
        warnings.append(f"Menos de {limits.near_expiry_sessions} pregões até o vencimento: o risco de gama é alto.")
    american_short = [
        quote.symbol
        for leg, quote in zip(legs, quotes)
        if leg.action is LegAction.SELL and quote.style is not None and quote.style.value == "AMERICAN"
    ]
    if any(quote.style is ExerciseStyle.AMERICAN for quote in quotes):
        warnings.append(
            "Há perna americana: heatmap e estresse usam árvore binomial, mas a vol implícita da fonte, "
            "as gregas e a probabilidade vêm do modelo europeu."
        )
    if any(quote.style is None for quote in quotes):
        warnings.append("A fonte não informou o estilo de alguma perna: avaliada pelo modelo europeu.")
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
        stress_test_results=stress_tests(legs, ivs, spot, t, r, [quote.style for quote in quotes]),
        warnings=warnings,
        final_verdict="Passou nas regras de risco; não é recomendação." if approved else "Reprovada nas regras de risco.",
        rejection_reason=None if approved else "; ".join(rejections),
    )
