/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { AlertTriangle, Bot, LayoutDashboard, LogOut, Radar, Zap, X } from 'lucide-react';
import { cn } from '../lib/utils';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  alertCount: number;
  onLogout: () => void;
}

const MENU = [
  { id: 'dashboard', label: 'Monitor', icon: LayoutDashboard },
  { id: 'scanner', label: 'Scanner B3', icon: Radar },
  { id: 'strategy', label: 'Estratégias', icon: Zap },
  { id: 'alerts', label: 'Alertas', icon: AlertTriangle },
];

export function Sidebar({ activeTab, setActiveTab, isOpen, setIsOpen, alertCount, onLogout }: SidebarProps) {
  return (
    <>
      {isOpen && <div onClick={() => setIsOpen(false)} className="fixed inset-0 bg-black/60 z-40 lg:hidden" />}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-full transition-transform duration-300 lg:relative lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sky-400">
            <Bot className="w-6 h-6" />
            <h1 className="font-bold text-lg tracking-tight text-white">B3 Opções Pro</h1>
          </div>
          <button aria-label="Fechar menu" onClick={() => setIsOpen(false)} className="lg:hidden text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {MENU.map((item) => (
            <button
              key={item.id}
              aria-current={activeTab === item.id ? 'page' : undefined}
              onClick={() => {
                setActiveTab(item.id);
                setIsOpen(false);
              }}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors',
                activeTab === item.id ? 'bg-sky-500/10 text-sky-400' : 'text-slate-400 hover:text-white hover:bg-slate-800/50',
              )}
            >
              <item.icon className="w-5 h-5" />
              <span className="font-medium text-sm">{item.label}</span>
              {item.id === 'alerts' && alertCount > 0 && (
                <span className="ml-auto text-xs font-bold bg-slate-800 text-slate-200 rounded-full px-2 py-0.5">{alertCount}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-800 space-y-3">
          <p className="text-xs text-slate-500 leading-relaxed">Análise e decisão. Este app não envia ordens.</p>
          <button onClick={onLogout} className="flex items-center gap-2 text-sm text-slate-400 hover:text-white">
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
      </div>
    </>
  );
}
