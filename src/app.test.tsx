/** Fluxos principais das telas. Respostas da API são fixtures, só deste teste. */
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';

vi.mock('./components/PriceChart', () => ({ PriceChart: () => <div>grafico</div>, HvChart: () => null }));

const row = (symbol: string, extra = {}) => ({
  symbol, name: null, price: 50.5, change_percent: -1.2, market_time: '2026-11-03T15:00:00+00:00', historical_volatility: 0.3,
  atm_iv: 0.35, iv_ratio: 1.1, regime: 'SIDEWAYS', expiry: '2026-12-18', market_date: '2026-10-30', spot_drift: 0, iv_rank: 57,
  iv_percentile: 70, iv_samples: 49, iv_samples_needed: 26, structure_trend: 'UP', events: [], source: 'brapi', data_status: 'REAL',
  missing: [], history_warnings: [], signals: [], ...extra,
});
const decision = (status: string, extra = {}) => ({
  status, reasons: [], missing: [], capital_required: 100, max_risk: 100, max_risk_pct: 1, limit_brl: 500, risk_reward: null, ...extra,
});
const candidate = (key: string, name: string, dec: object) => ({
  key, name, rationale: 'Texto.', assumptions: [], fits_regime: false, net_premium: 100, max_profit: null, max_loss: 100, breakevens: [51],
  risk_reward: null, probability_of_profit: 0.4, greeks: null,
  legs: [{ symbol: 'TESTC', action: 'BUY', kind: 'CALL', strike: 50, quantity: 100, premium: 1, price_basis: 'CLOSE', iv: 0.3, delta: 0.5, style: 'AMERICAN', probability_itm: 0.5 }],
  risk: { is_approved: true, liquidity_score: 0.9, stress: { 'Ativo -5% no vencimento': -100 }, warnings: ['Aviso de teste.'], verdict: '', rejection_reason: null },
  payoff: [{ price: 40, pnl: -100 }, { price: 60, pnl: 900 }], heatmap: null, decision: dec,
});
const strategies = {
  symbol: 'PETR4', expiry: '2026-12-18', market_date: '2026-10-30', spot: 50, live_price: 50, spot_drift: 0, risk_free_rate: 0.1375,
  time_to_expiry_years: 0.1, atm_iv: 0.3, historical_volatility: 0.3, iv_ratio: 1, regime: 'SIDEWAYS', profile: null, capital_configured: false,
  iv_rank: null, iv_percentile: null, iv_samples: 6, iv_samples_needed: 26, structure: null, events: [], events_error: 'limite atingido',
  quality: { is_valid: true, issues: [] },
  candidates: [
    candidate('long_call', 'Compra de call', decision('APROVADA')),
    candidate('iron_condor', 'Iron condor', decision('INCOMPLETA', { capital_required: null, missing: ['margem da corretora não disponível para perna vendida'] })),
    candidate('long_put', 'Compra de put', decision('REPROVADA', { reasons: ['perda máxima acima do limite'] })),
  ],
  unavailable: [],
};

type Route = { status?: number; body: unknown };
let routes: Record<string, Route>;
const calls: { path: string; method: string; body?: string }[] = [];

