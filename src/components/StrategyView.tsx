/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { type CSSProperties, FormEvent, useEffect, useMemo, useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, ApiError, useResource } from '../services/api';
import { Candidate, ChainQuote, ChainView, DecisionStatus, Profile, StrategiesView } from '../types';
import {
  cn,
  formatChange,
  formatCompact,
  formatCurrency,
  formatDay,
  formatLimit,
  formatMoment,
  formatNumber,
  formatRatio,
  REGIME_LABEL,
  saoPauloDate,
  TREND_LABEL,
} from '../lib/utils';
import { ErrorNotice, Loading, Panel, Signed, Stat } from './Common';
import { OpenInterestPanel, PnlHeatmap, SkewChart } from './OptionAnalytics';

interface StrategyViewProps {
  symbols: string[];
  symbol: string | null;
  onSymbol: (symbol: string) => void;
}

const INK = '#191916';
const PAPER = '#f3efe5';
const SECONDARY = '#494843';

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
    const limit = saoPauloDate(14);
    setExpiry(days.find((day) => day >= limit) ?? days[days.length - 1]);
  }, [expirations.data]);

  const [profile, setProfile] = useState<Profile | null>(null);
  const key = symbol && expiry ? `${symbol}:${expiry}` : null;
  const strategies = useResource(key && `${key}:${profile}`, () => api.strategies(symbol!, expiry!, profile));
  const chain = useResource(key, () => api.chain(symbol!, expiry!));

  return (
    <div className="space-y-4">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-4xl md:text-5xl">Estratégias</h2>
          <p className="np-note mt-1">Calculadas com regras fixas, sem IA. Nenhuma ordem é enviada.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="np-label">
            Seleção de strikes
            <select
              value={profile ?? ''}
              onChange={(event) => setProfile((event.target.value || null) as Profile | null)}
              className="np-input block mt-1"
            >
              <option value="">Distância de 5% do ativo</option>
              <option value="CONSERVATIVE">Delta: conservador</option>
              <option value="MODERATE">Delta: moderado</option>
              <option value="AGGRESSIVE">Delta: agressivo</option>
            </select>
          </label>
          <label className="np-label">
            Ativo
            <select value={symbol ?? ''} onChange={(event) => onSymbol(event.target.value)} className="np-input block mt-1">
              {symbol === null && <option value="">Selecione</option>}
              {symbols.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label className="np-label">
            Vencimento
            <select
              value={expiry ?? ''}
              disabled={!expiry}
              onChange={(event) => setExpiry(event.target.value)}
              className="np-input block mt-1 disabled:opacity-50"
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

      <RiskSettingsForm onSaved={strategies.reload} />

      {!symbol && <p>Selecione um ativo.</p>}
      {expirations.loading && <Loading label="Buscando vencimentos..." />}
      {expirations.error && <ErrorNotice error={expirations.error} onRetry={expirations.reload} />}
      {symbol && expirations.data && !expiry && <p>A fonte não listou vencimentos futuros para {symbol}.</p>}
      {key && strategies.loading && !strategies.data && <Loading label="Calculando estruturas..." />}
      {strategies.error && <ErrorNotice error={strategies.error} onRetry={strategies.reload} />}
      {strategies.data && <Analysis view={strategies.data} />}
      {chain.data && <OpenInterestPanel summary={chain.data.open_interest} />}
      {chain.data && <SkewChart chain={chain.data} />}
      {chain.data && <ChainTable chain={chain.data} />}
    </div>
  );
}

