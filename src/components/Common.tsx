import { AlertTriangle, Loader2 } from 'lucide-react';
import { ReactNode } from 'react';
import { ApiError } from '../services/api';
import { cn } from '../lib/utils';

export function Loading({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-3 p-6 text-sm text-slate-400">
      <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
      {label}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-sm text-amber-100">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 shrink-0 text-amber-400" />
        <div className="min-w-0">
          {error.label && <p className="font-bold text-amber-300">{error.label}</p>}
          <p>{error.message}</p>
          {error.reasons.length > 0 && (
            <ul className="mt-2 list-disc pl-4 text-amber-200/80">
              {error.reasons.slice(0, 5).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
          {onRetry && (
            <button onClick={onRetry} className="mt-3 text-xs font-bold text-sky-300 hover:underline">
              Tentar de novo
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="bg-slate-900 p-4 rounded-2xl border border-slate-800 min-w-0">
      <p className="text-[11px] uppercase font-semibold text-slate-400 tracking-wider">{label}</p>
      <p className="text-xl font-bold text-white mt-1 truncate">{value}</p>
      {hint && <p className="text-xs text-slate-500 mt-1">{hint}</p>}
    </div>
  );
}

export function Panel({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn('bg-slate-900 rounded-2xl border border-slate-800 p-4 md:p-6', className)}>
      {title && <h3 className="text-sm font-bold text-white mb-4">{title}</h3>}
      {children}
    </section>
  );
}

export function Signed({ value, children }: { value: number | null | undefined; children: ReactNode }) {
  return (
    <span className={cn(value === null || value === undefined ? 'text-slate-400' : value >= 0 ? 'text-emerald-400' : 'text-red-400')}>
      {children}
    </span>
  );
}
