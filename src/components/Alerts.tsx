import { Activity, AlertTriangle, TrendingDown, TrendingUp } from 'lucide-react';
import { ScannerRow, Signal } from '../types';
import { Panel } from './Common';

const SIGNAL: Record<Signal['type'], { label: string; icon: typeof Activity }> = {
  VOL_CARA: { label: 'Vol cara', icon: TrendingUp },
  VOL_BARATA: { label: 'Vol barata', icon: TrendingDown },
  MOVIMENTO: { label: 'Movimento forte', icon: Activity },
  GRADE_DEFASADA: { label: 'Grade defasada', icon: AlertTriangle },
  SALTO_HISTORICO: { label: 'Salto no histórico', icon: AlertTriangle },
  IV_RANK_ALTO: { label: 'IV Rank alto', icon: TrendingUp },
  IV_RANK_BAIXO: { label: 'IV Rank baixo', icon: TrendingDown },
  EVENTO_PROXIMO: { label: 'Resultado próximo', icon: AlertTriangle },
  ROMPIMENTO: { label: 'Rompimento de estrutura', icon: Activity },
};

export function alertCount(rows: ScannerRow[]) {
  return rows.reduce((total, row) => total + row.signals.length, 0);
}

export function Alerts({ rows, onOpenStrategies }: { rows: ScannerRow[]; onOpenStrategies: (symbol: string) => void }) {
  const signals = rows.flatMap((row) => row.signals.map((signal) => ({ symbol: row.symbol, signal })));
  const incomplete = rows.filter((row) => row.missing.length > 0);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white tracking-tight">Alertas</h2>
        <p className="text-slate-400 mt-1">Calculados agora a partir do scanner. Só aparecem com o app aberto.</p>
      </header>

      {signals.length === 0 && <Panel>Nenhum sinal nos ativos com dados completos.</Panel>}
      <ul className="space-y-3">
        {signals.map(({ symbol, signal }) => {
          const { label, icon: Icon } = SIGNAL[signal.type];
          return (
            <li key={`${symbol}-${signal.type}-${signal.detail}`} className="flex items-start gap-3 p-4 rounded-xl border border-slate-800 bg-slate-900">
              <Icon className="w-5 h-5 shrink-0 text-sky-400 mt-0.5" />
              <div>
                <button onClick={() => onOpenStrategies(symbol)} className="font-bold text-white hover:underline">
                  {symbol} · {label}
                </button>
                <p className="text-sm text-slate-400">{signal.detail}</p>
              </div>
            </li>
          );
        })}
      </ul>

      {incomplete.length > 0 && (
        <Panel title={`${incomplete.length} ativos sem análise completa`}>
          <p className="text-sm text-slate-400">
            Sem todos os dados, estes ativos podem ter sinais que não aparecem acima: {incomplete.map((row) => row.symbol).join(', ')}.
          </p>
        </Panel>
      )}
    </div>
  );
}
