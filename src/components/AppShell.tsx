/**
 * Shell único para Web e PWA: sidebar no desktop, barra inferior no celular.
 * A navegação é adaptada por largura de tela; as telas e regras são as mesmas.
 * Cores vêm dos tokens --dp-*, então o tema claro/escuro continua funcionando.
 */
import { type ComponentType, type ReactNode, useState } from 'react';
import { Bell, FlaskConical, LayoutDashboard, Layers, Menu, Radar, Wallet, X } from 'lucide-react';
import { cn } from '../lib/utils';
import { Masthead } from './Masthead';

interface NavItem {
  id: string;
  label: string;
  short: string;
  icon: ComponentType<{ className?: string }>;
}

/** As seis seções já implementadas. Módulos sem backend real não entram aqui. */
export const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Monitor', short: 'Início', icon: LayoutDashboard },
  { id: 'scanner', label: 'Scanner B3', short: 'Scanner', icon: Radar },
  { id: 'strategy', label: 'Estratégias', short: 'Travas', icon: Layers },
  { id: 'alerts', label: 'Alertas', short: 'Avisos', icon: Bell },
  { id: 'lab', label: 'Laboratório', short: 'Laboratório', icon: FlaskConical },
  { id: 'carteira', label: 'Carteira', short: 'Carteira', icon: Wallet },
];

const MOBILE_PRIMARY = ['dashboard', 'scanner', 'strategy', 'carteira'];

interface AppShellProps {
  activeTab: string;
  onTab: (tab: string) => void;
  alertCount: number;
  onLogout: () => void;
  children: ReactNode;
}

export function AppShell({ activeTab, onTab, alertCount, onLogout, children }: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const current = NAV_ITEMS.find((item) => item.id === activeTab) ?? NAV_ITEMS[0];

  const select = (id: string) => {
    onTab(id);
    setDrawerOpen(false);
  };

  const goToJarbas = () => {
    document.getElementById('jarbas')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="min-h-screen bg-[var(--dp-color-ground)] text-[var(--dp-color-ink)] flex">
      <aside
        aria-label="Navegação principal"
        className="hidden lg:flex lg:w-64 lg:shrink-0 lg:flex-col lg:fixed lg:inset-y-0 border-r border-[var(--dp-color-rule)] bg-[var(--dp-color-ground)]"
      >
        <div className="flex h-16 items-center border-b border-[var(--dp-color-rule)] px-5">
          <button
            type="button"
            onClick={() => select('dashboard')}
            aria-label="Ir para o monitor"
            className="text-left font-display text-base font-bold tracking-tight"
          >
            B3 Opções Pro
          </button>
        </div>
        <nav aria-label="Seções" className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                aria-current={active ? 'page' : undefined}
                onClick={() => select(item.id)}
                className={cn(
                  'flex w-full items-center gap-3 border px-3 py-2.5 text-left font-display text-sm min-h-10',
                  active
                    ? 'border-[var(--dp-color-ink)] bg-[var(--dp-color-highlight)] text-[var(--dp-color-ink)]'
                    : 'border-transparent hover:bg-[var(--dp-color-hover)]',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
                {item.id === 'alerts' && alertCount > 0 && (
                  <span className="ml-auto" aria-label={`${alertCount} alertas`}>({alertCount})</span>
                )}
              </button>
            );
          })}
        </nav>
        <p className="np-note border-t border-[var(--dp-color-rule)] px-5 py-4">
          Análise e decisão. Este app não envia ordens.
        </p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <Masthead
          title={current.label}
          onLogout={onLogout}
          onOpenMenu={() => setDrawerOpen(true)}
          onOpenJarbas={goToJarbas}
        />
        <div className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-4 pb-24 lg:px-8 lg:py-8 lg:pb-8">
          {children}
        </div>
      </div>

      <nav
        aria-label="Navegação móvel inferior"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--dp-color-rule)] bg-[var(--dp-color-ground)] lg:hidden"
      >
        <div className="mx-auto grid max-w-[1400px] grid-cols-5">
          {MOBILE_PRIMARY.map((id) => {
            const item = NAV_ITEMS.find((candidate) => candidate.id === id)!;
            const Icon = item.icon;
            const active = activeTab === id;
            return (
              <button
                key={id}
                type="button"
                aria-label={`${item.label} (menu inferior)`}
                aria-current={active ? 'page' : undefined}
                onClick={() => select(id)}
                className={cn(
                  'flex min-h-14 flex-col items-center justify-center gap-1 border-t-2 px-1 py-1.5 font-display text-[11px]',
                  active
                    ? 'border-[var(--dp-color-ink)] text-[var(--dp-color-ink)]'
                    : 'border-transparent text-[var(--dp-color-secondary)]',
                )}
              >
                <Icon className="h-5 w-5" />
                <span className="leading-none">{item.short}</span>
              </button>
            );
          })}
          <button
            type="button"
            aria-label="Todos os módulos (menu inferior)"
            onClick={() => setDrawerOpen(true)}
            className={cn(
              'flex min-h-14 flex-col items-center justify-center gap-1 border-t-2 px-1 py-1.5 font-display text-[11px]',
              drawerOpen ? 'border-[var(--dp-color-ink)]' : 'border-transparent text-[var(--dp-color-secondary)]',
            )}
          >
            <Menu className="h-5 w-5" />
            <span className="leading-none">Módulos</span>
          </button>
        </div>
      </nav>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/60 lg:hidden" onClick={() => setDrawerOpen(false)}>
          <div
            role="dialog"
            aria-label="Todos os módulos"
            aria-modal="true"
            className="max-h-[82vh] w-full overflow-y-auto border-t border-[var(--dp-color-rule)] bg-[var(--dp-color-ground)] p-5 pb-8"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mx-auto mb-4 h-1.5 w-10 rounded bg-[var(--dp-color-rule)]" />
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-xl">Todos os módulos</h2>
              <button className="np-btn" onClick={() => setDrawerOpen(false)} aria-label="Fechar menu">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-current={active ? 'page' : undefined}
                    onClick={() => select(item.id)}
                    className={cn(
                      'flex min-h-12 items-center gap-2 border p-3 text-left text-sm',
                      active
                        ? 'border-[var(--dp-color-ink)] bg-[var(--dp-color-highlight)]'
                        : 'border-[var(--dp-color-rule)] hover:bg-[var(--dp-color-hover)]',
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="leading-tight">{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
