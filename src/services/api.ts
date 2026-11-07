import { useCallback, useEffect, useState } from 'react';
import { AssetOverview, ChainView, DecisionEntry, LabAsset, LabOpportunity, LabRankingRow, LabStrategy, PortfolioView, Profile, ScannerResponse, StrategiesView } from '../types';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** "DADOS INSUFICIENTES" quando os dados não permitem concluir. */
    readonly label?: string,
    readonly reasons: string[] = [],
  ) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    });
  } catch {
    throw new ApiError(0, 'Sem conexão com o servidor.');
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/login')) onUnauthorized();
    const detail = typeof body?.detail === 'string' ? body.detail : `Erro ${response.status} no servidor.`;
    throw new ApiError(response.status, detail, body?.label, body?.reasons ?? []);
  }
  return body as T;
}

const post = (body?: unknown): RequestInit => ({ method: 'POST', body: body ? JSON.stringify(body) : undefined });

export const api = {
  session: () => request<{ authenticated: boolean; login_ready: boolean }>('/session'),
  login: (password: string) => request<{ authenticated: boolean }>('/login', post({ password })),
  logout: () => request<{ authenticated: boolean }>('/logout', post()),
  riskSettings: () =>
    request<{ capital_brl: number | null; max_loss_pct: number | null; updated_at: string | null }>('/settings/risk'),
  saveRiskSettings: (capital_brl: number, max_loss_pct: number) =>
    request<{ capital_brl: number; max_loss_pct: number; updated_at: string }>('/settings/risk', {
      method: 'PUT',
      body: JSON.stringify({ capital_brl, max_loss_pct }),
    }),
  costSettings: () =>
    request<{ per_order_brl: number | null; fee_pct: number | null; income_tax_pct: number | null; updated_at: string | null }>(
      '/settings/costs',
    ),
  saveCostSettings: (per_order_brl: number, fee_pct: number, income_tax_pct: number) =>
    request<{ per_order_brl: number; fee_pct: number; income_tax_pct: number; updated_at: string }>('/settings/costs', {
      method: 'PUT',
      body: JSON.stringify({ per_order_brl, fee_pct, income_tax_pct }),
    }),
  portfolio: () => request<PortfolioView>('/portfolio'),
  savePortfolioSettings: (initial_cash_brl: number, max_position_size: number) =>
    request<PortfolioView>('/portfolio/settings', { method: 'PUT', body: JSON.stringify({ initial_cash_brl, max_position_size }) }),
  addFill: (body: { symbol: string; side: 'BUY' | 'SELL'; quantity: number; price: number; fees_brl: number; trade_day: string }) =>
    request<PortfolioView>('/portfolio/fills', post(body)),
  voidFill: (id: number) => request<PortfolioView>(`/portfolio/fills/${id}/void`, post()),
  decisions: () => request<{ decisions: DecisionEntry[] }>('/decisions'),
  labOpportunities: () => request<{ generated_at: string; assets: LabAsset[]; opportunities: LabOpportunity[] }>('/lab/opportunities'),
  labStart: (body: {
    symbol: string;
    agent: string;
    key: string;
    capital_brl: number;
    period_days: number;
    target_pct: number | null;
    stop_pct: number | null;
    cost_brl: number | null;
  }) => request<{ id: string; created: boolean; entry_day: string; end_day: string }>('/lab/strategies', post(body)),
  labStrategies: (mode: 'FORWARD' | 'BACKTEST') => request<{ strategies: LabStrategy[] }>(`/lab/strategies?mode=${mode}`),
  labStrategy: (id: string) => request<LabStrategy>(`/lab/strategies/${encodeURIComponent(id)}`),
  labMonitor: () => request<{ active: number; marked: number; closed: number; failed: { id: string; reason: string }[]; not_reached: number }>('/lab/monitor', post()),
  labBacktest: (body: { symbol: string; capital_brl: number; period_days: number; weeks: number }) =>
    request<{ entries: number; created: number; closed: number; skipped: { entry: string; reason: string }[]; complete: boolean; symbol: string }>('/lab/backtests', post(body)),
  labRanking: (mode: 'FORWARD' | 'BACKTEST') =>
    request<{ mode: string; label: string; closed: number; agents: LabRankingRow[]; structures: LabRankingRow[] }>(`/lab/ranking?mode=${mode}`),
  addSymbol: (symbol: string) => request<{ symbols: string[] }>('/watchlist', post({ symbol })),
  removeSymbol: (symbol: string) =>
    request<{ symbols: string[] }>(`/watchlist/${encodeURIComponent(symbol)}`, { method: 'DELETE' }),
  scanner: () => request<ScannerResponse>('/scanner'),
  asset: (symbol: string) => request<AssetOverview>(`/assets/${encodeURIComponent(symbol)}`),
  expirations: (symbol: string) =>
    request<{ expirations: string[] }>(`/assets/${encodeURIComponent(symbol)}/expirations`),
  chain: (symbol: string, expiry: string) =>
    request<ChainView>(`/assets/${encodeURIComponent(symbol)}/chain?expiry=${expiry}`),
  strategies: (symbol: string, expiry: string, profile: Profile | null) =>
    request<StrategiesView>(
      `/assets/${encodeURIComponent(symbol)}/strategies?expiry=${expiry}${profile ? `&profile=${profile}` : ''}`,
    ),
};

/** Carrega ao montar e quando `key` muda. Com key null, não busca nada. */
export function useResource<T>(key: string | null, load: () => Promise<T>) {
  const [state, setState] = useState<{ key: string | null; data: T | null; error: ApiError | null; loading: boolean }>({
    key,
    data: null,
    error: null,
    loading: key !== null,
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (key === null) {
      setState({ key, data: null, error: null, loading: false });
      return;
    }
    let active = true;
    // Ao trocar de chave, o dado anterior sai: não pode parecer do novo ativo.
    setState((previous) => ({ key, data: previous.key === key ? previous.data : null, error: null, loading: true }));
    load()
      .then((data) => active && setState({ key, data, error: null, loading: false }))
      .catch((error: ApiError) => active && setState({ key, data: null, error, loading: false }));
    return () => {
      active = false;
    };
    // `load` muda a cada render; a identidade do pedido é `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  const current = state.key === key;
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: current ? state.loading : key !== null,
    reload,
  };
}
