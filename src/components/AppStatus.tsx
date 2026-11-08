import { useEffect, useState } from 'react';

interface InstallEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const DISMISS_KEY = 'b3-instalar-dispensado';

function standalone() {
  return window.matchMedia?.('(display-mode: standalone)').matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

function isIos() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) && !/crios|fxios/i.test(navigator.userAgent);
}

function dismissed() {
  try {
    return localStorage.getItem(DISMISS_KEY) === '1';
  } catch {
    return false;
  }
}

/** Convite para instalar: botão nativo no Android e no desktop, instruções no iPhone. */
function InstallPrompt() {
  const [event, setEvent] = useState<InstallEvent | null>(null);
  const [hidden, setHidden] = useState(() => standalone() || dismissed());

  useEffect(() => {
    const capture = (e: Event) => {
      e.preventDefault();
      setEvent(e as InstallEvent);
    };
    const installed = () => setHidden(true);
    window.addEventListener('beforeinstallprompt', capture);
    window.addEventListener('appinstalled', installed);
    return () => {
      window.removeEventListener('beforeinstallprompt', capture);
      window.removeEventListener('appinstalled', installed);
    };
  }, []);

  const dismiss = () => {
    setHidden(true);
    try {
      localStorage.setItem(DISMISS_KEY, '1');
    } catch {
      // Sem armazenamento: o convite volta na próxima visita.
    }
  };

  if (hidden || (!event && !isIos())) return null;
  return (
    <p role="status" className="border-y border-ink py-2 text-base flex flex-wrap items-center gap-3">
      {event ? (
        <>
          Instale o B3 Opções Pro na tela inicial para abrir como aplicativo.
          <button
            className="np-btn"
            onClick={async () => {
              await event.prompt();
              const choice = await event.userChoice;
              if (choice.outcome === 'accepted') setHidden(true);
              setEvent(null);
            }}
          >
            Instalar app
          </button>
        </>
      ) : (
        <>No iPhone: toque em Compartilhar e depois em “Adicionar à Tela de Início” para instalar o app.</>
      )}
      <button className="np-btn" onClick={dismiss}>
        Agora não
      </button>
    </p>
  );
}

/** Avisos do app instalado: sem conexão e versão nova esperando para entrar. */
export function AppStatus() {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine));
  const [waiting, setWaiting] = useState<ServiceWorkerRegistration | null>(null);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    const ready = (event: Event) => setWaiting((event as CustomEvent<ServiceWorkerRegistration>).detail);
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    window.addEventListener('b3-update-ready', ready);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
      window.removeEventListener('b3-update-ready', ready);
    };
  }, []);

  return (
    <>
      <InstallPrompt />
      {!online && (
        <p role="alert" className="border-y border-accent py-2 text-base">
          Sem conexão. Dados de mercado, login e o Jarbas precisam de internet: o que aparece na tela pode estar desatualizado.
        </p>
      )}
      {waiting && (
        <p role="status" className="border-y border-ink py-2 text-base flex flex-wrap items-center gap-3">
          Nova versão do app disponível.
          <button className="np-btn" onClick={() => waiting.waiting?.postMessage('SKIP_WAITING')}>
            Atualizar agora
          </button>
        </p>
      )}
    </>
  );
}
