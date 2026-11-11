/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { type CSSProperties, FormEvent, useEffect, useMemo, useState } from 'react';
import { api, ApiError, useResource } from '../services/api';
import { paraCampo, parseNumeroBR } from '../lib/numero';
import { CalendarCandidate, CalendarsView, Candidate, ChainQuote, ChainView, DecisionStatus, Profile, StrategiesView } from '../types';
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
import { PayoffMap } from './PayoffMap';
import { setJarbasContext } from '../lib/jarbasStore';
import { StrategyGuideCard } from './StrategyGuide';
import { guideOf, MarketView, VIEW_LABEL, VIEW_QUESTION } from '../lib/strategyGuide';

interface StrategyViewProps {
  symbols: string[];
  symbol: string | null;
  onSymbol: (symbol: string) => void;
}

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
  // Fora da tela de estratégias, o Jarbas não fala de uma estrutura que não está à vista.
  useEffect(() => () => setJarbasContext(null), []);

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

      <details
        className="np-section"
        open={!(strategies.data?.capital_configured && strategies.data?.costs_configured)}
      >
        <summary className="cursor-pointer text-xl">Seu capital, limite e custos</summary>
        <p className="np-note mt-1">Sem esses valores nenhuma estrutura é aprovada. Depois de salvos, esta parte fica recolhida.</p>
        <RiskSettingsForm onSaved={strategies.reload} />
        <CostSettingsForm onSaved={strategies.reload} />
      </details>

      {!symbol && <p>Selecione um ativo.</p>}
      {expirations.loading && <Loading label="Buscando vencimentos..." />}
      {expirations.error && <ErrorNotice error={expirations.error} onRetry={expirations.reload} />}
      {symbol && expirations.data && !expiry && <p>A fonte não listou vencimentos futuros para {symbol}.</p>}
      {key && strategies.loading && !strategies.data && <Loading label="Calculando estruturas..." />}
      {strategies.error && <ErrorNotice error={strategies.error} onRetry={strategies.reload} />}
      {strategies.data && <Analysis view={strategies.data} expirations={expirations.data?.expirations ?? []} />}
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
    const cap = parseNumeroBR(capital);
    const perda = parseNumeroBR(limit);
    if (!cap.ok || !perda.ok) {
      setFailure(!cap.ok ? `Capital: ${cap.reason}` : `Perda máxima: ${(perda as { reason: string }).reason}`);
      return;
    }
    try {
      await api.saveRiskSettings(cap.value, perda.value);
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
        <input type="text" inputMode="decimal" required value={capital} onChange={(event) => setCapital(event.target.value)} placeholder="ex.: 10.000,00" className="np-input block mt-1 w-40" />
      </label>
      <label className="np-label">
        Perda máxima por estrutura (%)
        <input type="text" inputMode="decimal" required value={limit} onChange={(event) => setLimit(event.target.value)} placeholder="ex.: 2" className="np-input block mt-1 w-40" />
      </label>
      <button type="submit" className="np-btn">
        Salvar
      </button>
      {message && <p role="status" className="basis-full text-base">{message}</p>}
      {failure && <p role="alert" className="basis-full text-accent text-base">{failure}</p>}
    </form>
  );
}

