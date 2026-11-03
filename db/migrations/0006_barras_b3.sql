-- Barras diárias oficiais da B3 (COTAHIST). Só acrescenta: nada existente é alterado.
CREATE TABLE IF NOT EXISTS b3_daily_bars (
    symbol TEXT NOT NULL,
    day TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER,
    trades INTEGER,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (symbol, day)
);
