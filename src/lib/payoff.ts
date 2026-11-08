/**
 * Contas do mapa de resultado, feitas no navegador para a tela responder na hora.
 * Mesmas fórmulas do backend (quant/payoff.py): preço lognormal neutro ao risco,
 * prazo em dias corridos / 365. São o que os parâmetros implicam, não previsão.
 */

export interface PayoffLeg {
  action: 'BUY' | 'SELL';
  kind: 'CALL' | 'PUT';
  strike: number;
  quantity: number;
  premium: number;
  iv: number | null;
  /** Anos até o vencimento desta perna; só em estruturas com dois vencimentos. */
  t?: number;
}

const direction = (leg: PayoffLeg) => (leg.action === 'BUY' ? 1 : -1);

/** Função de distribuição da normal padrão (Abramowitz e Stegun 7.1.26, erro < 1,5e-7). */
export function normCdf(x: number): number {
  const z = Math.abs(x) / Math.SQRT2;
  const t = 1 / (1 + 0.3275911 * z);
  const poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
  const erf = 1 - poly * Math.exp(-z * z);
  return x >= 0 ? (1 + erf) / 2 : (1 - erf) / 2;
}

/** Resultado em R$ no vencimento, com o ativo em `price`. */
export function expiryPnl(legs: PayoffLeg[], price: number): number {
  return legs.reduce((total, leg) => {
    const intrinsic = leg.kind === 'CALL' ? Math.max(price - leg.strike, 0) : Math.max(leg.strike - price, 0);
    return total + direction(leg) * (intrinsic - leg.premium) * leg.quantity;
  }, 0);
}

/** Black-Scholes europeu. Para americanas é uma aproximação, dita na tela. */
export function blackScholes(kind: 'CALL' | 'PUT', spot: number, strike: number, t: number, r: number, sigma: number): number {
  if (t <= 0 || sigma <= 0) return kind === 'CALL' ? Math.max(spot - strike, 0) : Math.max(strike - spot, 0);
  const root = sigma * Math.sqrt(t);
  const d1 = (Math.log(spot / strike) + (r + (sigma * sigma) / 2) * t) / root;
  const d2 = d1 - root;
  const discount = Math.exp(-r * t);
  return kind === 'CALL'
    ? spot * normCdf(d1) - strike * discount * normCdf(d2)
    : strike * discount * normCdf(-d2) - spot * normCdf(-d1);
}

/**
 * Resultado em R$ se a posição fosse desfeita a preço de modelo com `t` anos restantes.
 * `volShift` soma pontos de vol (0,05 = +5 pontos) à vol de cada perna. null sem vol.
 */
export function modelPnl(legs: PayoffLeg[], price: number, t: number, r: number, volShift = 0, fallbackIv: number | null = null): number | null {
  let total = 0;
  for (const leg of legs) {
    const base = leg.iv ?? fallbackIv;
    if (base === null || base <= 0) return null;
    const value = blackScholes(leg.kind, price, leg.strike, t, r, Math.max(base + volShift, 0.01));
    total += direction(leg) * (value - leg.premium) * leg.quantity;
  }
  return total;
}

/** Vol usada nas probabilidades: média das pernas, como o backend; senão a do dinheiro. */
export function modelSigma(legs: PayoffLeg[], atmIv: number | null): number | null {
  const ivs = legs.map((leg) => leg.iv);
  if (ivs.every((iv): iv is number => iv !== null && iv > 0)) return ivs.reduce((a, b) => a + b, 0) / ivs.length;
  return atmIv !== null && atmIv > 0 ? atmIv : null;
}

export interface OutcomeStats {
  probabilityOfProfit: number;
  probabilityOfMaxProfit: number | null;
  probabilityOfMaxLoss: number | null;
  /** Média do resultado no vencimento pelo modelo, em R$. */
  expectedPnl: number;
  /** Faixa em que o ativo termina com 68% de chance pelo modelo. */
  range68: [number, number];
}

const STEPS = 2400;
const Z_SPAN = 6;

