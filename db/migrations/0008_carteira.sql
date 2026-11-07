-- Só acrescenta: nenhum dado existente é alterado.

-- Caixa inicial e limite por série definidos pelo proprietário. Sem linha aqui, a carteira não é avaliada.
CREATE TABLE portfolio_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  initial_cash_brl REAL NOT NULL CHECK (initial_cash_brl >= 0),
  max_position_size INTEGER NOT NULL CHECK (max_position_size > 0),
  updated_at TEXT NOT NULL
);

-- Operações já feitas na corretora, informadas pelo proprietário. Nunca apagadas:
-- um lançamento errado é anulado (voided_at) e continua visível.
CREATE TABLE portfolio_fills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  price REAL NOT NULL CHECK (price >= 0),
  fees_brl REAL NOT NULL DEFAULT 0 CHECK (fees_brl >= 0),
  trade_day TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL,
  voided_at TEXT
);
CREATE INDEX portfolio_fills_order ON portfolio_fills (trade_day, id);

-- Cada decisão mostrada, com os dados que a originaram. O id é o hash do conteúdo:
-- a mesma análise repetida não duplica linhas.
CREATE TABLE decision_log (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  expiry TEXT NOT NULL,
  structure_key TEXT NOT NULL,
  status TEXT NOT NULL,
  reasons_json TEXT NOT NULL,
  missing_json TEXT NOT NULL,
  inputs_json TEXT NOT NULL
);
CREATE INDEX decision_log_recent ON decision_log (created_at);
CREATE INDEX decision_log_symbol ON decision_log (symbol, created_at);
