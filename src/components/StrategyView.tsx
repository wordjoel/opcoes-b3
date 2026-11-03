/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { CheckCircle2, ShieldAlert, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, useResource } from '../services/api';
import { Candidate, ChainQuote, ChainView, Profile, StrategiesView } from '../types';
import {
  cn,
  formatChange,
  formatCompact,
  formatCurrency,
  formatDay,
  formatLimit,
  formatNumber,
  formatRatio,
  REGIME_LABEL,
  TREND_LABEL,
} from '../lib/utils';
import { ErrorNotice, Loading, Panel, Signed, Stat } from './Common';
import { OpenInterestPanel, PnlHeatmap, SkewChart } from './OptionAnalytics';

interface StrategyViewProps {
  symbols: string[];
  symbol: string | null;
  onSymbol: (symbol: string) => void;
}

const CONTROL = 'bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-sky-500';

export function StrategyView({ symbols, symbol, onSymbol }: StrategyViewProps) {
  const expirations = useResource(symbol, () => api.expirations(symbol!));
  const [expiry, setExpiry] = useState<string | null>(null);

  useEffect(() => {
    const days = expirations.data?.expirations ?? [];
    if (days.length === 0) {
      setExpiry(null);
      return;
    }
    // Começa no primeiro vencimento a partir de 14 dias, como o scanner.
    const limit = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10);
    setExpiry(days.find((day) => day >= limit) ?? days[days.length - 1]);
  }, [expirations.data]);

  const [profile, setProfile] = useState<Profile | null>(null);
  const key = symbol && expiry ? `${symbol}:${expiry}` : null;
  const strategies = useResource(key && `${key}:${profile}`, () => api.strategies(symbol!, expiry!, profile));
  const chain = useResource(key, () => api.chain(symbol!, expiry!));

  return (
    <div className="space-y-6">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">Estratégias</h2>
          <p className="text-slate-400 mt-1">Calculadas com regras fixas, sem IA. Nenhuma ordem é enviada.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="text-xs text-slate-400">
            Seleção de strikes
            <select
              value={profile ?? ''}
              onChange={(event) => setProfile((event.target.value || null) as Profile | null)}
              className={cn(CONTROL, 'block mt-1')}
            >
              <option value="">Distância de 5% do ativo</option>
              <option value="CONSERVATIVE">Delta: conservador</option>
              <option value="MODERATE">Delta: moderado</option>
              <option value="AGGRESSIVE">Delta: agressivo</option>
            </select>
          </label>
          <label className="text-xs text-slate-400">
            Ativo
            <select value={symbol ?? ''} onChange={(event) => onSymbol(event.target.value)} className={cn(CONTROL, 'block mt-1')}>
              {symbol === null && <option value="">Selecione</option>}
              {symbols.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-400">
            Vencimento
            <select
              value={expiry ?? ''}
              disabled={!expiry}
              onChange={(event) => setExpiry(event.target.value)}
              className={cn(CONTROL, 'block mt-1 disabled:opacity-50')}
            >
              {(expirations.data?.expirations ?? []).map((day) => (
                <option key={day} value={day}>
                  {formatDay(day)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {!symbol && <Panel>Selecione um ativo.</Panel>}
      {expirations.loading && <Loading label="Buscando vencimentos..." />}
      {expirations.error && <ErrorNotice error={expirations.error} onRetry={expirations.reload} />}
      {symbol && expirations.data && !expiry && <Panel>A fonte não listou vencimentos futuros para {symbol}.</Panel>}
      {key && strategies.loading && !strategies.data && <Loading label="Calculando estruturas..." />}
      {strategies.error && <ErrorNotice error={strategies.error} onRetry={strategies.reload} />}
      {strategies.data && <Analysis view={strategies.data} />}
      {chain.data && <OpenInterestPanel summary={chain.data.open_interest} />}
      {chain.data && <SkewChart chain={chain.data} />}
      {chain.data && <ChainTable chain={chain.data} />}
    </div>
  );
}

function Analysis({ view }: { view: StrategiesView }) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const selected = view.candidates.find((item) => item.key === selectedKey) ?? view.candidates[0];
  const approved = view.candidates.filter((item) => item.risk.is_approved).length;
  const drifted = view.candidates.length > 0 && view.candidates.every((item) => item.risk.rejection_reason?.includes('defasados'));

  return (
    <div className="space-y-6">
      <div role="status" className="p-4 rounded-xl border border-slate-700 bg-slate-900 text-sm text-slate-200">
        Prêmios do <strong>fechamento de {formatDay(view.market_date)}</strong>, com o ativo a {formatCurrency(view.spot)}: são
        indicativos e não garantem execução. A grade do pregão do dia entra por volta das 21h.
      </div>
      {drifted && (
        <div role="alert" className="flex items-start gap-3 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-sm text-amber-100">
          <ShieldAlert className="w-5 h-5 shrink-0 text-amber-400" />
          <p>
            O ativo está em {formatCurrency(view.live_price)}, <strong>{formatChange((view.spot_drift ?? 0) * 100)}</strong> em relação à
            grade. Com essa diferença, os prêmios estão defasados e todas as estruturas ficam reprovadas até a próxima grade.
          </p>
        </div>
      )}

      <MarketContext view={view} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Vol implícita" value={formatRatio(view.atm_iv)} hint="Call e put no dinheiro" />
        <Stat label="Vol histórica" value={formatRatio(view.historical_volatility)} hint="1 ano" />
        <Stat label="Regime" value={view.regime ? REGIME_LABEL[view.regime] : '—'} hint={`Impl./Hist. ${formatNumber(view.iv_ratio)}`} />
        <Stat label="Juros" value={formatRatio(view.risk_free_rate, 2)} hint="Informado pela fonte" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <Panel title={`Estruturas: ${approved} de ${view.candidates.length} aprovadas`} className="xl:col-span-4">
          <ul className="space-y-2">
            {view.candidates.map((item) => (
              <li key={item.key}>
                <button
                  onClick={() => setSelectedKey(item.key)}
                  aria-current={selected?.key === item.key}
                  className={cn(
                    'w-full p-3 rounded-xl border text-left transition-colors',
                    selected?.key === item.key ? 'border-sky-500/50 bg-slate-800/60' : 'border-slate-800 hover:bg-slate-800/40',
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-sm text-white">{item.name}</span>
                    {item.risk.is_approved ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 className="w-3.5 h-3.5" /> Aprovada</span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-red-400"><XCircle className="w-3.5 h-3.5" /> Reprovada</span>
                    )}
                  </span>
                  <span className="block text-xs text-slate-400 mt-1">
                    Ganho {formatLimit(item.max_profit)} · Perda {formatLimit(item.max_loss)}
                    {item.fits_regime && ' · compatível com o regime'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {view.unavailable.length > 0 && (
            <div className="mt-4 text-xs text-slate-400 space-y-1">
              <p className="font-semibold text-slate-300">Sem strikes na grade:</p>
              {view.unavailable.map((item) => (
                <p key={item.key}>{item.name}: {item.reason}</p>
              ))}
            </div>
          )}
        </Panel>
        <div className="xl:col-span-8 min-w-0">{selected ? <Detail item={selected} spot={view.spot} /> : <Panel>Nenhuma estrutura pôde ser montada.</Panel>}</div>
      </div>
    </div>
  );
}

function MarketContext({ view }: { view: StrategiesView }) {
  const lastBreak = view.structure?.events.at(-1);
  return (
    <Panel title="Contexto do ativo">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-slate-400">Estrutura diária</p>
          <p className="font-bold text-white">{view.structure?.trend ? TREND_LABEL[view.structure.trend] : 'Sem rompimento'}</p>
          {lastBreak && (
            <p className="text-xs text-slate-400">
              {lastBreak.kind === 'CHOCH' ? 'CHoCH' : 'BOS'} em {formatDay(lastBreak.day)}, além de {formatCurrency(lastBreak.level)}
            </p>
          )}
        </div>
        <div>
          <p className="text-slate-400">IV Rank</p>
          <p className="font-bold text-white">
            {view.iv_rank !== null ? formatNumber(view.iv_rank, 0) : `${view.iv_samples} de ${view.iv_samples_needed} amostras`}
          </p>
          {view.iv_percentile !== null && <p className="text-xs text-slate-400">Percentil {formatNumber(view.iv_percentile, 0)}</p>}
        </div>
        <div>
          <p className="text-slate-400">Próximos eventos</p>
          {view.events_error ? (
            <p className="text-amber-200">DADOS INSUFICIENTES: {view.events_error}</p>
          ) : view.events.length === 0 ? (
            <p className="text-slate-200">Nenhum informado pela fonte nos próximos 180 dias</p>
          ) : (
            <ul className="text-slate-200">
              {view.events.slice(0, 4).map((event) => (
                <li key={`${event.day}-${event.label}`}>
                  {formatDay(event.day)}: {event.label}
                  {!event.confirmed && <span className="text-slate-400"> (data estimada)</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Panel>
  );
}

function Detail({ item, spot }: { item: Candidate; spot: number }) {
  return (
    <div className="space-y-4">
      <Panel>
        <h3 className="text-lg font-bold text-white">{item.name}</h3>
        <p className="text-sm text-slate-400 mt-1">{item.rationale}</p>
        <p className={cn('text-sm mt-3 font-semibold', item.risk.is_approved ? 'text-emerald-300' : 'text-red-300')}>
          {item.risk.verdict}
          {item.risk.rejection_reason && <span className="font-normal"> Motivo: {item.risk.rejection_reason}.</span>}
        </p>
      </Panel>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Ganho máximo" value={formatLimit(item.max_profit)} />
        <Stat label="Perda máxima" value={formatLimit(item.max_loss)} />
        <Stat
          label={item.net_premium >= 0 ? 'Débito' : 'Crédito'}
          value={formatCurrency(Math.abs(item.net_premium))}
          hint="Na montagem"
        />
        <Stat label="Prob. de lucro" value={formatRatio(item.probability_of_profit, 0)} hint="Neutra ao risco; não é previsão" />
      </div>

      <Panel title="Resultado no vencimento (R$)">
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={item.payoff} margin={{ top: 16, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#1E293B" vertical={false} />
              <XAxis
                dataKey="price"
                type="number"
                domain={['dataMin', 'dataMax']}
                stroke="#64748B"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value: number) => value.toFixed(0)}
              />
              <YAxis stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} width={56} />
              <ReferenceLine y={0} stroke="#64748B" />
              <ReferenceLine
                x={spot}
                stroke="#94A3B8"
                strokeDasharray="4 4"
                label={{ value: 'Ativo na grade', fill: '#CBD5E1', fontSize: 11, position: 'top' }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#0F172A', border: '1px solid #334155', borderRadius: 8 }}
                labelStyle={{ color: '#CBD5E1' }}
                itemStyle={{ color: '#F8FAFC' }}
                labelFormatter={(price) => `Ativo a ${formatCurrency(Number(price))}`}
                formatter={(value) => [formatCurrency(Number(value)), 'Resultado']}
              />
              <Line type="linear" dataKey="pnl" stroke="#0284C7" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-slate-400 mt-2">
          Breakeven: {item.breakevens.length ? item.breakevens.map((value) => formatCurrency(value)).join(' e ') : 'nenhum'} · Liquidez:{' '}
          {formatNumber(item.risk.liquidity_score)} de 1,00
        </p>
      </Panel>

      {item.heatmap && <PnlHeatmap heatmap={item.heatmap} />}

      <Panel title="Pernas" className="overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="text-xs text-slate-400">
            <tr>
              <th scope="col" className="text-left font-semibold py-1">Lado</th>
              <th scope="col" className="text-left font-semibold py-1">Série</th>
              <th scope="col" className="text-left font-semibold py-1">Tipo</th>
              <th scope="col" className="text-right font-semibold py-1">Strike</th>
              <th scope="col" className="text-right font-semibold py-1">Prêmio</th>
              <th scope="col" className="text-right font-semibold py-1">Qtd.</th>
              <th scope="col" className="text-right font-semibold py-1">Vol impl.</th>
              <th scope="col" className="text-right font-semibold py-1">Delta</th>
              <th scope="col" className="text-right font-semibold py-1">Prob. ITM</th>
            </tr>
          </thead>
          <tbody className="text-slate-200 font-mono">
            {item.legs.map((leg) => (
              <tr key={`${leg.symbol}-${leg.action}`} className="border-t border-slate-800">
                <td className="py-1.5 font-sans">{leg.action === 'BUY' ? 'Compra' : 'Venda'}</td>
                <td className="py-1.5">{leg.symbol}</td>
                <td className="py-1.5">{leg.kind === 'CALL' ? 'Call' : 'Put'}</td>
                <td className="py-1.5 text-right">{formatNumber(leg.strike)}</td>
                <td className="py-1.5 text-right">{formatNumber(leg.premium)}</td>
                <td className="py-1.5 text-right">{leg.quantity}</td>
                <td className="py-1.5 text-right">{formatRatio(leg.iv)}</td>
                <td className="py-1.5 text-right">{formatNumber(leg.delta)}</td>
                <td className="py-1.5 text-right">{formatRatio(leg.probability_itm, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Cenários de estresse">
          <ul className="text-sm space-y-1">
            {Object.entries(item.risk.stress).map(([label, value]) => (
              <li key={label} className="flex justify-between gap-4">
                <span className="text-slate-400">{label}</span>
                <span className="font-mono font-semibold"><Signed value={value}>{formatCurrency(value)}</Signed></span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Gregas da posição">
          {item.greeks ? (
            <ul className="text-sm space-y-1">
              <GreekRow label="Delta (R$ por R$ 1,00 no ativo)" value={item.greeks.delta} />
              <GreekRow label="Gama" value={item.greeks.gamma} />
              <GreekRow label="Theta (R$ por dia útil)" value={item.greeks.theta_per_business_day} />
              <GreekRow label="Vega (R$ por ponto de vol)" value={item.greeks.vega_per_vol_point} />
            </ul>
          ) : (
            <p className="text-sm text-amber-200">DADOS INSUFICIENTES: falta volatilidade implícita em alguma perna.</p>
          )}
        </Panel>
      </div>

      {(item.risk.warnings.length > 0 || item.assumptions.length > 0) && (
        <Panel title="Avisos e premissas">
          <ul className="text-sm text-slate-300 list-disc pl-4 space-y-1">
            {[...item.risk.warnings, ...item.assumptions].map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

function GreekRow({ label, value }: { label: string; value: number }) {
  return (
    <li className="flex justify-between gap-4">
      <span className="text-slate-400">{label}</span>
      <span className="font-mono text-slate-200">{formatNumber(value)}</span>
    </li>
  );
}

function ChainTable({ chain }: { chain: ChainView }) {
  // Só o miolo da grade: séries muito longe do ativo atrapalham a leitura.
  const rows = useMemo(() => {
    const byStrike = new Map<number, { call?: ChainQuote; put?: ChainQuote }>();
    for (const quote of chain.quotes) {
      if (Math.abs(quote.strike / chain.spot - 1) > 0.15) continue;
      const row = byStrike.get(quote.strike) ?? {};
      if (quote.kind === 'CALL') row.call = quote;
      else row.put = quote;
      byStrike.set(quote.strike, row);
    }
    return [...byStrike.entries()].sort(([a], [b]) => a - b);
  }, [chain]);
  const unusable = chain.quotes.filter((quote) => !quote.usable).length;

  return (
    <Panel title={`Grade de ${chain.symbol}: vencimento ${formatDay(chain.expiry)}, pregão ${formatDay(chain.market_date)}`} className="overflow-x-auto">
      <p className="text-xs text-slate-400 mb-3">
        Strikes até 15% do ativo. {unusable} de {chain.quotes.length} séries não negociaram no pregão ou falharam na validação e aparecem
        apagadas: não entram nas estruturas. O preço é o último negócio do dia.
      </p>
      <table className="w-full text-xs font-mono min-w-[720px]">
        <thead className="text-slate-400">
          <tr>
            <th scope="col" className="text-left font-semibold p-1">Call</th>
            <th scope="col" className="text-right font-semibold p-1">Em aberto</th>
            <th scope="col" className="text-right font-semibold p-1">Delta</th>
            <th scope="col" className="text-right font-semibold p-1">Fech.</th>
            <th scope="col" className="text-center font-semibold p-1 text-white">Strike</th>
            <th scope="col" className="text-left font-semibold p-1">Fech.</th>
            <th scope="col" className="text-left font-semibold p-1">Delta</th>
            <th scope="col" className="text-left font-semibold p-1">Em aberto</th>
            <th scope="col" className="text-right font-semibold p-1">Put</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([strike, { call, put }]) => (
            <tr key={strike} className="border-t border-slate-800/60">
              <td className={cn('p-1', dim(call))}>{call?.symbol ?? '—'}</td>
              <td className={cn('p-1 text-right', dim(call))}>{formatCompact(call?.open_interest)}</td>
              <td className={cn('p-1 text-right', dim(call))}>{formatNumber(call?.delta)}</td>
              <td className={cn('p-1 text-right font-bold', dim(call))}>{formatNumber(call?.close)}</td>
              <td className="p-1 text-center font-bold text-white bg-slate-800/50">{formatNumber(strike)}</td>
              <td className={cn('p-1 font-bold', dim(put))}>{formatNumber(put?.close)}</td>
              <td className={cn('p-1', dim(put))}>{formatNumber(put?.delta)}</td>
              <td className={cn('p-1', dim(put))}>{formatCompact(put?.open_interest)}</td>
              <td className={cn('p-1 text-right', dim(put))}>{put?.symbol ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function dim(quote?: ChainQuote) {
  return quote?.usable ? 'text-slate-200' : 'text-slate-600';
}
