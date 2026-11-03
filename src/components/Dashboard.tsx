/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import type { CSSProperties } from 'react';
import { api, useResource } from '../services/api';
import { ScannerRow } from '../types';
import { formatChange, formatCurrency, formatRatio, REGIME_LABEL, TREND_LABEL } from '../lib/utils';
import { DataStatusBadge, ErrorNotice, Loading, Signed, Stat } from './Common';
import { HvChart, PriceChart } from './PriceChart';

interface DashboardProps {
  rows: ScannerRow[];
  selected: string | null;
  onSelect: (symbol: string) => void;
  onOpenStrategies: (symbol: string) => void;
}

export function Dashboard({ rows, selected, onSelect, onOpenStrategies }: DashboardProps) {
  const asset = useResource(selected, () => api.asset(selected!));

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-4xl md:text-5xl">Monitor de Mercado</h2>
        <p className="np-note mt-1">Cotação com atraso da fonte e histórico diário ajustado.</p>
      </header>

      <div className="np-spread np-section">
        <div className="min-w-0 space-y-4">
          {!selected && <p>Selecione um ativo na lista.</p>}
          {selected && asset.loading && !asset.data && <Loading label={`Carregando ${selected}...`} />}
          {asset.error && <ErrorNotice error={asset.error} onRetry={asset.reload} />}
          {asset.data && (
            <>
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-3xl">{asset.data.quote.symbol}</h3>
                  {asset.data.quote.name && <p className="np-note">{asset.data.quote.name}</p>}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="np-label">Cotação</span>
                    <DataStatusBadge
                      status={asset.data.data_status}
                      source={asset.data.quote.provenance.source}
                      at={asset.data.quote.provenance.market_time}
                    />
                  </div>
                </div>
                <div className="sm:text-right font-display">
                  <p className="text-3xl font-black">{formatCurrency(asset.data.quote.price)}</p>
                  <p className="text-lg font-semibold">
                    <Signed value={asset.data.quote.change_percent}>{formatChange(asset.data.quote.change_percent)}</Signed>
                  </p>
                </div>
              </div>
              {asset.data.history_quality.issues
                .filter((issue) => issue.code === 'LARGE_JUMP')
                .map((issue) => (
                  <p key={issue.detail} role="alert" className="text-accent border-y border-accent py-2 text-base">
                    {issue.detail}
                  </p>
                ))}
              {asset.data.history.length > 0 ? (
                <>
                  <PriceChart bars={asset.data.history} structure={asset.data.structure} />
                  <HvChart bars={asset.data.history} />
                </>
              ) : (
                <p className="text-accent">DADOS INSUFICIENTES: histórico recusado na validação.</p>
              )}
              <div className="np-facts np-rule" style={{ '--np-columns': 4 } as CSSProperties}>
                <Stat label="Vol histórica" value={formatRatio(asset.data.historical_volatility)} hint="1 ano, anualizada" />
                <Stat label="Vol EWMA" value={formatRatio(asset.data.ewma_volatility)} hint="Decaimento 0,94" />
                <Stat label="Regime" value={asset.data.regime ? REGIME_LABEL[asset.data.regime] : '—'} hint="Médias de 20 e 50 dias" />
                <Stat
                  label="Estrutura"
                  value={asset.data.structure?.trend ? TREND_LABEL[asset.data.structure.trend] : '—'}
                  hint="Topos e fundos diários"
                />
              </div>
              <button onClick={() => onOpenStrategies(selected!)} className="np-btn w-full">
                Ver estratégias de {selected}
              </button>
            </>
          )}
        </div>

        <aside className="min-w-0">
          <h3 className="text-xl mb-2">Ativos acompanhados</h3>
          <ul>
            {rows.map((row) => (
              <li key={row.symbol} className="np-rule">
                <button
                  onClick={() => onSelect(row.symbol)}
                  aria-current={selected === row.symbol}
                  className="w-full flex items-start justify-between gap-3 py-2 px-1 text-left font-display cursor-pointer hover:bg-ink hover:text-paper aria-[current=true]:bg-ink aria-[current=true]:text-paper group"
                >
                  <span>
                    <span className="block font-black">{row.symbol}</span>
                    <span className="block text-sm">{formatCurrency(row.price)}</span>
                  </span>
                  <span className="text-sm font-semibold text-right">
                    {formatChange(row.change_percent)}
                    <span className="block text-xs font-normal">{statusText(row)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}

function statusText(row: ScannerRow) {
  return { REAL: 'Real', ATRASADO: 'Atrasado', INCOMPLETO: 'Incompleto', INDISPONIVEL: 'Indisponível' }[row.data_status];
}
