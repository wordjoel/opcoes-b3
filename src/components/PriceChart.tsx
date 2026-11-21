import { PALETA, useTemaVersao } from '../lib/tema';
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  createSeriesMarkers,
  LineSeries,
  LineStyle,
} from 'lightweight-charts';
import { useEffect, useRef } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AssetOverview, MarketStructure } from '../types';
import { formatDay, formatRatio } from '../lib/utils';

type Bars = AssetOverview['history'];


export function PriceChart({ bars, structure }: { bars: Bars; structure: MarketStructure | null }) {
  const container = useRef<HTMLDivElement>(null);

  const versao = useTemaVersao();
  useEffect(() => {
    if (!container.current) return;
    const chart = createChart(container.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: PALETA.SECONDARY,
        fontSize: 12,
        fontFamily: 'Source Serif 4, Georgia, serif',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: PALETA.GRID, style: LineStyle.Dotted },
      },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.12 } },
      timeScale: {
        borderVisible: false,
        barSpacing: 10,
        minBarSpacing: 3,
        rightOffset: 3,
        timeVisible: false,
        secondsVisible: false,
      },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: { color: PALETA.RULE, style: LineStyle.Dotted, labelBackgroundColor: PALETA.INK },
        horzLine: { color: PALETA.RULE, style: LineStyle.Dotted, labelBackgroundColor: PALETA.INK },
      },
      localization: { locale: 'pt-BR' },
    });
    // Alta em verde, baixa em vermelho. Mesma cor em corpo, pavio e borda para leitura imediata.
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: PALETA.CANDLE_UP,
      downColor: PALETA.CANDLE_DOWN,
      wickUpColor: PALETA.CANDLE_UP,
      wickDownColor: PALETA.CANDLE_DOWN,
      borderVisible: true,
      borderUpColor: PALETA.CANDLE_UP,
      borderDownColor: PALETA.CANDLE_DOWN,
    });
    candles.setData(bars.map((bar) => ({ time: bar.day, open: bar.open, high: bar.high, low: bar.low, close: bar.close })));
    if (structure) {
      createSeriesMarkers(
        candles,
        structure.events.map((event) => ({
          time: event.day,
          position: event.direction === 'UP' ? ('belowBar' as const) : ('aboveBar' as const),
          shape: event.direction === 'UP' ? ('arrowUp' as const) : ('arrowDown' as const),
          color: PALETA.ACCENT,
          text: event.kind === 'CHOCH' ? 'CHoCH' : 'BOS',
        })),
      );
      const level = (price: number | null, title: string) => {
        if (price !== null) {
          candles.createPriceLine({ price, title, color: PALETA.SECONDARY, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: true });
        }
      };
      level(structure.last_swing_high, 'Topo');
      level(structure.last_swing_low, 'Fundo');
    }

    const band = { color: PALETA.RULE, lineWidth: 1, priceLineVisible: false, lastValueVisible: false } as const;
    const line = (pick: (bar: Bars[number]) => number | null, style: LineStyle) =>
      chart.addSeries(LineSeries, { ...band, lineStyle: style }).setData(
        bars.flatMap((bar) => {
          const value = pick(bar);
          return value === null ? [] : [{ time: bar.day, value }];
        }),
      );
    line((bar) => bar.bb_upper, LineStyle.Dashed);
    line((bar) => bar.bb_middle, LineStyle.Solid);
    line((bar) => bar.bb_lower, LineStyle.Dashed);
    // Começa com os últimos ~70 pregões em destaque; o usuário pode dar zoom out para ver o resto.
    if (bars.length > 0) {
      const inicio = Math.max(0, bars.length - 70);
      chart.timeScale().setVisibleLogicalRange({ from: inicio, to: bars.length + 3 });
    } else {
      chart.timeScale().fitContent();
    }
    return () => chart.remove();
  }, [bars, structure, versao]);

  return (
    <div>
      <div ref={container} className="h-[420px]" />
      <p className="flex flex-wrap gap-x-4 gap-y-1 font-display text-xs text-ink-2 mt-2">
        <span>
          Candle diário, preço ajustado: <span className="text-[var(--dp-color-candle-up)]">verde sobe</span>,{' '}
          <span className="text-[var(--dp-color-candle-down)]">vermelho cai</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="w-4 border-t border-dashed border-rule" /> Bollinger de 20 dias e 2 desvios
        </span>
        <span>BOS: rompeu a favor da tendência. CHoCH: rompeu contra. Leitura de barras diárias.</span>
      </p>
    </div>
  );
}

export function HvChart({ bars }: { bars: Bars }) {
  const data = bars.filter((bar) => bar.hv_20d !== null);
  if (data.length === 0) return null;
  return (
    <div className="np-rule pt-3">
      <h4 className="text-base mb-2">Volatilidade histórica de 20 dias</h4>
      <div className="h-[140px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={PALETA.GRID} vertical={false} />
            <XAxis
              dataKey="day"
              stroke={PALETA.SECONDARY}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              minTickGap={48}
              tickFormatter={(day: string) => formatDay(day).slice(0, 5)}
            />
            <YAxis
              stroke={PALETA.SECONDARY}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(value: number) => formatRatio(value, 0)}
            />
            <Tooltip
              contentStyle={{ backgroundColor: PALETA.PAPER, border: `1px solid ${PALETA.INK}`, borderRadius: 0 }}
              labelStyle={{ color: PALETA.SECONDARY }}
              itemStyle={{ color: PALETA.INK }}
              labelFormatter={(day) => formatDay(String(day))}
              formatter={(value) => [formatRatio(Number(value)), 'Vol 20 dias']}
            />
            <Line type="linear" dataKey="hv_20d" stroke={PALETA.INK} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
