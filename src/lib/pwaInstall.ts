/**
 * Estado único do convite de instalação do PWA.
 *
 * Antes, o aviso no conteúdo e o botão do cabeçalho teriam cada um seu próprio
 * listener de `beforeinstallprompt`. Aqui existe um só listener para todo o app:
 * o evento do navegador é guardado uma vez e distribuído aos componentes.
 */
import { useSyncExternalStore } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export interface PwaInstallState {
  installable: boolean;
  installed: boolean;
  ios: boolean;
  dismissed: boolean;
  visible: boolean;
}

const DISMISS_KEY = 'b3-instalar-dispensado';

let deferred: BeforeInstallPromptEvent | null = null;
let installed = false;
let initialized = false;
let snapshot: PwaInstallState = { installable: false, installed: false, ios: false, dismissed: false, visible: false };
const listeners = new Set<() => void>();

function standalone(): boolean {
  try {
    return window.matchMedia?.('(display-mode: standalone)').matches || (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
  } catch {
    return false;
  }
}

function isIos(): boolean {
  const ua = window.navigator.userAgent;
  return /iphone|ipad|ipod/i.test(ua) && !/crios|fxios/i.test(ua);
}

function isDismissed(): boolean {
  try {
    return window.localStorage.getItem(DISMISS_KEY) === '1';
  } catch {
    return false;
  }
}

function refresh() {
  const state: PwaInstallState = {
    installable: deferred !== null,
    installed,
    ios: isIos(),
    dismissed: isDismissed(),
    visible: false,
  };
  state.visible = !state.installed && !state.dismissed && (state.installable || state.ios);
  snapshot = state;
  listeners.forEach((listener) => listener());
}

function init() {
  if (initialized || typeof window === 'undefined') return;
  initialized = true;
  installed = standalone();
  refresh();
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferred = event as BeforeInstallPromptEvent;
    refresh();
  });
  window.addEventListener('appinstalled', () => {
    installed = true;
    deferred = null;
    refresh();
  });
}

function subscribe(listener: () => void) {
  init();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  init();
  return snapshot;
}

export function usePwaInstall(): PwaInstallState & {
  install: () => Promise<boolean>;
  dismiss: () => void;
} {
  const state = useSyncExternalStore(subscribe, getSnapshot, () => snapshot);
  return {
    ...state,
    install: async () => {
      if (!deferred) return false;
      try {
        await deferred.prompt();
        const choice = await deferred.userChoice;
        if (choice.outcome === 'accepted') {
          installed = true;
          deferred = null;
          refresh();
          return true;
        }
        return false;
      } catch {
        return false;
      }
    },
    dismiss: () => {
      try {
        window.localStorage.setItem(DISMISS_KEY, '1');
      } catch {
        // Sem armazenamento: o convite volta na próxima visita.
      }
      deferred = null;
      refresh();
    },
  };
}
