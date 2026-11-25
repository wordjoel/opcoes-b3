import { useEffect, useState } from 'react';
import { usePwaInstall } from '../lib/pwaInstall';

/** Convite para instalar: botão nativo no Android/desktop e instruções no iPhone. */
function InstallPrompt() {
  const install = usePwaInstall();
  if (!install.visible) return null;
  return (
    <p role="status" className="np-card mb-4 flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
      {install.installable ? (
        <>
          Instale o B3 Opções Pro na tela inicial para abrir como aplicativo.
          <button className="np-btn" onClick={() => void install.install()}>
            Instalar app
          </button>
        </>
      ) : (
        <>No iPhone: toque em Compartilhar e depois em “Adicionar à Tela de Início” para instalar o app.</>
      )}
      <button className="np-btn" onClick={install.dismiss}>
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
        <p role="alert" className="np-card mb-4 border-[var(--dp-color-loss)] px-4 py-3 text-sm text-[var(--dp-color-loss)]">
          Sem conexão. Dados de mercado, login e o Jarbas precisam de internet: o que aparece na tela pode estar desatualizado.
        </p>
      )}
      {waiting && (
        <p role="status" className="np-card mb-4 flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
          Nova versão do app disponível.
          <button className="np-btn" onClick={() => waiting.waiting?.postMessage('SKIP_WAITING')}>
            Atualizar agora
          </button>
        </p>
      )}
    </>
  );
}
