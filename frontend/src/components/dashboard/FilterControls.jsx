import React, { useState } from 'react';
import { Calendar, Clock, RefreshCw, SlidersHorizontal, Info, RotateCcw, ChevronDown } from 'lucide-react';

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
  const [showCutoffHelp, setShowCutoffHelp] = useState(false);

  const presets = [
    { label: 'Jan 1–7 (Week 1)', start: '2026-01-01', end: '2026-01-07', desc: 'Initial severe overforecast storm window' },
    { label: 'Jan 1–14 (Fortnight)', start: '2026-01-01', end: '2026-01-14', desc: 'Mid-month transition' },
    { label: 'Full Jan (1–31)', start: '2026-01-01', end: '2026-01-31', desc: 'All 1,488 settlement periods' },
    { label: 'Jan 1 Only', start: '2026-01-01', end: '2026-01-01', desc: 'Single-day benchmark (48 SP)' },
  ];

  const handlePreset = (start, end) => {
    onStartDateChange(start);
    onEndDateChange(end);
  };

  const handleReset = () => {
    onStartDateChange('2026-01-01');
    onEndDateChange('2026-01-07');
    onDecisionCutoffChange('11:00');
  };

  const isDefaultFilters = startDate === '2026-01-01' && endDate === '2026-01-07' && decisionCutoff === '11:00';

  return (
    <section className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Header with human-centred explanation & quick presets */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-lg bg-cyan-950/80 border border-cyan-800/60 text-cyan-400">
              <SlidersHorizontal className="h-4 w-4" />
            </div>
            <h2 className="text-base font-semibold text-white tracking-tight">
              Procurement Decision Window
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Select the physical delivery dates you wish to evaluate. Each day's forecast is filtered to only include predictions published prior to your D-1 decision cutoff, preventing look-ahead bias.
          </p>
        </div>

        {/* Quick Range Presets */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-medium text-slate-400 mr-1.5 uppercase tracking-wider">Presets:</span>
          {presets.map((p) => {
            const isSelected = startDate === p.start && endDate === p.end;
            return (
              <button
                key={p.label}
                type="button"
                onClick={() => handlePreset(p.start, p.end)}
                title={p.desc}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  isSelected
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                    : 'bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700/60'
                }`}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main filter inputs grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Start Date */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-200 flex items-center justify-between">
            <span className="flex items-center space-x-1.5">
              <Calendar className="h-3.5 w-3.5 text-cyan-400" />
              <span>Start Delivery Date</span>
            </span>
            <span className="text-[11px] text-slate-500 font-normal">UK Local (GMT)</span>
          </label>
          <div className="relative">
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={startDate}
              onChange={(e) => onStartDateChange(e.target.value)}
              className="w-full bg-slate-950/90 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all font-sans"
            />
          </div>
          <p className="text-[11px] text-slate-500">First delivery interval: 00:00 UTC</p>
        </div>

        {/* End Date */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-200 flex items-center justify-between">
            <span className="flex items-center space-x-1.5">
              <Calendar className="h-3.5 w-3.5 text-cyan-400" />
              <span>End Delivery Date</span>
            </span>
            <span className="text-[11px] text-slate-500 font-normal">Inclusive</span>
          </label>
          <div className="relative">
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={endDate}
              onChange={(e) => onEndDateChange(e.target.value)}
              className="w-full bg-slate-950/90 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all font-sans"
            />
          </div>
          <p className="text-[11px] text-slate-500">Final delivery interval: 23:30 UTC</p>
        </div>

        {/* Decision Cutoff Time */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-200 flex items-center space-x-1.5">
              <Clock className="h-3.5 w-3.5 text-amber-400" />
              <span>D-1 Decision Cutoff</span>
            </label>
            <button
              type="button"
              onClick={() => setShowCutoffHelp(!showCutoffHelp)}
              className="text-[11px] text-amber-400/90 hover:text-amber-300 flex items-center space-x-1 transition-colors"
            >
              <Info className="h-3 w-3" />
              <span>What is this?</span>
            </button>
          </div>
          <div className="relative">
            <input
              type="text"
              value={decisionCutoff}
              onChange={(e) => onDecisionCutoffChange(e.target.value)}
              placeholder="11:00"
              className="w-full bg-slate-950/90 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 transition-all font-mono"
            />
          </div>
          <p className="text-[11px] text-slate-500">
            Order book deadline on preceding day (HH:MM UK local)
          </p>
        </div>

        {/* Action Controls */}
        <div className="space-y-2 flex flex-col justify-end">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onApply}
              disabled={loading}
              className="flex-1 flex items-center justify-center space-x-2 bg-gradient-to-r from-cyan-600 via-sky-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold px-5 py-2.5 rounded-xl transition-all shadow-md shadow-cyan-950/40 disabled:opacity-50 disabled:cursor-not-allowed text-xs sm:text-sm"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Recalculating...' : 'Update Evaluation'}</span>
            </button>

            {!isDefaultFilters && (
              <button
                type="button"
                onClick={handleReset}
                title="Reset to default (Jan 1–7 at 11:00)"
                className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all flex items-center justify-center"
              >
                <RotateCcw className="h-4 w-4" />
              </button>
            )}
          </div>
          <p className="text-[11px] text-slate-500 text-center">
            Applies D-1 gate independently per delivery day
          </p>
        </div>
      </div>

      {/* Expandable educational explanation for procurement cutoff */}
      {showCutoffHelp && (
        <div className="bg-amber-950/20 border border-amber-800/60 rounded-xl p-4 text-xs text-amber-200/90 space-y-2 animate-in fade-in duration-200">
          <div className="flex items-center justify-between font-semibold text-amber-400">
            <span className="flex items-center space-x-1.5">
              <Clock className="h-4 w-4" />
              <span>Why the D-1 Publication Cutoff Matters to Procurement</span>
            </span>
            <button
              type="button"
              onClick={() => setShowCutoffHelp(false)}
              className="text-amber-400/80 hover:text-amber-200 text-[11px]"
            >
              Close
            </button>
          </div>
          <p className="leading-relaxed">
            In Great Britain wholesale electricity markets, power procurement teams must submit physical purchase and sale commitments to Day-Ahead Power Exchange auctions (such as EPEX SPOT UK or Nord Pool) before order books close (typically around 11:00 UK time on the day prior to delivery, D-1).
          </p>
          <p className="leading-relaxed text-amber-300/80">
            <strong>Zero Look-Ahead Guarantee:</strong> A forecast published at 14:00 on D-1 or on delivery day might be more accurate, but it was physically unavailable to your desk when commitments were made. Our engine strictly selects the latest vintage published <em>at or before</em> your chosen cutoff, guaranteeing an honest historical audit of your real procurement positions.
          </p>
        </div>
      )}
    </section>
  );
}
