import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Só no build: em desenvolvimento, o cache atrapalharia o recarregamento do Vite.
// Versão nova só entra quando o usuário aceita (AppStatus mostra o aviso).
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js');
      const announce = () => window.dispatchEvent(new CustomEvent('b3-update-ready', { detail: registration }));
      if (registration.waiting && navigator.serviceWorker.controller) announce();
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        worker?.addEventListener('statechange', () => {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) announce();
        });
      });
      // O app instalado pode ficar aberto por dias: procura versão nova ao voltar para ele.
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') registration.update().catch(() => {});
      });
      let reloading = false;
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!reloading) {
          reloading = true;
          window.location.reload();
        }
      });
    } catch (error) {
      console.error('Falha ao registrar o service worker:', error);
    }
  });
}
