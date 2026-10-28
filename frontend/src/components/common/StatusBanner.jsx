import React from 'react';
import { Activity, AlertTriangle, CheckCircle, Info } from 'lucide-react';

export default function StatusBanner({ health, loading, error }) {
  if (loading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 text-xs text-slate-400 flex items-center justify-between animate-pulse">
        <div className="flex items-center space-x-2">
          <Activity className="h-4 w-4 text-cyan-400 animate-spin" />
          <span>Connecting to Wind Procurement Intelligence API...</span>
        </div>
      </div>
    );
  }

  if (error || !health) {
    return (
      <div className="bg-amber-950/30 border border-amber-800/60 rounded-lg p-3 text-xs text-amber-300 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          <span>Backend service offline or unreachable. Please verify backend is running on port 8000.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3.5 space-y-2 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <CheckCircle className="h-4 w-4 text-emerald-400" />
          <span className="font-semibold text-slate-200">Backend Connected</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400">Environment: {health.environment}</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400">Database: {health.database_connected ? 'Active (SQLite)' : 'Offline'}</span>
        </div>
        <div className="flex items-center space-x-3 text-slate-400">
          <span className="bg-slate-800 px-2.5 py-0.5 rounded text-cyan-400 font-mono">
            Default Cutoff: {health.default_decision_cutoff}
          </span>
          <span className="bg-slate-800 px-2.5 py-0.5 rounded text-slate-300">
            Scope: {health.dataset_scope}
          </span>
        </div>
      </div>

      <div className="flex items-start space-x-2 text-slate-400 border-t border-slate-800/80 pt-2 text-[11px] leading-relaxed">
        <Info className="h-3.5 w-3.5 text-cyan-400 mt-0.5 flex-shrink-0" />
        <p>
          <strong className="text-slate-300">Procurement Scope Note:</strong> This system evaluates UK national wind generation forecasts and verification metrics. It does not calculate total utility procurement requirements (demand, thermal plants, and market prices are outside scope). The 11:00 cutoff on D-1 is an initial client assumption and is fully configurable.
        </p>
      </div>
    </div>
  );
}
