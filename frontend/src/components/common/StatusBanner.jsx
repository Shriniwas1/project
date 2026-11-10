import React, { useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Database, Info, RefreshCw } from 'lucide-react';

export default function StatusBanner({ health, loading, error }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (loading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 text-xs text-slate-400 flex items-center justify-between animate-pulse">
        <div className="flex items-center space-x-2.5">
          <Activity className="h-4 w-4 text-cyan-400 animate-spin" />
          <span>Connecting to Wind Procurement Intelligence engine...</span>
        </div>
      </div>
    );
  }

  if (error || !health) {
    return (
      <div className="bg-amber-950/30 border border-amber-800/60 rounded-xl p-4 text-xs text-amber-300 flex items-start sm:items-center justify-between gap-3 shadow-md">
        <div className="flex items-start sm:items-center space-x-2.5">
          <AlertTriangle className="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5 sm:mt-0" />
          <div>
            <p className="font-semibold text-amber-200">Local Analytics Backend Offline</p>
            <p className="text-[11px] text-amber-400/90 mt-0.5">
              Cannot establish connection to FastAPI service at <code className="font-mono bg-amber-950 px-1 py-0.5 rounded">http://localhost:8000/api</code>. Start the backend with <code className="font-mono bg-amber-950 px-1 py-0.5 rounded">uvicorn backend.app.main:app --port 8000</code>.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 text-xs shadow-md space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: Health and state */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-slate-300">
          <div className="flex items-center space-x-1.5 text-emerald-400 font-semibold bg-emerald-950/70 border border-emerald-800/60 px-2.5 py-1 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Analytics Engine Online</span>
          </div>

          <span className="text-slate-600 hidden sm:inline">•</span>

          <span className="text-slate-400">
            Database: <strong className="text-slate-200 font-medium">SQLite Active</strong> ({health.actual_records?.toLocaleString() ?? 0} actuals, {health.forecast_records?.toLocaleString() ?? 0} vintages)
          </span>

          <span className="text-slate-600 hidden sm:inline">•</span>

          <span className="text-slate-400">
            Scope: <strong className="text-slate-200 font-medium">GB National Wind (January 2026)</strong>
          </span>
        </div>

        {/* Right: Expandable details toggle */}
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-slate-400 hover:text-cyan-400 text-[11px] font-medium flex items-center space-x-1 transition-colors ml-auto sm:ml-0"
        >
          <span>{isExpanded ? 'Hide Procurement Context' : 'View Procurement Context'}</span>
          {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* Expandable contextual drawer */}
      {isExpanded && (
        <div className="pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 leading-relaxed space-y-2 animate-in fade-in duration-200">
          <div className="flex items-start space-x-2 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
            <Info className="h-4 w-4 text-cyan-400 mt-0.5 flex-shrink-0" />
            <p>
              <strong className="text-slate-200">How to use this intelligence platform:</strong> Day-ahead wind forecasts inform your utility's volume commitments in the Day-Ahead Auction. Because forecasts locked at 11:00 on D-1 deviate from physical generation, your desk will experience volume imbalance. Use this dashboard to quantify historical bias, calibrate hedging haircuts, and avoid expensive Balancing Mechanism cash-out exposure.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