/** Integra o resultado no vencimento sobre a distribuição lognormal do ativo. */
export function outcomeStats(
  legs: PayoffLeg[],
  spot: number,
  sigma: number,
  t: number,
  r: number,
  maxProfit: number | null,
  maxLoss: number | null,
): OutcomeStats {
  if (spot <= 0 || sigma <= 0 || t <= 0) throw new Error('spot, sigma e t precisam ser positivos');
  const root = sigma * Math.sqrt(t);
  const mean = Math.log(spot) + (r - (sigma * sigma) / 2) * t;
  const cdf = (price: number) => (price <= 0 ? 0 : price === Infinity ? 1 : normCdf((Math.log(price) - mean) / root));
  // Só arredondamento: os máximos vêm do backend, calculados com os mesmos prêmios.
  const tolerance = 1e-6 * Math.max(Math.abs(maxProfit ?? 0), Math.abs(maxLoss ?? 0), 1);

  // Entre strikes o resultado é uma reta: as probabilidades saem exatas, trecho a trecho.
  const edges = [0, ...[...new Set(legs.map((leg) => leg.strike))].sort((a, b) => a - b), Infinity];
  const where = (test: (pnl: number) => boolean) => {
    let total = 0;
    for (let index = 0; index + 1 < edges.length; index += 1) {
      const a = edges[index];
      const b = edges[index + 1];
      const start = expiryPnl(legs, a);
      const slope = b === Infinity ? expiryPnl(legs, a + 1) - start : (expiryPnl(legs, b) - start) / (b - a);
      if (Math.abs(slope) < 1e-12) {
        if (test(start)) total += cdf(b) - cdf(a);
        continue;
      }
      // Ponto do trecho onde a condição troca, se trocar.
      const lowTrue = test(start + slope * 1e-9);
      const farPoint = b === Infinity ? a + 1e9 : b;
      const highTrue = test(start + slope * (farPoint - a - 1e-9));
      if (lowTrue && highTrue) total += cdf(b) - cdf(a);
      else if (lowTrue !== highTrue) {
        let lo = a;
        let hi = farPoint;
        for (let i = 0; i < 80; i += 1) {
          const mid = (lo + hi) / 2;
          if (test(start + slope * (mid - a)) === lowTrue) lo = mid;
          else hi = mid;
        }
        total += lowTrue ? cdf(lo) - cdf(a) : cdf(b) - cdf(lo);
      }
    }
    return total;
  };

  // A média não tem patamares: integração numérica fina basta.
  let expected = 0;
  let previous = normCdf(-Z_SPAN);
  for (let step = 0; step < STEPS; step += 1) {
    const low = -Z_SPAN + (2 * Z_SPAN * step) / STEPS;
    const high = low + (2 * Z_SPAN) / STEPS;
    const current = normCdf(high);
    expected += (current - previous) * expiryPnl(legs, Math.exp(mean + root * ((low + high) / 2)));
    previous = current;
  }

  const boundedProfit = maxProfit !== null && maxProfit > 0;
  const boundedLoss = maxLoss !== null && maxLoss > 0;
  return {
    probabilityOfProfit: where((pnl) => pnl > 1e-9),
    probabilityOfMaxProfit: boundedProfit ? where((pnl) => pnl >= maxProfit - tolerance) : null,
    probabilityOfMaxLoss: boundedLoss ? where((pnl) => pnl <= -maxLoss + tolerance) : null,
    expectedPnl: expected,
    range68: [Math.exp(mean - root), Math.exp(mean + root)],
  };
}

/** Chance de o ativo terminar acima de `price` no vencimento. */
export function probabilityAbove(price: number, spot: number, sigma: number, t: number, r: number): number {
  if (price <= 0) return 1;
  const root = sigma * Math.sqrt(t);
  return 1 - normCdf((Math.log(price / spot) - (r - (sigma * sigma) / 2) * t) / root);
}

