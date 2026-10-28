import React from 'react';
import { Target, TrendingUp, TrendingDown, HelpCircle, Activity } from 'lucide-react';

export default function KpiCards({ analytics, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 h-32 flex flex-col justify-between">
            <div className="h-4 bg-slate-800 rounded w-1/2"></div>
            <div className="h-8 bg-slate-800 rounded w-3/4"></div>
            <div className="h-3 bg-slate-800 rounded w-1/3"></div>
          </div>
        ))}
      </div>
    );
  }

  const mae = analytics?.mae_mw;
  const rmse = analytics?.rmse_mw;
  const bias = analytics?.bias_mw;
  const mape = analytics?.mape_pct;
  const matchedCount = analytics?.matched_interval_count ?? 0;
  const zeroActualExcluded = analytics?.zero_actual_excluded_count ?? 0;

  // Formatting helpers
  const formatVal = (val, decimals = 2) => {
    if (val === null || val === undefined) return '—';
    return Number(val).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const isOverforecast = bias !== null && bias > 0;
  const isUnderforecast = bias !== null && bias < 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. MAE */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg relative overflow-hidden flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 text-xs">
          <span className="font-semibold text-slate-300 uppercase tracking-wider">Mean Absolute Error</span>
          <Target className="h-4 w-4 text-cyan-400" />
        </div>
        <div className="my-2">
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {formatVal(mae, 1)}
            </span>
            <span className="text-sm font-semibold text-cyan-400">MW</span>
          </div>
        </div>
        <div className="text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-2">
          <span>MAE = mean(|forecast − actual|)</span>
          <span className="text-slate-500">{matchedCount} intervals</span>
        </div>
      </div>

      {/* 2. RMSE */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg relative overflow-hidden flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 text-xs">
          <span className="font-semibold text-slate-300 uppercase tracking-wider">Root Mean Squared Error</span>
          <Activity className="h-4 w-4 text-indigo-400" />
        </div>
        <div className="my-2">
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {formatVal(rmse, 1)}
            </span>
            <span className="text-sm font-semibold text-indigo-400">MW</span>
          </div>
        </div>
        <div className="text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-2">
          <span>Penalizes larger forecast errors</span>
          <span className="text-slate-500">{matchedCount} intervals</span>
        </div>
      </div>

      {/* 3. Bias */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg relative overflow-hidden flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 text-xs">
          <span className="font-semibold text-slate-300 uppercase tracking-wider">Mean Forecast Bias</span>
          {isOverforecast ? (
            <TrendingUp className="h-4 w-4 text-amber-400" />
          ) : isUnderforecast ? (
            <TrendingDown className="h-4 w-4 text-blue-400" />
          ) : (
            <HelpCircle className="h-4 w-4 text-slate-400" />
          )}
        </div>
        <div className="my-2">
          <div className="flex items-baseline space-x-2">
            <span
              className={`text-3xl font-extrabold tracking-tight ${
                isOverforecast
                  ? 'text-amber-300'
                  : isUnderforecast
                  ? 'text-blue-300'
                  : 'text-white'
              }`}
            >
              {bias !== null && bias > 0 ? `+${formatVal(bias, 1)}` : formatVal(bias, 1)}
            </span>
            <span className="text-sm font-semibold text-slate-400">MW</span>
          </div>
        </div>
        <div className="text-[11px] flex items-center justify-between border-t border-slate-800/80 pt-2">
          {bias === null ? (
            <span className="text-slate-500">No matched data</span>
          ) : isOverforecast ? (
            <span className="text-amber-400 font-medium">Overforecasting (+MW)</span>
          ) : isUnderforecast ? (
            <span className="text-blue-400 font-medium">Underforecasting (−MW)</span>
          ) : (
            <span className="text-slate-400">Zero Net Bias</span>
          )}
          <span className="text-slate-500">mean(forecast − actual)</span>
        </div>
      </div>

      {/* 4. MAPE */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg relative overflow-hidden flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 text-xs">
          <span className="font-semibold text-slate-300 uppercase tracking-wider">Mean Absolute % Error</span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-950 text-emerald-300 border border-emerald-800/60">
            Safe MAPE
          </span>
        </div>
        <div className="my-2">
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {formatVal(mape, 2)}
            </span>
            <span className="text-sm font-semibold text-emerald-400">%</span>
          </div>
        </div>
        <div className="text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-2">
          <span>
            {zeroActualExcluded > 0 ? (
              <span className="text-amber-400/90">{zeroActualExcluded} zero-actuals excluded</span>
            ) : (
              'All actuals non-zero'
            )}
          </span>
          <span className="text-slate-500">
            {analytics?.mape_eligible_count ?? 0} eligible
          </span>
        </div>
      </div>
    </div>
  );
}
