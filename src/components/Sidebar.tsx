/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { motion, AnimatePresence } from 'motion/react';
import { Activity, AlertTriangle, BarChart3, Bot, Cpu, LayoutDashboard, Radar, ShieldCheck, Zap, Menu, X } from 'lucide-react';
import { RobotState } from '../types';
import { cn } from '../lib/utils';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  robots: RobotState[];
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

export function Sidebar({ activeTab, setActiveTab, robots, isOpen, setIsOpen }: SidebarProps) {
  const menuItems = [
    { id: 'dashboard', label: 'Monitor', icon: LayoutDashboard },
    { id: 'scanner', label: 'Scanner B3', icon: Radar },
    { id: 'strategy', label: 'Estratégias', icon: Zap },
    { id: 'alerts', label: 'Alertas', icon: AlertTriangle },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          />
        )}
      </AnimatePresence>

      <div className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-full transition-transform duration-300 lg:relative lg:translate-x-0",
        isOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-sky-400 mb-1">
              <Bot className="w-6 h-6" />
              <h1 className="font-bold text-lg tracking-tight text-white">B3 Opções Pro</h1>
            </div>
            <p className="text-[10px] text-slate-500 font-mono">ALPHA ENGINE v1.0.4</p>
          </div>
          <button onClick={() => setIsOpen(false)} className="lg:hidden text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setActiveTab(item.id);
                if (window.innerWidth < 1024) setIsOpen(false);
              }}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group",
                activeTab === item.id 
                  ? "bg-sky-500/10 text-sky-400 border border-sky-500/10 shadow-[0_0_15px_rgba(56,189,248,0.05)]" 
                  : "text-slate-400 hover:text-white hover:bg-slate-800/50"
              )}
            >
              <item.icon className={cn("w-5 h-5", activeTab === item.id ? "text-sky-400" : "text-slate-500 group-hover:text-slate-300")} />
              <span className="font-medium text-sm">{item.label}</span>
              {activeTab === item.id && (
                <motion.div layoutId="active-pill" className="ml-auto w-1 h-4 bg-sky-500 rounded-full shadow-[0_0_8px_#38bdf8]" />
              )}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-800/50 bg-slate-900/50">
          <h3 className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.2em] px-2 mb-4 flex items-center gap-2">
            <Cpu className="w-3 h-3" /> ROBÔS ATIVOS
          </h3>
          <div className="space-y-4">
            {robots.map((robot) => (
              <div key={robot.id} className="px-2">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] font-semibold text-slate-300">{robot.name}</span>
                  <div className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    robot.status === 'IDLE' ? "bg-slate-700" : "bg-emerald-400 animate-pulse shadow-[0_0_8px_#10b981]"
                  )} />
                </div>
                <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                   <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: robot.status === 'IDLE' ? '0%' : '100%' }}
                    className="h-full bg-slate-600"
                   />
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="p-4 bg-slate-950/40 border-t border-slate-800">
          <div className="flex items-center gap-3 p-2 rounded-xl bg-slate-800/20 border border-slate-700/30">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/10">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-[11px] font-bold text-white">Risco Zero-Trust</p>
              <p className="text-[9px] text-slate-500">Monitorando B3</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