beforeEach(() => {
  calls.length = 0;
  routes = {
    'GET /api/session': { body: { authenticated: true, login_ready: true } },
    'GET /api/scanner': { body: { generated_at: '2026-11-03T15:00:00+00:00', complete: true, incomplete_symbols: [], timed_out_symbols: [], rows: [row('PETR4')] } },
    'GET /api/assets/PETR4': {
      body: {
        quote: { symbol: 'PETR4', name: 'Teste', price: 50.5, change_percent: -1.2, volume: 1, provenance: { source: 'brapi', kind: 'DELAYED', collected_at: '2026-11-03T15:00:00+00:00', market_time: '2026-11-03T15:00:00+00:00' } },
        quote_quality: { is_valid: true, issues: [] }, data_status: 'ATRASADO', history_quality: { is_valid: true, issues: [] },
        historical_volatility: 0.3, ewma_volatility: 0.3, regime: 'SIDEWAYS', structure: null,
        history: [{ day: '2026-11-03', open: 1, high: 1, low: 1, close: 1, hv_20d: null, bb_upper: null, bb_middle: null, bb_lower: null }],
      },
    },
    'GET /api/assets/PETR4/expirations': { body: { expirations: ['2026-12-18'] } },
    'GET /api/assets/PETR4/strategies': { body: strategies },
    'GET /api/assets/PETR4/chain': { body: { symbol: 'PETR4', expiry: '2026-12-18', market_date: '2026-10-30', spot: 50, risk_free_rate: 0.1, provenance: {}, quality: { is_valid: true, issues: [] }, open_interest: { calls: 100, puts: 200, put_call_ratio: 2, calls_change: 5, puts_change: null }, quotes: [] } },
    'GET /api/settings/risk': { body: { capital_brl: null, max_loss_pct: null, updated_at: null } },
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

describe('login', () => {
  it('mostra a senha sem sessão e entra ao acertar', async () => {
    routes['GET /api/session'] = { body: { authenticated: false, login_ready: true } };
    routes['POST /api/login'] = { body: { authenticated: true } };
    render(<App />);
    const field = await screen.findByLabelText('Senha');
    expect(screen.queryByText('Monitor de Mercado')).toBeNull();
    await userEvent.type(field, 'senha-de-teste');
    routes['GET /api/session'] = { body: { authenticated: true, login_ready: true } };
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByText('Monitor de Mercado')).toBeTruthy();
  });

  it('mostra o erro e limpa o campo ao errar', async () => {
    routes['GET /api/session'] = { body: { authenticated: false, login_ready: true } };
    routes['POST /api/login'] = { status: 401, body: { detail: 'Senha incorreta' } };
    render(<App />);
    const field = await screen.findByLabelText('Senha');
    await userEvent.type(field, 'errada');
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByText('Senha incorreta')).toBeTruthy();
    expect((field as HTMLInputElement).value).toBe('');
  });

  it('avisa quando o login não está configurado', async () => {
    routes['GET /api/session'] = { body: { authenticated: false, login_ready: false } };
    render(<App />);
    expect(await screen.findByText('O login ainda não foi configurado no servidor.')).toBeTruthy();
    expect((screen.getByLabelText('Senha') as HTMLInputElement).disabled).toBe(true);
  });

  it('volta para a senha quando a sessão vence', async () => {
    routes['GET /api/scanner'] = { status: 401, body: { detail: 'Sessão ausente ou vencida' } };
    render(<App />);
    expect(await screen.findByLabelText('Senha')).toBeTruthy();
  });
});

describe('origem dos dados', () => {
  it('identifica estado, fonte e horário da cotação', async () => {
    render(<App />);
    expect(await screen.findByText('Atrasado')).toBeTruthy();
    expect(screen.getByText('Fonte: brapi')).toBeTruthy();
    expect(screen.getByText(/^Mercado:/)).toBeTruthy();
  });

  it('nunca mostra preço quando a fonte falha', async () => {
    routes['GET /api/scanner'] = {
      body: { generated_at: '2026-11-03T15:00:00+00:00', complete: false, incomplete_symbols: ['VALE3'], timed_out_symbols: [], rows: [row('VALE3', { price: null, change_percent: null, market_time: null, source: null, data_status: 'INDISPONIVEL', atm_iv: null, iv_rank: null, missing: ['Cotação: brapi recusou o acesso'] })] },
    };
    routes['GET /api/assets/VALE3'] = { status: 422, body: { label: 'DADOS INSUFICIENTES', detail: 'brapi recusou o acesso', reasons: [] } };
    render(<App />);
    expect((await screen.findAllByText('DADOS INSUFICIENTES')).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: 'Scanner B3' }));
    const table = screen.getByRole('table');
    expect(within(table).getByText('Indisponível')).toBeTruthy();
    expect(screen.getByText(/Varredura incompleta/)).toBeTruthy();
    expect(within(table).queryByText(/R\$\s*\d/)).toBeNull();
  });
});

