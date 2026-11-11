/** Laboratório na tela. Respostas da API são fixtures, só deste teste. */
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Lab } from './components/Lab';

const opportunity = {
  agent: 'regra_5pct', agent_name: 'Regra de 5% do ativo', key: 'bull_call_spread', name: 'Trava de alta com call', symbol: 'PETR4',
  expiry: '2026-12-18', market_date: '2026-10-30', days_to_expiry: 45,
  legs: [{ symbol: 'TESTC', action: 'BUY', kind: 'CALL', strike: 50, expiry: '2026-12-18', quantity: 100, premium: 2, bid: null, ask: null, volume: 1000, open_interest: 10, iv: 0.3, style: 'AMERICAN' }],
  net_premium: 100, max_profit: 150, max_loss: 100, breakevens: [51], risk_reward: 1.5, probability_of_profit: 0.4, potential_return: 1.5,
  theoretical_return: -0.02, liquidity_score: 0.9,
  decision: { status: 'INCOMPLETA', reasons: [], missing: ['margem da corretora não disponível para perna vendida'], capital_required: null, max_risk: 100, max_risk_pct: null, limit_brl: null, risk_reward: 1.5 },
};
const strategy = (extra = {}) => ({
  id: 'abc', mode: 'BACKTEST', agent: 'regra_5pct', agent_name: 'Regra de 5% do ativo', symbol: 'PETR4', structure_key: 'x', structure_name: 'Trava de alta com call',
  expiry: '2026-12-18', entry_day: '2026-10-07', end_day: '2026-10-14', capital_brl: 1000, lots: 10, unit_debit: 100, max_profit: 150, max_loss: 100, probability: 0.4,
  theoretical_pnl: -2, regime: 'BULL', target_pct: null, stop_pct: null, cost_brl: 0, cost_informed: 0, status: 'ENCERRADA', close_reason: 'FIM_DO_PERIODO', closed_day: '2026-10-14',
  source: 'brapi', created_at: '', legs: opportunity.legs, breakevens: [51], employed_brl: 1000, max_risk_brl: 1000, horizon_days: 7,
  returns: { potential: 1.5, theoretical: -0.02, measured_label: 'SIMULADO', measured: 0.35 },
  pnl_brl: 350, return_on_capital: 0.35, return_on_employed: 0.35, return_on_risk: 0.35, pnl_book_brl: -200, return_on_risk_book: -0.2, best_brl: 400, worst_brl: -100, max_drawdown_brl: 500, exit_reason: 'FIM_DO_PERIODO', marks_used: 2, days_to_target: null,
  ...extra,
});
const rankRow = (name: string, position: number | null) => ({
  agent: name, agent_name: name, count: position ? 25 : 3, hit_rate: 0.6, mean_return: 0.2, median_return: 0.1, std_return: 0.3, best_return: 2, worst_return: -1, mean_risk_brl: 100, book_count: 5, book_hit_rate: 0.1, book_median_return: -0.3, reading: 'LUCRO_SO_NO_FECHAMENTO', entry_dates: 25, sufficient_sample: Boolean(position), position, by_symbol: {}, by_horizon: {}, by_regime: {},
});

let routes: Record<string, { status?: number; body: unknown }>;
const calls: { path: string; method: string; body?: string }[] = [];

