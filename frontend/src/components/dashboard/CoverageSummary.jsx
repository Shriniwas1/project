import React, { useState } from 'react';
import { Layers, Database, CheckCircle2, Clock, Info, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';

export default function CoverageSummary({ analytics, comparison, loading }) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  if (loading) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl animate-pulse h-48">
        <div className="h-4 bg-slate-800 rounded w-1/3 mb-4"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-slate-800 rounded-xl"></div>
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
    <section className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-7 shadow-xl space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Data Integrity & Market Settlement Coverage
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Accounting for all half-hourly settlement intervals and explaining the mathematical alignment between 1-hour National Grid forecasts and 30-minute market actuals.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 bg-emerald-950/60 border border-emerald-800/80 px-3 py-1.5 rounded-xl text-xs font-semibold text-emerald-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>Coverage: {matched} / {expected} Intervals ({matchedPercent}%)</span>
          </div>
        </div>
      </div>

      {/* Primary Humanized Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5 text-xs">
        {/* 1. Expected Settlement Intervals */}
        <div className="bg-slate-950/70 border border-slate-800/90 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-slate-400 font-medium text-[11px]">Expected Intervals</span>
          <span className="text-2xl font-extrabold text-white mt-1.5 font-sans">{expected}</span>
          <span className="text-[10px] text-slate-500 mt-1">48 half-hours/day</span>
        </div>

        {/* 2. Actuals Ingested */}
        <div className="bg-slate-950/70 border border-slate-800/90 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-slate-400 font-medium text-[11px]">Actuals (FUELHH)</span>
          <span className="text-2xl font-extrabold text-cyan-400 mt-1.5 font-sans">{actualCount}</span>
          <span className="text-[10px] text-slate-500 mt-1">30-min settlement</span>
        </div>

        {/* 3. Unique Hourly Forecasts */}
        <div className="bg-slate-950/70 border border-slate-800/90 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-slate-400 font-medium text-[11px]">Hourly Predictions</span>
          <span className="text-2xl font-extrabold text-amber-400 mt-1.5 font-sans">{uniqueHourlyFc}</span>
          <span className="text-[10px] text-slate-500 mt-1">1-hr WINDFOR</span>
        </div>

        {/* 4. Forecast-Covered Half-Hours */}
        <div className="bg-slate-950/70 border border-slate-800/90 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-slate-400 font-medium text-[11px]">Covered Half-Hours</span>
          <span className="text-2xl font-extrabold text-slate-200 mt-1.5 font-sans">{fcCovered}</span>
          <span className="text-[10px] text-slate-500 mt-1">2 intervals/hour</span>
        </div>

        {/* 5. Matched Rows */}
        <div className="bg-slate-950/70 border border-slate-800/90 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-slate-400 font-medium text-[11px]">Matched Pairs</span>
          <span className="text-2xl font-extrabold text-emerald-400 mt-1.5 font-sans">{matched}</span>
          <span className="text-[10px] text-slate-500 mt-1">Error calculation base</span>
        </div>

        {/* 6. MAPE Non-Zero Outturn */}
        <div className="bg-slate-950/70 border border-slate-800/90 p-4 rounded-xl flex flex-col justify-between">
          <span className="text-slate-400 font-medium text-[11px]">Safe MAPE Base</span>
          <span className="text-2xl font-extrabold text-purple-400 mt-1.5 font-sans">{mapeEligible}</span>
          <span className="text-[10px] text-slate-500 mt-1">{zeroActuals} zeros excluded</span>
        </div>
      </div>

      {/* Explanatory Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-1">
        {/* Card 1: Resolution Bridge */}
        <div className="bg-slate-950/50 border border-slate-800/80 rounded-xl p-4 text-slate-300 space-y-2">
          <div className="font-semibold text-white flex items-center space-x-2 text-xs">
            <Clock className="h-4 w-4 text-amber-400" />
            <span>How Hourly Forecasts Bridge to 30-Minute Settlement Periods</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            The GB electricity market settles in 30-minute intervals (Settlement Periods 1 through 48), but National Grid publishes wind forecasts in 1-hour blocks. Our platform bridges these resolutions by mapping each 1-hour forecast across its two constituent half-hours (<code className="text-amber-300 font-mono">:00</code> and <code className="text-amber-300 font-mono">:30</code>). Hence, {uniqueHourlyFc} hourly forecasts directly evaluate {fcCovered} settlement periods without interpolation or synthetic smoothing.
          </p>
        </div>

        {/* Card 2: Missing Data Honesty */}
        <div className="bg-slate-950/50 border border-slate-800/80 rounded-xl p-4 text-slate-300 space-y-2">
          <div className="font-semibold text-white flex items-center space-x-2 text-xs">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>Missing Observations Are Never Manufactured</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            If an actual outturn record or a forecast vintage is absent from the Elexon feed, our system marks the interval as <strong className="text-slate-200">unavailable</strong>. We strictly refuse to coerce missing observations into 0 MW or interpolate artificial numbers. This guarantees that calculated error metrics accurately reflect genuine operational exposure.
          </p>
        </div>
      </div>
    </section>
  );
}
