"""Catálogo de modelos do OpenRouter, consultado na API pública e guardado por 1 hora.

Gratuito é o modelo com preço zero de entrada e saída. Modelo pago só entra na lista de
uso se o proprietário autorizar nas configurações: o app nunca gera cobrança sozinho.
"""

import time
from collections.abc import Callable

import httpx

from app.jarbas.providers import OPENROUTER_FREE_MODELS

MODELS_URL = "https://openrouter.ai/api/v1/models"
CATALOG_TTL = 3600.0
# Modelos tentados por pergunta: o escolhido mais os gratuitos de reserva.
MAX_CHAIN = 4

_cache: dict = {"at": None, "models": []}


def _price(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_models(payload: dict) -> list[dict]:
    models = []
    for item in payload.get("data") or []:
        identity = item.get("id")
        if not isinstance(identity, str) or not identity:
            continue
        architecture = item.get("architecture") or {}
        outputs = architecture.get("output_modalities")
        # Modelos de música, imagem ou embeddings não conversam.
        if (isinstance(outputs, list) and "text" not in outputs) or str(architecture.get("modality", "")).split("->")[-1] not in ("", "text"):
            continue
        pricing = item.get("pricing") or {}
        prompt, completion = _price(pricing.get("prompt")), _price(pricing.get("completion"))
        free = identity.endswith(":free") or (prompt == 0 and completion == 0)
        models.append(
            {
                "id": identity,
                "name": item.get("name") or identity,
                "context_length": item.get("context_length"),
                "free": free,
                # US$ por milhão de tokens, como o OpenRouter mostra.
                "prompt_per_million": None if prompt is None else prompt * 1_000_000,
                "completion_per_million": None if completion is None else completion * 1_000_000,
            }
        )
    models.sort(key=lambda model: (not model["free"], -(model["context_length"] or 0), model["id"]))
    return models


def list_models(client: httpx.Client, clock: Callable[[], float] = time.monotonic, refresh: bool = False) -> list[dict]:
    """Lista em cache; se a API falhar, devolve a última lista boa (ou vazia)."""
    now = clock()
    if not refresh and _cache["at"] is not None and now - _cache["at"] < CATALOG_TTL:
        return _cache["models"]
    try:
        response = client.get(MODELS_URL, timeout=10.0)
        response.raise_for_status()
        models = parse_models(response.json())
    except (httpx.HTTPError, ValueError):
        return _cache["models"]
    if models:
        _cache.update(at=now, models=models)
    return _cache["models"] or models


def is_paid(model_id: str, catalog: list[dict]) -> bool:
    """Desconhecido conta como pago: na dúvida, não arrisca cobrança."""
    if model_id.endswith(":free"):
        return False
    found = next((model for model in catalog if model["id"] == model_id), None)
    return not (found and found["free"])


def model_chain(selected: str | None, catalog: list[dict], allow_paid: bool) -> str:
    """Modelo escolhido primeiro e gratuitos de reserva, sem repetir e sem pago não autorizado."""
    chain: list[str] = []

    def add(model_id: str) -> None:
        if model_id and model_id not in chain and (allow_paid or not is_paid(model_id, catalog)):
            chain.append(model_id)

    if selected:
        add(selected)
    available = {model["id"] for model in catalog}
    for model_id in OPENROUTER_FREE_MODELS.split(","):
        if not catalog or model_id in available:
            add(model_id)
    for model in catalog:
        if model["free"]:
            add(model["id"])
    return ",".join(chain[:MAX_CHAIN])
