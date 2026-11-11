import { PALETA } from '../lib/tema';
import { type CSSProperties, useEffect, useMemo, useState } from 'react';
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { expiryPnl, isMultiExpiry, modelSigma, numericStats, outcomeStats, PayoffLeg, pnlAfter, priceDensity, priceGrid, probabilityAbove } from '../lib/payoff';
import { formatCurrency, formatLimit, formatNumber, formatRatio } from '../lib/utils';
import { assemblyOrder, useJarbasState } from '../lib/jarbasStore';
import { Panel, Signed, Stat } from './Common';


interface PayoffMapProps {
  symbol: string;
  legs: PayoffLeg[];
  spot: number;
  /** Anos até o vencimento (o mais curto, se houver dois), em dias corridos / 365. */
  t: number;
  r: number;
  atmIv: number | null;
  maxProfit: number | null;
  maxLoss: number | null;
  breakevens: number[];
}

export function PayoffMap({ symbol, legs, spot, t, r, atmIv, maxProfit, maxLoss, breakevens }: PayoffMapProps) {
  const totalDays = Math.max(Math.round(t * 365), 0);
  const [target, setTarget] = useState(spot);
  const [daysLeft, setDaysLeft] = useState(totalDays);
  const [volPoints, setVolPoints] = useState(0);

  // Outra estrutura ou outra grade: volta ao ponto de partida.
  const identity = legs.map((leg) => `${leg.action}${leg.kind}${leg.strike}`).join('|');
  useEffect(() => {
    setTarget(spot);
    setDaysLeft(totalDays);
    setVolPoints(0);
  }, [identity, spot, totalDays]);

  // Com dois vencimentos, o resultado é medido no curto e a perna longa fica pelo modelo.
  const multi = isMultiExpiry(legs);
  const horizonLabel = multi ? 'no vencimento curto' : 'no vencimento';
  const shift = volPoints / 100;
  const nearLegs = multi ? legs.filter((leg) => Math.abs((leg.t ?? t) - t) < 1e-9) : legs;
  const baseSigma = modelSigma(nearLegs, atmIv);
  const sigma = baseSigma !== null ? Math.max(baseSigma + shift, 0.01) : null;
  const elapsed = t - daysLeft / 365;
  const atHorizon = (price: number) => (multi ? (pnlAfter(legs, price, t, t, r, shift, atmIv) ?? expiryPnl(legs, price)) : expiryPnl(legs, price));

  const stats = useMemo(
    () =>
      sigma === null || t <= 0
        ? null
        : multi
          ? numericStats((price) => pnlAfter(legs, price, t, t, r, shift, atmIv) ?? 0, spot, sigma, t, r)
          : outcomeStats(legs, spot, sigma, t, r, maxProfit, maxLoss),
    [legs, spot, sigma, t, r, maxProfit, maxLoss, multi, shift, atmIv],
  );

  const prices = useMemo(() => priceGrid(legs, spot, sigma, t, breakevens), [legs, spot, sigma, t, breakevens]);
  const data = useMemo(
    () =>
      prices.map((price) => {
        const expiry = multi ? (pnlAfter(legs, price, t, t, r, shift, atmIv) ?? expiryPnl(legs, price)) : expiryPnl(legs, price);
        return {
          price,
          expiry,
          gain: Math.max(expiry, 0),
          loss: Math.min(expiry, 0),
          simulated: daysLeft > 0 ? pnlAfter(legs, price, elapsed, t, r, shift, atmIv) : expiry,
          density: sigma !== null && t > 0 ? priceDensity(price, spot, sigma, t, r) : null,
        };
      }),
    [prices, legs, daysLeft, elapsed, r, shift, atmIv, sigma, t, spot, multi],
  );

  const low = prices[0];
  const high = prices[prices.length - 1];
  const step = Math.max(Math.round(((high - low) / 400) * 100) / 100, 0.01);
  const clampedTarget = Math.min(Math.max(target, low), high);
  const atTarget = atHorizon(clampedTarget);
  const simulatedAtTarget = daysLeft > 0 ? pnlAfter(legs, clampedTarget, elapsed, t, r, shift, atmIv) : atTarget;
  const chanceAbove = sigma !== null && t > 0 ? probabilityAbove(clampedTarget, spot, sigma, t, r) : null;
  const move = clampedTarget / spot - 1;
  // Pernas na ordem de montagem; cada strike leva os números dos passos que o usam.
  const ordered = assemblyOrder(legs);
  const { highlight } = useJarbasState();
  const focused = highlight !== null ? ordered[highlight] : undefined;
  const strikeSteps = new Map<number, number[]>();
  ordered.forEach((leg, index) => strikeSteps.set(leg.strike, [...(strikeSteps.get(leg.strike) ?? []), index + 1]));

  return (
    <Panel title="Mapa de resultado">
      <p className="np-note mb-3">
        Arraste os controles ou toque no gráfico. A área <strong style={{ color: PALETA.GAIN }}>verde</strong> é onde a estrutura ganha {horizonLabel}, a{' '}
        <strong style={{ color: PALETA.LOSS }}>vermelha</strong> onde perde. A linha tracejada mostra o resultado se você desfizer a posição antes, e a
        sombra cinza indica onde o preço tem mais chance de terminar.
      </p>

      {stats && (
        <div className="np-facts np-rule mb-3" style={{ '--np-columns': 5 } as CSSProperties}>
          <Stat label="Chance de lucro" value={formatRatio(stats.probabilityOfProfit, 0)} hint={`${horizonLabel[0].toUpperCase()}${horizonLabel.slice(1)}, pelo modelo`} />
          <Stat
            label="Chance do ganho máx."
            value={stats.probabilityOfMaxProfit !== null ? formatRatio(stats.probabilityOfMaxProfit, 0) : maxProfit === null ? 'Sem teto' : '—'}
          />
          <Stat
            label="Chance da perda máx."
            value={stats.probabilityOfMaxLoss !== null ? formatRatio(stats.probabilityOfMaxLoss, 0) : maxLoss === null ? 'Sem limite' : '—'}
          />
          <Stat
            label="Estimativa média"
            value={<Signed value={stats.expectedPnl}>{formatCurrency(stats.expectedPnl)}</Signed>}
            hint="Média de todos os cenários do modelo, antes dos custos"
          />
          <Stat
            label="Faixa provável"
            value={`${formatNumber(stats.range68[0])} a ${formatNumber(stats.range68[1])}`}
            hint="68% de chance de o ativo terminar aqui"
          />
        </div>
      )}
      {!stats && <p className="text-accent text-base mb-3">DADOS INSUFICIENTES: sem volatilidade para calcular as probabilidades.</p>}

      {focused && (
        <p role="status" className="mb-2 border-l-4 pl-2 text-base" style={{ borderColor: PALETA.FOCUS }}>
          Passo {highlight! + 1} de {ordered.length}: <strong>{focused.action === 'BUY' ? 'compre' : 'venda'}</strong>{' '}
          {formatNumber(focused.quantity, 0)} {focused.kind === 'CALL' ? 'call' : 'put'} de strike {formatCurrency(focused.strike)} a{' '}
          {formatCurrency(focused.premium)}.
        </p>
      )}
      <div
        className="h-[320px] cursor-crosshair"
        role="img"
        aria-label={`Resultado de ${formatLimit(-(maxLoss ?? 0))} a ${formatLimit(maxProfit)} conforme o preço de ${symbol} ${horizonLabel}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
            margin={{ top: 20, right: 8, bottom: 0, left: 0 }}
            onClick={(state) => {
              const label = Number(state?.activeLabel);
              if (Number.isFinite(label)) setTarget(label);
            }}
          >
            <CartesianGrid stroke={PALETA.RULE} vertical={false} />
            <XAxis
              dataKey="price"
              type="number"
              domain={[low, high]}
              stroke={PALETA.SECONDARY}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => value.toFixed(value < 20 ? 1 : 0)}
            />
            <YAxis yAxisId="pnl" stroke={PALETA.SECONDARY} fontSize={12} tickLine={false} axisLine={false} width={60} />
            <YAxis yAxisId="density" hide domain={[0, 'dataMax']} />
            <Area yAxisId="density" type="monotone" dataKey="density" stroke="none" fill={PALETA.SECONDARY} fillOpacity={0.12} isAnimationActive={false} />
            <Area yAxisId="pnl" type="linear" dataKey="gain" stroke="none" fill={PALETA.GAIN} fillOpacity={0.22} isAnimationActive={false} />
            <Area yAxisId="pnl" type="linear" dataKey="loss" stroke="none" fill={PALETA.LOSS} fillOpacity={0.18} isAnimationActive={false} />
            <ReferenceLine yAxisId="pnl" y={0} stroke={PALETA.SECONDARY} />
            {[...strikeSteps.entries()].map(([strike, steps]) => {
              const active = focused?.strike === strike;
              return (
                <ReferenceLine
                  key={strike}
                  yAxisId="pnl"
                  x={strike}
                  stroke={active ? PALETA.FOCUS : PALETA.RULE}
                  strokeWidth={active ? 3 : 1}
                  label={{ value: `${steps.join('·')} | ${formatNumber(strike)}`, fill: active ? PALETA.FOCUS : PALETA.SECONDARY, fontSize: active ? 12 : 10, position: 'insideBottom' }}
                />
              );
            })}
            {breakevens.map((value) => (
              <ReferenceLine key={value} yAxisId="pnl" x={value} stroke={PALETA.SECONDARY} strokeDasharray="2 3" />
            ))}
            <ReferenceLine yAxisId="pnl" x={spot} stroke={PALETA.SECONDARY} strokeDasharray="4 4" label={{ value: 'Hoje', fill: PALETA.SECONDARY, fontSize: 11, position: 'top' }} />
            <ReferenceLine yAxisId="pnl" x={clampedTarget} stroke={atTarget >= 0 ? PALETA.GAIN : PALETA.LOSS} strokeWidth={2} />
            <Line yAxisId="pnl" type="linear" dataKey="expiry" stroke={PALETA.INK} strokeWidth={2} dot={false} isAnimationActive={false} />
            {daysLeft > 0 && (
              <Line yAxisId="pnl" type="monotone" dataKey="simulated" stroke={PALETA.SECONDARY} strokeWidth={1.5} strokeDasharray="5 4" dot={false} isAnimationActive={false} connectNulls />
            )}
            <Tooltip
              contentStyle={{ backgroundColor: PALETA.PAPER, border: `1px solid ${PALETA.INK}`, borderRadius: 0 }}
              labelStyle={{ color: PALETA.SECONDARY }}
              itemStyle={{ color: PALETA.INK }}
              labelFormatter={(price) => `${symbol} a ${formatCurrency(Number(price))}`}
              formatter={(value, name) => {
                if (name === 'expiry') return [formatCurrency(Number(value)), horizonLabel[0].toUpperCase() + horizonLabel.slice(1)];
                if (name === 'simulated') return [formatCurrency(Number(value)), `Faltando ${daysLeft} dias`];
                return [null, null];
              }}
              filterNull
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <label className="np-label">
          {symbol} {horizonLabel}: {formatCurrency(clampedTarget)} ({move >= 0 ? '+' : ''}
          {formatNumber(move * 100, 1)}%)
          <input
            type="range"
            min={low}
            max={high}
            step={step}
            value={clampedTarget}
            onChange={(event) => setTarget(Number(event.target.value))}
            className="block w-full mt-1 accent-ink"
          />
        </label>
        <label className="np-label">
          Dias até o {multi ? 'vencimento curto' : 'vencimento'}: {daysLeft === totalDays ? `${daysLeft} (hoje)` : daysLeft}
          <input
            type="range"
            min={0}
            max={totalDays}
            step={1}
            value={daysLeft}
            onChange={(event) => setDaysLeft(Number(event.target.value))}
            className="block w-full mt-1 accent-ink"
          />
        </label>
        <label className="np-label">
          Volatilidade: {sigma !== null ? formatRatio(sigma, 0) : '—'} ({volPoints >= 0 ? '+' : ''}
          {volPoints} pontos)
          <input
            type="range"
            min={-20}
            max={20}
            step={1}
            value={volPoints}
            onChange={(event) => setVolPoints(Number(event.target.value))}
            className="block w-full mt-1 accent-ink"
          />
        </label>
      </div>

      <div role="status" className="mt-3 border-y border-ink py-2 text-base space-y-1">
        <p>
          Se {symbol} estiver em <strong>{formatCurrency(clampedTarget)}</strong> {horizonLabel}, o resultado é{' '}
          <strong>
            <Signed value={atTarget}>{formatCurrency(atTarget)}</Signed>
          </strong>
          .{chanceAbove !== null && ` Chance de estar acima desse preço: ${formatRatio(chanceAbove, 0)}.`}
        </p>
        {daysLeft > 0 && daysLeft < totalDays && simulatedAtTarget !== null && (
          <p>
            Desfazendo a posição faltando {daysLeft} dias, com o ativo nesse preço: cerca de{' '}
            <Signed value={simulatedAtTarget}>{formatCurrency(simulatedAtTarget)}</Signed> pelo modelo.
          </p>
        )}
      </div>
      <p className="font-display text-xs text-ink-2 mt-2">
        Breakeven: {breakevens.length ? breakevens.map((value) => formatCurrency(value)).join(' e ') : 'nenhum'}. Probabilidades neutras ao risco, com a
        vol das pernas: é o que os preços de hoje implicam, não uma previsão. A curva antes do vencimento usa Black-Scholes, aproximado para opções
        americanas.{multi && ' Na calendário e na diagonal, a perna longa é avaliada pelo modelo no vencimento curto, com a vol ajustada no controle: o ganho máximo é estimativa.'}{' '}
        Valores antes de custos e impostos.
      </p>
    </Panel>
  );
}
