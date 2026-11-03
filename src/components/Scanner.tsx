import { FormEvent, useState } from 'react';
import { api, ApiError } from '../services/api';
import { ScannerRow } from '../types';
import { formatChange, formatCurrency, formatDay, formatMoment, formatNumber, formatRatio, REGIME_LABEL, TREND_LABEL } from '../lib/utils';
import { DataStatusBadge, Signed } from './Common';

interface ScannerProps {
  rows: ScannerRow[];
  generatedAt: string | null;
  complete: boolean;
  timedOut: string[];
  loading: boolean;
  onReload: () => void;
  onOpenStrategies: (symbol: string) => void;
}

export function Scanner({ rows, generatedAt, complete, timedOut, loading, onReload, onOpenStrategies }: ScannerProps) {
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
    <div className="space-y-4">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-4xl md:text-5xl">Scanner</h2>
          <p className="np-note mt-1">Vol implícita no vencimento de referência (a partir de 14 dias) contra a histórica.</p>
          <p className="font-display text-xs text-ink-2 mt-1">Gerado em {formatMoment(generatedAt)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
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
              className="np-input w-32"
            />
            <button type="submit" disabled={!symbol.trim()} className="np-btn">
              Adicionar
            </button>
          </form>
          <button onClick={onReload} disabled={loading} className="np-btn">
            {loading ? 'Atualizando...' : 'Atualizar'}
          </button>
        </div>
      </header>
      {error && (
        <p role="alert" className="text-accent">
          {error}
        </p>
      )}
      {!complete && (
        <p role="status" className="border-y border-accent py-2 text-base">
          <strong>Varredura incompleta.</strong> Parte dos ativos não pôde ser analisada por inteiro; veja o motivo em cada um.
          {timedOut.length > 0 && ` Tempo esgotado antes de: ${timedOut.join(', ')}.`}
        </p>
      )}

      <div className="np-section overflow-x-auto">
        <table className="np-table min-w-[1020px]">
          <thead>
            <tr>
              <th scope="col" className="text-left">Ativo</th>
              <th scope="col" className="text-left">Dado</th>
              <th scope="col" className="text-right">Preço</th>
              <th scope="col" className="text-right">Dia</th>
              <th scope="col" className="text-right">Vol hist.</th>
              <th scope="col" className="text-right">Vol impl.</th>
              <th scope="col" className="text-right">Impl./Hist.</th>
              <th scope="col" className="text-right">IV Rank</th>
              <th scope="col" className="text-left">Regime</th>
              <th scope="col" className="text-left">Estrutura</th>
              <th scope="col" className="text-left">Vencimento · pregão</th>
              <th scope="col"><span className="sr-only">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol}>
                <td className="max-w-[300px]">
                  <button onClick={() => onOpenStrategies(row.symbol)} className="font-black underline underline-offset-2 cursor-pointer">
                    {row.symbol}
                  </button>
                  {row.missing.map((reason) => (
                    <p key={reason} className="text-xs text-accent mt-1">
                      DADOS INSUFICIENTES · {reason}
                    </p>
                  ))}
                  {row.history_warnings.map((warning) => (
                    <p key={warning} className="text-xs text-accent mt-1">
                      {warning}
                    </p>
                  ))}
                </td>
                <td>
                  <DataStatusBadge status={row.data_status} source={row.source} at={row.market_time} />
                </td>
                <td className="text-right font-semibold">{formatCurrency(row.price)}</td>
                <td className="text-right">
                  <Signed value={row.change_percent}>{formatChange(row.change_percent)}</Signed>
                </td>
                <td className="text-right">{formatRatio(row.historical_volatility)}</td>
                <td className="text-right">{formatRatio(row.atm_iv)}</td>
                <td className="text-right">{formatNumber(row.iv_ratio)}</td>
                <td className="text-right">
                  {row.iv_rank !== null ? (
                    formatNumber(row.iv_rank, 0)
                  ) : row.atm_iv !== null ? (
                    <span className="text-xs text-ink-2">
                      {row.iv_samples} de {row.iv_samples_needed} amostras
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td>{row.regime ? REGIME_LABEL[row.regime] : '—'}</td>
                <td>{row.structure_trend ? TREND_LABEL[row.structure_trend] : '—'}</td>
                <td className="text-xs text-ink-2">
                  {formatDay(row.expiry)} · {formatDay(row.market_date)}
                </td>
                <td className="text-right">
                  <button aria-label={`Remover ${row.symbol}`} onClick={() => change(() => api.removeSymbol(row.symbol))} className="np-btn !min-h-0 !px-2 !py-1">
                    Remover
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
