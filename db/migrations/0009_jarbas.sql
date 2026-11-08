-- Jarbas IA: configuração, conversas, mensagens e consumo. Só acrescenta: nenhum dado existente é alterado.
-- Chaves de API nunca ficam aqui: só em variáveis de ambiente do servidor.

CREATE TABLE IF NOT EXISTS jarbas_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    -- Provedores em ordem de prioridade, separados por vírgula (ex.: "openrouter,gemini,groq").
    provider_order TEXT,
    -- Modelo principal do OpenRouter; os gratuitos entram depois como fallback.
    openrouter_model TEXT,
    -- 0 = só modelos gratuitos. Modelo pago só com autorização explícita do proprietário.
    allow_paid INTEGER NOT NULL DEFAULT 0,
    daily_limit INTEGER NOT NULL DEFAULT 200,
    retention_days INTEGER NOT NULL DEFAULT 90,
    speak_replies INTEGER NOT NULL DEFAULT 1,
    voice_name TEXT,
    voice_rate REAL NOT NULL DEFAULT 1.0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jarbas_conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jarbas_conversations_updated ON jarbas_conversations (updated_at);

CREATE TABLE IF NOT EXISTS jarbas_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES jarbas_conversations (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    -- Estrutura que estava na tela e ferramentas consultadas, para rastrear a resposta.
    context_json TEXT,
    tools_json TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jarbas_messages_conversation ON jarbas_messages (conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_jarbas_messages_created ON jarbas_messages (created_at);

CREATE TABLE IF NOT EXISTS jarbas_usage (
    day TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    failures INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, provider, model)
);
