/**
 * Ligação entre a tela de estratégias e o Jarbas: a estrutura selecionada e a perna
 * destacada no gráfico durante a montagem guiada.
 */
import { useSyncExternalStore } from 'react';

export interface JarbasLeg {
  symbol: string;
  action: 'BUY' | 'SELL';
  kind: 'CALL' | 'PUT';
  strike: number;
  quantity: number;
  premium: number;
  expiry?: string | null;
  iv?: number | null;
  delta?: number | null;
  style?: string | null;
}

/** Mesmo formato que o backend valida em app/jarbas/assistant.py. */
export interface JarbasContext {
  symbol: string;
  structure_key: string;
  structure_name: string;
  section?: string | null;
  market_date?: string | null;
  spot: number;
  live_price?: number | null;
  spot_drift?: number | null;
  expiry?: string | null;
  business_days_to_expiry?: number | null;
  net_premium: number;
  max_profit: number | null;
  max_loss: number | null;
  max_profit_is_estimate?: boolean;
  breakevens: number[];
  probability_of_profit: number | null;
  expected_pnl?: number | null;
  costs_brl?: number | null;
  decision_status: string;
  decision_reasons: string[];
  decision_missing: string[];
  warnings: string[];
  atm_iv?: number | null;
  legs: JarbasLeg[];
}

interface State {
  context: JarbasContext | null;
  /** Índice na ordem de montagem (compras primeiro), ou null. */
  highlight: number | null;
}

let state: State = { context: null, highlight: null };
const listeners = new Set<() => void>();
let tour: ReturnType<typeof setTimeout>[] = [];

function emit(next: Partial<State>) {
  state = { ...state, ...next };
  listeners.forEach((listener) => listener());
}

export function setJarbasContext(context: JarbasContext | null) {
  if (JSON.stringify(context) === JSON.stringify(state.context)) return;
  stopTour();
  emit({ context });
}

export function setHighlight(highlight: number | null) {
  emit({ highlight });
}

export function stopTour() {
  tour.forEach(clearTimeout);
  tour = [];
  if (state.highlight !== null) emit({ highlight: null });
}

/** Destaca cada perna em sequência no gráfico e na lista de montagem. */
export function startTour(legCount: number, stepMs = 2800) {
  stopTour();
  for (let index = 0; index < legCount; index += 1) {
    tour.push(setTimeout(() => emit({ highlight: index }), index * stepMs));
  }
  tour.push(setTimeout(() => emit({ highlight: null }), legCount * stepMs));
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useJarbasState(): State {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

/** Ordem de montagem usada em todo o app: compras antes das vendas. */
export function assemblyOrder<T extends { action: 'BUY' | 'SELL' }>(legs: T[]): T[] {
  return [...legs].sort((a, b) => (a.action === b.action ? 0 : a.action === 'BUY' ? -1 : 1));
}
