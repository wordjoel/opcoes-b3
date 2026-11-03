"""Avalia intenções e registra operações informadas, sempre pelo barramento.

Intenção (tópico intent.STRATEGY): {"id": str, "legs": [campos de OptionLeg]}.
Operação já feita na corretora (tópico portfolio.FILL):
{"symbol": str, "quantity": int, "price": float, "side": "BUY" | "SELL"}.
"""

import logging
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import ValidationError

from core.bus import B3Bus, Event
from core.types import LegAction, OptionLeg
from quant.payoff import analyze_payoff
from quant.portfolio import PortfolioState

logger = logging.getLogger("B3.RiskManager")


@dataclass(frozen=True)
class RiskConfig:
    # Tamanho máximo da posição por série, em opções. Sem valor padrão: o limite é decisão do usuário.
    max_position_size: int


class RiskManager:
    def __init__(self, bus: B3Bus, portfolio: PortfolioState, config: RiskConfig) -> None:
        self.bus = bus
        self.portfolio = portfolio
        self.config = config
        bus.subscribe("intent.STRATEGY", self._on_intent)
        bus.subscribe("portfolio.FILL", self._on_fill)

    def evaluate(self, data: dict[str, Any]) -> list[str]:
        """Motivos de reprovação. Lista vazia = aprovada nestas regras."""
        try:
            legs = [OptionLeg(**leg) for leg in data["legs"]]
            if not legs:
                return ["NO_LEGS"]
            payoff = analyze_payoff(legs)
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            # A intenção é registrada no barramento: não repete o conteúdo recusado aqui.
            return [f"INVALID_INTENT: {type(error).__name__}"]

        reasons = []
        for leg in legs:
            current = self.portfolio.positions.get(leg.symbol)
            signed = leg.quantity if leg.action is LegAction.BUY else -leg.quantity
            proposed = (current.quantity if current else 0) + signed
            if abs(proposed) > self.config.max_position_size:
                reasons.append(
                    f"EXPOSURE_LIMIT: {leg.symbol} iria a {proposed}; o limite é {self.config.max_position_size}"
                )
        if payoff.max_loss is None:
            reasons.append("UNLIMITED_LOSS")
        elif payoff.max_loss > self.portfolio.cash:
            # Em débito é o custo; em crédito, o que pode ser exigido. Margem não é calculada.
            reasons.append(f"INSUFFICIENT_CASH: perda máxima de {payoff.max_loss:.2f} acima do caixa")
        return reasons

    async def _on_intent(self, event: Event) -> None:
        data = event["data"]
        reasons = self.evaluate(data)
        await self.bus.publish(
            "risk.VERDICT",
            {"intent_id": data.get("id"), "decision": "REJECTED" if reasons else "APPROVED", "reasons": reasons},
        )

    async def _on_fill(self, event: Event) -> None:
        fill = event["data"]
        if fill["side"] not in ("BUY", "SELL"):
            raise ValueError("Lado inválido na operação informada")
        self.portfolio.apply_fill(fill["symbol"], fill["quantity"], fill["price"], fill["side"] == "BUY")
        await self.bus.publish(
            "portfolio.STATE",
            {
                "cash": self.portfolio.cash,
                "realized_pnl": self.portfolio.realized_pnl,
                "positions": {symbol: asdict(p) for symbol, p in self.portfolio.positions.items()},
            },
        )
