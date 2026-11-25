/** O shell adapta a navegação ao tamanho da tela sem duplicar ações. */
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppShell } from './components/AppShell';

afterEach(cleanup);

function setup(activeTab = 'dashboard') {
  const onTab = vi.fn();
  const onLogout = vi.fn();
  render(
    <AppShell activeTab={activeTab} onTab={onTab} alertCount={2} onLogout={onLogout}>
      <p>Conteúdo da seção</p>
    </AppShell>,
  );
  return { onTab, onLogout };
}

describe('shell Web/PWA', () => {
  it('navega pela sidebar sem repetir Sair', async () => {
    const { onTab } = setup();
    expect(screen.getByText('Conteúdo da seção')).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Sair' })).toHaveLength(1);
    const sidebar = screen.getByRole('navigation', { name: 'Seções' });
    await userEvent.click(within(sidebar).getByRole('button', { name: /Scanner B3/ }));
    expect(onTab).toHaveBeenCalledWith('scanner');
  });

  it('oferece skip link para o conteúdo principal', async () => {
    setup();
    const link = screen.getByRole('link', { name: 'Ir para o conteúdo principal' });
    expect(link.getAttribute('href')).toBe('#conteudo-principal');
    await userEvent.click(link);
    expect(document.getElementById('conteudo-principal')?.textContent).toContain('Conteúdo da seção');
  });

  it('usa a barra inferior no celular', async () => {
    const { onTab } = setup();
    const bottom = screen.getByRole('navigation', { name: 'Navegação móvel inferior' });
    await userEvent.click(within(bottom).getByRole('button', { name: 'Carteira (menu inferior)' }));
    expect(onTab).toHaveBeenCalledWith('carteira');
  });

  it('abre o drawer com todos os módulos e fecha ao escolher', async () => {
    const { onTab } = setup();
    const bottom = screen.getByRole('navigation', { name: 'Navegação móvel inferior' });
    await userEvent.click(within(bottom).getByRole('button', { name: 'Todos os módulos (menu inferior)' }));
    const drawer = screen.getByRole('dialog', { name: 'Todos os módulos' });
    for (const label of ['Monitor', 'Scanner B3', 'Estratégias', 'Alertas', 'Laboratório', 'Carteira']) {
      expect(within(drawer).getByRole('button', { name: new RegExp(label) })).toBeTruthy();
    }
    await userEvent.click(within(drawer).getByRole('button', { name: 'Laboratório' }));
    expect(onTab).toHaveBeenCalledWith('lab');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('coloca foco no drawer, prende Tab e devolve o foco ao fechar com Escape', async () => {
    setup();
    const bottom = screen.getByRole('navigation', { name: 'Navegação móvel inferior' });
    const opener = within(bottom).getByRole('button', { name: 'Todos os módulos (menu inferior)' });
    await userEvent.click(opener);
    const drawer = screen.getByRole('dialog', { name: 'Todos os módulos' });
    expect(document.activeElement).toBe(within(drawer).getByRole('button', { name: 'Fechar menu' }));

    // Shift+Tab do primeiro botão volta ao último; Tab volta ao primeiro.
    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(within(drawer).getByRole('button', { name: 'Carteira' }));
    await userEvent.tab();
    expect(document.activeElement).toBe(within(drawer).getByRole('button', { name: 'Fechar menu' }));

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it('expõe a contagem de alertas ao leitor de tela e respeita a área segura', () => {
    setup();
    const sidebar = screen.getByRole('navigation', { name: 'Seções' });
    expect(within(sidebar).getByText('2 alertas')).toBeTruthy();
    const bottom = screen.getByRole('navigation', { name: 'Navegação móvel inferior' });
    expect(bottom.className).toContain('pb-[env(safe-area-inset-bottom)]');
  });
});
