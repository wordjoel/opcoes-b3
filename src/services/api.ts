import { useCallback, useEffect, useState } from 'react';
import type { JarbasContext } from '../lib/jarbasStore';
import {
  AssetOverview,
  CalendarsView,
  ChainView,
  DataLabel,
  DataStatus,
  DecisionsView,
  Envelope,
  ExpirationsView,
  LabOpportunitiesView,
  LabRankingView,
  LabStrategiesView,
  LabStrategy,
  LabStrategyView,
  PortfolioView,
  Profile,
  Provenance,
  Quality,
  ScannerResponse,
  StrategiesView,
  WithEnvelope,
} from '../types';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** "DADOS INSUFICIENTES" quando os dados não permitem concluir. */
    readonly label?: string,
    readonly reasons: string[] = [],
    /** Provedores tentados e o motivo sanitizado de cada falha. */
    readonly attempts: { provider: string; error: string | null }[] = [],
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
    const detail =
      typeof body?.detail === 'string'
        ? body.detail
        : typeof body?.detail?.message === 'string'
          ? body.detail.message
          : `Erro ${response.status} no servidor.`;
    throw new ApiError(response.status, detail, body?.label, body?.reasons ?? [], body?.detail?.attempts ?? []);
  }
  return body as T;
}

const post = (body?: unknown): RequestInit => ({ method: 'POST', body: body ? JSON.stringify(body) : undefined });

/**
 * Valida o envelope de leitura. Se a API não informar procedência/qualidade/rótulo,
 * o cliente não inventa: marca a resposta como INDISPONÍVEL e registra o motivo.
 */
export function readEnvelope(body: unknown): Envelope {
  const value = body && typeof body === 'object' ? (body as Record<string, unknown>) : {};
  const hasEnvelope = ['data_status', 'quality', 'missing', 'label'].every((key) => key in value);
  if (!hasEnvelope) {
    return {
      provenance: null,
      data_status: 'INDISPONIVEL',
      quality: {
        is_valid: false,
        issues: [{ code: 'ENVELOPE_AUSENTE', severity: 'ERROR', detail: 'A resposta não informou procedência, qualidade e rótulo dos dados.' }],
      },
      missing: ['envelope de procedência ausente na resposta'],
      label: 'INDISPONÍVEL',
    };
  }
  const quality = value.quality as Quality | undefined;
  return {
    provenance: (value.provenance as Provenance | null) ?? null,
    data_status: value.data_status as DataStatus,
    quality: quality ?? { is_valid: false, issues: [] },
    missing: Array.isArray(value.missing) ? (value.missing as string[]) : [],
    label: value.label as DataLabel,
  };
}

/** Leitura de mercado/lab: devolve os dados legados e um `envelope` validado à parte. */
function checked<T>(path: string): Promise<WithEnvelope<T>> {
  return request<T>(path).then((data) => ({ ...data, envelope: readEnvelope(data) }));
}

