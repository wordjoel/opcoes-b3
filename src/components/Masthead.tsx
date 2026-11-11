import { useState } from 'react';
import { aplicarPreferencia, lerPreferencia, PREFERENCIAS, Preferencia, salvarPreferencia } from '../lib/tema';

const MENU = [
  { id: 'dashboard', label: 'Monitor' },
  { id: 'scanner', label: 'Scanner B3' },
  { id: 'strategy', label: 'Estratégias' },
  { id: 'alerts', label: 'Alertas' },
  { id: 'lab', label: 'Laboratório' },
  { id: 'carteira', label: 'Carteira' },
];

function SeletorAparencia() {
  const [preferencia, setPreferencia] = useState<Preferencia>(() => lerPreferencia());

  const escolher = (valor: Preferencia) => {
    setPreferencia(valor);
    salvarPreferencia(valor);
    aplicarPreferencia(valor);
  };

  return (
    <label className="np-label">
      Aparência
      <select value={preferencia} onChange={(event) => escolher(event.target.value as Preferencia)} className="np-input block mt-1">
        {PREFERENCIAS.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  );
}

interface MastheadProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  alertCount: number;
  onLogout: () => void;
}

export function Masthead({ activeTab, setActiveTab, alertCount, onLogout }: MastheadProps) {
  return (
    <header>
      <h1 className="text-[clamp(2.75rem,10vw,7.5rem)] leading-[0.95] tracking-tight">B3 Opções Pro</h1>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-y border-ink mt-3 py-2">
        <nav aria-label="Seções" className="flex flex-wrap gap-2">
          {MENU.map((item) => (
            <button
              key={item.id}
              aria-current={activeTab === item.id ? 'page' : undefined}
              onClick={() => setActiveTab(item.id)}
              className="np-btn"
            >
              {item.label}
              {item.id === 'alerts' && alertCount > 0 && <span aria-label={`${alertCount} alertas`}>({alertCount})</span>}
            </button>
          ))}
        </nav>
        <div className="flex flex-wrap items-center gap-4">
          <p className="np-label">Análise e decisão. Este app não envia ordens.</p>
          <SeletorAparencia />
          <button onClick={onLogout} className="np-btn">
            Sair
          </button>
        </div>
      </div>
    </header>
  );
}
