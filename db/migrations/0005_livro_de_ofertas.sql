-- Limite conservador: entrada e saída no lado desfavorável das ofertas finais do pregão.
-- Só acrescenta colunas. Nulo: alguma perna não tinha oferta dos dois lados.
ALTER TABLE lab_strategies ADD COLUMN entry_book_json TEXT;
ALTER TABLE lab_marks ADD COLUMN pnl_book_unit REAL;
