import { ReactNode } from 'react';
import { ApiError } from '../services/api';
import { cn, formatMoment } from '../lib/utils';
import { DataStatus as Status } from '../types';

export function Loading({ label }: { label: string }) {
  return (
    <p role="status" className="np-note py-6">
      {label}
    </p>
  );
}

export function ErrorNotice({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" className="border-y border-accent py-3">
      {error.label && <p className="np-label !text-accent">{error.label}</p>}
      <p>{error.message}</p>
      {error.reasons.length > 0 && (
        <ul className="mt-2 list-disc pl-5 np-note">
          {error.reasons.slice(0, 5).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
      {onRetry && (
        <button onClick={onRetry} className="np-btn mt-3">
          Tentar de novo
        </button>
      )}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div>
      <p className="np-label">{label}</p>
      <p className="font-display text-2xl font-black mt-1 break-words">{value}</p>
      {hint && <p className="font-display text-xs text-ink-2 mt-1">{hint}</p>}
    </div>
  );
}

export function Panel({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn('np-section', className)}>
      {title && <h3 className="text-xl mb-3">{title}</h3>}
      {children}
    </section>
  );
}

/** O sinal acompanha o valor: a leitura não depende só da cor. */
export function Signed({ value, children }: { value: number | null | undefined; children: ReactNode }) {
  return <span className={cn(value !== null && value !== undefined && value < 0 ? 'text-accent' : 'text-ink')}>{children}</span>;
}

const STATUS: Record<Status, { label: string; hint: string; className: string }> = {
  REAL: { label: 'Real', hint: 'Cotação dentro da janela de atraso da fonte', className: 'border-ink text-ink' },
  ATRASADO: { label: 'Atrasado', hint: 'Última cotação com mais de 20 minutos', className: 'border-accent text-accent' },
  INCOMPLETO: { label: 'Incompleto', hint: 'Parte dos dados não veio da fonte', className: 'border-accent text-accent' },
  INDISPONIVEL: { label: 'Indisponível', hint: 'A fonte não entregou este dado', className: 'border-rule text-ink-2' },
};

export function DataStatusBadge({ status, source, at }: { status: Status; source?: string | null; at?: string | null }) {
  const info = STATUS[status];
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      <span title={info.hint} className={cn('np-label border px-1.5 py-0.5 !text-[inherit]', info.className)}>
        {info.label}
      </span>
      {source && <span className="font-display text-xs text-ink-2">Fonte: {source}</span>}
      {at && <span className="font-display text-xs text-ink-2">Mercado: {formatMoment(at)}</span>}
    </span>
  );
}