function CostSettingsForm({ onSaved }: { onSaved: () => void }) {
  const settings = useResource('cost-settings', api.costSettings);
  const [perOrder, setPerOrder] = useState('');
  const [fee, setFee] = useState('');
  const [tax, setTax] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (settings.data?.per_order_brl != null) setPerOrder(paraCampo(settings.data.per_order_brl));
    if (settings.data?.fee_pct != null) setFee(paraCampo(settings.data.fee_pct));
    if (settings.data?.income_tax_pct != null) setTax(paraCampo(settings.data.income_tax_pct));
  }, [settings.data]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    setFailure(null);
    const ordem = parseNumeroBR(perOrder);
    const taxa = parseNumeroBR(fee);
    const imposto = parseNumeroBR(tax);
    if (!ordem.ok || !taxa.ok || !imposto.ok) {
      setFailure(!ordem.ok ? `Corretagem: ${ordem.reason}` : !taxa.ok ? `Taxas: ${taxa.reason}` : `Imposto: ${(imposto as { reason: string }).reason}`);
      return;
    }
    try {
      await api.saveCostSettings(ordem.value, taxa.value, imposto.value);
      setMessage('Custos salvos.');
      settings.reload();
      onSaved();
    } catch (error) {
      setFailure((error as ApiError).status === 422 ? 'Corretagem a partir de zero, taxas entre 0 e 5% e alíquota entre 0 e 100%.' : (error as ApiError).message);
    }
  };

  return (
    <form onSubmit={submit} className="np-section flex flex-wrap items-end gap-3">
      <div className="basis-full md:basis-auto md:max-w-sm">
        <h3 className="text-xl">Seus custos</h3>
        <p className="font-display text-xs text-ink-2 mt-1">
          {settings.data?.per_order_brl != null
            ? `Última alteração: ${formatMoment(settings.data.updated_at)}`
            : 'Sem custos informados, nenhuma estrutura é aprovada. Se não paga corretagem, informe zero.'}
        </p>
      </div>
      <label className="np-label">
        Corretagem por ordem (R$)
        <input type="text" inputMode="decimal" required value={perOrder} onChange={(event) => setPerOrder(event.target.value)} placeholder="ex.: 4,90" className="np-input block mt-1 w-32" />
      </label>
      <label className="np-label">
        Taxas da B3 (% do financeiro)
        <input type="text" inputMode="decimal" required value={fee} onChange={(event) => setFee(event.target.value)} placeholder="ex.: 0,0275" className="np-input block mt-1 w-32" />
      </label>
      <label className="np-label">
        Imposto sobre o ganho (%)
        <input type="text" inputMode="decimal" required value={tax} onChange={(event) => setTax(event.target.value)} placeholder="ex.: 15" className="np-input block mt-1 w-32" />
      </label>
      <button type="submit" className="np-btn" aria-label="Salvar custos">
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

const VIEWS: MarketView[] = ['ALTA', 'BAIXA', 'LATERAL', 'MOVIMENTO'];

type Section = 'BASE' | 'RANKING' | 'CALENDAR';

const SECTION_LABEL: Record<Section, string> = {
  BASE: 'Estruturas clássicas',
  RANKING: 'Travas mais rentáveis',
  CALENDAR: 'Calendário e diagonal',
};

function Analysis({ view, expirations }: { view: StrategiesView; expirations: string[] }) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [marketView, setMarketView] = useState<MarketView | null>(null);
  const [section, setSection] = useState<Section>('BASE');
  const inView = (item: { key: string; family?: string }) => marketView === null || guideOf(item)?.view === marketView;
  const base = view.candidates.filter((item) => (item.group ?? 'BASE') === 'BASE');
  const ranked = view.candidates.filter((item) => item.group === 'RANKING');
  const shown = (section === 'RANKING' ? ranked : base).filter(inView);
  const selected = shown.find((item) => item.key === selectedKey) ?? shown[0];
  const approved = base.filter((item) => item.decision.status === 'APROVADA').length;
  const drifted = view.candidates.length > 0 && view.candidates.every((item) => item.risk.rejection_reason?.includes('defasados'));

  return (
    <div className="space-y-4">
      <p role="status" className="border-y border-ink py-2 text-base">
        Prêmios do <strong>fechamento de {formatDay(view.market_date)}</strong>, com o ativo a {formatCurrency(view.spot)}: são
        indicativos e não garantem execução. Faltam {view.business_days_to_expiry} pregões até o vencimento, pelo calendário da B3. A grade
        do pregão do dia entra por volta das 21h. Fonte: {view.source ?? 'não informada'}.
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

      <div className="np-section">
        <h3 className="text-xl">O que você espera de {view.symbol} até {formatDay(view.expiry)}?</h3>
        <p className="np-note mt-1">Escolha uma visão e veja só as estruturas feitas para ela.</p>
        <div className="flex flex-wrap gap-2 mt-2" role="group" aria-label="Visão de mercado">
          <button className="np-btn" aria-pressed={marketView === null} onClick={() => setMarketView(null)}>
            Todas
          </button>
          {VIEWS.map((option) => (
            <button key={option} className="np-btn" aria-pressed={marketView === option} onClick={() => setMarketView(option)} title={VIEW_LABEL[option]}>
              {VIEW_QUESTION[option]}
            </button>
          ))}
        </div>
      </div>

      <nav aria-label="Tipo de estrutura" className="flex flex-wrap gap-2 border-y border-ink py-2">
        {(Object.keys(SECTION_LABEL) as Section[]).map((option) => (
          <button key={option} className="np-btn" aria-current={section === option ? 'page' : undefined} onClick={() => setSection(option)}>
            {SECTION_LABEL[option]}
            {option === 'RANKING' && ` (${ranked.length})`}
          </button>
        ))}
      </nav>

      {section === 'CALENDAR' ? (
        <CalendarSection symbol={view.symbol} near={view.expiry} expirations={expirations} inView={inView} />
      ) : (
      <div className="np-spread-side np-section">
        <aside className="min-w-0">
          {section === 'BASE' ? (
            <h3 className="text-xl mb-2">{`Estruturas: ${approved} de ${base.length} aprovadas`}</h3>
          ) : (
            <>
              <h3 className="text-xl mb-1">Travas mais rentáveis</h3>
              <p className="font-display text-xs text-ink-2 mb-2">
                Todos os pares de strikes com liquidez foram testados. Ficam os 3 melhores de cada tipo pela estimativa média por real
                de risco, que pesa o ganho junto com a chance de acontecer. Retorno máximo alto quase sempre vem com chance baixa.
              </p>
              {ranked.length === 0 && <p className="text-base">Nenhum par de séries passou nos filtros de liquidez desta grade.</p>}
            </>
          )}
          {shown.length === 0 && <p className="text-base">Nenhuma estrutura desta visão pôde ser montada nesta grade.</p>}
          <ul>
            {shown.map((item) => (
              <li key={item.key} className="np-rule">
                <button
                  onClick={() => setSelectedKey(item.key)}
                  aria-current={selected?.key === item.key}
                  className="w-full py-2 px-1 text-left font-display cursor-pointer hover:bg-[var(--dp-color-hover)] aria-[current=true]:bg-[var(--dp-color-hover)]"
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-sm">
                      {item.ranking && `${item.ranking.rank}º · `}
                      {item.name}
                    </span>
                    <DecisionLabel status={item.decision.status} />
                  </span>
                  <span className="block text-xs text-ink-2 mt-1">
                    {guideOf(item) && `${VIEW_LABEL[guideOf(item)!.view]} · `}
                    Chance de lucro {formatRatio(item.probability_of_profit, 0)}
                  </span>
                  {item.ranking && (
                    <span className="block text-xs text-ink-2">
                      Retorno máx. {item.ranking.max_return_on_risk !== null ? formatRatio(item.ranking.max_return_on_risk, 0) : '—'} do risco ·
                      Estimativa média {formatCurrency(item.ranking.expected_pnl)} ({formatRatio(item.ranking.expected_return_on_risk, 1)} do risco)
                    </span>
                  )}
                  <span className="block text-xs text-ink-2">
                    Ganho {formatLimit(item.max_profit)} · Perda {formatLimit(item.max_loss)}
                    {item.fits_regime && ' · compatível com o regime'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {section === 'BASE' && view.unavailable.length > 0 && (
            <div className="mt-3 pt-3 np-rule font-display text-xs text-ink-2 space-y-1">
              <p className="font-semibold">Sem strikes na grade:</p>
              {view.unavailable.map((item) => (
                <p key={item.key}>{item.name}: {item.reason}</p>
              ))}
            </div>
          )}
        </aside>
        <div className="min-w-0">{selected ? <Detail item={selected} view={view} /> : <p>Nenhuma estrutura pôde ser montada.</p>}</div>
      </div>
      )}
    </div>
  );
}

function CalendarSection({
  symbol,
  near,
  expirations,
  inView,
}: {
  symbol: string;
  near: string;
  expirations: string[];
  inView: (item: { key: string; family?: string }) => boolean;
}) {
  const fars = useMemo(() => expirations.filter((day) => day > near), [expirations, near]);
  const [far, setFar] = useState<string | null>(fars[0] ?? null);
  useEffect(() => setFar(fars[0] ?? null), [fars]);
  const calendars = useResource(far ? `calendars:${symbol}:${near}:${far}` : null, () => api.calendars(symbol, near, far!));
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  if (fars.length === 0) return <p className="np-section">Não há vencimento depois de {formatDay(near)} para montar calendário ou diagonal.</p>;
  const data = calendars.data;
  const shown = (data?.candidates ?? []).filter(inView);
  const selected = shown.find((item) => item.key === selectedKey) ?? shown[0];

  return (
    <div className="space-y-4">
      <div className="np-section flex flex-wrap items-end gap-3">
        <p className="basis-full md:basis-auto md:max-w-md text-base">
          Vende no vencimento curto (<strong>{formatDay(near)}</strong>, o escolhido acima) e compra no longo. O resultado é medido no dia do
          vencimento curto.
        </p>
        <label className="np-label">
          Vencimento longo
          <select value={far ?? ''} onChange={(event) => setFar(event.target.value)} className="np-input block mt-1">
            {fars.map((day) => (
              <option key={day} value={day}>
                {formatDay(day)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {calendars.loading && !data && <Loading label="Montando calendários..." />}
      {calendars.error && <ErrorNotice error={calendars.error} onRetry={calendars.reload} />}
      {data && (
        <div className="np-spread-side np-section">
          <aside className="min-w-0">
            <h3 className="text-xl mb-2">Calendário e diagonal</h3>
            {shown.length === 0 && <p className="text-base">Nenhuma estrutura desta visão pôde ser montada.</p>}
            <ul>
              {shown.map((item) => (
                <li key={item.key} className="np-rule">
                  <button
                    onClick={() => setSelectedKey(item.key)}
                    aria-current={selected?.key === item.key}
                    className="w-full py-2 px-1 text-left font-display cursor-pointer hover:bg-[var(--dp-color-hover)] aria-[current=true]:bg-[var(--dp-color-hover)]"
                  >
                    <span className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-sm">{item.name}</span>
                      <DecisionLabel status={item.decision.status} />
                    </span>
                    <span className="block text-xs text-ink-2 mt-1">
                      Chance de lucro {formatRatio(item.probability_of_profit, 0)} · Débito {formatCurrency(item.net_premium)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {data.unavailable.length > 0 && (
              <div className="mt-3 pt-3 np-rule font-display text-xs text-ink-2 space-y-1">
                <p className="font-semibold">Não montadas:</p>
                {data.unavailable.map((item) => (
                  <p key={item.key}>
                    {item.name}: {item.reason}
                  </p>
                ))}
              </div>
            )}
          </aside>
          <div className="min-w-0">{selected ? <CalendarDetail item={selected} view={data} /> : <p>Nenhuma estrutura pôde ser montada.</p>}</div>
        </div>
      )}
    </div>
  );
}

function CalendarDetail({ item, view }: { item: CalendarCandidate; view: CalendarsView }) {
  const credit = item.net_premium < 0;
  useEffect(() => {
    setJarbasContext({
      symbol: view.symbol,
      structure_key: item.family,
      structure_name: item.name,
      section: 'CALENDAR',
      market_date: view.market_date,
      spot: view.spot,
      expiry: view.near,
      business_days_to_expiry: view.business_days_to_near,
      net_premium: item.net_premium,
      max_profit: item.max_profit,
      max_loss: item.max_loss,
      max_profit_is_estimate: true,
      breakevens: item.breakevens.slice(0, 6),
      probability_of_profit: item.probability_of_profit,
      expected_pnl: item.expected_pnl,
      decision_status: item.decision.status,
      decision_reasons: item.decision.reasons,
      decision_missing: item.decision.missing,
      warnings: [...item.warnings, ...item.assumptions].slice(0, 16),
      legs: item.legs.map((leg) => ({
        symbol: leg.symbol, action: leg.action, kind: leg.kind, strike: leg.strike, quantity: leg.quantity,
        premium: leg.premium, expiry: leg.expiry, iv: leg.iv, delta: leg.delta, style: leg.style,
      })),
    });
  }, [item, view]);
  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-3xl">{item.name}</h3>
          <DecisionLabel status={item.decision.status} />
        </div>
        <p className="mt-1">{item.rationale}</p>
        <div className="mt-2 text-base">
          <p className="np-label">Por que não é aprovada</p>
          <ul className="list-disc pl-5">
            {item.decision.missing.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="np-facts np-rule" style={{ '--np-columns': 4 } as CSSProperties}>
        <Stat label={credit ? 'Crédito' : 'Débito'} value={formatCurrency(Math.abs(item.net_premium))} hint="Na montagem" />
        <Stat label="Perda máxima" value={formatCurrency(item.max_loss)} hint="No vencimento curto, pelo modelo" />
        <Stat label="Ganho máx. estimado" value={formatLimit(item.max_profit)} hint="Depende da vol da perna longa" />
        <Stat label="Faltam" value={`${view.business_days_to_near} pregões`} hint={`Até o vencimento curto, ${formatDay(view.near)}`} />
      </div>

      <StrategyGuideCard item={item} />

      <PayoffMap
        symbol={view.symbol}
        legs={item.legs}
        spot={view.spot}
        t={view.t_near}
        r={view.risk_free_rate}
        atmIv={null}
        maxProfit={item.max_profit}
        maxLoss={item.max_loss}
        breakevens={item.breakevens}
      />

      {(item.warnings.length > 0 || item.assumptions.length > 0) && (
        <Panel title="Avisos e premissas">
          <ul className="list-disc pl-5 text-base space-y-1">
            {[...item.warnings, ...item.assumptions].map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </Panel>
      )}
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

function Detail({ item, view }: { item: Candidate; view: StrategiesView }) {
  const decision = item.decision;
  useEffect(() => {
    setJarbasContext({
      symbol: view.symbol,
      structure_key: item.family ?? item.key,
      structure_name: item.name,
      section: item.group ?? 'BASE',
      market_date: view.market_date,
      spot: view.spot,
      live_price: view.live_price,
      spot_drift: view.spot_drift,
      expiry: view.expiry,
      business_days_to_expiry: view.business_days_to_expiry,
      net_premium: item.net_premium,
      max_profit: item.max_profit,
      max_loss: item.max_loss,
      breakevens: item.breakevens.slice(0, 6),
      probability_of_profit: item.probability_of_profit,
      expected_pnl: item.ranking?.expected_pnl ?? null,
      costs_brl: decision.costs_brl ?? null,
      decision_status: decision.status,
      decision_reasons: decision.reasons.slice(0, 12),
      decision_missing: decision.missing.slice(0, 12),
      warnings: [...item.risk.warnings, ...item.assumptions].slice(0, 16),
      atm_iv: view.atm_iv,
      legs: item.legs.map((leg) => ({
        symbol: leg.symbol, action: leg.action, kind: leg.kind, strike: leg.strike, quantity: leg.quantity,
        premium: leg.premium, iv: leg.iv, delta: leg.delta, style: leg.style,
      })),
    });
  }, [item, view]);
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
      <div className="np-facts" style={{ '--np-columns': 5 } as CSSProperties}>
        <Stat
          label="Custos"
          value={decision.costs_brl != null ? formatCurrency(decision.costs_brl) : 'Não informados'}
          hint="Montagem e desmonte; perda máxima com custos entra no limite"
        />
        <Stat
          label="Ganho líquido máx."
          value={decision.costs_brl != null ? formatLimit(decision.max_profit_net ?? null) : '—'}
          hint="Após custos e imposto, sem compensar prejuízos"
        />
        <Stat label="Capital necessário" value={decision.capital_required !== null ? formatCurrency(decision.capital_required) : 'Margem desconhecida'} hint={decision.capital_required === null ? 'Calculada pela B3 e pela corretora' : 'Custo da montagem'} />
        <Stat label="Limite de perda" value={decision.limit_brl !== null ? formatCurrency(decision.limit_brl) : 'Não informado'} />
        <Stat label="Risco / retorno" value={item.risk_reward !== null ? `1 : ${formatNumber(item.risk_reward)}` : 'Sem limite definido'} />
      </div>

      <StrategyGuideCard item={item} />

      <PayoffMap
        symbol={view.symbol}
        legs={item.legs}
        spot={view.spot}
        t={view.time_to_expiry_years}
        r={view.risk_free_rate}
        atmIv={view.atm_iv}
        maxProfit={item.max_profit}
        maxLoss={item.max_loss}
        breakevens={item.breakevens}
      />

      <details className="np-section">
        <summary className="cursor-pointer text-xl">Detalhes técnicos: pernas, gregas, estresse e mapa de calor</summary>
        <p className="font-display text-xs text-ink-2 mt-1">Liquidez: {formatNumber(item.risk.liquidity_score)} de 1,00</p>
        <div className="space-y-4 mt-3">
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
      </details>
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
