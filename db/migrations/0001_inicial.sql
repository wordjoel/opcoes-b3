-- Ativos acompanhados. Só os códigos: preços vêm sempre da fonte de dados.
CREATE TABLE watchlist (
  symbol TEXT PRIMARY KEY,
  added_at TEXT NOT NULL
);

INSERT INTO watchlist (symbol, added_at) VALUES
  ('PETR4', '2026-11-03T00:00:00+00:00'),
  ('VALE3', '2026-11-03T00:00:00+00:00'),
  ('ITUB4', '2026-11-03T00:00:00+00:00'),
  ('BBAS3', '2026-11-03T00:00:00+00:00'),
  ('BBDC4', '2026-11-03T00:00:00+00:00'),
  ('MGLU3', '2026-11-03T00:00:00+00:00'),
  ('WEGE3', '2026-11-03T00:00:00+00:00'),
  ('B3SA3', '2026-11-03T00:00:00+00:00');

-- Respostas da fonte, com a procedência original dentro do payload.
CREATE TABLE provider_cache (
  key TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  fetched_at TEXT NOT NULL
);

-- Tentativas de login recusadas, para limitar força bruta entre instâncias serverless.
CREATE TABLE login_failures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL
);
CREATE INDEX login_failures_at ON login_failures (at);
