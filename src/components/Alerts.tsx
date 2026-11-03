import { ScannerRow, Signal } from '../types';

const SIGNAL: Record<Signal['type'], string> = {
  VOL_CARA: 'Vol cara',
  VOL_BARATA: 'Vol barata',
  MOVIMENTO: 'Movimento forte',
  GRADE_DEFASADA: 'Grade defasada',
  SALTO_HISTORICO: 'Salto no histórico',
  IV_RANK_ALTO: 'IV Rank alto',
  IV_RANK_BAIXO: 'IV Rank baixo',
  EVENTO_PROXIMO: 'Resultado próximo',
  ROMPIMENTO: 'Rompimento de estrutura',
};

export function alertCount(rows: ScannerRow[]) {
  return rows.reduce((total, row) => total + row.signals.length, 0);
}

export function Alerts({ rows, onOpenStrategies }: { rows: ScannerRow[]; onOpenStrategies: (symbol: string) => void }) {
  const signals = rows.flatMap((row) => row.signals.map((signal) => ({ symbol: row.symbol, signal })));
  const incomplete = rows.filter((row) => row.missing.length > 0);

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-4xl md:text-5xl">Alertas</h2>
        <p className="np-note mt-1">Calculados agora a partir do scanner. Só aparecem com o app aberto.</p>
      </header>

      <div className="np-spread-side np-section">
        <aside className="min-w-0">
          {incomplete.length > 0 ? (
            <>
              <h3 className="text-xl mb-2">{incomplete.length} ativos sem análise completa</h3>
              <p className="np-note">
                Sem todos os dados, estes ativos podem ter sinais que não aparecem aqui: {incomplete.map((row) => row.symbol).join(', ')}.
              </p>
            </>
          ) : (
            <p className="np-note">Todos os ativos foram analisados por inteiro.</p>
          )}
        </aside>
        <div className="min-w-0">
          {signals.length === 0 && <p>Nenhum sinal nos ativos com dados completos.</p>}
          <ul>
            {signals.map(({ symbol, signal }) => (
              <li key={`${symbol}-${signal.type}-${signal.detail}`} className="py-3 np-rule first:border-t-0 first:pt-0">
                <p className="np-label !text-accent">{SIGNAL[signal.type]}</p>
                <button onClick={() => onOpenStrategies(symbol)} className="font-display text-2xl font-black underline underline-offset-2 cursor-pointer text-left">
                  {symbol}
                </button>
                <p>{signal.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
