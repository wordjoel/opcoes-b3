/** Contratos da API. null significa "não disponível", nunca zero; em ganho e perda, "ilimitado". */

export type Regime = 'BULL' | 'BEAR' | 'SIDEWAYS' | 'HIGH_VOL' | 'UNCERTAIN';

export interface Provenance {
  source: string;
  kind: string;
  collected_at: string;
  market_time: string;
}

export interface Quality {
  is_valid: boolean;
  issues: { code: string; severity: 'WARNING' | 'ERROR'; detail: string }[];
}

export type DataStatus = 'REAL' | 'ATRASADO' | 'INCOMPLETO' | 'INDISPONIVEL';
export type DecisionStatus = 'APROVADA' | 'REPROVADA' | 'INCOMPLETA';

export type Profile = 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE';

export interface MarketStructure {
  trend: 'UP' | 'DOWN' | null;
  last_swing_high: number | null;
  last_swing_low: number | null;
  events: { day: string; kind: 'BOS' | 'CHOCH'; direction: 'UP' | 'DOWN'; level: number }[];
}

export interface CorporateEvent {
  kind: 'RESULTADO' | 'PROVENTO' | 'EVENTO_SOCIETARIO';
  day: string;
  label: string;
  confirmed: boolean;
}

export interface Signal {
  type: 'VOL_CARA' | 'VOL_BARATA' | 'MOVIMENTO' | 'GRADE_DEFASADA' | 'SALTO_HISTORICO' | 'IV_RANK_ALTO' | 'IV_RANK_BAIXO' | 'EVENTO_PROXIMO' | 'ROMPIMENTO';
  detail: string;
}

export interface ScannerRow {
  symbol: string;
  name: string | null;
  price: number | null;
  change_percent: number | null;
  market_time: string | null;
  historical_volatility: number | null;
  atm_iv: number | null;
  iv_ratio: number | null;
  regime: Regime | null;
  expiry: string | null;
  market_date: string | null;
  spot_drift: number | null;
  iv_rank: number | null;
  iv_percentile: number | null;
  iv_samples: number;
  iv_samples_needed: number;
  structure_trend: 'UP' | 'DOWN' | null;
  events: CorporateEvent[];
  source: string | null;
  data_status: DataStatus;
  missing: string[];
  history_warnings: string[];
  signals: Signal[];
}

export interface ScannerResponse {
  generated_at: string;
  complete: boolean;
  incomplete_symbols: string[];
  timed_out_symbols: string[];
  rows: ScannerRow[];
}

export interface AssetOverview {
  quote: {
    symbol: string;
    name: string | null;
    price: number;
    change_percent: number | null;
    volume: number | null;
    provenance: Provenance;
  };
  quote_quality: Quality;
  data_status: DataStatus;
  history_quality: Quality;
  historical_volatility: number | null;
  ewma_volatility: number | null;
  regime: Regime | null;
  structure: MarketStructure | null;
  history: {
    day: string;
    open: number;
    high: number;
    low: number;
    close: number;
    hv_20d: number | null;
    bb_upper: number | null;
    bb_middle: number | null;
    bb_lower: number | null;
  }[];
}

export interface ChainQuote {
  symbol: string;
  kind: 'CALL' | 'PUT';
  strike: number;
  style: 'AMERICAN' | 'EUROPEAN' | null;
  bid: number | null;
  ask: number | null;
  close: number | null;
  open_interest: number | null;
  volume: number | null;
  trades: number | null;
  iv: number | null;
  delta: number | null;
  usable: boolean;
}

export interface ChainView {
  symbol: string;
  expiry: string;
  market_date: string | null;
  spot: number;
  risk_free_rate: number | null;
  provenance: Provenance;
  quality: Quality;
  open_interest: {
    calls: number;
    puts: number;
    put_call_ratio: number | null;
    calls_change: number | null;
    puts_change: number | null;
  };
  quotes: ChainQuote[];
}

