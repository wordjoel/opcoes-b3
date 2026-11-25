import { type MouseEvent } from 'react';
import { Bot, Menu } from 'lucide-react';
import { PWAInstallButton } from './PWAInstallButton';
import { ThemeToggle } from './ThemeToggle';

interface MastheadProps {
  title: string;
  onLogout: () => void;
  onOpenMenu: (event: MouseEvent<HTMLElement>) => void;
  onOpenJarbas: () => void;
}

/** Barra compacta: navegação em AppShell, identidade e ações do PWA no topo. */
export function Masthead({ title, onLogout, onOpenMenu, onOpenJarbas }: MastheadProps) {
  return (
    <header className="sticky top-0 z-30 flex min-h-14 items-center justify-between gap-3 border-b border-[var(--dp-color-rule)] bg-[var(--dp-color-panel)]/95 px-4 py-2 backdrop-blur md:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <button type="button" onClick={onOpenMenu} aria-label="Abrir todos os módulos" className="np-btn !px-2 lg:hidden">
          <Menu className="h-4 w-4" />
        </button>
        <img src="/icon.svg" alt="" className="h-8 w-8 shrink-0 rounded-lg" aria-hidden="true" />
        <div className="min-w-0">
          <p className="np-label leading-none">B3 Opções Pro</p>
          <h1 className="truncate font-display text-base font-semibold md:text-lg">{title}</h1>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2 md:gap-3">
        <PWAInstallButton compact />
        <button
          type="button"
          onClick={onOpenJarbas}
          aria-label="Ir para o Jarbas"
          className="np-btn !border-[var(--dp-color-violet)] !text-[var(--dp-color-violet)]"
        >
          <Bot className="h-4 w-4" />
          <span className="hidden sm:inline">Jarbas</span>
        </button>
        <ThemeToggle />
        <button type="button" onClick={onLogout} className="np-btn">
          Sair
        </button>
      </div>
    </header>
  );
}