export interface JarbasUsageModel {
  provider: string;
  model: string;
  requests: number;
  failures: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface JarbasUsage {
  day: string;
  questions: number;
  requests: number;
  failures: number;
  tokens: number;
  daily_limit: number;
  models?: JarbasUsageModel[];
}

export interface JarbasStatus {
  available: boolean;
  providers: { name: string; label: string; model: string; paused: boolean }[];
  usage: JarbasUsage;
  voice: { speak_replies: boolean; voice_name: string | null; voice_rate: number };
}

export interface JarbasReply {
  reply: string;
  provider: string;
  model: string;
  latency_ms?: number;
  attempts: { provider: string; error: string | null }[];
  conversation_id: string;
  tools: string[];
  usage: { questions: number; daily_limit: number };
}

export interface JarbasSettings {
  provider_order: string[];
  openrouter_model: string | null;
  allow_paid: boolean;
  daily_limit: number;
  retention_days: number;
  speak_replies: boolean;
  voice_name: string | null;
  voice_rate: number;
  updated_at: string | null;
  configured_providers: string[];
}

export interface JarbasModel {
  id: string;
  name: string;
  context_length: number | null;
  free: boolean;
  prompt_per_million: number | null;
  completion_per_million: number | null;
}

export interface JarbasDiagnosis {
  ok: boolean;
  providers: {
    name: string;
    label: string;
    ok: boolean;
    reachable: boolean;
    latency_ms: number;
    http_status: number | null;
    reason: string | null;
  }[];
  issues: string[];
}

export interface JarbasConversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: unknown;
}

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
  decisions: () => checked<DecisionsView>('/decisions'),
  labOpportunities: () => checked<LabOpportunitiesView>('/lab/opportunities'),
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
  labStrategies: (mode: 'FORWARD' | 'BACKTEST') => checked<LabStrategiesView>(`/lab/strategies?mode=${mode}`),
  labStrategy: (id: string) => checked<LabStrategyView>(`/lab/strategies/${encodeURIComponent(id)}`),
  labMonitor: () => request<{ active: number; marked: number; closed: number; failed: { id: string; reason: string }[]; not_reached: number }>('/lab/monitor', post()),
  labBacktest: (body: { symbol: string; capital_brl: number; period_days: number; weeks: number }) =>
    request<{ entries: number; created: number; closed: number; skipped: { entry: string; reason: string }[]; complete: boolean; symbol: string }>('/lab/backtests', post(body)),
  labRanking: (mode: 'FORWARD' | 'BACKTEST') => checked<LabRankingView>(`/lab/ranking?mode=${mode}`),
  addSymbol: (symbol: string) => request<{ symbols: string[] }>('/watchlist', post({ symbol })),
  removeSymbol: (symbol: string) =>
    request<{ symbols: string[] }>(`/watchlist/${encodeURIComponent(symbol)}`, { method: 'DELETE' }),
  scanner: () => checked<ScannerResponse>('/scanner'),
  asset: (symbol: string) => checked<AssetOverview>(`/assets/${encodeURIComponent(symbol)}`),
  expirations: (symbol: string) =>
    checked<ExpirationsView>(`/assets/${encodeURIComponent(symbol)}/expirations`),
  chain: (symbol: string, expiry: string) =>
    checked<ChainView>(`/assets/${encodeURIComponent(symbol)}/chain?expiry=${expiry}`),
  jarbasStatus: () => request<JarbasStatus>('/jarbas/status'),
  jarbasDiagnose: () => request<JarbasDiagnosis>('/jarbas/diagnose'),
  jarbasChat: (question: string, conversationId: string | null, context: JarbasContext | null) =>
    request<JarbasReply>('/jarbas/chat', post({ question, conversation_id: conversationId ?? undefined, context })),
  jarbasSettings: () => request<JarbasSettings>('/jarbas/settings'),
  saveJarbasSettings: (settings: Omit<JarbasSettings, 'updated_at' | 'configured_providers'>) =>
    request<JarbasSettings>('/jarbas/settings', { method: 'PUT', body: JSON.stringify(settings) }),
  jarbasModels: () => request<{ configured: boolean; models: JarbasModel[]; chain: string[] }>('/jarbas/models'),
  jarbasConversations: () => request<{ conversations: JarbasConversation[] }>('/jarbas/conversations'),
  jarbasConversation: (id: string) =>
    request<JarbasConversation & { messages: { role: 'user' | 'assistant'; content: string; provider: string | null; model: string | null; created_at: string }[] }>(
      `/jarbas/conversations/${id}`,
    ),
  deleteJarbasConversation: (id: string) => request<{ deleted: boolean }>(`/jarbas/conversations/${id}`, { method: 'DELETE' }),
  calendars: (symbol: string, near: string, far: string) =>
    checked<CalendarsView>(`/assets/${encodeURIComponent(symbol)}/calendars?near=${near}&far=${far}`),
  strategies: (symbol: string, expiry: string, profile: Profile | null) =>
    checked<StrategiesView>(
      `/assets/${encodeURIComponent(symbol)}/strategies?expiry=${expiry}${profile ? `&profile=${profile}` : ''}`,
    ),
  /** Comando explícito: gravar decisões nunca é efeito colateral de uma leitura. */
  recordStrategiesDecisions: (symbol: string, expiry: string, profile: Profile | null) =>
    request<{ recorded: number }>(
      `/assets/${encodeURIComponent(symbol)}/strategies/decisions?expiry=${expiry}${profile ? `&profile=${profile}` : ''}`,
      post(),
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
