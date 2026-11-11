import { afterEach, describe, expect, it } from 'vitest';
import { aplicarPreferencia, lerPreferencia, salvarPreferencia } from './lib/tema';

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = '';
});

describe('preferência de aparência', () => {
  it('começa no automático quando nada foi salvo', () => {
    expect(lerPreferencia()).toBe('automatico');
  });

  it('salva e lê a escolha do usuário', () => {
    salvarPreferencia('escuro');
    expect(lerPreferencia()).toBe('escuro');
    salvarPreferencia('claro');
    expect(lerPreferencia()).toBe('claro');
  });

  it('ignora valor salvo inválido e volta ao automático', () => {
    window.localStorage.setItem('b3-opcoes-tema', 'neon');
    expect(lerPreferencia()).toBe('automatico');
  });

  it('volta ao automático quando o armazenamento falha', () => {
    const original = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error('bloqueado');
    };
    try {
      expect(lerPreferencia()).toBe('automatico');
    } finally {
      Storage.prototype.getItem = original;
    }
  });
});

describe('aplicação no documento', () => {
  it('marca claro e escuro no atributo data-theme', () => {
    aplicarPreferencia('claro');
    expect(document.documentElement.dataset.theme).toBe('light');
    aplicarPreferencia('escuro');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('automático remove o atributo, deixando o sistema decidir', () => {
    aplicarPreferencia('escuro');
    aplicarPreferencia('automatico');
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(document.documentElement.style.colorScheme).toBe('');
  });
});
