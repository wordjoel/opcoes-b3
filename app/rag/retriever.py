"""Recuperação local de trechos para o RAG do Jarbas.

Arquitetura: o retriever lê os chunks gravados pelo ingest, reconstrói os vetores
e ordena por cosseno com a pergunta. O texto devolvido é rotulado com documento e
página, e trechos que parecem conter segredos são descartados antes do prompt.
"""

import re
from dataclasses import dataclass

from app.rag.embedding import cosine, embed, loads
from db.client import Database

SECRET_HINT = re.compile(r"sk-[A-Za-z0-9_-]{8,}|bearer\s+\S+|api[_-]?key\s*[:=]|senha\s*[:=]", re.I)


@dataclass(frozen=True)
class RetrievedChunk:
    name: str
    page: int
    content: str
    score: float

    def label(self) -> str:
        page = f", pág. {self.page}" if self.page else ""
        return f"[{self.name}{page}] {self.content}"


def retrieve(db: Database, query: str, limit: int = 4, min_score: float = 0.02) -> list[RetrievedChunk]:
    wanted = embed(query)
    if not any(wanted):
        return []
    try:
        rows = db.fetch(
            "SELECT d.name, c.page, c.content, c.embedding FROM rag_chunks c"
            " JOIN rag_documents d ON d.id = c.document_id ORDER BY c.id"
        )
    except Exception:  # noqa: BLE001 — tabela ausente: RAG é apoio opcional
        return []
    found: list[RetrievedChunk] = []
    for name, page, content, raw in rows:
        text = " ".join(str(content).split())
        if not text or SECRET_HINT.search(text):
            continue
        score = cosine(wanted, loads(raw))
        if score >= min_score:
            found.append(RetrievedChunk(str(name), int(page or 0), text, score))
    return sorted(found, key=lambda item: -item.score)[:limit]


def build_context(db: Database, query: str, limit: int = 4) -> str:
    chunks = retrieve(db, query, limit)
    if not chunks:
        return ""
    return "\n".join(f"{index}. {chunk.label()}" for index, chunk in enumerate(chunks, start=1))
