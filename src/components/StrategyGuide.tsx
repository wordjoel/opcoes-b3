import { AssemblyLeg, assemblySteps, guideOf, VIEW_LABEL } from '../lib/strategyGuide';
import { cn, formatCurrency, formatDay, formatNumber } from '../lib/utils';
import { startTour, stopTour, useJarbasState } from '../lib/jarbasStore';
import { Panel } from './Common';

interface GuideItem {
  key: string;
  family?: string;
  net_premium: number;
  legs: AssemblyLeg[];
}

export function StrategyGuideCard({ item }: { item: GuideItem }) {
  const guide = guideOf(item);
  const steps = assemblySteps(item.legs);
  const credit = item.net_premium < 0;
  const { highlight } = useJarbasState();

  return (
    <Panel title="Como funciona">
      {guide && (
        <>
          <p className="flex flex-wrap gap-2 mb-3">
            <span className="np-label border border-ink px-1.5 py-0.5">Para quem espera: {VIEW_LABEL[guide.view]}</span>
            <span className="np-label border border-rule px-1.5 py-0.5">Nível: {guide.level}</span>
          </p>
          <dl className="grid gap-3 md:grid-cols-2 text-base">
            <div>
              <dt className="np-label">O que é</dt>
              <dd className="mt-1">{guide.whatIs}</dd>
            </div>
            <div>
              <dt className="np-label">Cuidado</dt>
              <dd className="mt-1">{guide.careful}</dd>
            </div>
            <div>
              <dt className="np-label" style={{ color: '#2f6b3a' }}>
                Quando ganha
              </dt>
              <dd className="mt-1">{guide.wins}</dd>
            </div>
            <div>
              <dt className="np-label !text-accent">Quando perde</dt>
              <dd className="mt-1">{guide.loses}</dd>
            </div>
          </dl>
        </>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 mt-4 mb-2">
        <h4 className="text-lg">Montagem passo a passo</h4>
        <button className="np-btn" onClick={() => (highlight === null ? startTour(steps.length) : stopTour())}>
          {highlight === null ? 'Ver montagem no gráfico' : 'Parar demonstração'}
        </button>
      </div>
      <ol className="space-y-2">
        {steps.map(({ leg, cash, role }, index) => (
          <li
            key={`${leg.symbol}-${leg.action}`}
            className={cn('flex gap-3 np-rule pt-2 transition-colors', highlight === index && 'bg-[#dfe7f2] outline outline-2 outline-[#1f4e8c]')}
            aria-current={highlight === index ? 'step' : undefined}
          >
            <span className="font-display font-black text-2xl leading-none w-6 shrink-0">{index + 1}</span>
            <div className="min-w-0">
              <p className="text-base">
                <strong>{leg.action === 'BUY' ? 'Compre' : 'Venda'}</strong> {formatNumber(leg.quantity, 0)} <strong>{leg.symbol}</strong> (
                {leg.kind === 'CALL' ? 'call' : 'put'}, strike {formatCurrency(leg.strike)}{leg.expiry ? `, vence ${formatDay(leg.expiry)}` : ''}) a {formatCurrency(leg.premium)} cada:{' '}
                {cash >= 0 ? (
                  <>você paga {formatCurrency(cash)}</>
                ) : (
                  <span style={{ color: '#2f6b3a' }}>você recebe {formatCurrency(-cash)}</span>
                )}
                .
              </p>
              <p className="font-display text-xs text-ink-2 mt-0.5">{role}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-3 border-y border-ink py-2 text-base">
        Ao final da montagem: <strong>{credit ? `crédito de ${formatCurrency(-item.net_premium)}` : `débito de ${formatCurrency(item.net_premium)}`}</strong>{' '}
        {credit ? '(entra na sua conta).' : '(sai da sua conta).'} Comece pelas compras para nunca ficar com uma venda descoberta.
      </p>
      <p className="font-display text-xs text-ink-2 mt-2">
        Você monta na sua corretora; o app não envia ordens. Os preços são do fechamento: confira o livro antes de enviar.
      </p>
    </Panel>
  );
}