/** Densidade lognormal do preço no vencimento, para desenhar a curva de probabilidade. */
export function priceDensity(price: number, spot: number, sigma: number, t: number, r: number): number {
  if (price <= 0) return 0;
  const root = sigma * Math.sqrt(t);
  const z = (Math.log(price / spot) - (r - (sigma * sigma) / 2) * t) / root;
  return Math.exp((-z * z) / 2) / (price * root * Math.sqrt(2 * Math.PI));
}

/** Preços do mapa: faixa em torno do ativo que cobre strikes e a faixa provável, mais strikes e breakevens exatos. */
export function priceGrid(legs: PayoffLeg[], spot: number, sigma: number | null, t: number, breakevens: number[], points = 161): number[] {
  const spread = sigma ? Math.min(Math.max(3 * sigma * Math.sqrt(t), 0.15), 0.6) : 0.3;
  const strikes = legs.map((leg) => leg.strike);
  const low = Math.max(Math.min(spot * (1 - spread), Math.min(...strikes) * 0.95), 0.01);
  const high = Math.max(spot * (1 + spread), Math.max(...strikes) * 1.05);
  const grid = new Set<number>();
  for (let index = 0; index < points; index += 1) grid.add(low + ((high - low) * index) / (points - 1));
  for (const value of [...strikes, ...breakevens, spot]) if (value >= low && value <= high) grid.add(value);
  return [...grid].sort((a, b) => a - b);
}

/** Estrutura com pernas em vencimentos diferentes (calendário, diagonal). */
export function isMultiExpiry(legs: PayoffLeg[]): boolean {
  const times = legs.map((leg) => leg.t).filter((t): t is number => t !== undefined);
  return times.length > 0 && Math.max(...times) - Math.min(...times) > 1e-9;
}

/**
 * Resultado em R$ depois de `elapsed` anos: perna vencida pelo intrínseco, as demais pelo modelo.
 * Pernas sem `t` vencem em `horizon`. null se faltar vol a alguma perna ainda viva.
 */
export function pnlAfter(
  legs: PayoffLeg[],
  price: number,
  elapsed: number,
  horizon: number,
  r: number,
  volShift = 0,
  fallbackIv: number | null = null,
): number | null {
  let total = 0;
  for (const leg of legs) {
    const remaining = (leg.t ?? horizon) - elapsed;
    let value: number;
    if (remaining <= 1e-9) {
      value = leg.kind === 'CALL' ? Math.max(price - leg.strike, 0) : Math.max(leg.strike - price, 0);
    } else {
      const base = leg.iv ?? fallbackIv;
      if (base === null || base <= 0) return null;
      value = blackScholes(leg.kind, price, leg.strike, remaining, r, Math.max(base + volShift, 0.01));
    }
    total += direction(leg) * (value - leg.premium) * leg.quantity;
  }
  return total;
}

/** Probabilidade e média por integração numérica, para resultados que não são retas entre strikes. */
export function numericStats(pnl: (price: number) => number, spot: number, sigma: number, t: number, r: number): OutcomeStats {
  if (spot <= 0 || sigma <= 0 || t <= 0) throw new Error('spot, sigma e t precisam ser positivos');
  const root = sigma * Math.sqrt(t);
  const mean = Math.log(spot) + (r - (sigma * sigma) / 2) * t;
  const steps = 6000;
  let profit = 0;
  let expected = 0;
  let previous = normCdf(-Z_SPAN);
  for (let step = 0; step < steps; step += 1) {
    const low = -Z_SPAN + (2 * Z_SPAN * step) / steps;
    const high = low + (2 * Z_SPAN) / steps;
    const current = normCdf(high);
    const value = pnl(Math.exp(mean + root * ((low + high) / 2)));
    expected += (current - previous) * value;
    if (value > 1e-9) profit += current - previous;
    previous = current;
  }
  return {
    probabilityOfProfit: profit,
    probabilityOfMaxProfit: null,
    probabilityOfMaxLoss: null,
    expectedPnl: expected,
    range68: [Math.exp(mean - root), Math.exp(mean + root)],
  };
}
