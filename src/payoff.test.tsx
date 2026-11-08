/** Contas do mapa de resultado contra valores conhecidos de Black-Scholes. */
import { describe, expect, it } from 'vitest';
import { blackScholes, expiryPnl, modelPnl, modelSigma, normCdf, outcomeStats, PayoffLeg, priceGrid, probabilityAbove } from './lib/payoff';
import { assemblySteps } from './lib/strategyGuide';

const call = (action: 'BUY' | 'SELL', strike: number, premium: number, iv: number | null = 0.3): PayoffLeg => ({
  action, kind: 'CALL', strike, quantity: 100, premium, iv,
});

describe('payoff', () => {
  it('normal acumulada', () => {
    expect(normCdf(0)).toBeCloseTo(0.5, 7);
    expect(normCdf(1.96)).toBeCloseTo(0.975, 4);
    expect(normCdf(-1)).toBeCloseTo(0.158655, 5);
  });

  it('Black-Scholes bate com o valor de referência e com a paridade', () => {
    // S=100, K=100, t=1, r=5%, vol=20%: call 10,4506.
    expect(blackScholes('CALL', 100, 100, 1, 0.05, 0.2)).toBeCloseTo(10.4506, 3);
    const put = blackScholes('PUT', 100, 100, 1, 0.05, 0.2);
    expect(10.4506 - put).toBeCloseTo(100 - 100 * Math.exp(-0.05), 3);
  });

  it('trava de alta: ganho e perda no vencimento', () => {
    const legs = [call('BUY', 50, 2), call('SELL', 55, 0.5)];
    expect(expiryPnl(legs, 40)).toBeCloseTo(-150);
    expect(expiryPnl(legs, 60)).toBeCloseTo(350);
    expect(expiryPnl(legs, 51.5)).toBeCloseTo(0);
  });

  it('estatísticas batem com a fórmula fechada da call comprada', () => {
    const t = 0.25, r = 0.1, sigma = 0.3, spot = 50, strike = 50;
    const premium = blackScholes('CALL', spot, strike, t, r, sigma);
    const legs = [call('BUY', strike, premium, sigma)];
    const stats = outcomeStats(legs, spot, sigma, t, r, null, premium * 100);
    // Lucro = terminar acima do breakeven.
    expect(stats.probabilityOfProfit).toBeCloseTo(probabilityAbove(strike + premium, spot, sigma, t, r), 5);
    // Perda máxima = terminar abaixo do strike.
    expect(stats.probabilityOfMaxLoss!).toBeCloseTo(1 - probabilityAbove(strike, spot, sigma, t, r), 5);
    // Média neutra ao risco: valor justo capitalizado menos o prêmio pago.
    expect(stats.expectedPnl).toBeCloseTo(100 * premium * (Math.exp(r * t) - 1), 0);
    expect(stats.probabilityOfMaxProfit).toBeNull();
    expect(stats.range68[0]).toBeLessThan(spot);
    expect(stats.range68[1]).toBeGreaterThan(spot);
  });

  it('trava: chance do ganho máximo é terminar acima do strike vendido', () => {
    const legs = [call('BUY', 50, 2), call('SELL', 55, 0.5)];
    const stats = outcomeStats(legs, 50, 0.3, 0.25, 0.1, 350, 150);
    expect(stats.probabilityOfMaxProfit!).toBeCloseTo(probabilityAbove(55, 50, 0.3, 0.25, 0.1), 5);
    expect(stats.probabilityOfMaxLoss!).toBeCloseTo(1 - probabilityAbove(50, 50, 0.3, 0.25, 0.1), 5);
    expect(stats.probabilityOfProfit).toBeCloseTo(probabilityAbove(51.5, 50, 0.3, 0.25, 0.1), 5);
  });

  it('modelo antes do vencimento converge para o vencimento', () => {
    const legs = [call('BUY', 50, 2)];
    expect(modelPnl(legs, 55, 0, 0.1)).toBeCloseTo(expiryPnl(legs, 55));
    expect(modelPnl([call('BUY', 50, 2, null)], 55, 0.1, 0.1)).toBeNull();
    expect(modelPnl([call('BUY', 50, 2, null)], 55, 0.1, 0.1, 0, 0.3)).not.toBeNull();
  });

  it('vol do modelo é a média das pernas, como no backend', () => {
    expect(modelSigma([call('BUY', 50, 2, 0.2), call('SELL', 55, 1, 0.4)], 0.9)).toBeCloseTo(0.3);
    expect(modelSigma([call('BUY', 50, 2, null)], 0.25)).toBe(0.25);
    expect(modelSigma([call('BUY', 50, 2, null)], null)).toBeNull();
  });

  it('grade inclui strikes e breakevens', () => {
    const grid = priceGrid([call('BUY', 50, 2), call('SELL', 70, 1)], 50, 0.3, 0.1, [51]);
    expect(grid).toContain(50);
    expect(grid).toContain(70);
    expect(grid).toContain(51);
    expect(grid[grid.length - 1]).toBeGreaterThan(70);
  });
});

describe('montagem', () => {
  const legs = [
    { symbol: 'VENDA', action: 'SELL' as const, kind: 'PUT' as const, strike: 48, quantity: 100, premium: 1 },
    { symbol: 'COMPRA', action: 'BUY' as const, kind: 'PUT' as const, strike: 46, quantity: 100, premium: 0.4 },
  ];

  it('compra antes da venda e papel de crédito', () => {
    const steps = assemblySteps(legs);
    expect(steps.map((step) => step.leg.symbol)).toEqual(['COMPRA', 'VENDA']);
    expect(steps[0].cash).toBeCloseTo(40);
    expect(steps[1].cash).toBeCloseTo(-100);
    expect(steps[0].role).toMatch(/Proteção/);
    expect(steps[1].role).toMatch(/crédito/);
  });

  it('em débito a compra é a aposta e a venda financia', () => {
    const steps = assemblySteps([
      { symbol: 'A', action: 'SELL', kind: 'CALL', strike: 55, quantity: 100, premium: 0.5 },
      { symbol: 'B', action: 'BUY', kind: 'CALL', strike: 50, quantity: 100, premium: 2 },
    ]);
    expect(steps[0].role).toMatch(/Aposta principal/);
    expect(steps[1].role).toMatch(/Financiamento/);
  });
});
