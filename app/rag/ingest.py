"""Ingestão de documentos para o RAG local.

Arquitetura: um arquivo é extraído em páginas, dividido em trechos sobrepostos e
gravado com um embedding determinístico. ``pypdf`` é usado quando instalado; na
falta dele, um extrator stdlib lê fluxos de PDF simples (inclusive FlateDecode).
O hash do conteúdo evita duplicar o mesmo documento.
"""

import hashlib
import io
import re
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.rag.embedding import dumps, embed
from db.client import Database

MAX_CHARS = 1200
OVERLAP = 160


@dataclass(frozen=True)
class IngestResult:
    document_id: int
    name: str
    pages: int
    chunks: int
    updated: bool


def _unescape(value: str) -> str:
    return re.sub(r"\\([()\\])", r"\1", value)


def _streams(data: bytes) -> list[str]:
    found: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = match.group(1)
        prefix = data[max(0, match.start() - 300) : match.start()]
        if b"FlateDecode" in prefix:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                continue
        found.append(raw.decode("latin-1", errors="replace"))
    return found


def _text_from_stream(stream: str) -> str:
    pieces: list[str] = []
    for match in re.finditer(r"\(((?:\\.|[^()\\])*)\)\s*Tj", stream):
        pieces.append(_unescape(match.group(1)))
    for array in re.finditer(r"\[(.*?)\]\s*TJ", stream, re.S):
        for match in re.finditer(r"\(((?:\\.|[^()\\])*)\)", array.group(1)):
            pieces.append(_unescape(match.group(1)))
    return " ".join(" ".join(pieces).split())


def _fallback_pdf(data: bytes) -> list[str]:
    pages = max(1, len(re.findall(rb"/Type\s*/Page\b", data)))
    text = "\n\f\n".join(_text_from_stream(stream) for stream in _streams(data))
    if not text.strip():
        text = data.decode("latin-1", errors="replace")
    parts = text.split("\f")
    return [part.strip() for part in parts[:pages]] or [""]


def extract_pages(data: bytes, name: str) -> list[str]:
    """Texto por página. Nunca lança se o PDF estiver corrompido: devolve o que deu para ler."""
    if not name.lower().endswith(".pdf"):
        text = data.decode("utf-8", errors="replace")
        return [text] if text.strip() else []
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        return [page for page in pages if page]
    except ImportError:
        return [page for page in _fallback_pdf(data) if page]
    except Exception:  # noqa: BLE001 — PDF inválido cai para o leitor simples
        return [page for page in _fallback_pdf(data) if page]


def extract_text(data: bytes, name: str) -> str:
    return "\n\n".join(extract_pages(data, name))


def chunk_pages(pages: Sequence[tuple[int, str]], max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    for page, text in pages:
        words = text.split()
        if not words:
            continue
        current: list[str] = []
        size = 0
        for word in words:
            extra = len(word) + (1 if current else 0)
            if current and size + extra > max_chars:
                chunks.append((page, " ".join(current)))
                tail: list[str] = []
                tail_size = 0
                for previous in reversed(current):
                    cost = len(previous) + (1 if tail else 0)
                    if tail_size + cost > overlap:
                        break
                    tail.insert(0, previous)
                    tail_size += cost
                current = tail
                size = tail_size
            current.append(word)
            size += len(word) + (1 if len(current) > 1 else 0)
        if current:
            chunks.append((page, " ".join(current)))
    return chunks


def ingest_bytes(db: Database, name: str, data: bytes, now: datetime, source: str | None = None) -> IngestResult:
    """Grava um documento e seus chunks. Chamadas repetidas com o mesmo bytes são idempotentes."""
    digest = hashlib.sha256(data).hexdigest()
    existing = db.fetch("SELECT id, name, page_count FROM rag_documents WHERE content_hash = ?", (digest,))
    if existing:
        identity, stored_name, pages = existing[0]
        count = db.fetch("SELECT COUNT(*) FROM rag_chunks WHERE document_id = ?", (identity,))[0][0]
        return IngestResult(identity, stored_name, pages, count, False)

    pages = extract_pages(data, name)
    chunks = chunk_pages(list(enumerate(pages, start=1)))
    db.run(
        "INSERT INTO rag_documents (name, source, page_count, content_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (name[:240], (source or "")[:240], len(pages), digest, now.isoformat()),
    )
    row = db.fetch("SELECT id FROM rag_documents WHERE content_hash = ?", (digest,))
    identity = row[0][0]
    for ordinal, (page, text) in enumerate(chunks, start=1):
        db.run(
            "INSERT INTO rag_chunks (document_id, ordinal, page, content, embedding, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (identity, ordinal, page, text, dumps(embed(text)), now.isoformat()),
        )
    return IngestResult(identity, name[:240], len(pages), len(chunks), True)
