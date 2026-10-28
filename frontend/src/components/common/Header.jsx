import React from 'react';
import { Wind, ShieldCheck, Clock, Layers, Database } from 'lucide-react';

export default function Header({ activeTab, setActiveTab }) {
  const tabs = [
    { id: 'overview', label: 'Dashboard Overview', icon: Layers },
    { id: 'forecasts', label: 'Forecast Vintages', icon: Wind },
    { id: 'actuals', label: 'Actual Outturn', icon: Database },
    { id: 'methodology', label: 'Methodology & Scope', icon: ShieldCheck },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-lg bg-cyan-600/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <Wind className="h-6 w-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-bold text-white tracking-tight">Wind Procurement Intelligence</span>
                <span className="px-2 py-0.5 text-xs font-medium bg-cyan-950 text-cyan-300 border border-cyan-800 rounded-full">
                  GB Market
                </span>
              </div>
              <p className="text-xs text-slate-400">Day-Ahead Wind Forecast Evaluation & Verification</p>
            </div>
          </div>

          <nav className="flex space-x-1 sm:space-x-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden md:inline">{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