beforeEach(() => {
  calls.length = 0;
  routes = {
    'GET /api/lab/opportunities': { body: { generated_at: '', opportunities: [opportunity], assets: [
      { symbol: 'PETR4', status: 'ANALISADO', reason: null, liquidity: { usable_series: 100, liquid_series: 50, calls: 25, puts: 25, sufficient: true }, market_date: '2026-10-30', expiry: '2026-12-18', source: 'brapi' },
      { symbol: 'VALE3', status: 'DADOS_INSUFICIENTES', reason: 'brapi recusou o acesso', liquidity: null },
      { symbol: 'MGLU3', status: 'SEM_LIQUIDEZ', reason: 'menos de 4 séries líquidas', liquidity: { usable_series: 2, liquid_series: 1, calls: 1, puts: 0, sufficient: false }, market_date: '2026-10-30', expiry: '2026-12-18', source: 'brapi' },
    ] } },
    'GET /api/lab/strategies': { body: { strategies: [] } },
    'GET /api/lab/ranking': { body: { mode: 'BACKTEST', label: 'SIMULADO', closed: 28, agents: [rankRow('Delta moderado', 1), rankRow('Poucos dados', null)], structures: [] } },
  };
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    const path = String(url).split('?')[0];
    calls.push({ path, method, body: init?.body as string });
    const route = routes[`${method} ${path}`] ?? { status: 404, body: { detail: 'não encontrado' } };
    return new Response(JSON.stringify(route.body), { status: route.status ?? 200 });
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('oportunidades', () => {
  it('separa ativos analisados, sem liquidez e sem dados', async () => {
    render(<Lab />);
    expect(await screen.findByText('Analisado')).toBeTruthy();
    expect(screen.getByText('Sem liquidez')).toBeTruthy();
    expect(screen.getByText('Dados insuficientes')).toBeTruthy();
    expect(screen.getByText('brapi recusou o acesso')).toBeTruthy();
  });

  it('abre a estratégia com pernas, breakeven e o que falta para decidir', async () => {
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Abrir' }));
    expect(screen.getByText(/TESTC, strike 50,00/)).toBeTruthy();
    expect(screen.getByText(/Pontos de equilíbrio:/)).toBeTruthy();
    expect(screen.getByText('margem da corretora não disponível para perna vendida')).toBeTruthy();
  });

  it('inicia o acompanhamento sem enviar preços', async () => {
    routes['POST /api/lab/strategies'] = { body: { id: 'x', created: true, entry_day: '2026-10-30', end_day: '2026-11-08' } };
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Abrir' }));
    await userEvent.type(screen.getByLabelText('Capital hipotético (R$)'), '1000');
    await userEvent.selectOptions(screen.getByLabelText('Período'), '10');
    await userEvent.type(screen.getByLabelText('Alvo (% do risco)'), '50');
    await userEvent.click(screen.getByRole('button', { name: 'Acompanhar' }));
    expect(await screen.findByText(/Em acompanhamento desde o pregão de 30\/10\/2026/)).toBeTruthy();
    const body = JSON.parse(calls.find((call) => call.method === 'POST')!.body!);
    expect(body).toMatchObject({ symbol: 'PETR4', agent: 'regra_5pct', capital_brl: 1000, period_days: 10, target_pct: 50, stop_pct: null, cost_brl: null });
    expect(JSON.stringify(body)).not.toContain('premium');
  });

  it('aceita período personalizado', async () => {
    routes['POST /api/lab/strategies'] = { body: { id: 'x', created: false, entry_day: '2026-10-30', end_day: '2026-11-08' } };
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Abrir' }));
    await userEvent.type(screen.getByLabelText('Capital hipotético (R$)'), '1000');
    await userEvent.selectOptions(screen.getByLabelText('Período'), 'custom');
    await userEvent.type(screen.getByLabelText('Dias'), '21');
    await userEvent.click(screen.getByRole('button', { name: 'Acompanhar' }));
    expect(await screen.findByText('Esta estratégia já está em acompanhamento.')).toBeTruthy();
    expect(JSON.parse(calls.find((call) => call.method === 'POST')!.body!).period_days).toBe(21);
  });

  it('mostra a recusa quando a grade está defasada', async () => {
    routes['POST /api/lab/strategies'] = { status: 422, body: { label: 'DADOS INSUFICIENTES', detail: 'grade defasada: o ativo já se moveu -5,0%', reasons: [] } };
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Abrir' }));
    await userEvent.type(screen.getByLabelText('Capital hipotético (R$)'), '1000');
    await userEvent.click(screen.getByRole('button', { name: 'Acompanhar' }));
    expect(await screen.findByText(/grade defasada/)).toBeTruthy();
  });

  it('não oferece nenhum envio de ordem', async () => {
    render(<Lab />);
    await screen.findByText('Analisado');
    expect(screen.queryByRole('button', { name: /ordem|executar|comprar|vender/i })).toBeNull();
  });
});

describe('resultados', () => {
  it('separa potencial, teórico e simulado e avisa que é hipotético', async () => {
    routes['GET /api/lab/strategies'] = { body: { strategies: [strategy()] } };
    routes['GET /api/lab/strategies/abc'] = { body: { ...strategy(), marks: [
      { day: '2026-10-08', pnl_brl: 100, spot: 50, prices: {}, complete: true, settlement: false, source: 'brapi', fetched_at: '' },
      { day: '2026-10-09', pnl_brl: null, spot: 50, prices: {}, complete: false, settlement: false, source: 'brapi', fetched_at: '' },
    ] } };
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Simulação histórica' }));
    await userEvent.click(await screen.findByRole('button', { name: /Abrir PETR4/ }));
    expect(await screen.findByText('Retorno potencial')).toBeTruthy();
    expect(screen.getByText('Retorno teórico')).toBeTruthy();
    expect(screen.getByText('Retorno simulado')).toBeTruthy();
    expect(screen.getByText('Limite conservador, sobre o risco')).toBeTruthy();
    expect(screen.queryByText('Retorno observado')).toBeNull();
    expect(screen.getByText(/nenhuma operação foi executada/)).toBeTruthy();
    expect(screen.getByText('Não informados: resultado sem custos')).toBeTruthy();
    expect(screen.getByText('Incompleta: perna sem negócio')).toBeTruthy();
  });

  it('acompanhamento usa o rótulo observado, e sem marcação não há resultado', async () => {
    const forward = strategy({ mode: 'FORWARD', status: 'ATIVA', close_reason: null, pnl_brl: null, return_on_capital: null, return_on_risk: null, returns: { potential: 1.5, theoretical: -0.02, measured_label: 'OBSERVADO', measured: null } });
    routes['GET /api/lab/strategies'] = { body: { strategies: [forward] } };
    routes['GET /api/lab/strategies/abc'] = { body: { ...forward, marks: [] } };
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Em acompanhamento' }));
    await userEvent.click(await screen.findByRole('button', { name: /Abrir PETR4/ }));
    expect(await screen.findByText('Retorno observado')).toBeTruthy();
    expect(screen.getByText('Sem dado')).toBeTruthy();
    expect(screen.getByText(/Ainda não há marcação completa/)).toBeTruthy();
  });

  it('atualiza o acompanhamento e informa o resultado', async () => {
    routes['POST /api/lab/monitor'] = { body: { active: 2, marked: 1, closed: 0, failed: [{ id: 'x', reason: 'limite' }], not_reached: 0 } };
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Em acompanhamento' }));
    await userEvent.click(await screen.findByRole('button', { name: /Atualizar com a grade/ }));
    expect(await screen.findByText(/Marcadas: 1\. Encerradas: 0\. Falhas: 1/)).toBeTruthy();
  });

  it('roda backtest e avisa quando fica parcial', async () => {
    routes['POST /api/lab/backtests'] = { body: { entries: 2, created: 10, closed: 5, skipped: [{ entry: '2026-01-01', reason: 'limite de requisições' }], complete: false, symbol: 'PETR4' } };
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Simulação histórica' }));
    await userEvent.type(await screen.findByLabelText('Capital hipotético (R$)'), '1000');
    await userEvent.click(screen.getByRole('button', { name: 'Rodar' }));
    expect(await screen.findByText(/Parcial: rode de novo.*limite de requisições/)).toBeTruthy();
  });
});

describe('rankings', () => {
  it('não dá posição a amostra pequena e explica o critério', async () => {
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Rankings' }));
    const table = (await screen.findByText('Delta moderado')).closest('table')!;
    expect(within(table).getByText('Amostra pequena')).toBeTruthy();
    expect(screen.getByText(/usa a mediana no livro, não a média/)).toBeTruthy();
    expect(within(table).getAllByText('Lucro só no fechamento').length).toBeGreaterThan(0);
  });

  it('troca entre simulado e observado sem misturar', async () => {
    render(<Lab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Rankings' }));
    await screen.findByText('Delta moderado');
    routes['GET /api/lab/ranking'] = { body: { mode: 'FORWARD', label: 'OBSERVADO', closed: 0, agents: [], structures: [] } };
    await userEvent.click(screen.getByRole('button', { name: /Observado/ }));
    await waitFor(() => expect(screen.getByText('Agentes: observado')).toBeTruthy());
    expect(screen.queryByText('Delta moderado')).toBeNull();
  });
});
