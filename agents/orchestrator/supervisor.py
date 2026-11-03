"""Leva uma estratégia até a decisão de risco. Termina na decisão: este sistema não envia ordens.

Sem um veredito explícito de aprovação, o resultado é reprovação: falha ou demora do
gestor de risco nunca libera uma estratégia.
"""

import asyncio
import logging
import uuid
from typing import Any

from core.bus import B3Bus, Event

logger = logging.getLogger("B3.Supervisor")

_DEFAULT_TIMEOUT_SECONDS = 5.0


class IntelligenceSupervisor:
    def __init__(self, bus: B3Bus, timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS) -> None:
        self.bus = bus
        self.timeout_seconds = timeout_seconds

    async def propose_strategy(self, symbol: str, strategy_type: str, legs: list[dict[str, Any]]) -> dict[str, Any]:
        """Publica a intenção, aguarda o risco e publica o resultado em decision.RESULT."""
        intent_id = str(uuid.uuid4())
        verdicts: list[dict[str, Any]] = []

        def capture(event: Event) -> None:
            if event["data"].get("intent_id") == intent_id:
                verdicts.append(event["data"])

        self.bus.subscribe("risk.VERDICT", capture)
        reasons = ["NO_VERDICT: o gestor de risco não respondeu"]
        try:
            await asyncio.wait_for(
                self.bus.publish(
                    "intent.STRATEGY", {"id": intent_id, "symbol": symbol, "strategy_type": strategy_type, "legs": legs}
                ),
                self.timeout_seconds,
            )
        except TimeoutError:
            reasons = ["RISK_TIMEOUT: o gestor de risco demorou demais"]
        finally:
            self.bus.unsubscribe("risk.VERDICT", capture)

        if verdicts:
            decision, reasons = verdicts[0]["decision"], verdicts[0]["reasons"]
        else:
            decision = "REJECTED"
            logger.warning("Estratégia %s reprovada: %s", intent_id, reasons)

        result = {"intent_id": intent_id, "symbol": symbol, "decision": decision, "reasons": reasons}
        await self.bus.publish("decision.RESULT", result)
        return result
