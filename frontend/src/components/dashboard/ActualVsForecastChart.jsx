import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { Wind, AlertCircle, Eye, EyeOff, Maximize2, Info } from 'lucide-react';

export default function ActualVsForecastChart({ intervals, loading }) {
  const [showActual, setShowActual] = useState(true);
  const [showForecast, setShowForecast] = useState(true);

  if (loading) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-8 shadow-xl h-[420px] flex items-center justify-center animate-pulse">
        <div className="text-center text-slate-400 text-sm space-y-3">
          <Wind className="h-8 w-8 text-cyan-500 animate-spin mx-auto" />
          <p className="font-medium text-slate-300">Rendering time-series generation profiles...</p>
          <p className="text-xs text-slate-500">Mapping 30-min settlement intervals against 1-hour forecasts</p>
        </div>
      </div>
    );
  }

  if (!intervals || intervals.length === 0) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-10 shadow-xl h-[420px] flex flex-col items-center justify-center text-center space-y-3">
        <div className="p-3 bg-slate-800/80 rounded-2xl text-slate-400">
          <AlertCircle className="h-8 w-8" />
        </div>
        <h3 className="text-base font-semibold text-slate-200">No Generation Outturn Records in Selected Window</h3>
        <p className="text-xs text-slate-400 max-w-md leading-relaxed">
          The requested delivery period does not contain matching records. Select January 2026 delivery dates to view verified outturns and day-ahead forecast comparisons.
        </p>
      </div>
    );
  }

  // Format data for Recharts without filling missing data
  const chartData = intervals.map((interval) => {
    const ts = new Date(interval.delivery_timestamp);
    const day = String(ts.getUTCDate()).padStart(2, '0');
    const month = ts.toLocaleString('en-GB', { month: 'short', timeZone: 'UTC' });
    const hours = String(ts.getUTCHours()).padStart(2, '0');
    const mins = String(ts.getUTCMinutes()).padStart(2, '0');
    const timeLabel = `${day} ${month} ${hours}:${mins}`;

    return {
      rawTimestamp: interval.delivery_timestamp,
      timeLabel,
      settlementPeriod: interval.settlement_period,
      actualMw: interval.actual_generation_mw,
      forecastMw: interval.forecast_generation_mw,
      errorMw: interval.forecast_error_mw,
      isMatched: interval.is_matched,
    };
  });

  // Calculate highest generation for context
  const maxActual = Math.max(...chartData.map((d) => d.actualMw || 0));
  const maxForecast = Math.max(...chartData.map((d) => d.forecastMw || 0));
  const peakVal = Math.max(maxActual, maxForecast);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const isOver = data.errorMw !== null && data.errorMw > 0;
      return (
        <div className="bg-slate-950/95 border border-slate-700/80 rounded-xl p-4 shadow-2xl text-xs space-y-2.5 z-50 backdrop-blur-md min-w-[240px]">
          <div className="font-semibold text-slate-200 border-b border-slate-800 pb-1.5 flex justify-between items-center">
            <span className="text-sm font-sans text-white">{data.timeLabel} UTC</span>
            <span className="text-cyan-400 font-mono text-[11px] bg-cyan-950/80 border border-cyan-800 px-1.5 py-0.5 rounded">
              Settlement Period {data.settlementPeriod}
            </span>
          </div>

          <div className="space-y-1.5 text-xs">
            <div className="flex items-center justify-between text-cyan-300">
              <span className="flex items-center space-x-1.5">
                <span className="h-2 w-2 rounded-full bg-cyan-400"></span>
                <span>Actual Delivery (FUELHH):</span>
              </span>
              <span className="font-mono font-bold">
                {data.actualMw !== null ? `${Number(data.actualMw).toLocaleString()} MW` : 'Missing'}
              </span>
            </div>

            <div className="flex items-center justify-between text-amber-300">
              <span className="flex items-center space-x-1.5">
                <span className="h-2 w-2 rounded-full bg-amber-400"></span>
                <span>Day-Ahead Forecast:</span>
              </span>
              <span className="font-mono font-bold">
                {data.forecastMw !== null ? `${Number(data.forecastMw).toLocaleString()} MW` : 'Missing'}
              </span>
            </div>

            {data.errorMw !== null && (
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                <span className="text-slate-400">Volume Variance:</span>
                <span className={`font-mono font-bold ${isOver ? 'text-amber-400' : 'text-blue-400'}`}>
                  {isOver ? `+${data.errorMw.toLocaleString()} MW (Over)` : `${data.errorMw.toLocaleString()} MW (Under)`}
                </span>
              </div>
            )}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <section className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-7 shadow-xl space-y-5">
      {/* Visual Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Physical Generation Outturn vs. Day-Ahead Forecast
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Comparing national half-hourly wind generation (<span className="text-cyan-400 font-medium">FUELHH</span>) with the day-ahead forecast (<span className="text-amber-400 font-medium">WINDFOR</span>) locked in prior to your decision cutoff.
          </p>
        </div>

        {/* Interactive Series Toggle Buttons */}
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => setShowActual(!showActual)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
              showActual
                ? 'bg-cyan-950/80 text-cyan-300 border-cyan-700/80 shadow-sm'
                : 'bg-slate-950 text-slate-500 border-slate-800'
            }`}
          >
            {showActual ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Actual Outturn</span>
          </button>

          <button
            type="button"
            onClick={() => setShowForecast(!showForecast)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
              showForecast
                ? 'bg-amber-950/80 text-amber-300 border-amber-700/80 shadow-sm'
                : 'bg-slate-950 text-slate-500 border-slate-800'
            }`}
          >
            {showForecast ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Day-Ahead Forecast</span>
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="h-88 sm:h-96 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 15, left: 5, bottom: 25 }}>
            <defs>
              <linearGradient id="actualGradientClean" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis
              dataKey="timeLabel"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={45}
            />
            <YAxis
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `${(v / 1000).toFixed(1)} GW`}
            />
            <Tooltip content={<CustomTooltip />} />
            {showActual && (
              <Area
                type="monotone"
                dataKey="actualMw"
                name="Actual Generation (FUELHH)"
                stroke="#06b6d4"
                strokeWidth={2.2}
                fill="url(#actualGradientClean)"
                connectNulls={false}
                isAnimationActive={false}
              />
            )}
            {showForecast && (
              <Line
                type="stepAfter"
                dataKey="forecastMw"
                name="Day-Ahead Forecast (WINDFOR)"
                stroke="#f59e0b"
                strokeWidth={2.4}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Human Footnote / Contextual guide */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 pt-3 gap-2">
        <div className="flex items-center space-x-2">
          <Info className="h-3.5 w-3.5 text-slate-500" />
          <span>
            The amber forecast curve steps in 1-hour blocks, matching two consecutive 30-minute actual settlement periods.
          </span>
        </div>
        <div className="text-slate-500 font-mono text-right">
          Peak Window Generation: <strong className="text-slate-300 font-semibold">{peakVal.toLocaleString()} MW</strong>
        </div>
      </div>
    </section>
  );
}
