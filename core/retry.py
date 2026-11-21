"""Tentativas curtas para falhas HTTP transitórias, com backoff e jitter.

Só 408, 425 e 5xx são repetidos. 404 ("sem arquivo"), 429 (limite de requisições)
e 4xx de autoria continuam com a semântica de cada fonte. A função não devolve
valor inventado: se todas as tentativas falharem, a última resposta ou exceção
segue para o tratamento existente no provider.
"""

import logging
import random
import time
from collections.abc import Callable

import httpx

logger = logging.getLogger("B3.Retry")

TRANSIENT_STATUS = frozenset({408, 425, 500, 502, 503, 504})
DEFAULT_ATTEMPTS = 3
BASE_DELAY_SECONDS = 0.25
MAX_DELAY_SECONDS = 2.0
JITTER_RATIO = 0.20

# Indireção para os testes não dormirem de verdade; a assinatura pública aceita
# uma função de espera própria quando o teste quer conferir o intervalo.
_sleep = time.sleep


def _pause(attempt: int, base_delay: float, max_delay: float, sleep: Callable[[float], None], reason: str) -> None:
    delay = min(base_delay * (2**attempt), max_delay)
    delay += random.uniform(0.0, delay * JITTER_RATIO)
    logger.warning("Falha HTTP transitória (%s): nova tentativa em %.2fs", reason, delay)
    sleep(delay)


def retry_request(
    call: Callable[[], httpx.Response],
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = BASE_DELAY_SECONDS,
    max_delay: float = MAX_DELAY_SECONDS,
    sleep: Callable[[float], None] | None = None,
) -> httpx.Response:
    """Chama `call` até obter resposta não transitória ou esgotar as tentativas.

    Erros de transporte (timeout, conexão) também são transitórios. Na última
    tentativa a exceção é propagada, sem engolir a causa original.
    """
    if attempts < 1:
        raise ValueError("attempts precisa ser pelo menos 1")
    sleeper = _sleep if sleep is None else sleep
    for attempt in range(attempts):
        try:
            response = call()
        except httpx.TransportError as error:
            if attempt == attempts - 1:
                raise
            _pause(attempt, base_delay, max_delay, sleeper, type(error).__name__)
        else:
            if response.status_code not in TRANSIENT_STATUS or attempt == attempts - 1:
                return response
            _pause(attempt, base_delay, max_delay, sleeper, f"HTTP {response.status_code}")
    raise AssertionError("código inalcançável")
