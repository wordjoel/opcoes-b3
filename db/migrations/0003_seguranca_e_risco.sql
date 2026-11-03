-- Só acrescenta: nenhum dado existente é alterado.

-- Tentativa recusada por origem. A origem é guardada como HMAC, nunca o IP em claro.
ALTER TABLE login_failures ADD COLUMN ip_key TEXT;
CREATE INDEX login_failures_ip ON login_failures (ip_key, at);

-- Sessões emitidas antes deste instante deixam de valer (ao sair).
CREATE TABLE auth_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  revoked_before INTEGER NOT NULL
);

-- Capital e limite definidos pelo proprietário. Sem linha aqui, nada é aprovado.
CREATE TABLE risk_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  capital_brl REAL NOT NULL CHECK (capital_brl > 0),
  max_loss_pct REAL NOT NULL CHECK (max_loss_pct > 0 AND max_loss_pct <= 100),
  updated_at TEXT NOT NULL
);
