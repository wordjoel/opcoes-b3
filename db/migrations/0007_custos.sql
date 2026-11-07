-- Só acrescenta: nenhum dado existente é alterado.

-- Custos operacionais definidos pelo proprietário. Sem linha aqui, nada é aprovado.
CREATE TABLE cost_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  per_order_brl REAL NOT NULL CHECK (per_order_brl >= 0),
  fee_pct REAL NOT NULL CHECK (fee_pct >= 0 AND fee_pct <= 5),
  income_tax_pct REAL NOT NULL CHECK (income_tax_pct >= 0 AND income_tax_pct <= 100),
  updated_at TEXT NOT NULL
);
