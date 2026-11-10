import React from 'react';
import { Wind, Layers, Database, BookOpen, Clock, Activity, ShieldCheck, ChevronRight } from 'lucide-react';

export default function Header({ activeTab, setActiveTab, health }) {
  const tabs = [
    {
      id: 'overview',
      label: 'Procurement Overview',
      subtitle: 'Executive intelligence & verification',
      icon: Layers,
    },
    {
      id: 'forecasts',
      label: 'Forecast Vintages',
      subtitle: 'Revision timelines (WINDFOR)',
      icon: Wind,
    },
    {
      id: 'actuals',
      label: 'Actual Outturn',
      subtitle: 'Settlement periods (FUELHH)',
      icon: Database,
    },
    {
      id: 'methodology',
      label: 'Methodology & Scope',
      subtitle: 'Cutoff rules & market definitions',
      icon: BookOpen,
    },
  ];

  return (
    <header className="border-b border-slate-800/80 bg-slate-900/95 backdrop-blur-md sticky top-0 z-50">
      {/* Top micro-bar: live market context */}
      <div className="border-b border-slate-800/60 bg-slate-950/60 px-4 sm:px-6 lg:px-8 py-1.5 text-xs">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-2 text-slate-400">
          <div className="flex items-center space-x-2">
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-800/50">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse"></span>
              GB Balancing Mechanism
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-[11px] text-slate-300">National Wind Generation Intelligence</span>
          </div>

          <div className="flex items-center space-x-4 text-[11px]">
            <span className="flex items-center space-x-1">
              <Clock className="w-3 h-3 text-cyan-400" />
              <span>Market Timezone: <strong className="text-slate-200 font-mono">Europe/London (GMT)</strong></span>
            </span>
            <span className="hidden sm:inline text-slate-600">|</span>
            <span className="hidden sm:inline">
              Data: <strong className="text-slate-200">Elexon BMRS</strong> (FUELHH & WINDFOR)
            </span>
          </div>
        </div>
      </div>

      {/* Main navigation bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Brand & Purpose */}
          <div className="flex items-center space-x-3.5">
            <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-cyan-500/20 via-sky-500/10 to-blue-600/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-sm shadow-cyan-950/50">
              <Wind className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg sm:text-xl font-bold text-white tracking-tight font-sans">
                  Wind Procurement Intelligence
                </span>
                <span className="px-2 py-0.5 text-[11px] font-medium bg-cyan-950/90 text-cyan-300 border border-cyan-800/70 rounded-full">
                  Day-Ahead Desk
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Ex-ante forecast verification & volume exposure analysis
              </p>
            </div>
          </div>

          {/* Clean Segmented Navigation Tabs */}
          <nav className="hidden lg:flex items-center space-x-1 bg-slate-950/80 p-1.5 rounded-xl border border-slate-800">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2.5 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-slate-800/90 text-white shadow-sm border border-slate-700/80'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <div className="text-left">
                    <span className="block font-semibold leading-tight">{tab.label}</span>
                  </div>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Mobile / Tablet Horizontal Scroll Navigation */}
        <div className="lg:hidden flex space-x-1 pb-3 overflow-x-auto no-scrollbar pt-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                  isActive
                    ? 'bg-slate-800 text-white border border-slate-700'
                    : 'text-slate-400 hover:text-slate-200 bg-slate-950/60'
                }`}
              >
                <Icon className={`h-3.5 w-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
}
