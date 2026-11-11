import { PALETA } from '../lib/tema';
import { type CSSProperties, useMemo } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Candidate, ChainView } from '../types';
import { formatChange, formatCompact, formatCurrency, formatNumber, formatRatio } from '../lib/utils';
import { Panel, Stat } from './Common';


/** Sensibilidade hoje: número com sinal sempre visível, para a leitura não depender só da cor. */
export function PnlHeatmap({ heatmap }: { heatmap: NonNullable<Candidate['heatmap']> }) {
  const largest = Math.max(1, ...heatmap.pnl.flat().map(Math.abs));
  const shade = (value: number) => {
    const share = Math.abs(value) / largest;
    if (Math.abs(value) < 0.5) return undefined;
    return value > 0 ? `rgba(25, 25, 22, ${0.05 + 0.2 * share})` : `rgba(163, 35, 29, ${0.08 + 0.3 * share})`;
  };
  return (
    <Panel title="Resultado hoje por preço do ativo e vol implícita (R$)" className="overflow-x-auto">
      <table className="np-table min-w-[560px]">
        <thead>
          <tr>
            <th scope="col" className="text-left">Vol \ Ativo</th>
            {heatmap.spot_shocks.map((shock) => (
              <th key={shock} scope="col" className="text-right">
                {formatChange(shock * 100).replace(',00', '')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {heatmap.vol_shocks.map((shock, row) => (
            <tr key={shock}>
              <th scope="row" className="text-left whitespace-nowrap !border-b-rule">
                {shock === 0 ? 'Atual' : `${shock > 0 ? '+' : ''}${Math.round(shock * 100)} pts`}
              </th>
              {heatmap.pnl[row].map((value, column) => {
                const rounded = Math.round(value) || 0;
                return (
                  <td key={column} className="text-right" style={{ backgroundColor: shade(value) }}>
                    {rounded > 0 ? '+' : ''}
                    {formatNumber(rounded, 0)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="font-display text-xs text-ink-2 mt-2">
        Árvore binomial nas pernas americanas e Black-Scholes nas europeias, com a vol implícita de cada perna e os prêmios de montagem. Não é resultado no vencimento.
      </p>
    </Panel>
  );
}

export function OpenInterestPanel({ summary }: { summary: ChainView['open_interest'] }) {
  const change = (value: number | null) =>
    value === null ? 'variação não informada' : `${value > 0 ? '+' : ''}${formatCompact(value)} no pregão`;
  return (
    <Panel title="Contratos em aberto neste vencimento">
      <div className="np-facts" style={{ '--np-columns': 3 } as CSSProperties}>
        <Stat label="Calls" value={formatCompact(summary.calls)} hint={change(summary.calls_change)} />
        <Stat label="Puts" value={formatCompact(summary.puts)} hint={change(summary.puts_change)} />
        <Stat label="Puts por call" value={formatNumber(summary.put_call_ratio)} />
      </div>
      <p className="font-display text-xs text-ink-2 mt-2">A variação mostra quanto mudou, não quem abriu ou fechou posição.</p>
    </Panel>
  );
}

export function SkewChart({ chain }: { chain: ChainView }) {
  const data = useMemo(() => {
    const byStrike = new Map<number, { strike: number; call?: number; put?: number }>();
    for (const quote of chain.quotes) {
      if (!quote.usable || !quote.iv || Math.abs(quote.strike / chain.spot - 1) > 0.15) continue;
      const row = byStrike.get(quote.strike) ?? { strike: quote.strike };
      row[quote.kind === 'CALL' ? 'call' : 'put'] = quote.iv;
      byStrike.set(quote.strike, row);
    }
    return [...byStrike.values()].sort((a, b) => a.strike - b.strike);
  }, [chain]);
  if (data.length < 3) return null;

  return (
    <Panel title="Vol implícita por strike">
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 16, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={PALETA.GRID} vertical={false} />
            <XAxis
              dataKey="strike"
              type="number"
              domain={['dataMin', 'dataMax']}
              stroke={PALETA.SECONDARY}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => value.toFixed(0)}
            />
            <YAxis
              stroke={PALETA.SECONDARY}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              width={48}
              domain={['auto', 'auto']}
              tickFormatter={(value: number) => formatRatio(value, 0)}
            />
            <ReferenceLine
              x={chain.spot}
              stroke={PALETA.SECONDARY}
              strokeDasharray="4 4"
              label={{ value: 'Ativo na grade', fill: PALETA.SECONDARY, fontSize: 11, position: 'top' }}
            />
            <Tooltip
              contentStyle={{ backgroundColor: PALETA.PAPER, border: `1px solid ${PALETA.INK}`, borderRadius: 0 }}
              labelStyle={{ color: PALETA.SECONDARY }}
              itemStyle={{ color: PALETA.INK }}
              labelFormatter={(strike) => `Strike ${formatCurrency(Number(strike))}`}
              formatter={(value, name) => [formatRatio(Number(value)), name]}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: PALETA.SECONDARY }} />
            <Line name="Call" dataKey="call" stroke={PALETA.INK} strokeWidth={2} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
            <Line name="Put" dataKey="put" stroke={PALETA.ACCENT} strokeWidth={2} strokeDasharray="5 3" dot={{ r: 2 }} connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="font-display text-xs text-ink-2 mt-2">
        Séries negociadas no pregão. Cada ponto vem do último negócio da série, e os horários podem ser diferentes.
      </p>
    </Panel>
  );
}
