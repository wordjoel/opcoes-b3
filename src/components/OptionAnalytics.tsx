import { useMemo } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Candidate, ChainView } from '../types';
import { cn, formatChange, formatCompact, formatCurrency, formatNumber, formatRatio } from '../lib/utils';
import { Panel } from './Common';

/** Sensibilidade hoje: número sempre visível, para a leitura não depender só da cor. */
export function PnlHeatmap({ heatmap }: { heatmap: NonNullable<Candidate['heatmap']> }) {
  const largest = Math.max(1, ...heatmap.pnl.flat().map(Math.abs));
  const shade = (value: number) => {
    const alpha = 0.08 + 0.55 * (Math.abs(value) / largest);
    return Math.abs(value) < 0.5 ? undefined : value > 0 ? `rgba(2, 132, 199, ${alpha})` : `rgba(220, 38, 38, ${alpha})`;
  };
  return (
    <Panel title="Resultado hoje por preço do ativo e vol implícita (R$)" className="overflow-x-auto">
      <table className="w-full text-xs font-mono min-w-[560px] border-separate border-spacing-0.5">
        <thead className="text-slate-400">
          <tr>
            <th scope="col" className="text-left font-semibold font-sans p-1">Vol \ Ativo</th>
            {heatmap.spot_shocks.map((shock) => (
              <th key={shock} scope="col" className="text-right font-semibold p-1">
                {formatChange(shock * 100).replace(',00', '')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {heatmap.vol_shocks.map((shock, row) => (
            <tr key={shock}>
              <th scope="row" className="text-left font-semibold text-slate-400 p-1 whitespace-nowrap">
                {shock === 0 ? 'Atual' : `${shock > 0 ? '+' : ''}${Math.round(shock * 100)} pts`}
              </th>
              {heatmap.pnl[row].map((value, column) => (
                <td key={column} className="text-right text-slate-100 p-1 rounded-sm" style={{ backgroundColor: shade(value) }}>
                  {formatNumber(Math.round(value) || 0, 0)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-slate-400 mt-2">
        Modelo europeu, com a vol implícita de cada perna e os prêmios de montagem. Não é resultado no vencimento.
      </p>
    </Panel>
  );
}

export function OpenInterestPanel({ summary }: { summary: ChainView['open_interest'] }) {
  const change = (value: number | null) =>
    value === null ? 'variação não informada' : `${value > 0 ? '+' : ''}${formatCompact(value)} no pregão`;
  return (
    <Panel title="Contratos em aberto neste vencimento">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-slate-400">Calls</p>
          <p className="text-xl font-bold text-white">{formatCompact(summary.calls)}</p>
          <p className="text-xs text-slate-400">{change(summary.calls_change)}</p>
        </div>
        <div>
          <p className="text-slate-400">Puts</p>
          <p className="text-xl font-bold text-white">{formatCompact(summary.puts)}</p>
          <p className="text-xs text-slate-400">{change(summary.puts_change)}</p>
        </div>
        <div>
          <p className="text-slate-400">Puts por call</p>
          <p className="text-xl font-bold text-white">{formatNumber(summary.put_call_ratio)}</p>
        </div>
      </div>
      <p className="text-xs text-slate-400 mt-3">A variação mostra quanto mudou, não quem abriu ou fechou posição.</p>
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
      <div className={cn('h-[260px]')}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 16, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#1E293B" vertical={false} />
            <XAxis
              dataKey="strike"
              type="number"
              domain={['dataMin', 'dataMax']}
              stroke="#64748B"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => value.toFixed(0)}
            />
            <YAxis
              stroke="#64748B"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              width={48}
              domain={['auto', 'auto']}
              tickFormatter={(value: number) => formatRatio(value, 0)}
            />
            <ReferenceLine
              x={chain.spot}
              stroke="#94A3B8"
              strokeDasharray="4 4"
              label={{ value: 'Ativo na grade', fill: '#CBD5E1', fontSize: 11, position: 'top' }}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#0F172A', border: '1px solid #334155', borderRadius: 8 }}
              labelStyle={{ color: '#CBD5E1' }}
              itemStyle={{ color: '#F8FAFC' }}
              labelFormatter={(strike) => `Strike ${formatCurrency(Number(strike))}`}
              formatter={(value, name) => [formatRatio(Number(value)), name]}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: '#CBD5E1' }} />
            <Line name="Call" dataKey="call" stroke="#0284C7" strokeWidth={2} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
            <Line name="Put" dataKey="put" stroke="#D97706" strokeWidth={2} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-slate-400 mt-2">
        Séries negociadas no pregão. Cada ponto vem do último negócio da série, e os horários podem ser diferentes.
      </p>
    </Panel>
  );
}
