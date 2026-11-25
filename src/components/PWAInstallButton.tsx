import { useEffect, useRef, useState } from 'react';
import { Download, Share, X } from 'lucide-react';
import { usePwaInstall } from '../lib/pwaInstall';

/**
 * Ação de instalação no cabeçalho. Usa o mesmo evento do aviso no conteúdo:
 * Android/desktop abrem o diálogo nativo; iOS mostra o passo a passo no Safari.
 */
export function PWAInstallButton({ compact = false }: { compact?: boolean }) {
  const install = usePwaInstall();
  const [guide, setGuide] = useState(false);
  const guideRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);

  const closeGuide = () => {
    setGuide(false);
    openerRef.current?.focus();
  };

  // O guia iOS é um diálogo modal: foco inicial, Escape e Tab preso dentro dele.
  useEffect(() => {
    if (!guide) return;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeGuide();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusables: HTMLElement[] = [];
      guideRef.current
        ?.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        .forEach((element: HTMLElement) => focusables.push(element));
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const inside = guideRef.current?.contains(document.activeElement);
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
    // `closeGuide` muda a cada render; o ciclo de vida é o estado `guide`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guide]);

  if (!install.visible) return null;

  if (install.installable) {
    return (
      <button
        type="button"
        className="np-btn !min-h-10 !border-[var(--dp-color-accent)] !bg-[var(--dp-color-accent)] !text-[var(--dp-color-ground)]"
        onClick={() => void install.install()}
        aria-label="Instalar o B3 Opções Pro"
      >
        <Download className="h-4 w-4" aria-hidden="true" />
        <span className="hidden sm:inline">{compact ? 'Instalar' : 'Instalar app'}</span>
      </button>
    );
  }

  if (install.ios) {
    return (
      <>
        <button
          ref={openerRef}
          type="button"
          className="np-btn !border-[var(--dp-color-violet)] !text-[var(--dp-color-violet)]"
          onClick={() => setGuide(true)}
          aria-label="Como instalar no iPhone ou iPad"
        >
          <Share className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Instalar no iOS</span>
        </button>
        {guide && (
          <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/70 p-4 sm:items-center" onClick={closeGuide}>
            <div
              ref={guideRef}
              role="dialog"
              aria-label="Instalar no iPhone ou iPad"
              aria-modal="true"
              className="np-card w-full max-w-sm p-5"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="text-lg">Instalar no iPhone / iPad</h2>
                <button ref={closeRef} type="button" className="np-btn !min-h-0 !px-2 !py-1" onClick={closeGuide} aria-label="Fechar guia de instalação">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <ol className="space-y-2 text-sm np-note">
                <li>1. Toque em Compartilhar na barra do Safari.</li>
                <li>2. Escolha Adicionar à Tela de Início.</li>
                <li>3. Confirme para abrir em tela cheia.</li>
              </ol>
            </div>
          </div>
        )}
      </>
    );
  }

  return null;
}