function RiskSettingsForm({ onSaved }: { onSaved: () => void }) {
  const settings = useResource('risk-settings', api.riskSettings);
  const [capital, setCapital] = useState('');
  const [limit, setLimit] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (settings.data?.capital_brl != null) setCapital(String(settings.data.capital_brl));
    if (settings.data?.max_loss_pct != null) setLimit(String(settings.data.max_loss_pct));
  }, [settings.data]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    setFailure(null);
    try {
      await api.saveRiskSettings(Number(capital), Number(limit));
      setMessage('Capital e limite salvos.');
      settings.reload();
      onSaved();
    } catch (error) {
      setFailure((error as ApiError).status === 422 ? 'Informe um capital positivo e um limite entre 0 e 100%.' : (error as ApiError).message);
    }
  };

  return (
    <form onSubmit={submit} className="np-section flex flex-wrap items-end gap-3">
      <div className="basis-full md:basis-auto md:max-w-sm">
        <h3 className="text-xl">Seu capital e limite</h3>
        <p className="font-display text-xs text-ink-2 mt-1">
          {settings.data?.capital_brl != null
            ? `Última alteração: ${formatMoment(settings.data.updated_at)}`
            : 'Sem esses valores, nenhuma estrutura é aprovada. O app não os presume.'}
        </p>
      </div>
      <label className="np-label">
        Capital (R$)
        <input type="number" min="0.01" step="0.01" required value={capital} onChange={(event) => setCapital(event.target.value)} className="np-input block mt-1 w-40" />
      </label>
      <label className="np-label">
        Perda máxima por estrutura (%)
        <input type="number" min="0.01" max="100" step="0.01" required value={limit} onChange={(event) => setLimit(event.target.value)} className="np-input block mt-1 w-40" />
      </label>
      <button type="submit" className="np-btn">
        Salvar
      </button>
      {message && <p role="status" className="basis-full text-base">{message}</p>}
      {failure && <p role="alert" className="basis-full text-accent text-base">{failure}</p>}
    </form>
  );
}

const STATUS_LABEL: Record<DecisionStatus, string> = { APROVADA: 'Aprovada', REPROVADA: 'Reprovada', INCOMPLETA: 'Incompleta' };

