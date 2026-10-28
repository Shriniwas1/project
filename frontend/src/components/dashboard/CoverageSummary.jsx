import React from 'react';
import { Layers, Database, CheckCircle, AlertTriangle, Info, Clock } from 'lucide-react';

export default function CoverageSummary({ analytics, comparison, loading }) {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg animate-pulse h-48">
        <div className="h-4 bg-slate-800 rounded w-1/3 mb-4"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-slate-800 rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  const expected = analytics?.expected_interval_count ?? comparison?.expected_interval_count ?? 0;
  const actualCount = analytics?.actual_interval_count ?? comparison?.actual_interval_count ?? 0;
  const uniqueHourlyFc = analytics?.unique_hourly_forecast_count ?? comparison?.unique_hourly_forecast_count ?? 0;
  const fcCovered = analytics?.forecast_covered_interval_count ?? comparison?.forecast_covered_interval_count ?? 0;
  const matched = analytics?.matched_interval_count ?? comparison?.matched_interval_count ?? 0;
  const zeroActuals = analytics?.zero_actual_excluded_count ?? 0;
  const mapeEligible = analytics?.mape_eligible_count ?? 0;
  const missingActual = comparison?.missing_actual_intervals ?? (expected - actualCount);
  const missingForecast = comparison?.missing_forecast_intervals ?? (expected - fcCovered);

  const matchedPercent = expected > 0 ? ((matched / expected) * 100).toFixed(1) : 0;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
        <div className="flex items-center space-x-2 text-slate-200 font-semibold text-sm">
          <Layers className="h-4 w-4 text-cyan-400" />
          <span>Data Coverage & Resolution Accounting Audit</span>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-400">Coverage Matched:</span>
          <span className="font-mono font-bold text-cyan-400 bg-slate-800 px-2 py-0.5 rounded">
            {matched} / {expected} ({matchedPercent}%)
          </span>
        </div>
      </div>

      {/* 5-way coverage cards grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
        {/* 1. Expected Half-Hours */}
        <div className="bg-slate-950/70 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-slate-400 text-[11px]">Expected Half-Hours</span>
          <span className="text-xl font-bold text-white mt-1">{expected}</span>
          <span className="text-[10px] text-slate-500 mt-1">Days × 48 SPs</span>
        </div>

        {/* 2. Actuals Available */}
        <div className="bg-slate-950/70 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-slate-400 text-[11px]">Actuals in DB</span>
          <span className="text-xl font-bold text-cyan-400 mt-1">{actualCount}</span>
          <span className="text-[10px] text-slate-500 mt-1">FUELHH 30-min SPs</span>
        </div>

        {/* 3. Unique Hourly Forecasts */}
        <div className="bg-slate-950/70 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-slate-400 text-[11px]">Hourly Forecasts</span>
          <span className="text-xl font-bold text-amber-400 mt-1">{uniqueHourlyFc}</span>
          <span className="text-[10px] text-slate-500 mt-1">WINDFOR 1-hr native</span>
        </div>

        {/* 4. Covered Half-Hours */}
        <div className="bg-slate-950/70 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-slate-400 text-[11px]">Covered Half-Hours</span>
          <span className="text-xl font-bold text-slate-200 mt-1">{fcCovered}</span>
          <span className="text-[10px] text-slate-500 mt-1">Bridged (2 per hour)</span>
        </div>

        {/* 5. Matched Rows */}
        <div className="bg-slate-950/70 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-slate-400 text-[11px]">Matched Rows</span>
          <span className="text-xl font-bold text-emerald-400 mt-1">{matched}</span>
          <span className="text-[10px] text-slate-500 mt-1">MAE/RMSE Denom</span>
        </div>

        {/* 6. MAPE Eligible */}
        <div className="bg-slate-950/70 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
          <span className="text-slate-400 text-[11px]">MAPE Eligible</span>
          <span className="text-xl font-bold text-purple-400 mt-1">{mapeEligible}</span>
          <span className="text-[10px] text-slate-500 mt-1">Non-zero actuals</span>
        </div>
      </div>

      {/* Audit & Bridge Explanations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
        <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 text-slate-400 space-y-1">
          <div className="font-semibold text-slate-300 flex items-center space-x-1.5">
            <Clock className="h-3.5 w-3.5 text-amber-400" />
            <span>Resolution Bridge Architecture</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            WINDFOR publishes at 1-hour resolution, while FUELHH operates on 30-minute settlement periods. Each 1-hour forecast maps to two half-hourly actuals (<code className="text-cyan-300 font-mono">:00</code> and <code className="text-cyan-300 font-mono">:30</code>). Therefore, {uniqueHourlyFc} hourly forecast records cover {fcCovered} half-hourly settlement intervals.
          </p>
        </div>

        <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 text-slate-400 space-y-1">
          <div className="font-semibold text-slate-300 flex items-center space-x-1.5">
            <Info className="h-3.5 w-3.5 text-cyan-400" />
            <span>Missing Data Integrity</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            Missing actuals ({missingActual}) and missing forecasts ({missingForecast}) are excluded from metric denominators and never substituted with 0 MW. Matched intervals ({matched}) form the strict basis for MAE, RMSE, and Bias. {zeroActuals} zero-actual intervals are excluded from MAPE to prevent division by zero.
          </p>
        </div>
      </div>
    </div>
  );
}
