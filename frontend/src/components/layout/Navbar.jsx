import React from 'react';
import {
  ShieldAlert,
  LayoutDashboard,
  Search,
  Cpu,
  Layers,
  Clock,
  Database,
  Network,
} from 'lucide-react';
import { StatusDot } from '../common/StatusDot';

export function Navbar({ activeTab, setActiveTab, health }) {
  const tgConnected = health?.components?.tigergraph?.status === 'connected';

  const navItems = [
    { id: 'workspace', label: 'Investigation Workspace', icon: Search, primary: true },
    { id: 'overview', label: '20-Case Overview', icon: LayoutDashboard },
    { id: 'evidence', label: 'Case Evidence', icon: Layers },
    { id: 'graph', label: 'Relationship Graph', icon: Network },
    { id: 'timeline', label: 'Investigation Timeline', icon: Clock },
    { id: 'agents', label: 'Agents & Architecture', icon: Cpu },
    { id: 'health', label: 'System Health', icon: ShieldAlert },
  ];

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & System Brand */}
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-slate-900 text-white flex items-center justify-center shadow-xs">
              <ShieldAlert className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-900 text-base tracking-tight">
                  Fraud Investigation System
                </span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                  IEEE-HHGOA
                </span>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                TigerGraph-powered multi-agent fraud investigation & decision support
              </p>
            </div>
          </div>

          {/* Demo Mode & System Status Badges */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1 bg-amber-50/80 border border-amber-200/90 rounded-full text-xs">
              <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
              <span className="font-bold text-amber-900 uppercase tracking-wider text-[10px]">Demo Mode</span>
              <span className="text-amber-700 text-[11px] font-medium hidden md:inline">• Stored Results (20 Cases)</span>
            </div>

            <div className="hidden lg:flex items-center gap-2">
              <div className="flex items-center gap-2 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-xs">
                <Database className="h-3.5 w-3.5 text-slate-500" />
                <span className="font-medium text-slate-700">TigerGraph:</span>
                <span className="flex items-center gap-1.5 font-medium text-slate-900">
                  <StatusDot status={tgConnected ? 'connected' : 'unavailable'} pulse={tgConnected} />
                  {tgConnected ? 'HHGOA_IEEE' : 'Offline'}
                </span>
              </div>

              <div className="flex items-center gap-2 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-xs">
                <Cpu className="h-3.5 w-3.5 text-slate-500" />
                <span className="font-medium text-slate-700">Workflow:</span>
                <span className="flex items-center gap-1.5 font-medium text-slate-900">
                  <StatusDot status="connected" />
                  LangGraph
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-1 border-t border-slate-100 overflow-x-auto py-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all cursor-pointer ${
                  isActive
                    ? item.primary
                      ? 'bg-slate-900 text-white shadow-xs font-semibold'
                      : 'bg-slate-100 text-slate-900 font-semibold'
                    : item.primary
                    ? 'text-indigo-600 hover:bg-indigo-50/70 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive && item.primary ? 'text-indigo-400' : ''}`} />
                {item.label}
                {item.primary && !isActive && (
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-600" />
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
