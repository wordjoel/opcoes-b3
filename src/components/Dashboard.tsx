/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { api, useResource } from '../services/api';
import { ScannerRow } from '../types';
import { cn, formatChange, formatCurrency, formatMoment, formatRatio, REGIME_LABEL, TREND_LABEL } from '../lib/utils';
import { ErrorNotice, Loading, Panel, Signed, Stat } from './Common';
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
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white tracking-tight">Monitor de Mercado</h2>
        <p className="text-slate-400 mt-1">Cotação com atraso da fonte e histórico diário ajustado.</p>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-8 space-y-6 min-w-0">
          {!selected && <Panel>Selecione um ativo na lista.</Panel>}
          {selected && asset.loading && !asset.data && <Loading label={`Carregando ${selected}...`} />}
          {asset.error && <ErrorNotice error={asset.error} onRetry={asset.reload} />}
          {asset.data && (
            <>
              <Panel>
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-white">
                      {asset.data.quote.symbol}
                      {asset.data.quote.name && <span className="text-slate-400 font-normal"> · {asset.data.quote.name}</span>}
                    </h3>
                    <p className="text-xs text-slate-500">
                      Histórico diário ajustado · fonte {asset.data.quote.provenance.source}
                    </p>
                  </div>
                  <div className="sm:text-right">
                    <p className="text-2xl font-bold text-white">{formatCurrency(asset.data.quote.price)}</p>
                    <p className="text-sm font-bold font-mono">
                      <Signed value={asset.data.quote.change_percent}>{formatChange(asset.data.quote.change_percent)}</Signed>
                    </p>
                    <p className="text-xs text-slate-500">Mercado: {formatMoment(asset.data.quote.provenance.market_time)}</p>
                  </div>
                </div>
                {asset.data.quote_quality.issues.length > 0 && (
                  <p className="text-xs text-amber-200 mb-3">Cotação fora da janela de 20 minutos: confira o horário de mercado acima.</p>
                )}
                {asset.data.history_quality.issues
                  .filter((issue) => issue.code === 'LARGE_JUMP')
                  .map((issue) => (
                    <p key={issue.detail} role="alert" className="text-xs text-amber-200 mb-3">
                      {issue.detail}
                    </p>
                  ))}
                {asset.data.history.length > 0 ? (
                  <>
                    <PriceChart bars={asset.data.history} structure={asset.data.structure} />
                    <HvChart bars={asset.data.history} />
                  </>
                ) : (
                  <p className="text-sm text-amber-200">DADOS INSUFICIENTES: histórico recusado na validação.</p>
                )}
              </Panel>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Stat label="Vol histórica" value={formatRatio(asset.data.historical_volatility)} hint="1 ano, anualizada" />
                <Stat label="Vol EWMA" value={formatRatio(asset.data.ewma_volatility)} hint="Decaimento 0,94" />
                <Stat
                  label="Regime"
                  value={asset.data.regime ? REGIME_LABEL[asset.data.regime] : '—'}
                  hint="Médias de 20 e 50 dias"
                />
                <Stat
                  label="Estrutura"
                  value={asset.data.structure?.trend ? TREND_LABEL[asset.data.structure.trend] : '—'}
                  hint="Topos e fundos diários"
                />
              </div>
              <button
                onClick={() => onOpenStrategies(selected!)}
                className="w-full py-3 rounded-xl bg-sky-500/10 hover:bg-sky-500 text-sky-400 hover:text-slate-950 text-sm font-bold border border-sky-500/20 transition-colors"
              >
                Ver estratégias de {selected}
              </button>
            </>
          )}
        </div>

        <Panel title="Ativos acompanhados" className="xl:col-span-4">
          <ul className="space-y-2">
            {rows.map((row) => (
              <li key={row.symbol}>
                <button
                  onClick={() => onSelect(row.symbol)}
                  aria-current={selected === row.symbol}
                  className={cn(
                    'w-full flex items-center justify-between p-3 rounded-xl border text-left transition-colors',
                    selected === row.symbol ? 'border-sky-500/50 bg-slate-800/60' : 'border-slate-800 hover:bg-slate-800/40',
                  )}
                >
                  <span>
                    <span className="block font-bold text-white text-sm">{row.symbol}</span>
                    <span className="block text-xs text-slate-400">{formatCurrency(row.price)}</span>
                  </span>
                  <span className="font-mono text-sm font-bold">
                    <Signed value={row.change_percent}>{formatChange(row.change_percent)}</Signed>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
