"""RAG local do Jarbas: documentos viram trechos consultáveis por similaridade.

Arquitetura: ``ingest`` extrai texto e grava chunks com embeddings determinísticos;
``retriever`` devolve trechos rotulados para o orquestrador. Nenhum documento é
enviado a terceiros e nenhuma chave é gravada no banco.
"""

from app.rag.ingest import IngestResult, extract_text, ingest_bytes
from app.rag.retriever import RetrievedChunk, build_context, retrieve

__all__ = [
    "IngestResult",
    "RetrievedChunk",
    "build_context",
    "extract_text",
    "ingest_bytes",
    "retrieve",
]
