"""Barramento de eventos assíncrono em memória, com tópicos e registro para replay.

O registro é limitado e some quando o processo termina: serve para depuração, não
para auditoria permanente.
"""

import asyncio
import inspect
import logging
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("B3.Bus")

Event = dict[str, Any]
Handler = Callable[[Event], Any]


class B3Bus:
    def __init__(self, max_log_size: int = 10_000) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._event_log: deque[Event] = deque(maxlen=max_log_size)

    def subscribe(self, topic: str, handler: Handler) -> None:
        if not callable(handler):
            raise ValueError("O handler precisa ser chamável")
        self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        if handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)

    async def publish(self, topic: str, data: dict[str, Any]) -> str:
        """Registra o evento e espera todos os handlers. Devolve o id do evento."""
        event = {
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "data": data,
        }
        self._event_log.append(event)
        # Cópia: um handler pode se descadastrar durante a entrega.
        handlers = list(self._subscribers[topic])
        await asyncio.gather(*(self._safe_call(handler, event) for handler in handlers))
        return event["id"]

    async def _safe_call(self, handler: Handler, event: Event) -> None:
        """Falha de um handler não derruba os outros. Quem depende de resposta deve tratar a ausência dela."""
        try:
            result = handler(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception("Erro em handler do tópico %s", event["topic"])

    def get_replay_stream(self, topic_prefix: str = "", since_ts: str | None = None) -> list[Event]:
        return [
            event
            for event in self._event_log
            if event["topic"].startswith(topic_prefix) and (since_ts is None or event["ts"] >= since_ts)
        ]
