import React from 'react';
import { Calendar, Clock, RefreshCw, Filter } from 'lucide-react';

export default function FilterControls({
  startDate,
  endDate,
  decisionCutoff,
  onStartDateChange,
  onEndDateChange,
  onDecisionCutoffChange,
  onApply,
  loading,
}) {
  const setPreset = (start, end) => {
    onStartDateChange(start);
    onEndDateChange(end);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
        <div className="flex items-center space-x-2 text-slate-200 font-semibold text-sm">
          <Filter className="h-4 w-4 text-cyan-400" />
          <span>Procurement Parameters & Date Selection</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-slate-400 mr-1 text-[11px]">Quick Presets:</span>
          <button
            type="button"
            onClick={() => setPreset('2026-01-01', '2026-01-07')}
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            Jan 1–7
          </button>
          <button
            type="button"
            onClick={() => setPreset('2026-01-01', '2026-01-14')}
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            Jan 1–14
          </button>
          <button
            type="button"
            onClick={() => setPreset('2026-01-01', '2026-01-31')}
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            Full Jan (1–31)
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
        {/* Start Date */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center space-x-1.5">
            <Calendar className="h-3.5 w-3.5 text-cyan-400" />
            <span>Start Date (Europe/London)</span>
          </label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
          />
        </div>

        {/* End Date */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center space-x-1.5">
            <Calendar className="h-3.5 w-3.5 text-cyan-400" />
            <span>End Date (Inclusive)</span>
          </label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
          />
        </div>

        {/* Decision Cutoff */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center justify-between">
            <span className="flex items-center space-x-1.5">
              <Clock className="h-3.5 w-3.5 text-amber-400" />
              <span>D-1 Decision Cutoff</span>
            </span>
            <span className="text-[10px] text-slate-500">Default: 11:00</span>
          </label>
          <input
            type="text"
            value={decisionCutoff}
            onChange={(e) => onDecisionCutoffChange(e.target.value)}
            placeholder="11:00"
            className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent font-mono"
          />
        </div>

        {/* Apply Button */}
        <div>
          <button
            type="button"
            onClick={onApply}
            disabled={loading}
            className="w-full flex items-center justify-center space-x-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium px-4 py-2 rounded-lg transition-all shadow-md shadow-cyan-900/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Evaluating...' : 'Apply Filters'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
