-- Vol implícita no dinheiro por ativo e pregão, calculada a partir da fonte.
-- Pregão passado não muda, então cada amostra só é buscada uma vez.
-- iv nulo: a fonte não tinha dado suficiente nessa data.
CREATE TABLE iv_history (
  symbol TEXT NOT NULL,
  day TEXT NOT NULL,
  iv REAL,
  expiry TEXT,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (symbol, day)
);
