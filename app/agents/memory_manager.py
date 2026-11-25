"""Memória de longo prazo do Jarbas, persistida no mesmo banco do app.

Arquitetura: a memória é um serviço injetado no orquestrador. Ela guarda apenas
trechos curtos das conversas, nunca chaves de API, e devolve lembretes rotulados
para o prompt. A recuperação usa sobreposição de termos: determinística, auditável
e sem dependência de serviço externo de vetores.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from db.client import Database

MAX_CONTENT = 600
MAX_RECORDS = 240
STOPWORDS = frozenset(
    "a as o os e ou de da do das dos em no na nos nas um uma uns umas que com para por como "
    "mais menos muito seu sua seus suas meu minha meus minhas esta este esse essa isto aq ui".split()
)
SECRET_HINT = re.compile(r"sk-[A-Za-z0-9_-]{8,}|bearer\s+\S+|api[_-]?key\s*[:=]|senha\s*[:=]", re.I)
TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)


@dataclass(frozen=True)
class MemoryRecord:
    identity: int
    content: str
    source: str
    created_at: str
    score: float = 0.0


def _tokens(text: str) -> Counter[str]:
    return Counter(word.lower() for word in TOKEN.findall(text) if word.lower() not in STOPWORDS)


class MemoryManager:
    """Leitura e escrita best-effort: ausência da tabela nunca derruba a resposta."""

    def __init__(self, max_records: int = MAX_RECORDS) -> None:
        self.max_records = max_records

    @staticmethod
    def safe(content: str) -> bool:
        return not SECRET_HINT.search(content)

    def remember(self, db: Database, conversation: str, role: str, content: str, now: datetime) -> bool:
        text = " ".join(content.split())[:MAX_CONTENT]
        if role not in ("user", "assistant") or not text or not self.safe(text):
            return False
        try:
            db.run(
                "INSERT INTO jarbas_memory (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation, role, text, now.isoformat()),
            )
            db.run(
                "DELETE FROM jarbas_memory WHERE id NOT IN (SELECT id FROM jarbas_memory ORDER BY id DESC LIMIT ?)",
                (self.max_records,),
            )
            return True
        except Exception:  # noqa: BLE001 — tabela ausente ou banco indisponível: memória é opcional
            return False

    def recall(self, db: Database, question: str, limit: int = 5) -> list[MemoryRecord]:
        query = _tokens(question)
        if not query:
            return []
        try:
            rows = db.fetch("SELECT id, content, role, created_at FROM jarbas_memory ORDER BY id DESC LIMIT ?", (self.max_records,))
        except Exception:  # noqa: BLE001
            return []
        scored: list[MemoryRecord] = []
        for identity, content, role, created_at in rows:
            words = _tokens(content)
            if not words:
                continue
            score = sum(query[word] for word in words & query.keys()) / (len(query) ** 0.5)
            if score > 0:
                scored.append(MemoryRecord(identity, content, role, created_at, score))
        return sorted(scored, key=lambda item: (-item.score, -item.identity))[:limit]

    @staticmethod
    def render(records: Sequence[MemoryRecord]) -> str:
        if not records:
            return ""
        return "\n".join(f"{index}. {item.content}" for index, item in enumerate(records, start=1))

    def purge(self, db: Database, retention_days: int, now: datetime) -> None:
        limit = (now - timedelta(days=retention_days)).isoformat()
        try:
            db.run("DELETE FROM jarbas_memory WHERE created_at < ?", (limit,))
        except Exception:  # noqa: BLE001
            pass
