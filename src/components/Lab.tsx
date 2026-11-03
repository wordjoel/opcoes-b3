import { FormEvent, useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, ApiError, useResource } from '../services/api';
import { LabOpportunity, LabRankingRow, LabStrategy } from '../types';
import { formatCurrency, formatDay, formatLimit, formatNumber, formatRatio } from '../lib/utils';
import { ErrorNotice, Loading, Panel, Signed } from './Common';

const INK = '#191916';
const PAPER = '#f3efe5';
const SECONDARY = '#494843';
const PERIODS = [1, 3, 5, 10, 15, 30];
type Section = 'oportunidades' | 'acompanhamento' | 'backtest' | 'ranking';

const STATUS_ASSET: Record<string, string> = {
  ANALISADO: 'Analisado',
  SEM_LIQUIDEZ: 'Sem liquidez',
  DADOS_INSUFICIENTES: 'Dados insuficientes',
  NAO_ANALISADO: 'Não analisado',
};
const READING: Record<LabRankingRow['reading'], string> = {
  LUCRO_NOS_DOIS_LIMITES: 'Lucro nos dois limites',
  LUCRO_SO_NO_FECHAMENTO: 'Lucro só no fechamento',
  SEM_LUCRO: 'Sem lucro',
  EXECUCAO_NAO_MEDIDA: 'Execução não medida',
};
const REASON: Record<string, string> = {
  ALVO: 'Alvo atingido',
  STOP: 'Stop atingido',
  VENCIMENTO: 'Vencimento',
  FIM_DO_PERIODO: 'Fim do período',
  SEM_MARCACAO: 'Sem marcação',
};

export function Lab() {
  const [section, setSection] = useState<Section>('oportunidades');
  const [selected, setSelected] = useState<string | null>(null);
  const sections: [Section, string][] = [
    ['oportunidades', 'Oportunidades'],
    ['acompanhamento', 'Em acompanhamento'],
    ['backtest', 'Backtest'],
    ['ranking', 'Rankings'],
  ];

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-4xl md:text-5xl">Laboratório de Estratégias</h2>
        <p className="np-note mt-1">
          Testa se as estratégias propostas funcionariam, com preços reais e sem enviar ordens. Todo resultado é hipotético.
        </p>
      </header>
      <nav aria-label="Seções do laboratório" className="flex flex-wrap gap-2 border-y border-ink py-2">
        {sections.map(([id, label]) => (
          <button
            key={id}
            aria-current={section === id ? 'page' : undefined}
            onClick={() => {
              setSection(id);
              setSelected(null);
            }}
            className="np-btn"
          >
            {label}
          </button>
        ))}
      </nav>
      {selected ? (
        <StrategyDetail id={selected} onBack={() => setSelected(null)} />
      ) : (
        <>
          {section === 'oportunidades' && <Opportunities />}
          {section === 'acompanhamento' && <Tracked onOpen={setSelected} />}
          {section === 'backtest' && <Backtests onOpen={setSelected} />}
          {section === 'ranking' && <Rankings />}
        </>
      )}
    </div>
  );
}

