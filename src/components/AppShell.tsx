/**
 * Shell único para Web e PWA: sidebar no desktop, barra inferior no celular.
 * A navegação é adaptada por largura de tela; as telas e regras são as mesmas.
 * Cores vêm dos tokens --dp-*, então o tema claro/escuro continua funcionando.
 */
import { type ComponentType, type MouseEvent, type ReactNode, useEffect, useRef, useState } from 'react';
import { Bell, FlaskConical, LayoutDashboard, Layers, Menu, Radar, Wallet, X } from 'lucide-react';
import { cn } from '../lib/utils';
import { requestJarbasFocus } from '../lib/jarbasStore';
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

/** Agrupamento visual inspirado na referência, sem criar telas sem backend. */
const NAV_GROUPS = [
  { title: 'Mercado', ids: ['dashboard', 'scanner'] },
  { title: 'Análise', ids: ['strategy', 'alerts'] },
  { title: 'Operação', ids: ['lab', 'carteira'] },
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
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const current = NAV_ITEMS.find((item) => item.id === activeTab) ?? NAV_ITEMS[0];

  const openDrawer = (event?: MouseEvent<HTMLElement>) => {
    openerRef.current = event?.currentTarget ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    setDrawerOpen(true);
  };

  const closeDrawer = () => setDrawerOpen(false);

  // O drawer é um diálogo modal: foco inicial, Escape e Tab preso dentro dele.
  useEffect(() => {
    if (!drawerOpen) return;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeDrawer();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusables: HTMLElement[] = Array.from(
        drawerRef.current?.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])') ?? [],
      );
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const inside = drawerRef.current?.contains(document.activeElement);
      if (event.shiftKey && (document.activeElement === first || !inside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !inside)) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [drawerOpen]);

  // Ao fechar, o foco volta para quem abriu o menu.
  useEffect(() => {
    if (drawerOpen) return;
    openerRef.current?.focus();
    openerRef.current = null;
  }, [drawerOpen]);

  const select = (id: string) => {
    onTab(id);
    closeDrawer();
  };

  const goToJarbas = () => {
    document.getElementById('jarbas')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
    requestJarbasFocus();
  };

  const navButton = (item: NavItem, compact: boolean) => {
    const Icon = item.icon;
    const active = activeTab === item.id;
    return (
      <button
        key={item.id}
        type="button"
        aria-current={active ? 'page' : undefined}
        onClick={() => select(item.id)}
        className={cn(
          'flex w-full items-center gap-3 border text-left font-display text-sm min-h-10',
          compact ? 'p-3' : 'px-3 py-2.5',
          'rounded-xl transition-colors',
          active
            ? 'border-[var(--dp-color-accent)] bg-[var(--dp-color-highlight)] text-[var(--dp-color-accent)]'
            : 'border-transparent text-[var(--dp-color-secondary)] hover:bg-[var(--dp-color-hover)] hover:text-[var(--dp-color-ink)]',
        )}
      >
        <Icon className={cn('h-4 w-4 shrink-0', active ? 'text-[var(--dp-color-accent)]' : 'text-[var(--dp-color-secondary)]')} />
        <span className="truncate">{item.label}</span>
        {item.id === 'alerts' && alertCount > 0 && (
          <span className="ml-auto">
            <span className="sr-only">{alertCount} alertas</span>
            <span aria-hidden="true">({alertCount})</span>
          </span>
        )}
      </button>
    );
  };

  return (
    <div className="min-h-screen bg-[var(--dp-color-ground)] text-[var(--dp-color-ink)] flex">
      <a
        href="#conteudo-principal"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-xl focus:bg-[var(--dp-color-accent)] focus:px-4 focus:py-2 focus:font-display focus:text-sm focus:text-[var(--dp-color-ground)]"
      >
        Ir para o conteúdo principal
      </a>
      <aside
        aria-label="Navegação principal"
        className="hidden lg:flex lg:w-64 lg:shrink-0 lg:flex-col lg:fixed lg:inset-y-0 border-r border-[var(--dp-color-rule)] bg-[var(--dp-color-panel)]"
      >
        <div className="flex h-16 items-center gap-3 border-b border-[var(--dp-color-rule)] px-5">
          <img src="/icon.svg" alt="" className="h-8 w-8 shrink-0 rounded-lg" aria-hidden="true" />
          <button
            type="button"
            onClick={() => select('dashboard')}
            aria-label="Ir para o monitor"
            className="truncate text-left font-display text-base font-bold tracking-tight"
          >
            B3 Opções Pro
          </button>
        </div>
        <nav aria-label="Seções" className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.title}>
              <p className="np-label mb-1.5 px-3">{group.title}</p>
              <div className="space-y-0.5">
                {group.ids.map((id) => navButton(NAV_ITEMS.find((item) => item.id === id)!, false))}
              </div>
            </div>
          ))}
        </nav>
        <p className="np-note border-t border-[var(--dp-color-rule)] px-5 py-4">
          Análise e decisão. Este app não envia ordens.
        </p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <Masthead
          title={current.label}
          onLogout={onLogout}
          onOpenMenu={(event) => openDrawer(event)}
          onOpenJarbas={goToJarbas}
        />
        <div id="conteudo-principal" tabIndex={-1} className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-4 pb-[calc(6rem+env(safe-area-inset-bottom))] lg:px-8 lg:py-8 lg:pb-8">
          {children}
        </div>
      </div>

      <nav
        aria-label="Navegação móvel inferior"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--dp-color-rule)] bg-[var(--dp-color-panel)]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        <div className="mx-auto grid max-w-[1440px] grid-cols-5">
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
                    ? 'border-[var(--dp-color-accent)] text-[var(--dp-color-accent)]'
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
            onClick={openDrawer}
            className={cn(
              'flex min-h-14 flex-col items-center justify-center gap-1 border-t-2 px-1 py-1.5 font-display text-[11px]',
              drawerOpen ? 'border-[var(--dp-color-accent)]' : 'border-transparent text-[var(--dp-color-secondary)]',
            )}
          >
            <Menu className="h-5 w-5" />
            <span className="leading-none">Módulos</span>
          </button>
        </div>
      </nav>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/70 backdrop-blur-sm lg:hidden" onClick={closeDrawer}>
          <div
            ref={drawerRef}
            role="dialog"
            aria-label="Todos os módulos"
            aria-modal="true"
            className="max-h-[82vh] w-full overflow-y-auto rounded-t-2xl border-t border-[var(--dp-color-rule)] bg-[var(--dp-color-panel)] p-5 pb-[calc(2rem+env(safe-area-inset-bottom))]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mx-auto mb-4 h-1.5 w-10 rounded bg-[var(--dp-color-rule)]" />
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-xl">Todos os módulos</h2>
              <button ref={closeRef} className="np-btn !min-h-0 !px-2 !py-1" onClick={closeDrawer} aria-label="Fechar menu">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-4">
              {NAV_GROUPS.map((group) => (
                <div key={group.title}>
                  <p className="np-label mb-2 px-1">{group.title}</p>
                  <div className="grid grid-cols-2 gap-2">
                    {group.ids.map((id) => navButton(NAV_ITEMS.find((item) => item.id === id)!, true))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
