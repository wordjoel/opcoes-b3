-- Laboratório de Estratégias. Só acrescenta tabelas; nada aqui representa operação real.

-- Grade de um pregão passado, como veio da fonte. Pregão encerrado não muda.
-- payload nulo: a fonte não tem esse pregão (feriado, por exemplo).
CREATE TABLE option_history (
  symbol TEXT NOT NULL,
  expiry TEXT NOT NULL,
  day TEXT NOT NULL,
  payload TEXT,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (symbol, expiry, day)
);

-- O id é um hash do conteúdo: a mesma estratégia não entra duas vezes.
CREATE TABLE lab_strategies (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL CHECK (mode IN ('FORWARD', 'BACKTEST')),
  agent TEXT NOT NULL,
  symbol TEXT NOT NULL,
  structure_key TEXT NOT NULL,
  structure_name TEXT NOT NULL,
  expiry TEXT NOT NULL,
  entry_day TEXT NOT NULL,
  end_day TEXT NOT NULL,
  legs_json TEXT NOT NULL,
  capital_brl REAL NOT NULL,
  lots INTEGER NOT NULL,
  unit_debit REAL NOT NULL,
  max_profit REAL,
  max_loss REAL NOT NULL,
  breakevens_json TEXT NOT NULL,
  probability REAL,
  theoretical_pnl REAL,
  regime TEXT,
  target_pct REAL,
  stop_pct REAL,
  cost_brl REAL NOT NULL,
  cost_informed INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ATIVA', 'ENCERRADA')),
  close_reason TEXT,
  closed_day TEXT,
  source TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX lab_strategies_status ON lab_strategies (mode, status);

-- Marcação de um pregão, com os preços usados. complete = 0: faltou preço de alguma perna.
CREATE TABLE lab_marks (
  strategy_id TEXT NOT NULL REFERENCES lab_strategies (id),
  day TEXT NOT NULL,
  pnl_unit REAL,
  spot REAL,
  prices_json TEXT NOT NULL,
  complete INTEGER NOT NULL,
  settlement INTEGER NOT NULL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (strategy_id, day)
);
