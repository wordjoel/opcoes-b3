/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useState } from 'react';
import { Alerts, alertCount } from './components/Alerts';
import { AppStatus } from './components/AppStatus';
import { Jarbas } from './components/Jarbas';
import { Carteira } from './components/Carteira';
import { ErrorNotice, Loading } from './components/Common';
import { Dashboard } from './components/Dashboard';
import { Lab } from './components/Lab';
import { Login } from './components/Login';
import { Masthead } from './components/Masthead';
import { Scanner } from './components/Scanner';
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
      <div className="min-h-screen p-4 md:p-8 max-w-3xl mx-auto">
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
    <div className="max-w-[1400px] mx-auto p-4 md:p-8 space-y-6">
      <Masthead activeTab={activeTab} setActiveTab={setActiveTab} alertCount={alertCount(rows)} onLogout={onLogout} />
      <AppStatus />
      <Jarbas />
      <main className="space-y-6 min-w-0">
        {scanner.loading && !scanner.data && <Loading label="Consultando a fonte de dados..." />}
        {scanner.error && <ErrorNotice error={scanner.error} onRetry={scanner.reload} />}

        {scanner.data && activeTab === 'dashboard' && (
          <Dashboard rows={rows} selected={selected} onSelect={setSelected} onOpenStrategies={openStrategies} />
        )}
        {scanner.data && activeTab === 'scanner' && (
          <Scanner
            rows={rows}
            generatedAt={scanner.data.generated_at}
            complete={scanner.data.complete}
            timedOut={scanner.data.timed_out_symbols}
            loading={scanner.loading}
            onReload={scanner.reload}
            onOpenStrategies={openStrategies}
          />
        )}
        {scanner.data && activeTab === 'strategy' && <StrategyView symbols={symbols} symbol={selected} onSymbol={setSelected} />}
        {scanner.data && activeTab === 'alerts' && <Alerts rows={rows} onOpenStrategies={openStrategies} />}
        {activeTab === 'lab' && <Lab />}
        {activeTab === 'carteira' && <Carteira />}
      </main>
    </div>
  );
}
