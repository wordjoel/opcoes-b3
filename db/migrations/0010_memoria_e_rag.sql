-- Memória de longo prazo do Jarbas e índice local de documentos para RAG.
-- Só acrescenta tabelas: nenhum dado existente é alterado. Nenhuma chave de API é gravada aqui.

CREATE TABLE IF NOT EXISTS jarbas_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jarbas_memory_created ON jarbas_memory (created_at);

CREATE TABLE IF NOT EXISTS rag_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source TEXT,
    page_count INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (content_hash)
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    page INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    embedding TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES rag_documents (id) ON DELETE CASCADE,
    UNIQUE (document_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks (document_id);
