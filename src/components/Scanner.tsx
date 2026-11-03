import { Plus, RefreshCw, X } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { api, ApiError } from '../services/api';
import { ScannerRow } from '../types';
import { formatChange, formatCurrency, formatDay, formatMoment, formatNumber, formatRatio, REGIME_LABEL, TREND_LABEL } from '../lib/utils';
import { Panel, Signed } from './Common';

interface ScannerProps {
  rows: ScannerRow[];
  generatedAt: string | null;
  loading: boolean;
  onReload: () => void;
  onOpenStrategies: (symbol: string) => void;
}

export function Scanner({ rows, generatedAt, loading, onReload, onOpenStrategies }: ScannerProps) {
  const [symbol, setSymbol] = useState('');
  const [error, setError] = useState<string | null>(null);

  const change = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
      setSymbol('');
      onReload();
    } catch (failure) {
      setError((failure as ApiError).message);
    }
  };

  const add = (event: FormEvent) => {
    event.preventDefault();
    change(() => api.addSymbol(symbol));
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">Scanner</h2>
          <p className="text-slate-400 mt-1">
            Vol implícita no vencimento de referência (a partir de 14 dias) contra a histórica.
          </p>
          <p className="text-xs text-slate-500 mt-1">Gerado em {formatMoment(generatedAt)}</p>
        </div>
        <div className="flex items-center gap-2">
          <form onSubmit={add} className="flex items-center gap-2">
            <label htmlFor="new-symbol" className="sr-only">
              Código do ativo
            </label>
            <input
              id="new-symbol"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value.toUpperCase())}
              placeholder="Ex.: KLBN11"
              maxLength={12}
              className="w-32 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-sky-500"
            />
            <button type="submit" disabled={!symbol.trim()} aria-label="Adicionar ativo" className="p-2 rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 disabled:opacity-50">
              <Plus className="w-5 h-5" />
            </button>
          </form>
          <button onClick={onReload} disabled={loading} aria-label="Atualizar" className="p-2 rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 disabled:opacity-50">
            <RefreshCw className={loading ? 'w-5 h-5 animate-spin' : 'w-5 h-5'} />
          </button>
        </div>
      </header>
      {error && (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      )}

      <Panel className="p-0 md:p-0 overflow-x-auto">
        <table className="w-full text-sm min-w-[1020px]">
          <thead className="text-xs text-slate-400 border-b border-slate-800">
            <tr>
              <th scope="col" className="text-left font-semibold p-3">Ativo</th>
              <th scope="col" className="text-right font-semibold p-3">Preço</th>
              <th scope="col" className="text-right font-semibold p-3">Dia</th>
              <th scope="col" className="text-right font-semibold p-3">Vol hist.</th>
              <th scope="col" className="text-right font-semibold p-3">Vol impl.</th>
              <th scope="col" className="text-right font-semibold p-3">Impl./Hist.</th>
              <th scope="col" className="text-right font-semibold p-3">IV Rank</th>
              <th scope="col" className="text-left font-semibold p-3">Regime</th>
              <th scope="col" className="text-left font-semibold p-3">Estrutura</th>
              <th scope="col" className="text-left font-semibold p-3">Vencimento · pregão</th>
              <th scope="col" className="p-3"><span className="sr-only">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol} className="border-b border-slate-800/60 align-top">
                <td className="p-3">
                  <button onClick={() => onOpenStrategies(row.symbol)} className="font-bold text-sky-400 hover:underline">
                    {row.symbol}
                  </button>
                  {row.missing.map((reason) => (
                    <p key={reason} className="text-xs text-amber-200/90 mt-1 max-w-[260px]">
                      DADOS INSUFICIENTES · {reason}
                    </p>
                  ))}
                  {row.history_warnings.map((warning) => (
                    <p key={warning} className="text-xs text-amber-200/90 mt-1 max-w-[260px]">
                      {warning}
                    </p>
                  ))}
                </td>
                <td className="p-3 text-right font-mono text-white">{formatCurrency(row.price)}</td>
                <td className="p-3 text-right font-mono">
                  <Signed value={row.change_percent}>{formatChange(row.change_percent)}</Signed>
                </td>
                <td className="p-3 text-right font-mono text-slate-200">{formatRatio(row.historical_volatility)}</td>
                <td className="p-3 text-right font-mono text-slate-200">{formatRatio(row.atm_iv)}</td>
                <td className="p-3 text-right font-mono text-slate-200">{formatNumber(row.iv_ratio)}</td>
                <td className="p-3 text-right font-mono text-slate-200">
                  {row.iv_rank !== null ? (
                    formatNumber(row.iv_rank, 0)
                  ) : row.atm_iv !== null ? (
                    <span className="text-xs font-sans text-slate-400">
                      {row.iv_samples} de {row.iv_samples_needed} amostras
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="p-3 text-slate-200">{row.regime ? REGIME_LABEL[row.regime] : '—'}</td>
                <td className="p-3 text-slate-200">{row.structure_trend ? TREND_LABEL[row.structure_trend] : '—'}</td>
                <td className="p-3 text-xs text-slate-400">
                  {formatDay(row.expiry)} · {formatDay(row.market_date)}
                </td>
                <td className="p-3 text-right">
                  <button
                    aria-label={`Remover ${row.symbol}`}
                    onClick={() => change(() => api.removeSymbol(row.symbol))}
                    className="text-slate-500 hover:text-white"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
