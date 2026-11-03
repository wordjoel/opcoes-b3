"""Estrutura de mercado em barras diárias: topos e fundos, BOS e CHoCH.

Um topo ou fundo só existe depois de `pivot` barras de cada lado, então a leitura não usa
o futuro. O rompimento é pelo fechamento. BOS rompe a favor da tendência; CHoCH, contra.
Descreve o que o preço fez: não é previsão nem sinal de operação.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from core.types import PriceBar

DEFAULT_PIVOT = 5


@dataclass(frozen=True)
class StructureEvent:
    day: str
    kind: str  # BOS ou CHOCH
    direction: str  # UP ou DOWN
    level: float
    bar_index: int


@dataclass(frozen=True)
class MarketStructure:
    # UP, DOWN ou None enquanto nada foi rompido.
    trend: str | None
    # Topo e fundo mais recentes ainda não rompidos.
    last_swing_high: float | None
    last_swing_low: float | None
    events: list[StructureEvent] = field(default_factory=list)


def analyze_structure(bars: Sequence[PriceBar], pivot: int = DEFAULT_PIVOT) -> MarketStructure:
    if pivot < 1:
        raise ValueError("pivot precisa ser positivo")
    trend: str | None = None
    swing_high: float | None = None
    swing_low: float | None = None
    events: list[StructureEvent] = []

    for index, bar in enumerate(bars):
        center = index - pivot
        if center >= pivot:
            window = bars[center - pivot : index + 1]
            middle = bars[center]
            others = [item for position, item in enumerate(window) if position != pivot]
            if all(middle.high > item.high for item in others):
                swing_high = middle.high
            if all(middle.low < item.low for item in others):
                swing_low = middle.low

        direction, level = None, None
        if swing_high is not None and bar.close > swing_high:
            direction, level, swing_high = "UP", swing_high, None
        elif swing_low is not None and bar.close < swing_low:
            direction, level, swing_low = "DOWN", swing_low, None
        if direction:
            against = trend is not None and trend != direction
            events.append(StructureEvent(bar.day.isoformat(), "CHOCH" if against else "BOS", direction, level, index))
            trend = direction

    return MarketStructure(trend, swing_high, swing_low, events)
