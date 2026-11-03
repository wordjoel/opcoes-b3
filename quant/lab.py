"""Matemática do laboratório: tamanho, resultado, caminho e ranking.

Tudo é hipotético. Nenhuma função aqui representa uma operação executada:
- POTENCIAL: o máximo que a estrutura permite no vencimento.
- TEÓRICO: valor esperado pelo modelo lognormal, usando a vol da entrada.
- SIMULADO: backtest, com preços históricos reais e execução presumida no fechamento.
- OBSERVADO: acompanhamento à frente, com preços reais posteriores à entrada, sem execução.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import floor, log, sqrt
from statistics import mean, median, pstdev

import numpy as np

from core.types import LegAction, OptionKind, OptionLeg, OptionQuote, StrategyProposal
from quant.payoff import analyze_payoff, position_pnl
from quant.strategies import Candidate, PriceBasis, execution_price

# Estratégias da mesma data se movem juntas: a amostra que conta é o número de datas de entrada.
MIN_RANKED_ENTRIES = 20
# Em opções: 50 e 100 contratos de 100 opções, como na seleção por delta.
MIN_SCAN_VOLUME = 5_000
MIN_SCAN_OPEN_INTEREST = 10_000
# Abaixo disto, o ativo não tem séries suficientes para estruturas confiáveis.
MIN_LIQUID_SERIES = 4
_SCAN_MAX_WIDTH = 0.15
# Fechamentos não são simultâneos. Sem estes filtros, escolher o maior valor esperado seleciona
# justamente pernas com preço velho, que parecem risco quase zero (medido no backtest de 03/11/2026).
_SCAN_MAX_IV_GAP = 0.05
_SCAN_MIN_TRADES = 3
# Ganho e perda máximos precisam ser ao menos esta fração da largura entre os strikes.
_SCAN_MIN_WIDTH_SHARE = 0.10


@dataclass(frozen=True)
class PositionSize:
    lots: int
    # Em R$, para a quantidade de lotes.
    employed: float
    max_risk: float


def size_position(max_loss_unit: float, debit_unit: float, capital: float) -> PositionSize | None:
    """Quantos lotes cabem sem que a perda máxima passe do capital. None se nem um lote couber."""
    unit_risk = max(max_loss_unit, debit_unit, 0.0)
    if unit_risk <= 0 or capital <= 0:
        return None
    lots = floor(capital / unit_risk)
    if lots < 1:
        return None
    return PositionSize(lots, unit_risk * lots, max_loss_unit * lots)


def mark_pnl(legs: Sequence[OptionLeg], prices: Mapping[str, float]) -> float | None:
    """Resultado por unidade de estrutura a preços de um pregão. None se faltar alguma perna."""
    total = 0.0
    for leg in legs:
        price = prices.get(leg.symbol)
        if price is None:
            return None
        total += (1 if leg.action is LegAction.BUY else -1) * (price - leg.premium) * leg.quantity
    return total


def settlement_pnl(legs: Sequence[OptionLeg], spot: float) -> float:
    """No vencimento, o resultado depende só do preço do ativo."""
    return float(position_pnl(legs, spot))


def book_entry(legs: Sequence[OptionLeg], quotes: Mapping[str, OptionQuote]) -> dict[str, float] | None:
    """Preço de entrada no lado desfavorável: compra no ask, venda no bid. None sem os dois lados."""
    prices = {}
    for leg in legs:
        quote = quotes.get(leg.symbol)
        if quote is None or not quote.bid or not quote.ask or quote.bid > quote.ask:
            return None
        prices[leg.symbol] = quote.ask if leg.action is LegAction.BUY else quote.bid
    return prices


def book_pnl(
    legs: Sequence[OptionLeg], entry: Mapping[str, float] | None, quotes: Mapping[str, OptionQuote], settlement_spot: float | None = None
) -> float | None:
    """Resultado saindo no lado desfavorável. No vencimento, a saída é o valor intrínseco, sem spread."""
    if not entry:
        return None
    total = 0.0
    for leg in legs:
        sign = 1 if leg.action is LegAction.BUY else -1
        if settlement_spot is not None:
            intrinsic = settlement_spot - leg.strike if leg.kind is OptionKind.CALL else leg.strike - settlement_spot
            leave = max(intrinsic, 0.0)
        else:
            quote = quotes.get(leg.symbol)
            if quote is None or not quote.bid or not quote.ask or quote.bid > quote.ask:
                return None
            leave = quote.bid if leg.action is LegAction.BUY else quote.ask
        total += sign * (leave - entry[leg.symbol]) * leg.quantity
    return total


def book_max_loss(legs: Sequence[OptionLeg], entry: Mapping[str, float] | None) -> float | None:
    """Perda máxima com os preços de entrada do livro. None se não houver risco definido."""
    if not entry:
        return None
    repriced = [leg.model_copy(update={"premium": entry[leg.symbol]}) for leg in legs]
    loss = analyze_payoff(repriced).max_loss
    return loss if loss and loss > 0 else None


def expected_pnl(legs: Sequence[OptionLeg], spot: float, sigma: float, t: float, r: float) -> float:
    """Valor esperado no vencimento, sob distribuição lognormal neutra ao risco, sem descontar."""
    if spot <= 0 or sigma <= 0 or t <= 0:
        raise ValueError("spot, sigma e t precisam ser positivos")
    root = sigma * sqrt(t)
    drift = log(spot) + (r - sigma * sigma / 2) * t
    points = np.linspace(-6, 6, 4001)
    prices = np.exp(drift + root * points)
    density = np.exp(-(points**2) / 2) / sqrt(2 * np.pi)
    return float(np.trapezoid(position_pnl(legs, prices) * density, points))


@dataclass(frozen=True)
class PathResult:
    final_pnl_unit: float | None
    best_unit: float | None
    worst_unit: float | None
    max_drawdown_unit: float
    exit_day: str | None
    exit_reason: str
    marks_used: int


def evaluate_path(
    marks: Sequence[tuple[str, float]], max_loss_unit: float, target_pct: float | None, stop_pct: float | None
) -> PathResult:
    """Percorre só marcações completas, em ordem. Alvo e stop são % da perda máxima.

    A saída é presumida no fechamento do pregão em que o limite foi cruzado: dentro do dia
    não há dado, e a execução real poderia ser pior.
    """
    if not marks:
        return PathResult(None, None, None, 0.0, None, "SEM_MARCACAO", 0)
    peak = 0.0
    drawdown = 0.0
    best = worst = marks[0][1]
    for index, (day, pnl) in enumerate(marks):
        best, worst = max(best, pnl), min(worst, pnl)
        peak = max(peak, pnl)
        drawdown = max(drawdown, peak - pnl)
        if target_pct is not None and pnl >= max_loss_unit * target_pct / 100:
            return PathResult(pnl, best, worst, drawdown, day, "ALVO", index + 1)
        if stop_pct is not None and pnl <= -max_loss_unit * stop_pct / 100:
            return PathResult(pnl, best, worst, drawdown, day, "STOP", index + 1)
    return PathResult(marks[-1][1], best, worst, drawdown, marks[-1][0], "FIM_DO_PERIODO", len(marks))


def returns_summary(
    pnl_unit: float | None, lots: int, capital: float, employed: float, max_risk: float, cost: float
) -> dict:
    if pnl_unit is None:
        return {"pnl_brl": None, "return_on_capital": None, "return_on_employed": None, "return_on_risk": None}
    pnl = pnl_unit * lots - cost
    return {
        "pnl_brl": pnl,
        "return_on_capital": pnl / capital if capital else None,
        "return_on_employed": pnl / employed if employed else None,
        "return_on_risk": pnl / max_risk if max_risk else None,
    }


def _vertical(key: str, name: str, buy: OptionQuote, sell: OptionQuote, lot: int, rationale: str) -> Candidate | None:
    buy_price, _ = execution_price(buy, LegAction.BUY, use_book=False)
    sell_price, _ = execution_price(sell, LegAction.SELL, use_book=False)
    legs = [
        OptionLeg(symbol=buy.symbol, strike=buy.strike, expiry=buy.expiry, kind=buy.kind, action=LegAction.BUY, quantity=lot, premium=buy_price),
        OptionLeg(symbol=sell.symbol, strike=sell.strike, expiry=sell.expiry, kind=sell.kind, action=LegAction.SELL, quantity=lot, premium=sell_price),
    ]
    payoff = analyze_payoff(legs)
    # Preços não simultâneos podem sugerir arbitragem: fora, em vez de parecer lucro garantido.
    if payoff.max_loss is None or payoff.max_profit is None:
        return None
    minimum = abs(buy.strike - sell.strike) * lot * _SCAN_MIN_WIDTH_SHARE
    if payoff.max_loss < minimum or payoff.max_profit < minimum:
        return None
    return Candidate(
        key=key,
        proposal=StrategyProposal(
            name=name,
            legs=legs,
            max_profit=payoff.max_profit,
            max_loss=payoff.max_loss,
            breakeven_points=list(payoff.breakevens),
            risk_reward_ratio=payoff.risk_reward_ratio,
            rationale=rationale,
            assumptions=["Prêmios pelo fechamento do pregão: indicativos, sem garantia de execução."],
        ),
        quotes=(buy, sell),
        bases=(PriceBasis.CLOSE, PriceBasis.CLOSE),
    )


def vertical_scan(quotes: Sequence[OptionQuote], spot: float, t: float, r: float, lot: int = 100) -> list[Candidate]:
    """Varre pares de strikes líquidos e fica, em cada um dos 4 tipos de trava, com o de maior
    valor esperado por real de risco. Só usa dados do pregão recebido."""
    pool = [
        quote
        for quote in quotes
        if quote.close
        and quote.iv
        and (quote.volume or 0) >= MIN_SCAN_VOLUME
        and (quote.open_interest or 0) >= MIN_SCAN_OPEN_INTEREST
        and (quote.trades or 0) >= _SCAN_MIN_TRADES
    ]
    kinds = (
        ("varredura_alta_call", "Trava de alta com call (varredura)", OptionKind.CALL, "low_buy", "Melhor par de calls para alta."),
        ("varredura_baixa_call", "Trava de baixa com call (varredura)", OptionKind.CALL, "high_buy", "Melhor par de calls com crédito."),
        ("varredura_alta_put", "Trava de alta com put (varredura)", OptionKind.PUT, "low_buy", "Melhor par de puts com crédito."),
        ("varredura_baixa_put", "Trava de baixa com put (varredura)", OptionKind.PUT, "high_buy", "Melhor par de puts para queda."),
    )
    found: list[Candidate] = []
    for key, name, kind, side, rationale in kinds:
        series = sorted((quote for quote in pool if quote.kind is kind), key=lambda quote: quote.strike)
        best, best_score = None, None
        for index, low in enumerate(series):
            for high in series[index + 1 :]:
                if (high.strike - low.strike) / spot > _SCAN_MAX_WIDTH:
                    break
                if abs(low.iv - high.iv) > _SCAN_MAX_IV_GAP:
                    continue
                buy, sell = (low, high) if side == "low_buy" else (high, low)
                candidate = _vertical(key, name, buy, sell, lot, rationale)
                if candidate is None:
                    continue
                sigma = (buy.iv + sell.iv) / 2
                score = expected_pnl(candidate.proposal.legs, spot, sigma, t, r) / candidate.proposal.max_loss
                if best_score is None or score > best_score:
                    best, best_score = candidate, score
        if best:
            found.append(best)
    return found


@dataclass
class _Group:
    returns: list[float] = field(default_factory=list)
    risks: list[float] = field(default_factory=list)


def _stats(values: list[float]) -> dict:
    return {
        "count": len(values),
        "hit_rate": sum(value > 0 for value in values) / len(values),
        "mean_return": mean(values),
        "median_return": median(values),
        "std_return": pstdev(values),
        "best_return": max(values),
        "worst_return": min(values),
    }


def _reading(close_median: float, book_median: float | None) -> str:
    if book_median is None:
        return "EXECUCAO_NAO_MEDIDA"
    if book_median > 0:
        return "LUCRO_NOS_DOIS_LIMITES"
    if close_median > 0:
        return "LUCRO_SO_NO_FECHAMENTO"
    return "SEM_LUCRO"


def rank_groups(rows: Sequence[Mapping], key: str) -> list[dict]:
    """Ordena pela mediana do retorno sobre o risco, não pela média: uma operação excepcional
    não sobe o grupo. Grupo com poucas datas de entrada fica sem posição."""
    groups: dict[str, _Group] = {}
    entries: dict[str, set[str]] = {}
    book: dict[str, list[float]] = {}
    breakdowns: dict[str, dict[str, dict[str, list[float]]]] = {}
    for row in rows:
        value = row["return_on_risk"]
        if value is None:
            continue
        name = row[key]
        groups.setdefault(name, _Group()).returns.append(value)
        groups[name].risks.append(row["max_risk_brl"])
        if row.get("return_on_risk_book") is not None:
            book.setdefault(name, []).append(row["return_on_risk_book"])
        entries.setdefault(name, set()).add(row["entry_day"])
        slot = breakdowns.setdefault(name, {"symbol": {}, "horizon": {}, "regime": {}})
        slot["symbol"].setdefault(row["symbol"], []).append(value)
        slot["horizon"].setdefault(str(row["horizon_days"]), []).append(value)
        slot["regime"].setdefault(row.get("regime") or "SEM_DADO", []).append(value)

    ranked = []
    for name, group in groups.items():
        stats = _stats(group.returns)
        book_values = book.get(name, [])
        book_median = median(book_values) if book_values else None
        ranked.append(
            {
                key: name,
                **stats,
                "book_count": len(book_values),
                "book_hit_rate": sum(value > 0 for value in book_values) / len(book_values) if book_values else None,
                "book_median_return": book_median,
                "reading": _reading(stats["median_return"], book_median),
                "mean_risk_brl": mean(group.risks),
                "entry_dates": len(entries[name]),
                "sufficient_sample": len(entries[name]) >= MIN_RANKED_ENTRIES,
                "by_symbol": {k: _stats(v) for k, v in breakdowns[name]["symbol"].items()},
                "by_horizon": {k: _stats(v) for k, v in breakdowns[name]["horizon"].items()},
                "by_regime": {k: _stats(v) for k, v in breakdowns[name]["regime"].items()},
            }
        )
    # Ordena pelo limite conservador: lucrar só no fechamento não prova que a operação era possível.
    ranked.sort(
        key=lambda item: (
            not item["sufficient_sample"],
            item["book_median_return"] is None,
            -(item["book_median_return"] or 0.0),
            -item["median_return"],
            -item["hit_rate"],
        )
    )
    position = 0
    for item in ranked:
        if item["sufficient_sample"]:
            position += 1
            item["position"] = position
        else:
            item["position"] = None
    return ranked
