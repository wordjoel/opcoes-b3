/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Menu, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Alerts, alertCount } from './components/Alerts';
import { ErrorNotice, Loading } from './components/Common';
import { Dashboard } from './components/Dashboard';
import { Login } from './components/Login';
import { Scanner } from './components/Scanner';
import { Sidebar } from './components/Sidebar';
import { StrategyView } from './components/StrategyView';
import { api, ApiError, setUnauthorizedHandler, useResource } from './services/api';

type Session = { authenticated: boolean; login_ready: boolean };

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const check = () => {
    setFailure(null);
    api.session().then(setSession).catch(setFailure);
  };

  useEffect(() => {
    setUnauthorizedHandler(() => setSession((current) => current && { ...current, authenticated: false }));
    check();
  }, []);

  if (failure) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-slate-950">
        <ErrorNotice error={failure} onRetry={check} />
      </div>
    );
  }
  if (!session) return <Loading label="Abrindo..." />;
  if (!session.authenticated) return <Login ready={session.login_ready} onSuccess={check} />;
  return <Workspace onLogout={() => api.logout().finally(check)} />;
}

function Workspace({ onLogout }: { onLogout: () => void }) {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selected, setSelected] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const scanner = useResource('scanner', api.scanner);
  const rows = scanner.data?.rows ?? [];
  const symbols = rows.map((row) => row.symbol);

  useEffect(() => {
    if (rows.length > 0 && (selected === null || !symbols.includes(selected))) {
      setSelected((rows.find((row) => row.price !== null) ?? rows[0]).symbol);
    }
    // `rows` é novo a cada render; o que importa é a lista de códigos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbols.join()]);

  const openStrategies = (symbol: string) => {
    setSelected(symbol);
    setActiveTab('strategy');
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200 overflow-hidden font-sans">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isOpen={isSidebarOpen}
        setIsOpen={setIsSidebarOpen}
        alertCount={alertCount(rows)}
        onLogout={onLogout}
      />
      <main className="flex-1 relative overflow-y-auto min-w-0">
        <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between p-4 bg-slate-950/90 border-b border-slate-800">
          <div className="flex items-center gap-2 text-sky-400">
            <Zap className="w-5 h-5" />
            <span className="font-bold tracking-tight">B3 Pro</span>
          </div>
          <button aria-label="Abrir menu" onClick={() => setIsSidebarOpen(true)} className="p-2 rounded-lg bg-slate-900 border border-slate-800">
            <Menu className="w-5 h-5 text-slate-300" />
          </button>
        </header>

        <div className="max-w-[1400px] mx-auto p-4 md:p-8 space-y-6">
          {scanner.loading && !scanner.data && <Loading label="Consultando a fonte de dados..." />}
          {scanner.error && <ErrorNotice error={scanner.error} onRetry={scanner.reload} />}

          {scanner.data && activeTab === 'dashboard' && (
            <Dashboard rows={rows} selected={selected} onSelect={setSelected} onOpenStrategies={openStrategies} />
          )}
          {scanner.data && activeTab === 'scanner' && (
            <Scanner
              rows={rows}
              generatedAt={scanner.data.generated_at}
              loading={scanner.loading}
              onReload={scanner.reload}
              onOpenStrategies={openStrategies}
            />
          )}
          {scanner.data && activeTab === 'strategy' && <StrategyView symbols={symbols} symbol={selected} onSymbol={setSelected} />}
          {scanner.data && activeTab === 'alerts' && <Alerts rows={rows} onOpenStrategies={openStrategies} />}
        </div>
      </main>
    </div>
  );
}
