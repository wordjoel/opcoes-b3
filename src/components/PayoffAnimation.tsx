/**
 * Payoff animado do Laboratório, construído com Remotion Player.
 *
 * Arquitetura: `PayoffScene` é uma cena pura (props + progresso), sem depender do
 * Runtime do Remotion; `PayoffComposition` só liga o `useCurrentFrame()` ao progresso.
 * Assim a mesma cena roda animada no navegador e estática em ambientes sem
 * `ResizeObserver` (testes). Os pontos vêm das marcações reais do backtest: a
 * animação revela a curva, nunca inventa resultado nem sugere operação.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Player, type PlayerRef } from '@remotion/player';
import { interpolate, useCurrentFrame } from 'remotion';
import { PALETA, useTemaVersao } from '../lib/tema';
import { formatCurrency, formatDay } from '../lib/utils';

export interface PayoffPoint {
  day: string;
  pnl: number;
}

interface PayoffSceneProps {
  points: PayoffPoint[];
  progress: number;
  colors: { ink: string; paper: string; secondary: string; grid: string; rule: string; gain: string; loss: string };
}

const WIDTH = 960;
const HEIGHT = 300;
const LEFT = 76;
const RIGHT = 18;
const TOP = 18;
const BOTTOM = 42;

function coordinates(points: PayoffPoint[], progress: number) {
  const values = points.map((point) => point.pnl);
  const high = Math.max(0, ...values);
  const low = Math.min(0, ...values);
  const span = high - low || 1;
  const plotWidth = WIDTH - LEFT - RIGHT;
  const plotHeight = HEIGHT - TOP - BOTTOM;
  const x = (index: number) => LEFT + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const y = (value: number) => TOP + ((high - value) / span) * plotHeight;
  const full = points.map((point, index) => ({ ...point, x: x(index), y: y(point.pnl) }));
  const visibleCount = Math.max(1, Math.ceil(full.length * Math.min(1, Math.max(0, progress))));
  const visible = full.slice(0, visibleCount);
  const cursor = visible[visible.length - 1];
  return { high, low, span, plotWidth, plotHeight, x, y, full, visible, cursor };
}

/** Cena pura: o mesmo desenho serve para o Player e para o fallback estático. */
export function PayoffScene({ points, progress, colors }: PayoffSceneProps) {
  if (points.length === 0) return null;
  const geo = coordinates(points, progress);
  const zeroY = geo.y(0);
  const label = geo.cursor ? formatDay(geo.cursor.day) : '';
  const value = geo.cursor ? formatCurrency(geo.cursor.pnl) : '';
  const stroke = geo.cursor && geo.cursor.pnl < 0 ? colors.loss : colors.gain;

  return (
    <div style={{ width: '100%', height: '100%', backgroundColor: colors.paper, color: colors.ink }}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label={`Evolução hipotética do payoff: ${points.length} pregões, último valor ${value}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const lineY = TOP + ratio * geo.plotHeight;
          const amount = geo.high - ratio * geo.span;
          return (
            <g key={ratio}>
              <line x1={LEFT} x2={WIDTH - RIGHT} y1={lineY} y2={lineY} stroke={colors.grid} strokeWidth="1" />
              <text x={LEFT - 10} y={lineY + 4} textAnchor="end" fontSize="12" fill={colors.secondary}>
                {formatCurrency(amount)}
              </text>
            </g>
          );
        })}
        <line x1={LEFT} x2={WIDTH - RIGHT} y1={zeroY} y2={zeroY} stroke={colors.rule} strokeWidth="1.5" />
        {points.length <= 8 &&
          points.map((point, index) => (
            <text key={point.day} x={geo.x(index)} y={HEIGHT - 14} textAnchor="middle" fontSize="11" fill={colors.secondary}>
              {formatDay(point.day).slice(0, 5)}
            </text>
          ))}
        <polyline
          points={geo.visible.map((point) => `${point.x},${point.y}`).join(' ')}
          fill="none"
          stroke={stroke}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {geo.visible.map((point) => (
          <circle key={point.day} cx={point.x} cy={point.y} r="3" fill={colors.paper} stroke={stroke} strokeWidth="2" />
        ))}
        {geo.cursor && <circle cx={geo.cursor.x} cy={geo.cursor.y} r="7" fill="none" stroke={colors.ink} strokeWidth="2" />}
        <text x={WIDTH - RIGHT} y={TOP + 12} textAnchor="end" fontSize="13" fontWeight="700" fill={colors.ink}>
          {label} · {value}
        </text>
      </svg>
    </div>
  );
}

type PayoffCompositionProps = {
  points: PayoffPoint[];
  colors: PayoffSceneProps['colors'];
};

function PayoffComposition({ points, colors }: PayoffCompositionProps) {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [0, 28], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return <PayoffScene points={points} progress={progress} colors={colors} />;
}

export interface PayoffAnimationProps {
  points: PayoffPoint[];
  /** Texto curto para o leitor de tela; o gráfico em si já tem aria-label. */
  description?: string;
}

export function PayoffAnimation({ points, description = 'Animação da evolução hipotética do resultado.' }: PayoffAnimationProps) {
  const versao = useTemaVersao();
  const colors = useMemo(
    () => ({
      ink: PALETA.INK,
      paper: PALETA.PAPER,
      secondary: PALETA.SECONDARY,
      grid: PALETA.GRID,
      rule: PALETA.RULE,
      gain: PALETA.GAIN,
      loss: PALETA.LOSS,
    }),
    // As cores vêm de CSS; a versão do tema força a releitura.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [versao],
  );
  const animation = useMemo(() => (points.length >= 2 && typeof ResizeObserver !== 'undefined'), [points.length]);
  const player = useRef<PlayerRef>(null);
  const [playing, setPlaying] = useState(false);
  const [frame, setFrame] = useState(0);
  const duration = 60;

  useEffect(() => {
    if (!animation || !player.current) return;
    const current = player.current;
    const update = (event: { frame: number }) => setFrame(event.frame);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    current.addEventListener('frameupdate', update);
    current.addEventListener('play', onPlay);
    current.addEventListener('pause', onPause);
    current.addEventListener('ended', onPause);
    return () => {
      current.removeEventListener('frameupdate', update);
      current.removeEventListener('play', onPlay);
      current.removeEventListener('pause', onPause);
      current.removeEventListener('ended', onPause);
    };
  }, [animation]);

  const toggle = () => {
    const current = player.current;
    if (!current) return;
    if (current.isPlaying()) current.pause();
    else {
      if (current.getCurrentFrame() >= duration - 1) current.seekTo(0);
      current.play();
    }
  };

  return (
    <div className="space-y-2">
      <div className="h-[260px] w-full border border-[var(--dp-color-rule)]" data-testid="payoff-animation">
        {animation ? (
          <Player
            ref={player}
            component={PayoffComposition}
            inputProps={{ points, colors }}
            durationInFrames={duration}
            compositionWidth={WIDTH}
            compositionHeight={HEIGHT}
            fps={30}
            style={{ width: '100%', height: '100%' }}
            controls={false}
            loop={false}
            clickToPlay={false}
            doubleClickToFullscreen={false}
            spaceKeyToPlayOrPause={false}
            acknowledgeRemotionLicense
          />
        ) : (
          <PayoffScene points={points} progress={1} colors={colors} />
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {animation && (
          <button type="button" className="np-btn" onClick={toggle} aria-label={playing ? 'Pausar animação do payoff' : 'Reproduzir animação do payoff'}>
            {playing ? 'Pausar' : 'Reproduzir'}
          </button>
        )}
        <p className="np-note" aria-live="polite">
          {description} {animation ? `Quadro ${Math.min(frame + 1, duration)} de ${duration}.` : 'Animação indisponível neste ambiente; curva completa.'}
        </p>
      </div>
    </div>
  );
}
