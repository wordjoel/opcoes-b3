import { useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { aplicarPreferencia, lerPreferencia, Preferencia, salvarPreferencia } from '../lib/tema';

type Modo = 'claro' | 'escuro';

/** Modo efetivo: a escolha manual vale; no automático, segue o sistema operacional. */
function modoEfetivo(preferencia: Preferencia): Modo {
  if (preferencia === 'claro' || preferencia === 'escuro') return preferencia;
  return window.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'escuro' : 'claro';
}

/** Ícone no topo que alterna entre modo claro e escuro. */
export function ThemeToggle() {
  const [preferencia, setPreferencia] = useState<Preferencia>(() => lerPreferencia());
  const atual = modoEfetivo(preferencia);
  const proximo: Modo = atual === 'escuro' ? 'claro' : 'escuro';
  const Icone = atual === 'escuro' ? Sun : Moon;

  const alternar = () => {
    setPreferencia(proximo);
    salvarPreferencia(proximo);
    aplicarPreferencia(proximo);
  };

  return (
    <button
      type="button"
      onClick={alternar}
      className="np-btn inline-flex items-center justify-center"
      aria-label={`Ativar modo ${proximo}`}
      title={`Ativar modo ${proximo}`}
    >
      <Icone aria-hidden="true" size={18} />
    </button>
  );
}
