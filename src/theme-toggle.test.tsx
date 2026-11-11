import { afterEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ThemeToggle } from './components/ThemeToggle';

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = '';
});

describe('ícone de alternância de modo', () => {
  it('alterna entre escuro e claro e grava a escolha', () => {
    render(<ThemeToggle />);
    const botao = screen.getByRole('button', { name: 'Ativar modo escuro' });

    fireEvent.click(botao);
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.localStorage.getItem('b3-opcoes-tema')).toBe('escuro');
    expect(screen.getByRole('button', { name: 'Ativar modo claro' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Ativar modo claro' }));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(window.localStorage.getItem('b3-opcoes-tema')).toBe('claro');
    expect(screen.getByRole('button', { name: 'Ativar modo escuro' })).toBeTruthy();
  });

  it('recupera a escolha salva ao montar', () => {
    window.localStorage.setItem('b3-opcoes-tema', 'escuro');
    render(<ThemeToggle />);
    expect(screen.getByRole('button', { name: 'Ativar modo claro' })).toBeTruthy();
  });
});