function Opportunities() {
  const data = useResource('lab-opportunities', api.labOpportunities);
  const [open, setOpen] = useState<string | null>(null);
  if (data.loading && !data.data) return <Loading label="Varrendo os ativos acompanhados..." />;
  if (data.error) return <ErrorNotice error={data.error} onRetry={data.reload} />;
  if (!data.data) return null;
  const rowKey = (item: LabOpportunity) => `${item.symbol}-${item.agent}-${item.key}`;

  return (
    <div className="space-y-4">
      <Panel title="Ativos" className="overflow-x-auto">
        <table className="np-table min-w-[640px]">
          <thead>
            <tr>
              <th scope="col" className="text-left">Ativo</th>
              <th scope="col" className="text-left">Situação</th>
              <th scope="col" className="text-right">Séries líquidas</th>
              <th scope="col" className="text-right">Calls</th>
              <th scope="col" className="text-right">Puts</th>
              <th scope="col" className="text-left">Pregão · fonte</th>
            </tr>
          </thead>
          <tbody>
            {data.data.assets.map((asset) => (
              <tr key={asset.symbol}>
                <td className="font-black">{asset.symbol}</td>
                <td>
                  {STATUS_ASSET[asset.status] ?? asset.status}
                  {asset.reason && <span className="block text-xs text-accent">{asset.reason}</span>}
                </td>
                <td className="text-right">{asset.liquidity?.liquid_series ?? '—'}</td>
                <td className="text-right">{asset.liquidity?.calls ?? '—'}</td>
                <td className="text-right">{asset.liquidity?.puts ?? '—'}</td>
                <td className="text-xs text-ink-2">{asset.market_date ? `${formatDay(asset.market_date)} · ${asset.source}` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel title={`Estratégias descobertas: ${data.data.opportunities.length}`} className="overflow-x-auto">
        <p className="font-display text-xs text-ink-2 mb-2">
          Ordenadas pelo retorno teórico por real de risco, que é modelo e não previsão. Prêmios pelo fechamento do pregão.
        </p>
        {data.data.opportunities.length === 0 && <p>Nenhuma estrutura pôde ser montada com os dados disponíveis.</p>}
        {data.data.opportunities.length > 0 && (
          <table className="np-table min-w-[980px]">
            <thead>
              <tr>
                <th scope="col" className="text-left">Estrutura</th>
                <th scope="col" className="text-left">Agente</th>
                <th scope="col" className="text-right">Ganho máx.</th>
                <th scope="col" className="text-right">Perda máx.</th>
                <th scope="col" className="text-right">Potencial</th>
                <th scope="col" className="text-right">Teórico</th>
                <th scope="col" className="text-right">Prob.</th>
                <th scope="col" className="text-right">Liquidez</th>
                <th scope="col" className="text-right">Prazo</th>
                <th scope="col" className="text-left">Decisão</th>
                <th scope="col"><span className="sr-only">Ações</span></th>
              </tr>
            </thead>
            <tbody>
              {data.data.opportunities.map((item) => (
                <OpportunityRow
                  key={rowKey(item)}
                  item={item}
                  open={open === rowKey(item)}
                  onToggle={() => setOpen(open === rowKey(item) ? null : rowKey(item))}
                />
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

function OpportunityRow({ item, open, onToggle }: { key?: string; item: LabOpportunity; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr>
        <td>
          <span className="font-black">{item.symbol}</span> {item.name}
          <span className="block text-xs text-ink-2">Vencimento {formatDay(item.expiry)} · pregão {formatDay(item.market_date)}</span>
        </td>
        <td>{item.agent_name}</td>
        <td className="text-right">{formatLimit(item.max_profit)}</td>
        <td className="text-right">{formatCurrency(item.max_loss)}</td>
        <td className="text-right">{item.potential_return === null ? 'Sem limite' : formatRatio(item.potential_return, 0)}</td>
        <td className="text-right"><Signed value={item.theoretical_return}>{formatRatio(item.theoretical_return)}</Signed></td>
        <td className="text-right">{formatRatio(item.probability_of_profit, 0)}</td>
        <td className="text-right">{formatNumber(item.liquidity_score)}</td>
        <td className="text-right">{item.days_to_expiry} dias</td>
        <td>{item.decision.status}</td>
        <td className="text-right">
          <button onClick={onToggle} aria-expanded={open} className="np-btn !min-h-0 !px-2 !py-1">
            {open ? 'Fechar' : 'Abrir'}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={11}>
            <div className="np-spread-side">
              <div className="min-w-0">
                <h4 className="text-base mb-1">Opções utilizadas</h4>
                <ul className="text-sm">
                  {item.legs.map((leg) => (
                    <li key={`${leg.symbol}-${leg.action}`}>
                      {leg.action === 'BUY' ? 'Compra' : 'Venda'} {leg.quantity} {leg.symbol}, strike {formatNumber(leg.strike)}, prêmio {formatNumber(leg.premium)}
                      {' · '}bid {formatNumber(leg.bid)} / ask {formatNumber(leg.ask)} · volume {formatNumber(leg.volume, 0)}
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-ink-2 mt-2">
                  Breakeven: {item.breakevens.length ? item.breakevens.map((value) => formatCurrency(value)).join(' e ') : 'nenhum'}. Bid e ask são as ofertas finais do pregão.
                </p>
                {[...item.decision.reasons, ...item.decision.missing].length > 0 && (
                  <ul className="text-xs text-accent mt-2 list-disc pl-4">
                    {[...item.decision.reasons, ...item.decision.missing].map((text) => (
                      <li key={text}>{text}</li>
                    ))}
                  </ul>
                )}
              </div>
              <StartForm item={item} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function StartForm({ item }: { item: LabOpportunity }) {
  const [capital, setCapital] = useState('');
  const [period, setPeriod] = useState('5');
  const [custom, setCustom] = useState('');
  const [target, setTarget] = useState('');
  const [stop, setStop] = useState('');
  const [cost, setCost] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    setFailure(null);
    try {
      const result = await api.labStart({
        symbol: item.symbol,
        agent: item.agent,
        key: item.key,
        capital_brl: Number(capital),
        period_days: Number(period === 'custom' ? custom : period),
        target_pct: target ? Number(target) : null,
        stop_pct: stop ? Number(stop) : null,
        cost_brl: cost ? Number(cost) : null,
      });
      setMessage(
        result.created
          ? `Em acompanhamento desde o pregão de ${formatDay(result.entry_day)}, até ${formatDay(result.end_day)}.`
          : 'Esta estratégia já está em acompanhamento.',
      );
    } catch (error) {
      setFailure((error as ApiError).message);
    }
  };

  return (
    <form onSubmit={submit} className="min-w-0 space-y-2">
      <h4 className="text-base">Acompanhar sem operar</h4>
      <div className="flex flex-wrap gap-2 items-end">
        <label className="np-label">
          Capital hipotético (R$)
          <input type="number" min="0.01" step="0.01" required value={capital} onChange={(event) => setCapital(event.target.value)} className="np-input block mt-1 w-32" />
        </label>
        <label className="np-label">
          Período
          <select value={period} onChange={(event) => setPeriod(event.target.value)} className="np-input block mt-1">
            {PERIODS.map((days) => (
              <option key={days} value={days}>
                {days} {days === 1 ? 'dia' : 'dias'}
              </option>
            ))}
            <option value="custom">Personalizado</option>
          </select>
        </label>
        {period === 'custom' && (
          <label className="np-label">
            Dias
            <input type="number" min="1" max="365" required value={custom} onChange={(event) => setCustom(event.target.value)} className="np-input block mt-1 w-20" />
          </label>
        )}
        <label className="np-label">
          Alvo (% do risco)
          <input type="number" min="0.01" step="any" value={target} onChange={(event) => setTarget(event.target.value)} className="np-input block mt-1 w-24" />
        </label>
        <label className="np-label">
          Stop (% do risco)
          <input type="number" min="0.01" max="100" step="any" value={stop} onChange={(event) => setStop(event.target.value)} className="np-input block mt-1 w-24" />
        </label>
        <label className="np-label">
          Custos (R$)
          <input type="number" min="0" step="0.01" value={cost} onChange={(event) => setCost(event.target.value)} className="np-input block mt-1 w-24" />
        </label>
        <button type="submit" className="np-btn">Acompanhar</button>
      </div>
      {message && <p role="status" className="text-sm">{message}</p>}
      {failure && <p role="alert" className="text-sm text-accent">{failure}</p>}
    </form>
  );
}

function StrategyTable({ rows, onOpen }: { rows: LabStrategy[]; onOpen: (id: string) => void }) {
  return (
    <table className="np-table min-w-[900px]">
      <thead>
        <tr>
          <th scope="col" className="text-left">Estratégia</th>
          <th scope="col" className="text-left">Agente</th>
          <th scope="col" className="text-left">Entrada · fim</th>
          <th scope="col" className="text-left">Situação</th>
          <th scope="col" className="text-right">Resultado</th>
          <th scope="col" className="text-right">Sobre capital</th>
          <th scope="col" className="text-right">Sobre risco</th>
          <th scope="col"><span className="sr-only">Ações</span></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td><span className="font-black">{row.symbol}</span> {row.structure_name}</td>
            <td>{row.agent_name}</td>
            <td className="text-xs text-ink-2">{formatDay(row.entry_day)} · {formatDay(row.end_day)}</td>
            <td>{row.status === 'ATIVA' ? 'Ativa' : REASON[row.close_reason ?? ''] ?? 'Encerrada'}</td>
            <td className="text-right"><Signed value={row.pnl_brl}>{formatCurrency(row.pnl_brl)}</Signed></td>
            <td className="text-right"><Signed value={row.return_on_capital}>{formatRatio(row.return_on_capital)}</Signed></td>
            <td className="text-right"><Signed value={row.return_on_risk}>{formatRatio(row.return_on_risk)}</Signed></td>
            <td className="text-right">
              <button onClick={() => onOpen(row.id)} className="np-btn !min-h-0 !px-2 !py-1" aria-label={`Abrir ${row.symbol} ${row.structure_name}`}>Abrir</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Tracked({ onOpen }: { onOpen: (id: string) => void }) {
  const data = useResource('lab-forward', () => api.labStrategies('FORWARD'));
  const [note, setNote] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const update = async () => {
    setNote(null);
    setFailure(null);
    try {
      const result = await api.labMonitor();
      setNote(`Marcadas: ${result.marked}. Encerradas: ${result.closed}. Falhas: ${result.failed.length}. Fora do tempo: ${result.not_reached}.`);
      data.reload();
    } catch (error) {
      setFailure((error as ApiError).message);
    }
  };

  if (data.loading && !data.data) return <Loading label="Carregando..." />;
  if (data.error) return <ErrorNotice error={data.error} onRetry={data.reload} />;
  const rows = data.data?.strategies ?? [];
  const winners = rows.filter((row) => (row.pnl_brl ?? 0) > 0).length;
  const losers = rows.filter((row) => (row.pnl_brl ?? 0) < 0).length;
  return (
    <Panel title="Estratégias em acompanhamento: retorno observado, sem execução" className="overflow-x-auto">
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <button onClick={update} className="np-btn">Atualizar com a grade mais recente</button>
        <p className="font-display text-xs text-ink-2">
          A grade é diária: há nova marcação a cada pregão. {rows.length > 0 && `Ganhando: ${winners}. Perdendo: ${losers}.`}
        </p>
      </div>
      {note && <p role="status" className="text-sm mb-2">{note}</p>}
      {failure && <p role="alert" className="text-sm text-accent mb-2">{failure}</p>}
      {rows.length === 0 ? <p>Nenhuma estratégia em acompanhamento. Abra uma oportunidade para começar.</p> : <StrategyTable rows={rows} onOpen={onOpen} />}
    </Panel>
  );
}

function Backtests({ onOpen }: { onOpen: (id: string) => void }) {
  const data = useResource('lab-backtest', () => api.labStrategies('BACKTEST'));
  const [symbol, setSymbol] = useState('PETR4');
  const [capital, setCapital] = useState('');
  const [period, setPeriod] = useState('5');
  const [weeks, setWeeks] = useState('8');
  const [running, setRunning] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const run = async (event: FormEvent) => {
    event.preventDefault();
    setRunning(true);
    setNote(null);
    setFailure(null);
    try {
      const result = await api.labBacktest({ symbol, capital_brl: Number(capital), period_days: Number(period), weeks: Number(weeks) });
      setNote(
        `Entradas: ${result.entries}. Novas estratégias: ${result.created}. ${
          result.complete ? 'Concluído.' : 'Parcial: rode de novo para continuar de onde parou.'
        }${result.skipped[0] ? ` Motivo: ${result.skipped[0].reason}.` : ''}`,
      );
      data.reload();
    } catch (error) {
      setFailure((error as ApiError).message);
    } finally {
      setRunning(false);
    }
  };

  const rows = data.data?.strategies ?? [];
  return (
    <div className="space-y-4">
      <form onSubmit={run} className="np-section flex flex-wrap items-end gap-3">
        <div className="basis-full md:basis-auto md:max-w-sm">
          <h3 className="text-xl">Rodar backtest</h3>
          <p className="font-display text-xs text-ink-2 mt-1">
            Cada proposta usa só a grade do dia da entrada. Entrada e saída são presumidas no fechamento, sem provar que a execução seria possível.
          </p>
        </div>
        <label className="np-label">
          Ativo
          <input value={symbol} maxLength={12} required onChange={(event) => setSymbol(event.target.value.toUpperCase())} className="np-input block mt-1 w-28" />
        </label>
        <label className="np-label">
          Capital hipotético (R$)
          <input type="number" min="0.01" step="0.01" required value={capital} onChange={(event) => setCapital(event.target.value)} className="np-input block mt-1 w-32" />
        </label>
        <label className="np-label">
          Período
          <select value={period} onChange={(event) => setPeriod(event.target.value)} className="np-input block mt-1">
            {PERIODS.map((days) => (
              <option key={days} value={days}>{days} pregões</option>
            ))}
          </select>
        </label>
        <label className="np-label">
          Semanas
          <input type="number" min="1" max="52" required value={weeks} onChange={(event) => setWeeks(event.target.value)} className="np-input block mt-1 w-20" />
        </label>
        <button type="submit" disabled={running} className="np-btn">{running ? 'Rodando...' : 'Rodar'}</button>
        {note && <p role="status" className="basis-full text-sm">{note}</p>}
        {failure && <p role="alert" className="basis-full text-sm text-accent">{failure}</p>}
      </form>
      {data.error && <ErrorNotice error={data.error} onRetry={data.reload} />}
      <Panel title={`Resultados simulados: ${rows.length}`} className="overflow-x-auto">
        {rows.length === 0 ? <p>Nenhum backtest ainda.</p> : <StrategyTable rows={rows} onOpen={onOpen} />}
      </Panel>
    </div>
  );
}

function RankingTable({ title, rows, name }: { title: string; rows: LabRankingRow[]; name: (row: LabRankingRow) => string }) {
  return (
    <Panel title={title} className="overflow-x-auto">
      {rows.length === 0 ? (
        <p>Nenhum resultado encerrado ainda.</p>
      ) : (
        <table className="np-table min-w-[1100px]">
          <thead>
            <tr>
              <th scope="col" className="text-left">Posição</th>
              <th scope="col" className="text-left">Nome</th>
              <th scope="col" className="text-left">Leitura</th>
              <th scope="col" className="text-right">Estratégias</th>
              <th scope="col" className="text-right">Datas</th>
              <th scope="col" className="text-right">Mediana no livro</th>
              <th scope="col" className="text-right">Acerto no livro</th>
              <th scope="col" className="text-right">Mediana no fechamento</th>
              <th scope="col" className="text-right">Acerto no fechamento</th>
              <th scope="col" className="text-right">Média</th>
              <th scope="col" className="text-right">Desvio</th>
              <th scope="col" className="text-right">Melhor</th>
              <th scope="col" className="text-right">Pior</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={name(row)}>
                <td>{row.position ?? <span className="text-xs text-ink-2">Amostra pequena</span>}</td>
                <td className="font-semibold">{name(row)}</td>
                <td>{READING[row.reading]}</td>
                <td className="text-right">{row.count}</td>
                <td className="text-right">{row.entry_dates}</td>
                <td className="text-right font-semibold"><Signed value={row.book_median_return}>{formatRatio(row.book_median_return)}</Signed></td>
                <td className="text-right">{formatRatio(row.book_hit_rate, 0)}</td>
                <td className="text-right"><Signed value={row.median_return}>{formatRatio(row.median_return)}</Signed></td>
                <td className="text-right">{formatRatio(row.hit_rate, 0)}</td>
                <td className="text-right"><Signed value={row.mean_return}>{formatRatio(row.mean_return)}</Signed></td>
                <td className="text-right">{formatRatio(row.std_return)}</td>
                <td className="text-right">{formatRatio(row.best_return)}</td>
                <td className="text-right">{formatRatio(row.worst_return)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

function Rankings() {
  const [mode, setMode] = useState<'BACKTEST' | 'FORWARD'>('BACKTEST');
  const data = useResource(`lab-ranking-${mode}`, () => api.labRanking(mode));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button aria-current={mode === 'BACKTEST'} onClick={() => setMode('BACKTEST')} className="np-btn">Simulado (backtest)</button>
        <button aria-current={mode === 'FORWARD'} onClick={() => setMode('FORWARD')} className="np-btn">Observado (acompanhamento)</button>
      </div>
      <p className="font-display text-xs text-ink-2">
        Retorno sobre o risco máximo, em dois limites: fechamento, que tende a ser otimista, e livro final, comprando no ask e vendendo no bid, que tende a ser pessimista porque é sobra de ofertas. A ordem usa a mediana no livro, não a média, para uma operação excepcional não decidir. Com menos de 20 datas de entrada, não há posição, porque estratégias da mesma data se movem juntas. Simulado e observado nunca se misturam.
      </p>
      {data.loading && !data.data && <Loading label="Calculando..." />}
      {data.error && <ErrorNotice error={data.error} onRetry={data.reload} />}
      {data.data && (
        <>
          <RankingTable title={`Agentes: ${data.data.label.toLowerCase()}`} rows={data.data.agents} name={(row) => row.agent_name ?? row.agent ?? ''} />
          <RankingTable title={`Estruturas: ${data.data.label.toLowerCase()}`} rows={data.data.structures} name={(row) => row.structure_name ?? ''} />
        </>
      )}
    </div>
  );
}

function StrategyDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const data = useResource(`lab-${id}`, () => api.labStrategy(id));
  if (data.loading && !data.data) return <Loading label="Carregando..." />;
  if (data.error) return <ErrorNotice error={data.error} onRetry={data.reload} />;
  const item = data.data;
  if (!item) return null;
  const measuredName = item.returns.measured_label === 'SIMULADO' ? 'Retorno simulado' : 'Retorno observado';
  const curve = (item.marks ?? []).filter((mark) => mark.complete);

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="np-btn">Voltar</button>
      <header>
        <h3 className="text-3xl">{item.symbol}: {item.structure_name}</h3>
        <p className="np-note">
          {item.agent_name} · entrada no pregão de {formatDay(item.entry_day)} · até {formatDay(item.end_day)} · vencimento {formatDay(item.expiry)} · fonte {item.source}
        </p>
      </header>
      <div className="np-section">
        <p className="np-label !text-accent mb-2">Resultado hipotético: nenhuma operação foi executada</p>
        <table className="np-table">
          <tbody>
            <ReturnRow name="Retorno potencial" hint="Máximo que a estrutura permite no vencimento" value={item.returns.potential} />
            <ReturnRow name="Retorno teórico" hint="Valor esperado pelo modelo, com a vol da entrada" value={item.returns.theoretical} />
            <ReturnRow name={measuredName} hint={item.returns.measured_label === 'SIMULADO' ? 'Preços históricos reais, com execução presumida no fechamento' : 'Preços reais posteriores à entrada, sem execução'} value={item.returns.measured} strong />
            <ReturnRow
              name="Limite conservador, sobre o risco"
              hint="Compra no ask e venda no bid das ofertas finais. Sem oferta dos dois lados, não há valor"
              value={item.return_on_risk_book}
            />
          </tbody>
        </table>
      </div>
      <div className="np-section overflow-x-auto">
        <table className="np-table min-w-[640px]">
          <tbody>
            <FactRow name="Capital hipotético" value={formatCurrency(item.capital_brl)} other="Lotes" otherValue={String(item.lots)} />
            <FactRow name="Capital empregado" value={formatCurrency(item.employed_brl)} other="Risco máximo" otherValue={formatCurrency(item.max_risk_brl)} />
            <FactRow name="Resultado" value={formatCurrency(item.pnl_brl)} other="Sobre o risco" otherValue={formatRatio(item.return_on_risk)} />
            <FactRow name="Sobre o capital empregado" value={formatRatio(item.return_on_employed)} other="Drawdown" otherValue={formatCurrency(item.max_drawdown_brl)} />
            <FactRow name="Maior ganho" value={formatCurrency(item.best_brl)} other="Maior perda" otherValue={formatCurrency(item.worst_brl)} />
            <FactRow name="Custos" value={item.cost_informed ? formatCurrency(item.cost_brl) : 'Não informados: resultado sem custos'} other="Dias até o alvo" otherValue={item.days_to_target === null ? '—' : String(item.days_to_target)} />
            <FactRow name="Alvo" value={item.target_pct === null ? 'Sem alvo' : `${formatNumber(item.target_pct)}% do risco`} other="Stop" otherValue={item.stop_pct === null ? 'Sem stop' : `${formatNumber(item.stop_pct)}% do risco`} />
            <FactRow name="Situação" value={item.status === 'ATIVA' ? 'Ativa' : REASON[item.close_reason ?? ''] ?? 'Encerrada'} other="Regime na entrada" otherValue={item.regime ?? '—'} />
          </tbody>
        </table>
      </div>
      <Panel title="Evolução (R$)">
        {curve.length === 0 ? (
          <p>Ainda não há marcação completa. Sem preço de todas as pernas no pregão, nenhum resultado é calculado.</p>
        ) : (
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={curve} margin={{ top: 12, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#d9d4c8" vertical={false} />
                <XAxis dataKey="day" stroke={SECONDARY} fontSize={12} tickLine={false} axisLine={false} tickFormatter={(day: string) => formatDay(day).slice(0, 5)} />
                <YAxis stroke={SECONDARY} fontSize={12} tickLine={false} axisLine={false} width={64} />
                <ReferenceLine y={0} stroke={SECONDARY} />
                <Tooltip
                  contentStyle={{ backgroundColor: PAPER, border: `1px solid ${INK}`, borderRadius: 0 }}
                  labelStyle={{ color: SECONDARY }}
                  itemStyle={{ color: INK }}
                  labelFormatter={(day) => formatDay(String(day))}
                  formatter={(value) => [formatCurrency(Number(value)), 'Resultado']}
                />
                <Line type="linear" dataKey="pnl_brl" stroke={INK} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>
      <Panel title="Pernas e preços usados" className="overflow-x-auto">
        <table className="np-table min-w-[560px]">
          <thead>
            <tr>
              <th scope="col" className="text-left">Lado</th>
              <th scope="col" className="text-left">Série</th>
              <th scope="col" className="text-right">Strike</th>
              <th scope="col" className="text-right">Qtd.</th>
              <th scope="col" className="text-right">Prêmio de entrada</th>
            </tr>
          </thead>
          <tbody>
            {item.legs.map((leg) => (
              <tr key={`${leg.symbol}-${leg.action}`}>
                <td>{leg.action === 'BUY' ? 'Compra' : 'Venda'}</td>
                <td>{leg.symbol}</td>
                <td className="text-right">{formatNumber(leg.strike)}</td>
                <td className="text-right">{leg.quantity}</td>
                <td className="text-right">{formatNumber(leg.premium)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {(item.marks ?? []).length > 0 && (
          <table className="np-table min-w-[560px] mt-4">
            <thead>
              <tr>
                <th scope="col" className="text-left">Pregão</th>
                <th scope="col" className="text-right">Ativo</th>
                <th scope="col" className="text-right">Resultado</th>
                <th scope="col" className="text-left">Qualidade</th>
              </tr>
            </thead>
            <tbody>
              {(item.marks ?? []).map((mark) => (
                <tr key={mark.day}>
                  <td>{formatDay(mark.day)}</td>
                  <td className="text-right">{formatNumber(mark.spot)}</td>
                  <td className="text-right"><Signed value={mark.pnl_brl}>{formatCurrency(mark.pnl_brl)}</Signed></td>
                  <td>{mark.settlement ? 'Liquidação pelo ativo' : mark.complete ? 'Completa' : 'Incompleta: perna sem negócio'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

function ReturnRow({ name, hint, value, strong }: { name: string; hint: string; value: number | null; strong?: boolean }) {
  return (
    <tr>
      <th scope="row" className="text-left !normal-case !tracking-normal !text-ink !text-sm">
        {name}
        <span className="block text-xs font-normal text-ink-2">{hint}</span>
      </th>
      <td className={strong ? 'text-right font-black text-xl' : 'text-right'}>
        {value === null ? 'Sem dado' : <Signed value={value}>{formatRatio(value)}</Signed>}
      </td>
    </tr>
  );
}

function FactRow({ name, value, other, otherValue }: { name: string; value: string; other: string; otherValue: string }) {
  return (
    <tr>
      <td className="text-ink-2">{name}</td>
      <td className="font-semibold">{value}</td>
      <td className="text-ink-2">{other}</td>
      <td className="font-semibold">{otherValue}</td>
    </tr>
  );
}
