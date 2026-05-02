/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './components/Dashboard';
import { StrategyView } from './components/StrategyView';
import { INITIAL_ROBOTS, MOCK_ASSETS } from './constants';
import { AssetData, RobotState, Strategy } from './types';
import { analyzeMarketAndSuggestStrategy } from './services/geminiService';
import { Radar, AlertCircle, Zap, Menu } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn, formatCurrency } from './lib/utils';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [assets, setAssets] = useState<AssetData[]>(MOCK_ASSETS);
  const [robots, setRobots] = useState<RobotState[]>(INITIAL_ROBOTS);
  const [selectedAsset, setSelectedAsset] = useState<AssetData | null>(null);
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loading, setLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Robot simulation logic
  useEffect(() => {
    const interval = setInterval(() => {
      setRobots(prev => prev.map(robot => {
        if (robot.id === 'scanner') {
          return { ...robot, status: 'SCANNING', message: `Monitorando ${assets.length} ativos...` };
        }
        return robot;
      }));
    }, 5000);
    return () => clearInterval(interval);
  }, [assets]);

  const handleSelectAsset = async (asset: AssetData) => {
    setSelectedAsset(asset);
    setActiveTab('strategy');
    setLoading(true);
    
    // Update robots to show status
    updateRobotStatus('strategy', 'ANALYZING', `Analisando ${asset.ticker}...`);
    updateRobotStatus('risk', 'EXECUTING', 'Calculando P&L...');
    
    try {
      const suggested = await analyzeMarketAndSuggestStrategy(asset);
      setStrategy(suggested);
      updateRobotStatus('strategy', 'IDLE', 'Estratégia pronta');
      updateRobotStatus('risk', 'IDLE', 'Risco calculado');
    } catch (error) {
      console.error(error);
      updateRobotStatus('strategy', 'IDLE', 'Erro na análise');
    } finally {
      setLoading(false);
    }
  };

  const updateRobotStatus = (id: string, status: RobotState['status'], message: string) => {
    setRobots(prev => prev.map(r => r.id === id ? { ...r, status, message } : r));
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200 overflow-hidden font-sans">
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        robots={robots} 
        isOpen={isSidebarOpen}
        setIsOpen={setIsSidebarOpen}
      />
      
      <main className="flex-1 relative overflow-y-auto bg-[radial-gradient(circle_at_50%_0%,#1e293b,transparent)] scroll-smooth">
        {/* Mobile Header */}
        <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between p-4 bg-slate-950/80 backdrop-blur-md border-b border-slate-800">
          <div className="flex items-center gap-2 text-sky-400">
            <Zap className="w-5 h-5" />
            <span className="font-bold tracking-tight">B3 Pro</span>
          </div>
          <button 
            onClick={() => setIsSidebarOpen(true)}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800"
          >
            <Menu className="w-5 h-5 text-slate-300" />
          </button>
        </header>

        <div className="max-w-[1400px] mx-auto p-4 md:p-8 lg:p-10 space-y-8">
          <AnimatePresence mode="wait">
            {activeTab === 'dashboard' && (
              <motion.div
                key="dashboard"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              >
                <Dashboard assets={assets} onSelectAsset={handleSelectAsset} />
              </motion.div>
            )}
            
            {activeTab === 'scanner' && (
              <motion.div
                key="scanner"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="space-y-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-3xl font-bold text-white tracking-tight">Scanner Alpha-Scan</h2>
                    <p className="text-slate-400">Varredura completa da grade de opções B3 em tempo real.</p>
                  </div>
                  <div className="flex items-center gap-3 bg-slate-900 px-4 py-2 rounded-xl border border-slate-800">
                    <Radar className="w-5 h-5 text-sky-400 animate-pulse" />
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-widest">BUSCANDO DISTORÇÕES</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {assets.map((asset) => (
                    <motion.div
                      key={asset.ticker}
                      whileHover={{ scale: 1.02 }}
                      className="bg-slate-900 border border-slate-800 rounded-2xl p-5 hover:border-sky-500/50 transition-all cursor-pointer group"
                      onClick={() => handleSelectAsset(asset)}
                    >
                      <div className="flex justify-between items-start mb-4">
                        <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center font-bold text-sky-400 border border-slate-700 font-mono">
                          {asset.ticker.substring(0, 4)}
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-bold text-white">{formatCurrency(asset.price)}</p>
                          <p className={cn("text-[10px] font-bold font-mono", asset.change >= 0 ? "text-emerald-400" : "text-red-400")}>
                            {asset.change > 0 ? "+" : ""}{asset.change}%
                          </p>
                        </div>
                      </div>
                      
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Tendência</span>
                          <span className={cn(
                            "text-[10px] font-bold px-2 py-0.5 rounded uppercase",
                            asset.trend === 'bullish' ? "bg-emerald-500/10 text-emerald-400" : 
                            asset.trend === 'bearish' ? "bg-red-500/10 text-red-400" : "bg-slate-800 text-slate-400"
                          )}>{asset.trend}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Volatilidade</span>
                          <span className="text-xs font-mono text-slate-300">{asset.volatility}%</span>
                        </div>
                      </div>

                      <button className="mt-4 w-full py-2 bg-sky-500/10 hover:bg-sky-500 text-sky-400 hover:text-slate-950 text-[10px] font-black rounded-lg transition-all uppercase tracking-widest border border-sky-500/20">
                        Calcular Estratégia
                      </button>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}

            {activeTab === 'strategy' && (
              <motion.div
                key="strategy"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <StrategyView strategy={strategy} loading={loading} />
              </motion.div>
            )}

            {activeTab === 'alerts' && (
               <motion.div
                key="alerts"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <h2 className="text-2xl font-bold text-white mb-6">Central de Alertas</h2>
                <AlertItem 
                  title="Oportunidade Pendente: PETR4" 
                  description="Distorção detectada entre Petr4C380 e Petr4C400. Razão risco/retorno superior a 3:1."
                  type="opportunity"
                />
                <AlertItem 
                  title="Riscos Elevados: BBDC4" 
                  description="Volatilidade aumentou 12% nos últimos 15 minutos. Monitorar pernas de venda."
                  type="risk"
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
function AlertItem({ title, description, type }: { title: string, description: string, type: 'opportunity' | 'risk' }) {
  return (
    <div className={cn(
      "p-6 rounded-2xl border flex gap-4 items-start",
      type === 'opportunity' ? "bg-emerald-500/5 border-emerald-500/20" : "bg-red-500/5 border-red-500/20"
    )}>
      <div className={cn(
        "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
        type === 'opportunity' ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
      )}>
        {type === 'opportunity' ? <Zap className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
      </div>
      <div>
        <h4 className="font-bold text-white mb-1">{title}</h4>
        <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
        <button className="mt-3 text-xs font-bold text-sky-400 hover:underline uppercase tracking-tight">Ver Detalhes da Análise</button>
      </div>
    </div>
  );
}
