/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { motion } from 'motion/react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, ArrowUpRight, ArrowDownRight, TrendingUp, TrendingDown, Scale, BarChart3 } from 'lucide-react';
import { AssetData } from '../types';
import { formatCurrency, formatPercent, cn } from '../lib/utils';

interface DashboardProps {
  assets: AssetData[];
  onSelectAsset: (asset: AssetData) => void;
}

const chartData = [
  { time: '09:00', price: 37.8 },
  { time: '10:00', price: 38.1 },
  { time: '11:00', price: 37.9 },
  { time: '12:00', price: 38.4 },
  { time: '13:00', price: 38.6 },
  { time: '14:00', price: 38.5 },
  { time: '15:00', price: 38.8 },
  { time: '16:00', price: 38.5 },
];

export function Dashboard({ assets, onSelectAsset }: DashboardProps) {
  return (
    <div className="space-y-8">
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">Monitor de Mercado</h2>
          <p className="text-slate-400 mt-1">Análise em tempo real de ativos e derivativos da B3.</p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[160px] bg-slate-900 shadow-xl p-4 rounded-2xl border border-slate-800 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <TrendingUp className="text-emerald-400 w-7 h-7" />
            </div>
            <div>
              <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Sentiment</p>
              <p className="text-xl font-bold text-emerald-400">OTIMISTA</p>
            </div>
          </div>
          <div className="flex-1 min-w-[160px] bg-slate-900 shadow-xl p-4 rounded-2xl border border-slate-800 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-sky-500/10 flex items-center justify-center">
              <Activity className="text-sky-400 w-7 h-7" />
            </div>
            <div>
              <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">IV Terminal</p>
              <p className="text-xl font-bold text-sky-400">24.2%</p>
            </div>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
        <div className="xl:col-span-8 bg-slate-900 rounded-3xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col">
          <div className="p-6 md:p-8 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-sky-500/10 rounded-2xl flex items-center justify-center border border-sky-500/10">
                <BarChart3 className="text-sky-400 w-7 h-7" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">PETR4 - Petróleo Brasil</h3>
                <p className="text-xs text-slate-500 font-mono">SPOT_PRICE • INTRADAY_VOL</p>
              </div>
            </div>
            <div className="sm:text-right bg-slate-800/20 sm:bg-transparent p-3 sm:p-0 rounded-xl">
              <p className="text-2xl font-bold text-white tracking-tight">R$ 38,50</p>
              <p className="text-sm font-bold text-emerald-400 flex items-center sm:justify-end gap-1 font-mono">
                <ArrowUpRight className="w-4 h-4" /> +1.20%
              </p>
            </div>
          </div>
          <div className="h-[350px] md:h-[400px] w-full p-6">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#38BDF8" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                <XAxis dataKey="time" stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0F172A', border: '1px solid #1E293B', borderRadius: '8px' }}
                  itemStyle={{ color: '#38BDF8' }}
                />
                <Area type="monotone" dataKey="price" stroke="#38BDF8" fillOpacity={1} fill="url(#colorPrice)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="xl:col-span-4 bg-slate-900 rounded-3xl border border-slate-800 p-6 md:p-8 flex flex-col shadow-2xl">
          <div className="flex items-center justify-between mb-8">
            <h3 className="font-bold text-white uppercase text-[10px] tracking-[0.2em] text-slate-500">Scanner B3 • Live</h3>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] text-emerald-400 font-bold">ATIVO</span>
            </div>
          </div>
          <div className="flex-1 space-y-4">
            {assets.slice(0, 5).map((asset) => (
              <motion.div 
                key={asset.ticker}
                whileHover={{ scale: 1.02, x: 5 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => onSelectAsset(asset)}
                className="group p-5 bg-slate-800/20 rounded-2xl border border-slate-800 hover:border-sky-500/30 hover:bg-slate-800/40 cursor-pointer transition-all duration-300"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-slate-900 border border-slate-700 flex items-center justify-center text-[10px] font-bold text-slate-400">
                      {asset.ticker.substring(0, 2)}
                    </div>
                    <span className="font-bold text-white tracking-widest text-sm">{asset.ticker}</span>
                  </div>
                  <span className={cn(
                    "font-mono text-sm font-bold px-2 py-0.5 rounded-lg",
                    asset.change >= 0 ? "text-emerald-400 bg-emerald-500/10" : "text-red-400 bg-red-500/10"
                  )}>
                    {asset.change > 0 ? "+" : ""}{asset.change}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400 font-medium">{formatCurrency(asset.price)}</span>
                  <div className="flex items-center gap-2">
                    {asset.change >= 0 ? <TrendingUp className="w-3 h-3 text-emerald-400" /> : <TrendingDown className="w-3 h-3 text-red-400" />}
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-tighter">{asset.trend}</span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
          <button className="mt-8 w-full py-4 rounded-2xl bg-slate-800 border border-slate-700 text-xs font-bold text-slate-300 hover:bg-slate-700 hover:text-white transition-all uppercase tracking-widest">
            Acessar Scanner Completo
          </button>
        </div>
      </div>
    </div>
  );
}
