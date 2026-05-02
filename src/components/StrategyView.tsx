/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { motion } from 'motion/react';
import { AreaChart, Area, ReferenceLine, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { Info, HelpCircle, CheckCircle2, ShieldAlert, Zap, BookOpen, Calculator, Target, BarChart3, TrendingUp, Activity } from 'lucide-react';
import { Strategy } from '../types';
import { formatCurrency, cn } from '../lib/utils';

interface StrategyViewProps {
  strategy: Strategy | null;
  loading: boolean;
}

export function StrategyView({ strategy, loading }: StrategyViewProps) {
  if (loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-12 space-y-8 min-h-[600px]">
        <div className="relative">
          <div className="w-24 h-24 border-4 border-slate-800 rounded-full" />
          <motion.div 
            animate={{ rotate: 360 }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
            className="absolute inset-0 w-24 h-24 border-4 border-sky-500 border-t-transparent rounded-full shadow-[0_0_20px_rgba(56,189,248,0.2)]"
          />
        </div>
        <div className="text-center space-y-3">
          <h3 className="text-2xl font-bold text-white tracking-tight">IA Analisando Cenários</h3>
          <p className="text-slate-400 max-w-sm mx-auto leading-relaxed text-sm">O robô de estratégia está varrendo a grade para encontrar strikes com a melhor relação risco/retorno.</p>
        </div>
      </div>
    );
  }

  if (!strategy) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-12 text-center min-h-[600px]">
        <div className="w-24 h-24 bg-slate-900 border border-slate-800 rounded-3xl flex items-center justify-center mb-8 shadow-2xl relative group">
          <Zap className="w-10 h-10 text-slate-700 group-hover:text-sky-500 transition-colors" />
          <div className="absolute -top-1 -right-1 w-4 h-4 bg-sky-500/20 rounded-full animate-ping" />
        </div>
        <h3 className="text-2xl font-bold text-white tracking-tight">Seleção de Ativo Pendente</h3>
        <p className="text-slate-400 max-w-md mt-3 leading-relaxed">Selecione um ativo no monitor para que nossos robôs automatizados calibrem uma estratégia baseada em probabilidades.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 h-full font-mono text-[11px] bg-[#1a1a1a] p-1 border border-slate-800 rounded-md overflow-hidden select-none">
      {/* Header Profit Style */}
      <div className="bg-[#2a2a2a] p-2 flex items-center gap-6 border border-[#3a3a3a]">
        <div className="flex items-center gap-2">
          <span className="bg-orange-500 text-black px-1 font-bold rounded-sm"> {strategy.ticker} </span>
          <span className="text-white font-bold text-sm">36,20</span>
          <span className="text-red-500 font-bold">-0,71%</span>
        </div>
        <div className="flex items-center gap-4 text-slate-400 text-[10px]">
          <div>BID <span className="text-white">36,20</span></div>
          <div>ASK <span className="text-white">36,21</span></div>
          <div>VOL. HIST <span className="text-white">33,40%</span></div>
          <div>VOL. IMP <span className="text-sky-400">66,33%</span></div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-slate-500">Layout:</span>
          <select className="bg-[#1a1a1a] border border-[#3a3a3a] text-white px-2 py-0.5 rounded cursor-pointer outline-none">
            <option>C. Abertos / Delta</option>
          </select>
        </div>
      </div>

      {/* Strategy Selector Profit Style */}
      <div className="bg-[#2a2a2a] p-1 flex items-center gap-4 border border-[#3a3a3a]">
        <div className="flex items-center gap-2">
          <span className="text-slate-400 uppercase text-[10px]">Estratégia:</span>
          <div className="bg-[#1a1a1a] border border-sky-500/50 text-sky-400 px-3 py-1 rounded font-bold min-w-[200px] flex justify-between items-center cursor-pointer">
            {strategy.type} <Info className="w-3 h-3" />
          </div>
        </div>
        <div className="bg-sky-600/20 text-sky-400 px-3 py-1 rounded border border-sky-600/30 font-bold cursor-pointer hover:bg-sky-600/30">
          CRIAR
        </div>
        <div className="ml-auto flex items-center gap-4">
          <div className="flex items-center gap-2">
             <span className="text-slate-500">Strikes:</span>
             <input type="number" defaultValue="8" className="w-12 bg-[#1a1a1a] border border-[#3a3a3a] text-white text-center px-1 rounded outline-none" />
          </div>
          <label className="flex items-center gap-2 text-slate-400 cursor-pointer">
            <input type="checkbox" defaultChecked className="accent-sky-500" /> Código do Ativo
          </label>
        </div>
      </div>

      {/* Grade de Opções (Matrix) */}
      <div className="flex-1 overflow-auto bg-[#131313] border border-[#3a3a3a]">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-[#2a2a2a] text-slate-400 text-[10px] uppercase font-bold border-b border-[#3a3a3a] z-10">
             <tr>
               <th className="p-1 px-3 text-center border-r border-[#3a3a3a]" colSpan={6}>CALLS</th>
               <th className="p-1 px-3 text-center bg-[#1a1a1a] text-white" rowSpan={1}>STRIKE</th>
               <th className="p-1 px-3 text-center border-l border-[#3a3a3a]" colSpan={6}>PUTS</th>
             </tr>
             <tr className="bg-[#232323]">
               <th className="p-1 font-normal">Ativo</th>
               <th className="p-1 font-normal">Tipo</th>
               <th className="p-1 font-normal text-right">C.Ab.</th>
               <th className="p-1 font-normal text-right">Delta</th>
               <th className="p-1 font-normal text-right">Bid</th>
               <th className="p-1 font-normal text-right border-r border-[#3a3a3a]">Ask</th>
               <th className="p-1 bg-[#1a1a1a]"></th>
               <th className="p-1 font-normal text-left border-l border-[#3a3a3a]">Bid</th>
               <th className="p-1 font-normal text-left">Ask</th>
               <th className="p-1 font-normal text-left">Delta</th>
               <th className="p-1 font-normal text-left">C.Ab.</th>
               <th className="p-1 font-normal">Tipo</th>
               <th className="p-1 font-normal">Ativo</th>
             </tr>
          </thead>
          <tbody>
            {[...Array(10)].map((_, i) => {
              const strike = strategy.legs[0].option.strike - (5 - i) * 0.5;
              const isStrategyStrike = strategy.legs.some(leg => Math.abs(leg.option.strike - strike) < 0.1);
              
              return (
                <tr key={i} className={cn(
                  "border-b border-[#1f1f1f] hover:bg-[#2a2a2a]/50 text-[10px]",
                  isStrategyStrike && "bg-sky-900/20"
                )}>
                  <td className="p-1 px-3 text-slate-500">BBASL{350 + i}</td>
                  <td className="p-1 text-center"><span className="w-2 h-2 bg-blue-500 rounded-full inline-block" /></td>
                  <td className="p-1 text-right text-slate-400">2,56M</td>
                  <td className="p-1 text-right text-slate-400">0,50</td>
                  <td className="p-1 text-right text-red-500 font-bold">0,86</td>
                  <td className="p-1 text-right text-red-500 font-bold border-r border-[#3a3a3a]">0,88</td>
                  
                  <td className="p-1 text-center bg-[#1a1a1a] text-white font-bold">{strike.toFixed(2)}</td>
                  
                  <td className="p-1 text-left text-emerald-500 font-bold border-l border-[#3a3a3a]">0,94</td>
                  <td className="p-1 text-left text-emerald-500 font-bold">0,95</td>
                  <td className="p-1 text-left text-slate-400">-0,50</td>
                  <td className="p-1 text-left text-slate-400">733k</td>
                  <td className="p-1 text-center"><span className="w-2 h-2 bg-blue-500 rounded-full inline-block" /></td>
                  <td className="p-1 px-3 text-slate-500">BBASX{350 + i}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Painel Inferior Profit Style */}
      <div className="bg-[#2a2a2a] p-3 border border-[#3a3a3a] grid grid-cols-12 gap-4">
        {/* Gráfico Mini Payoff */}
        <div className="col-span-3 bg-black/40 rounded-sm border border-[#3a3a3a] h-[140px] p-2 relative">
          <div className="text-[9px] text-slate-500 mb-1">PROJEÇÃO PAYOFF</div>
          <div className="h-full w-full opacity-60">
             <ResponsiveContainer width="100%" height="90%">
                <AreaChart data={[
                  {x: 0, y: -strategy.maxLoss},
                  {x: 50, y: 0},
                  {x: 80, y: strategy.maxProfit},
                  {x: 100, y: strategy.maxProfit}
                ]}>
                  <Area type="step" dataKey="y" stroke="#00ff00" fill="#00ff00" fillOpacity={0.1} />
                  <ReferenceLine y={0} stroke="#555" />
                </AreaChart>
             </ResponsiveContainer>
          </div>
        </div>

        {/* Resumo da Estratégia */}
        <div className="col-span-6 flex flex-col gap-2">
           <div className="grid grid-cols-4 gap-2 text-[10px]">
              <div className="bg-[#1a1a1a] p-1 border border-[#3a3a3a] text-center">
                 <div className="text-slate-500 uppercase text-[9px]">Ganho Máx</div>
                 <div className="text-emerald-500 font-bold">{formatCurrency(strategy.maxProfit)}</div>
              </div>
              <div className="bg-[#1a1a1a] p-1 border border-[#3a3a3a] text-center">
                 <div className="text-slate-500 uppercase text-[9px]">Perda Máx</div>
                 <div className="text-red-500 font-bold">{formatCurrency(strategy.maxLoss)}</div>
              </div>
              <div className="bg-[#1a1a1a] p-1 border border-[#3a3a3a] text-center">
                 <div className="text-slate-500 uppercase text-[9px]">Delta</div>
                 <div className="text-white">0,05</div>
              </div>
              <div className="bg-[#1a1a1a] p-1 border border-[#3a3a3a] text-center">
                 <div className="text-slate-500 uppercase text-[9px]">Theta</div>
                 <div className="text-white">0,00</div>
              </div>
           </div>

           <div className="bg-[#1a1a1a] p-2 border border-[#3a3a3a] flex-1 overflow-auto">
              <table className="w-full text-[9px]">
                <thead className="text-slate-500">
                  <tr className="border-b border-[#333]">
                    <th className="text-left py-1">Lado</th>
                    <th className="text-left font-normal py-1">C/P</th>
                    <th className="text-left font-normal py-1">Ativo</th>
                    <th className="text-right font-normal py-1">Strike</th>
                    <th className="text-right font-normal py-1">Preço</th>
                    <th className="text-right font-normal py-1">Qtd</th>
                  </tr>
                </thead>
                <tbody>
                  {strategy.legs.map((leg, idx) => (
                    <tr key={idx} className="text-white font-bold">
                      <td className="py-1">
                        <span className={cn(
                          "w-4 h-4 inline-flex items-center justify-center rounded-sm text-[8px]",
                          leg.action === 'BUY' ? "bg-emerald-500 text-black" : "bg-red-500 text-black"
                        )}>{leg.action[0]}</span>
                      </td>
                      <td className="py-1">{leg.option.type === 'CALL' ? 'Call' : 'Put'}</td>
                      <td className="py-1">{leg.option.ticker}</td>
                      <td className="py-1 text-right">{leg.option.strike.toFixed(2)}</td>
                      <td className="py-1 text-right">R$ {leg.option.premium.toFixed(2)}</td>
                      <td className="py-1 text-right underline cursor-pointer">100</td>
                    </tr>
                  ))}
                </tbody>
              </table>
           </div>
        </div>

        {/* Boleta Lateral e POP */}
        <div className="col-span-3 flex flex-col gap-2">
           <div className="bg-[#1a1a1a] p-2 border border-yellow-500/50 flex flex-col items-center justify-center rounded-sm">
              <div className="text-yellow-500 font-bold text-[9px] uppercase tracking-widest">POP</div>
              <div className="text-2xl font-bold text-white leading-none">{strategy.probability}%</div>
              <div className="text-[8px] text-slate-500">PROB. DE LUCRO</div>
           </div>

           <div className="bg-[#1a1a1a] p-2 border border-[#3a3a3a] flex flex-col gap-1">
              <div className="flex justify-between text-[9px]">
                <span className="text-slate-500">Custo Mercado:</span>
                <span className="text-white">R$ -0,15</span>
              </div>
              <div className="flex justify-between text-[9px]">
                <span className="text-slate-500">Custo Alvo:</span>
                <span className="text-white">-0,15</span>
              </div>
              <div className="mt-1 flex justify-between text-[10px] font-bold border-t border-[#333] pt-1">
                <span className="text-slate-400">Total:</span>
                <span className="text-emerald-500">R$ -15,00</span>
              </div>
           </div>

           <button className="bg-sky-600 hover:bg-sky-500 text-white font-bold py-2 rounded-sm text-xs shadow-lg transition-all active:scale-95">
              Enviar Ordem
           </button>
        </div>
      </div>

      {/* Footer Tabs Profit Style */}
      <div className="bg-[#2a2a2a] flex items-center px-2 py-1 border border-[#3a3a3a] gap-1">
         <div className="bg-[#1a1a1a] text-white px-3 py-0.5 text-[9px] border-x border-t border-sky-500/50 rounded-t-sm font-bold">Grade</div>
         <div className="text-slate-500 px-3 py-0.5 text-[9px] hover:text-white cursor-pointer transition-colors">Gráfico</div>
         <div className="text-slate-500 px-3 py-0.5 text-[9px] hover:text-white cursor-pointer transition-colors">Vols</div>
         <div className="text-slate-500 px-3 py-0.5 text-[9px] hover:text-white cursor-pointer transition-colors">Acompanhamento</div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }: { label: string, value: string, icon: any, color: string }) {
  const colors: Record<string, string> = {
    emerald: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    red: "bg-red-500/10 text-red-400 border-red-500/20",
    sky: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    slate: "bg-slate-800 text-slate-400 border-slate-700"
  };

  return (
    <div className={cn("p-4 rounded-2xl border flex flex-col gap-2", colors[color])}>
      <div className="flex items-center gap-2 opacity-80">
        <Icon className="w-4 h-4" />
        <span className="text-[10px] font-bold uppercase tracking-widest">{label}</span>
      </div>
      <p className="text-lg font-bold truncate">{value}</p>
    </div>
  );
}
