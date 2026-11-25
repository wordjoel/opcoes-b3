"""Embedding determinístico em memória, sem serviço externo.

Cada termo é maps para uma posição estável por hash e para um sinal também estável.
A similaridade é o cosseno dos vetores esparsos. Isso não é um modelo semântico:
é uma indexação local, auditável e suficiente para recuperar trechos por termos.
"""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence

DIMENSIONS = 192
STOPWORDS = frozenset(
    "a as o os e ou de da do das dos em no na nos nas um uma uns umas que com para por como "
    "mais menos muito seu sua seus suas meu minha meus minhas este esta esses estas isto "
    "do da ao aos ela ele eles elas foi foram sera será são era eram pelo pela pelos pelas "
    "se não sim quando onde quais qual quem porque então também".split()
)
TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def tokens(text: str) -> list[str]:
    return [word for word in TOKEN.findall(normalize(text)) if word not in STOPWORDS]


def embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    counts = Counter(tokens(text))
    for word, count in counts.items():
        digest = hashlib.md5(word.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def dumps(vector: Sequence[float]) -> str:
    return json.dumps([round(value, 6) for value in vector], separators=(",", ":"))


def loads(raw: str) -> list[float]:
    try:
        values = json.loads(raw)
        return [float(value) for value in values] if isinstance(values, list) else []
    except (ValueError, TypeError):
        return []


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