function DecisionLabel({ status }: { status: DecisionStatus }) {
  return (
    <span
      className={cn(
        'np-label border px-1.5 py-0.5 shrink-0',
        status === 'APROVADA' && '!text-paper bg-ink border-ink',
        status === 'REPROVADA' && '!text-accent border-accent',
        status === 'INCOMPLETA' && 'border-rule',
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

function Analysis({ view }: { view: StrategiesView }) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const selected = view.candidates.find((item) => item.key === selectedKey) ?? view.candidates[0];
  const approved = view.candidates.filter((item) => item.decision.status === 'APROVADA').length;
  const drifted = view.candidates.length > 0 && view.candidates.every((item) => item.risk.rejection_reason?.includes('defasados'));

  return (
    <div className="space-y-4">
      <p role="status" className="border-y border-ink py-2 text-base">
        Prêmios do <strong>fechamento de {formatDay(view.market_date)}</strong>, com o ativo a {formatCurrency(view.spot)}: são
        indicativos e não garantem execução. A grade do pregão do dia entra por volta das 21h. Fonte: brapi.
      </p>
      {drifted && (
        <p role="alert" className="border-y border-accent py-2 text-base">
          O ativo está em {formatCurrency(view.live_price)}, <strong className="text-accent">{formatChange((view.spot_drift ?? 0) * 100)}</strong> em relação à
          grade. Com essa diferença, os prêmios estão defasados e todas as estruturas ficam reprovadas até a próxima grade.
        </p>
      )}

      <MarketContext view={view} />

      <div className="np-facts" style={{ '--np-columns': 4 } as CSSProperties}>
        <Stat label="Vol implícita" value={formatRatio(view.atm_iv)} hint="Call e put no dinheiro" />
        <Stat label="Vol histórica" value={formatRatio(view.historical_volatility)} hint="1 ano" />
        <Stat label="Regime" value={view.regime ? REGIME_LABEL[view.regime] : '—'} hint={`Impl./Hist. ${formatNumber(view.iv_ratio)}`} />
        <Stat label="Juros" value={formatRatio(view.risk_free_rate, 2)} hint="Informado pela fonte" />
      </div>

      <div className="np-spread-side np-section">
        <aside className="min-w-0">
          <h3 className="text-xl mb-2">{`Estruturas: ${approved} de ${view.candidates.length} aprovadas`}</h3>
          <ul>
            {view.candidates.map((item) => (
              <li key={item.key} className="np-rule">
                <button
                  onClick={() => setSelectedKey(item.key)}
                  aria-current={selected?.key === item.key}
                  className="w-full py-2 px-1 text-left font-display cursor-pointer hover:bg-[#e6e0d2] aria-[current=true]:bg-[#e6e0d2]"
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-sm">{item.name}</span>
                    <DecisionLabel status={item.decision.status} />
                  </span>
                  <span className="block text-xs text-ink-2 mt-1">
                    Ganho {formatLimit(item.max_profit)} · Perda {formatLimit(item.max_loss)}
                    {item.fits_regime && ' · compatível com o regime'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {view.unavailable.length > 0 && (
            <div className="mt-3 pt-3 np-rule font-display text-xs text-ink-2 space-y-1">
              <p className="font-semibold">Sem strikes na grade:</p>
              {view.unavailable.map((item) => (
                <p key={item.key}>{item.name}: {item.reason}</p>
              ))}
            </div>
          )}
        </aside>
        <div className="min-w-0">{selected ? <Detail item={selected} spot={view.spot} /> : <p>Nenhuma estrutura pôde ser montada.</p>}</div>
      </div>
    </div>
  );
}

function MarketContext({ view }: { view: StrategiesView }) {
  const lastBreak = view.structure?.events.at(-1);
  return (
    <Panel title="Contexto do ativo">
      <div className="np-facts" style={{ '--np-columns': 3 } as CSSProperties}>
        <Stat
          label="Estrutura diária"
          value={view.structure?.trend ? TREND_LABEL[view.structure.trend] : 'Sem rompimento'}
          hint={lastBreak ? `${lastBreak.kind === 'CHOCH' ? 'CHoCH' : 'BOS'} em ${formatDay(lastBreak.day)}, além de ${formatCurrency(lastBreak.level)}` : undefined}
        />
        <Stat
          label="IV Rank"
          value={view.iv_rank !== null ? formatNumber(view.iv_rank, 0) : `${view.iv_samples} de ${view.iv_samples_needed} amostras`}
          hint={view.iv_percentile !== null ? `Percentil ${formatNumber(view.iv_percentile, 0)}` : undefined}
        />
        <div>
          <p className="np-label">Próximos eventos</p>
          {view.events_error ? (
            <p className="text-accent text-base mt-1">DADOS INSUFICIENTES: {view.events_error}</p>
          ) : view.events.length === 0 ? (
            <p className="text-base mt-1">Nenhum informado pela fonte nos próximos 180 dias</p>
          ) : (
            <ul className="text-base mt-1">
              {view.events.slice(0, 4).map((event) => (
                <li key={`${event.day}-${event.label}`}>
                  {formatDay(event.day)}: {event.label}
                  {!event.confirmed && <span className="text-ink-2"> (data estimada)</span>}
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
  const decision = item.decision;
  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-3xl">{item.name}</h3>
          <DecisionLabel status={decision.status} />
        </div>
        <p className="mt-1">{item.rationale}</p>
        {decision.reasons.length > 0 && (
          <div className="mt-2 text-base">
            <p className="np-label !text-accent">Motivos da reprovação</p>
            <ul className="list-disc pl-5">
              {decision.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        )}
        {decision.missing.length > 0 && (
          <div className="mt-2 text-base">
            <p className="np-label">Falta para decidir</p>
            <ul className="list-disc pl-5">
              {decision.missing.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        )}
        {decision.status === 'APROVADA' && <p className="mt-2 text-base">Passou nas regras de risco; não é recomendação.</p>}
      </div>

      <div className="np-facts np-rule" style={{ '--np-columns': 4 } as CSSProperties}>
        <Stat label="Ganho máximo" value={formatLimit(item.max_profit)} />
        <Stat label="Perda máxima" value={formatLimit(item.max_loss)} hint={decision.max_risk_pct !== null ? `${formatNumber(decision.max_risk_pct)}% do capital` : undefined} />
        <Stat label={item.net_premium >= 0 ? 'Débito' : 'Crédito'} value={formatCurrency(Math.abs(item.net_premium))} hint="Na montagem" />
        <Stat label="Prob. de lucro" value={formatRatio(item.probability_of_profit, 0)} hint="Neutra ao risco; não é previsão" />
      </div>
      <div className="np-facts" style={{ '--np-columns': 3 } as CSSProperties}>
        <Stat label="Capital necessário" value={decision.capital_required !== null ? formatCurrency(decision.capital_required) : 'Margem desconhecida'} hint={decision.capital_required === null ? 'Calculada pela B3 e pela corretora' : 'Custo da montagem'} />
        <Stat label="Limite de perda" value={decision.limit_brl !== null ? formatCurrency(decision.limit_brl) : 'Não informado'} />
        <Stat label="Risco / retorno" value={item.risk_reward !== null ? `1 : ${formatNumber(item.risk_reward)}` : 'Sem limite definido'} />
      </div>

      <Panel title="Resultado no vencimento (R$)">
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={item.payoff} margin={{ top: 16, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#d9d4c8" vertical={false} />
              <XAxis
                dataKey="price"
                type="number"
                domain={['dataMin', 'dataMax']}
                stroke={SECONDARY}
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value: number) => value.toFixed(0)}
              />
              <YAxis stroke={SECONDARY} fontSize={12} tickLine={false} axisLine={false} width={56} />
              <ReferenceLine y={0} stroke={SECONDARY} />
              <ReferenceLine
                x={spot}
                stroke={SECONDARY}
                strokeDasharray="4 4"
                label={{ value: 'Ativo na grade', fill: SECONDARY, fontSize: 11, position: 'top' }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: PAPER, border: `1px solid ${INK}`, borderRadius: 0 }}
                labelStyle={{ color: SECONDARY }}
                itemStyle={{ color: INK }}
                labelFormatter={(price) => `Ativo a ${formatCurrency(Number(price))}`}
                formatter={(value) => [formatCurrency(Number(value)), 'Resultado']}
              />
              <Line type="linear" dataKey="pnl" stroke={INK} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="font-display text-xs text-ink-2 mt-2">
          Breakeven: {item.breakevens.length ? item.breakevens.map((value) => formatCurrency(value)).join(' e ') : 'nenhum'} · Liquidez:{' '}
          {formatNumber(item.risk.liquidity_score)} de 1,00
        </p>
      </Panel>

      {item.heatmap && <PnlHeatmap heatmap={item.heatmap} />}

      <Panel title="Pernas" className="overflow-x-auto">
        <table className="np-table min-w-[720px]">
          <thead>
            <tr>
              <th scope="col" className="text-left">Lado</th>
              <th scope="col" className="text-left">Série</th>
              <th scope="col" className="text-left">Tipo</th>
              <th scope="col" className="text-left">Estilo</th>
              <th scope="col" className="text-right">Strike</th>
              <th scope="col" className="text-right">Prêmio</th>
              <th scope="col" className="text-right">Qtd.</th>
              <th scope="col" className="text-right">Vol impl.</th>
              <th scope="col" className="text-right">Delta</th>
              <th scope="col" className="text-right">Prob. ITM</th>
            </tr>
          </thead>
          <tbody>
            {item.legs.map((leg) => (
              <tr key={`${leg.symbol}-${leg.action}`}>
                <td>{leg.action === 'BUY' ? 'Compra' : 'Venda'}</td>
                <td>{leg.symbol}</td>
                <td>{leg.kind === 'CALL' ? 'Call' : 'Put'}</td>
                <td>{leg.style === 'AMERICAN' ? 'Americana' : leg.style === 'EUROPEAN' ? 'Europeia' : 'Não informado'}</td>
                <td className="text-right">{formatNumber(leg.strike)}</td>
                <td className="text-right">{formatNumber(leg.premium)}</td>
                <td className="text-right">{leg.quantity}</td>
                <td className="text-right">{formatRatio(leg.iv)}</td>
                <td className="text-right">{formatNumber(leg.delta)}</td>
                <td className="text-right">{formatRatio(leg.probability_itm, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div className="np-spread-side np-section !border-t-0 !pt-0">
        <div className="min-w-0">
          <h3 className="text-xl mb-2">Cenários de estresse</h3>
          <ul className="font-display text-sm">
            {Object.entries(item.risk.stress).map(([label, value]) => (
              <li key={label} className="flex justify-between gap-4 py-1 np-rule">
                <span className="text-ink-2">{label}</span>
                <span className="font-semibold"><Signed value={value}>{formatCurrency(value)}</Signed></span>
              </li>
            ))}
          </ul>
        </div>
        <div className="min-w-0">
          <h3 className="text-xl mb-2">Gregas da posição</h3>
          {item.greeks ? (
            <ul className="font-display text-sm">
              <GreekRow label="Delta (R$ por R$ 1,00 no ativo)" value={item.greeks.delta} />
              <GreekRow label="Gama" value={item.greeks.gamma} />
              <GreekRow label="Theta (R$ por dia útil)" value={item.greeks.theta_per_business_day} />
              <GreekRow label="Vega (R$ por ponto de vol)" value={item.greeks.vega_per_vol_point} />
            </ul>
          ) : (
            <p className="text-accent text-base">DADOS INSUFICIENTES: falta volatilidade implícita em alguma perna.</p>
          )}
        </div>
      </div>

      {(item.risk.warnings.length > 0 || item.assumptions.length > 0) && (
        <Panel title="Avisos e premissas">
          <ul className="list-disc pl-5 text-base space-y-1">
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
    <li className="flex justify-between gap-4 py-1 np-rule">
      <span className="text-ink-2">{label}</span>
      <span>{formatNumber(value)}</span>
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
      <p className="font-display text-xs text-ink-2 mb-3">
        Strikes até 15% do ativo. {unusable} de {chain.quotes.length} séries não negociaram no pregão ou falharam na validação e aparecem
        apagadas: não entram nas estruturas. O preço é o último negócio do dia.
      </p>
      <table className="np-table min-w-[720px]">
        <thead>
          <tr>
            <th scope="col" className="text-left">Call</th>
            <th scope="col" className="text-right">Em aberto</th>
            <th scope="col" className="text-right">Delta</th>
            <th scope="col" className="text-right">Fech.</th>
            <th scope="col" className="text-center">Strike</th>
            <th scope="col" className="text-left">Fech.</th>
            <th scope="col" className="text-left">Delta</th>
            <th scope="col" className="text-left">Em aberto</th>
            <th scope="col" className="text-right">Put</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([strike, { call, put }]) => (
            <tr key={strike}>
              <td className={dim(call)}>{call?.symbol ?? '—'}</td>
              <td className={cn('text-right', dim(call))}>{formatCompact(call?.open_interest)}</td>
              <td className={cn('text-right', dim(call))}>{formatNumber(call?.delta)}</td>
              <td className={cn('text-right font-semibold', dim(call))}>{formatNumber(call?.close)}</td>
              <td className="text-center font-black border-x border-rule">{formatNumber(strike)}</td>
              <td className={cn('font-semibold', dim(put))}>{formatNumber(put?.close)}</td>
              <td className={dim(put)}>{formatNumber(put?.delta)}</td>
              <td className={dim(put)}>{formatCompact(put?.open_interest)}</td>
              <td className={cn('text-right', dim(put))}>{put?.symbol ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function dim(quote?: ChainQuote) {
  return quote?.usable ? '' : 'text-rule';
}