describe('estratégias', () => {
  const open = async () => {
    render(<App />);
    await userEvent.click(await screen.findByRole('button', { name: 'Estratégias' }));
    await screen.findByText('Estruturas: 1 de 3 aprovadas');
  };

  it('distingue aprovada, incompleta e reprovada', async () => {
    await open();
    const list = screen.getByText('Estruturas: 1 de 3 aprovadas').parentElement!;
    expect(within(list).getByText('Reprovada')).toBeTruthy();
    expect(within(list).getByText('Incompleta')).toBeTruthy();
    expect(within(list).getByText('Aprovada')).toBeTruthy();
  });

  it('explica a margem que falta e não mostra capital inventado', async () => {
    await open();
    await userEvent.click(screen.getByRole('button', { name: /Iron condor/ }));
    expect(screen.getByText('margem da corretora não disponível para perna vendida')).toBeTruthy();
    expect(screen.getByText('Margem desconhecida')).toBeTruthy();
  });

  it('mostra o motivo da reprovação e o estilo da perna', async () => {
    await open();
    await userEvent.click(screen.getByRole('button', { name: /Compra de put/ }));
    expect(screen.getByText('perda máxima acima do limite')).toBeTruthy();
    expect(screen.getByText('Americana')).toBeTruthy();
  });

  it('declara falha no calendário em vez de dizer que não há eventos', async () => {
    await open();
    expect(screen.getByText('DADOS INSUFICIENTES: limite atingido')).toBeTruthy();
    expect(screen.queryByText(/Nenhum informado pela fonte/)).toBeNull();
  });

  it('salva capital e limite e recalcula', async () => {
    routes['PUT /api/settings/risk'] = { body: { capital_brl: 10000, max_loss_pct: 5, updated_at: '2026-11-03T15:00:00+00:00' } };
    await open();
    const before = calls.filter((call) => call.path.endsWith('/strategies')).length;
    await userEvent.type(screen.getByLabelText('Capital (R$)'), '10000');
    await userEvent.type(screen.getByLabelText('Perda máxima por estrutura (%)'), '5');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(await screen.findByText('Capital e limite salvos.')).toBeTruthy();
    const put = calls.find((call) => call.method === 'PUT')!;
    expect(JSON.parse(put.body!)).toEqual({ capital_brl: 10000, max_loss_pct: 5 });
    await waitFor(() => expect(calls.filter((call) => call.path.endsWith('/strategies')).length).toBeGreaterThan(before));
  });

  it('não oferece nenhum envio de ordem', async () => {
    await open();
    expect(screen.queryByRole('button', { name: /ordem/i })).toBeNull();
  });
});

describe('alertas e saída', () => {
  it('lista os sinais e informa ativos sem análise', async () => {
    routes['GET /api/scanner'] = {
      body: { generated_at: '2026-11-03T15:00:00+00:00', complete: false, incomplete_symbols: ['VALE3'], timed_out_symbols: [], rows: [row('PETR4', { signals: [{ type: 'EVENTO_PROXIMO', detail: 'Resultado Q3/2026 em 10/11/2026.' }] }), row('VALE3', { missing: ['Opções: sem token'], data_status: 'INCOMPLETO' })] },
    };
    render(<App />);
    await userEvent.click(await screen.findByRole('button', { name: /Alertas/ }));
    expect(screen.getByText('Resultado Q3/2026 em 10/11/2026.')).toBeTruthy();
    expect(screen.getByText(/1 ativos sem análise completa/)).toBeTruthy();
  });

  it('sair chama a API e volta para a senha', async () => {
    routes['POST /api/logout'] = { body: { authenticated: false } };
    render(<App />);
    await userEvent.click(await screen.findByRole('button', { name: 'Sair' }));
    routes['GET /api/session'] = { body: { authenticated: false, login_ready: true } };
    await waitFor(() => expect(calls.some((call) => call.method === 'POST' && call.path === '/api/logout')).toBe(true));
  });
});