export interface Candidate {
  key: string;
  name: string;
  rationale: string;
  assumptions: string[];
  fits_regime: boolean;
  net_premium: number;
  max_profit: number | null;
  max_loss: number | null;
  breakevens: number[];
  risk_reward: number | null;
  probability_of_profit: number | null;
  greeks: {
    delta: number;
    gamma: number;
    theta_per_business_day: number;
    vega_per_vol_point: number;
  } | null;
  legs: {
    symbol: string;
    action: 'BUY' | 'SELL';
    kind: 'CALL' | 'PUT';
    strike: number;
    quantity: number;
    premium: number;
    price_basis: 'BOOK' | 'CLOSE';
    iv: number | null;
    delta: number | null;
    style: 'AMERICAN' | 'EUROPEAN' | null;
    probability_itm: number | null;
  }[];
  risk: {
    is_approved: boolean;
    liquidity_score: number | null;
    stress: Record<string, number>;
    warnings: string[];
    verdict: string;
    rejection_reason: string | null;
  };
  payoff: { price: number; pnl: number }[];
  heatmap: { spot_shocks: number[]; vol_shocks: number[]; pnl: number[][] } | null;
  decision: {
    status: DecisionStatus;
    reasons: string[];
    missing: string[];
    capital_required: number | null;
    max_risk: number | null;
    max_risk_pct: number | null;
    limit_brl: number | null;
    risk_reward: number | null;
  };
}

export interface StrategiesView {
  symbol: string;
  expiry: string;
  market_date: string | null;
  spot: number;
  source?: string | null;
  live_price: number | null;
  spot_drift: number | null;
  risk_free_rate: number;
  time_to_expiry_years: number;
  atm_iv: number | null;
  historical_volatility: number | null;
  iv_ratio: number | null;
  regime: Regime | null;
  profile: Profile | null;
  capital_configured: boolean;
  iv_rank: number | null;
  iv_percentile: number | null;
  iv_samples: number;
  iv_samples_needed: number;
  structure: MarketStructure | null;
  events: CorporateEvent[];
  events_error: string | null;
  quality: Quality;
  candidates: Candidate[];
  unavailable: { key: string; name: string; reason: string }[];
}

export interface LabLeg {
  symbol: string;
  action: 'BUY' | 'SELL';
  kind: 'CALL' | 'PUT';
  strike: number;
  expiry: string;
  quantity: number;
  premium: number;
  bid?: number | null;
  ask?: number | null;
  volume?: number | null;
  open_interest?: number | null;
  iv?: number | null;
  style?: string | null;
}

export interface LabOpportunity {
  agent: string;
  agent_name: string;
  key: string;
  name: string;
  symbol: string;
  expiry: string;
  market_date: string | null;
  days_to_expiry: number;
  legs: LabLeg[];
  net_premium: number;
  max_profit: number | null;
  max_loss: number;
  breakevens: number[];
  risk_reward: number | null;
  probability_of_profit: number | null;
  potential_return: number | null;
  theoretical_return: number | null;
  liquidity_score: number;
  decision: Candidate['decision'];
}

export interface LabAsset {
  symbol: string;
  status: string;
  reason: string | null;
  liquidity: { usable_series: number; liquid_series: number; calls: number; puts: number; sufficient: boolean; open_interest_known?: boolean } | null;
  market_date?: string | null;
  expiry?: string;
  source?: string;
}

export interface LabMark {
  day: string;
  pnl_brl: number | null;
  spot: number | null;
  prices: Record<string, number>;
  complete: boolean;
  settlement: boolean;
  source: string;
  fetched_at: string;
}

export interface LabStrategy {
  id: string;
  mode: 'FORWARD' | 'BACKTEST';
  agent: string;
  agent_name: string;
  symbol: string;
  structure_name: string;
  expiry: string;
  entry_day: string;
  end_day: string;
  capital_brl: number;
  lots: number;
  regime: string | null;
  target_pct: number | null;
  stop_pct: number | null;
  cost_brl: number;
  cost_informed: number;
  status: 'ATIVA' | 'ENCERRADA';
  close_reason: string | null;
  source: string;
  legs: LabLeg[];
  employed_brl: number;
  max_risk_brl: number;
  returns: { potential: number | null; theoretical: number | null; measured_label: 'SIMULADO' | 'OBSERVADO'; measured: number | null };
  pnl_brl: number | null;
  return_on_capital: number | null;
  return_on_employed: number | null;
  return_on_risk: number | null;
  pnl_book_brl: number | null;
  return_on_risk_book: number | null;
  best_brl: number | null;
  worst_brl: number | null;
  max_drawdown_brl: number;
  days_to_target: number | null;
  marks?: LabMark[];
}

export interface LabRankingRow {
  agent?: string;
  agent_name?: string;
  structure_name?: string;
  count: number;
  hit_rate: number;
  mean_return: number;
  median_return: number;
  std_return: number;
  best_return: number;
  worst_return: number;
  book_count: number;
  book_hit_rate: number | null;
  book_median_return: number | null;
  reading: 'LUCRO_NOS_DOIS_LIMITES' | 'LUCRO_SO_NO_FECHAMENTO' | 'SEM_LUCRO' | 'EXECUCAO_NAO_MEDIDA';
  entry_dates: number;
  position: number | null;
}
