"""Custos operacionais definidos pelo proprietário: o sistema não presume corretagem, taxa nem imposto.

Modelo de ida e volta: cada perna gera uma ordem na montagem e outra no desmonte, e as taxas
da B3 incidem sobre o financeiro dos prêmios nas duas pontas. O financeiro do desmonte não é
conhecido na entrada; usa-se o da montagem como estimativa. Exercício no vencimento tem
custos próprios que este modelo não separa.

Imposto: alíquota sobre o ganho de cada estrutura, como se ela não fosse compensada com
prejuízos do mês. Serve de teto do imposto, não de cálculo do DARF.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from core.types import OptionLeg


@dataclass(frozen=True)
class CostSchedule:
    # Corretagem fixa por ordem, em reais.
    per_order_brl: float
    # Emolumentos e taxas da B3, em % do financeiro negociado.
    fee_pct: float
    # Alíquota de imposto sobre o ganho, em %.
    income_tax_pct: float

    def __post_init__(self) -> None:
        if self.per_order_brl < 0:
            raise ValueError("Corretagem não pode ser negativa")
        if not 0 <= self.fee_pct <= 5:
            raise ValueError("Taxas precisam estar entre 0 e 5%")
        if not 0 <= self.income_tax_pct <= 100:
            raise ValueError("Alíquota precisa estar entre 0 e 100%")


def premium_notional(legs: Sequence[OptionLeg]) -> float:
    """Financeiro bruto da montagem: soma dos prêmios pagos e recebidos, sem sinal."""
    return sum(abs(leg.premium) * leg.quantity for leg in legs)


def round_trip_cost(legs: Sequence[OptionLeg], schedule: CostSchedule, lots: int = 1) -> float:
    """Custo de montar e desmontar `lots` lotes. As ordens não crescem com os lotes; as taxas, sim."""
    if lots < 1:
        raise ValueError("lots precisa ser positivo")
    orders = 2 * len(legs) * schedule.per_order_brl
    fees = 2 * premium_notional(legs) * lots * schedule.fee_pct / 100
    return orders + fees


def net_of_costs(gross: float | None, cost: float, schedule: CostSchedule) -> float | None:
    """Resultado depois dos custos e, se positivo, do imposto. None = ilimitado."""
    if gross is None:
        return None
    before_tax = gross - cost
    if before_tax <= 0:
        return before_tax
    return before_tax * (1 - schedule.income_tax_pct / 100)
