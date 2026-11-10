import React, { useState } from 'react';
import { Target, TrendingUp, TrendingDown, HelpCircle, Activity, Info, ShieldAlert, ArrowUpRight, ArrowDownRight } from 'lucide-react';

export default function KpiCards({ analytics, loading }) {
  const [activeInfo, setActiveInfo] = useState(null);

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 animate-pulse">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 h-48 flex flex-col justify-between">
            <div className="h-4 bg-slate-800 rounded w-1/2"></div>
            <div className="h-10 bg-slate-800 rounded w-3/4"></div>
            <div className="h-4 bg-slate-800 rounded w-2/3"></div>
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
  const mapeEligible = analytics?.mape_eligible_count ?? 0;

  const formatVal = (val, decimals = 1) => {
    if (val === null || val === undefined) return '—';
    return Number(val).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const isOverforecast = bias !== null && bias > 0;
  const isUnderforecast = bias !== null && bias < 0;

  const toggleInfo = (cardId) => {
    setActiveInfo(activeInfo === cardId ? null : cardId);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* 1. Mean Absolute Error (MAE) */}
        <div className="bg-slate-900/90 border border-slate-800/90 hover:border-slate-700/80 transition-all rounded-2xl p-6 shadow-xl flex flex-col justify-between relative group">
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-semibold text-slate-400 uppercase tracking-wider text-[11px]">
                Average Forecast Error
              </span>
              <button
                type="button"
                onClick={() => toggleInfo('mae')}
                className="text-slate-500 hover:text-cyan-400 transition-colors p-1"
                title="Click for procurement interpretation"
              >
                <HelpCircle className="h-4 w-4" />
              </button>
            </div>
            <h3 className="text-sm font-medium text-slate-200">Mean Absolute Error (MAE)</h3>

            <div className="mt-3 flex items-baseline space-x-2">
              <span className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight font-sans">
                {formatVal(mae, 1)}
              </span>
              <span className="text-sm font-semibold text-cyan-400">MW</span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
            <p className="leading-snug">
              On average, day-ahead forecasts deviated from physical delivery by <strong className="text-slate-200">{formatVal(mae, 0)} MW</strong> per half hour.
            </p>
            <p className="text-[10px] text-slate-500 pt-0.5">
              Based on {matchedCount} matched settlement intervals
            </p>
          </div>
        </div>

        {/* 2. Forecast Bias */}
        <div className={`bg-slate-900/90 border transition-all rounded-2xl p-6 shadow-xl flex flex-col justify-between relative group ${
          isOverforecast
            ? 'border-amber-900/50 hover:border-amber-700/70'
            : isUnderforecast
            ? 'border-blue-900/50 hover:border-blue-700/70'
            : 'border-slate-800 hover:border-slate-700'
        }`}>
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-semibold text-slate-400 uppercase tracking-wider text-[11px]">
                Directional Tendency
              </span>
              <button
                type="button"
                onClick={() => toggleInfo('bias')}
                className="text-slate-500 hover:text-amber-400 transition-colors p-1"
                title="Click for procurement interpretation"
              >
                <HelpCircle className="h-4 w-4" />
              </button>
            </div>
            <h3 className="text-sm font-medium text-slate-200">Systemic Forecast Bias</h3>

            <div className="mt-3 flex items-baseline space-x-2">
              <span
                className={`text-3xl sm:text-4xl font-extrabold tracking-tight font-sans ${
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

          <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] space-y-1">
            {isOverforecast ? (
              <div className="text-amber-300/90 flex items-center space-x-1 font-medium">
                <ArrowUpRight className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
                <span>Overforecasting: Lower wind delivered than expected</span>
              </div>
            ) : isUnderforecast ? (
              <div className="text-blue-300/90 flex items-center space-x-1 font-medium">
                <ArrowDownRight className="h-3.5 w-3.5 text-blue-400 flex-shrink-0" />
                <span>Underforecasting: Surplus wind materialized</span>
              </div>
            ) : (
              <span className="text-slate-400">No net bias detected (balanced)</span>
            )}
            <p className="text-[10px] text-slate-500 pt-0.5">
              Net balance: mean(forecast − actual)
            </p>
          </div>
        </div>

        {/* 3. Root Mean Squared Error (RMSE) */}
        <div className="bg-slate-900/90 border border-slate-800/90 hover:border-slate-700/80 transition-all rounded-2xl p-6 shadow-xl flex flex-col justify-between relative group">
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-semibold text-slate-400 uppercase tracking-wider text-[11px]">
                Volatile Outlier Penalty
              </span>
              <button
                type="button"
                onClick={() => toggleInfo('rmse')}
                className="text-slate-500 hover:text-indigo-400 transition-colors p-1"
                title="Click for procurement interpretation"
              >
                <HelpCircle className="h-4 w-4" />
              </button>
            </div>
            <h3 className="text-sm font-medium text-slate-200">Root Mean Squared Error (RMSE)</h3>

            <div className="mt-3 flex items-baseline space-x-2">
              <span className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight font-sans">
                {formatVal(rmse, 1)}
              </span>
              <span className="text-sm font-semibold text-indigo-400">MW</span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
            <p className="leading-snug">
              Square-weighted error. Higher than MAE indicates occasional sudden multi-gigawatt forecasting swings.
            </p>
            <p className="text-[10px] text-slate-500 pt-0.5">
              RMSE/MAE ratio: {mae && rmse ? (rmse / mae).toFixed(2) : '—'} (volatility index)
            </p>
          </div>
        </div>

        {/* 4. Safe Percentage Error (MAPE) */}
        <div className="bg-slate-900/90 border border-slate-800/90 hover:border-slate-700/80 transition-all rounded-2xl p-6 shadow-xl flex flex-col justify-between relative group">
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-semibold text-slate-400 uppercase tracking-wider text-[11px]">
                Relative Accuracy
              </span>
              <button
                type="button"
                onClick={() => toggleInfo('mape')}
                className="text-slate-500 hover:text-emerald-400 transition-colors p-1"
                title="Click for procurement interpretation"
              >
                <HelpCircle className="h-4 w-4" />
              </button>
            </div>
            <h3 className="text-sm font-medium text-slate-200">Safe Percentage Error (MAPE)</h3>

            <div className="mt-3 flex items-baseline space-x-2">
              <span className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight font-sans">
                {formatVal(mape, 2)}
              </span>
              <span className="text-sm font-semibold text-emerald-400">%</span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
            <p className="leading-snug">
              Average error relative to actual outturn volume across non-zero generation intervals.
            </p>
            <p className="text-[10px] text-slate-500 pt-0.5">
              {zeroActualExcluded > 0
                ? `${zeroActualExcluded} zero-actual intervals safely excluded`
                : '100% intervals evaluated'}
            </p>
          </div>
        </div>
      </div>

      {/* Human contextual explanation cards when a metric is clicked */}
      {activeInfo && (
        <div className="bg-slate-900 border border-slate-700/80 rounded-2xl p-5 shadow-2xl text-xs space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
          <div className="flex items-center justify-between font-semibold">
            <div className="flex items-center space-x-2">
              <Info className="h-4 w-4 text-cyan-400" />
              <span className="text-white text-sm">
                {activeInfo === 'mae' && 'Procurement Desk Context: Mean Absolute Error'}
                {activeInfo === 'bias' && 'Procurement Desk Context: Forecast Bias & Imbalance Cash-Out Risk'}
                {activeInfo === 'rmse' && 'Procurement Desk Context: Root Mean Squared Error (Tail Risk)'}
                {activeInfo === 'mape' && 'Procurement Desk Context: Safe Percentage Error (Zero-Actual Guard)'}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setActiveInfo(null)}
              className="text-slate-400 hover:text-white px-2 py-0.5 rounded bg-slate-800"
            >
              Close
            </button>
          </div>

          {activeInfo === 'mae' && (
            <p className="text-slate-300 leading-relaxed text-[12px]">
              <strong>How to use this number:</strong> MAE tells you the expected volume shortfall or surplus in Megawatts that your desk will have to balance intraday. If your portfolio contracts 100% of the day-ahead forecast, you should expect an average of {formatVal(mae, 0)} MW of real-time physical volume variance that must be traded in the continuous balancing market.
            </p>
          )}

          {activeInfo === 'bias' && (
            <div className="text-slate-300 leading-relaxed text-[12px] space-y-1.5">
              <p>
                <strong>Systemic Overforecasting Risk (+Bias):</strong> A positive bias means WINDFOR consistently predicted <em>more</em> wind than actually generated. In January 2026, an average overforecast of ~1.8 GW forced utilities who trusted the day-ahead forecast to purchase expensive emergency replacement power at System Buy Prices (Cash-Out).
              </p>
              <p className="text-amber-300/90">
                <strong>Recommended Procurement Action:</strong> When persistent positive bias is observed, power traders should apply a discount haircut (e.g. 15–20%) to raw day-ahead forecasts before placing auction bids.
              </p>
            </div>
          )}

          {activeInfo === 'rmse' && (
            <p className="text-slate-300 leading-relaxed text-[12px]">
              <strong>Tail-Risk & Extreme Swings:</strong> Because errors are squared before averaging, RMSE penalizes large forecast blunders far more heavily than minor 50 MW tracking errors. A high RMSE relative to MAE indicates that while many intervals track reasonably well, sudden weather fronts created catastrophic multi-thousand-megawatt drop-offs that trigger major balancing penalties.
            </p>
          )}

          {activeInfo === 'mape' && (
            <p className="text-slate-300 leading-relaxed text-[12px]">
              <strong>Mathematical Integrity Guard:</strong> When wind speed drops to zero and wind generation is 0 MW, calculating <code className="font-mono text-cyan-300">error / actual</code> causes a mathematical division by zero. Our platform implements an industry-standard <em>Safe MAPE</em> rule: intervals with 0 MW outturn are transparently excluded from percentage summation, while remaining fully accounted for in MAE, RMSE, and Bias.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
