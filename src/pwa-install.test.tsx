/** Guia de instalação no iOS: diálogo modal com foco preso e retorno ao botão. */
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

const installState = vi.hoisted(() => ({
  visible: true,
  ios: true,
  installable: false,
  installed: false,
  dismissed: false,
  install: vi.fn(async () => true),
  dismiss: vi.fn(),
}));

vi.mock('./lib/pwaInstall', () => ({ usePwaInstall: () => installState }));

import { PWAInstallButton } from './components/PWAInstallButton';

afterEach(cleanup);

describe('PWAInstallButton', () => {
  it('abre o guia iOS como modal, prende o foco e devolve ao botão ao fechar', async () => {
    render(<PWAInstallButton />);
    const opener = screen.getByRole('button', { name: 'Como instalar no iPhone ou iPad' });
    await userEvent.click(opener);
    const dialog = screen.getByRole('dialog', { name: 'Instalar no iPhone ou iPad' });
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(document.activeElement).toBe(within(dialog).getByRole('button', { name: 'Fechar guia de instalação' }));

    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(within(dialog).getByRole('button', { name: 'Fechar guia de instalação' }));

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it('preserva as três instruções do guia sem duplicar a PWA', async () => {
    render(<PWAInstallButton compact />);
    await userEvent.click(screen.getByRole('button', { name: 'Como instalar no iPhone ou iPad' }));
    const dialog = screen.getByRole('dialog', { name: 'Instalar no iPhone ou iPad' });
    expect(within(dialog).getAllByRole('listitem')).toHaveLength(3);
  });
});
