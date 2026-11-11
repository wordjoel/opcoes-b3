import { useEffect, useState } from 'react';

/**
 * Aparência: claro, escuro ou automático (segue o dispositivo).
 *
 * As cores vêm de variáveis CSS em index.css. A preferência fica no navegador deste
 * aparelho (localStorage), porque é uma escolha de visualização, não dado de negócio.
 * Se o navegador bloquear o armazenamento, vale o automático.
 */

export type Preferencia = 'claro' | 'escuro' | 'automatico';

export const PREFERENCIAS: { value: Preferencia; label: string }[] = [
  { value: 'automatico', label: 'Automático' },
  { value: 'claro', label: 'Claro' },
  { value: 'escuro', label: 'Escuro' },
];

const CHAVE = 'b3-opcoes-tema';

function ehPreferencia(valor: unknown): valor is Preferencia {
  return valor === 'claro' || valor === 'escuro' || valor === 'automatico';
}

export function lerPreferencia(): Preferencia {
  try {
    const salvo = window.localStorage.getItem(CHAVE);
    return ehPreferencia(salvo) ? salvo : 'automatico';
  } catch {
    return 'automatico';
  }
}

export function salvarPreferencia(preferencia: Preferencia) {
  try {
    window.localStorage.setItem(CHAVE, preferencia);
  } catch {
    // Sem armazenamento, a escolha vale só nesta aba.
  }
}

/** Define o atributo que as regras CSS usam. Automático remove o atributo e segue o sistema. */
export function aplicarPreferencia(preferencia: Preferencia) {
  const dispararEvento = () => window.dispatchEvent(new Event(EVENTO));
  const html = document.documentElement;
  if (preferencia === 'automatico') {
    delete html.dataset.theme;
    html.style.colorScheme = '';
  } else {
    html.dataset.theme = preferencia === 'claro' ? 'light' : 'dark';
    html.style.colorScheme = preferencia === 'claro' ? 'light' : 'dark';
  }
  dispararEvento();
}

/** Valor atual de um token de cor, lido a cada uso para acompanhar a troca de tema. */
export function cor(token: string): string {
  if (typeof window === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim();
}

/** Cores para gráficos e marcações. Cada propriedade lê o token atual no momento do uso. */
export const PALETA = {
  get INK() {
    return cor('--dp-color-ink');
  },
  get PAPER() {
    return cor('--dp-color-ground');
  },
  get SECONDARY() {
    return cor('--dp-color-secondary');
  },
  get ACCENT() {
    return cor('--dp-color-accent');
  },
  get RULE() {
    return cor('--dp-color-rule');
  },
  get GRID() {
    return cor('--dp-color-grid');
  },
  get GAIN() {
    return cor('--dp-color-gain');
  },
  get LOSS() {
    return cor('--dp-color-loss');
  },
  get FOCUS() {
    return cor('--dp-color-focus');
  },
};

const EVENTO = 'b3-tema';

/** Hook: muda de valor quando a aparência muda, para forçar o redesenho dos gráficos. */
export function useTemaVersao(): number {
  const [versao, setVersao] = useState(0);
  useEffect(() => {
    const atualizar = () => setVersao((v) => v + 1);
    window.addEventListener(EVENTO, atualizar);
    // No automático, uma troca do sistema (dia/noite) também precisa redesenhar.
    const sistema = window.matchMedia?.('(prefers-color-scheme: dark)');
    sistema?.addEventListener?.('change', atualizar);
    return () => {
      window.removeEventListener(EVENTO, atualizar);
      sistema?.removeEventListener?.('change', atualizar);
    };
  }, []);
  return versao;
}
