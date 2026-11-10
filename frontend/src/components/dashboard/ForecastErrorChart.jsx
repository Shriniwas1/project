import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts';
import { Activity, Info, AlertTriangle, ArrowUpRight, ArrowDownRight } from 'lucide-react';

export default function ForecastErrorChart({ intervals, loading }) {
  const [filterMode, setFilterMode] = useState('all'); // 'all', 'over', 'under'

  if (loading) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-8 shadow-xl h-80 flex items-center justify-center animate-pulse">
        <div className="text-center text-slate-500 text-sm space-y-2">
          <Activity className="h-6 w-6 text-cyan-500 animate-spin mx-auto" />
          <p>Analyzing physical generation variance distribution...</p>
        </div>
      </div>
    );
  }

  if (!intervals || intervals.length === 0) {
    return null;
  }

  const rawChartData = intervals.map((interval) => {
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
      errorMw: interval.forecast_error_mw,
      isMatched: interval.is_matched,
    };
  });

  const overCount = rawChartData.filter((d) => d.errorMw !== null && d.errorMw > 0).length;
  const underCount = rawChartData.filter((d) => d.errorMw !== null && d.errorMw < 0).length;
  const exactCount = rawChartData.filter((d) => d.errorMw === 0).length;
  const totalMatched = overCount + underCount + exactCount;

  const overPercent = totalMatched > 0 ? ((overCount / totalMatched) * 100).toFixed(0) : 0;
  const underPercent = totalMatched > 0 ? ((underCount / totalMatched) * 100).toFixed(0) : 0;

  const chartData = rawChartData.map((d) => {
    if (filterMode === 'over' && (d.errorMw === null || d.errorMw <= 0)) {
      return { ...d, errorMw: null };
    }
    if (filterMode === 'under' && (d.errorMw === null || d.errorMw >= 0)) {
      return { ...d, errorMw: null };
    }
    return d;
  });

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      if (data.errorMw === null) return null;
      const isOver = data.errorMw > 0;
      return (
        <div className="bg-slate-950/95 border border-slate-700/80 rounded-xl p-4 shadow-2xl text-xs space-y-2 z-50 backdrop-blur-md min-w-[220px]">
          <div className="font-semibold text-slate-200 border-b border-slate-800 pb-1 flex justify-between items-center">
            <span className="text-sm font-sans text-white">{data.timeLabel} UTC</span>
            <span className="text-cyan-400 font-mono text-[11px] bg-cyan-950/80 border border-cyan-800 px-1.5 py-0.5 rounded">
              SP {data.settlementPeriod}
            </span>
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between text-slate-400">
              <span>Volume Discrepancy:</span>
              <span
                className={`font-mono font-bold text-sm ${
                  isOver ? 'text-amber-400' : 'text-blue-400'
                }`}
              >
                {data.errorMw > 0 ? `+${data.errorMw.toLocaleString()} MW` : `${data.errorMw.toLocaleString()} MW`}
              </span>
            </div>

            <div className="text-[11px] pt-1.5 border-t border-slate-800/80">
              {isOver ? (
                <span className="text-amber-300 font-medium">
                  Short Imbalance: Desk bought too little thermal backup
                </span>
              ) : (
                <span className="text-blue-300 font-medium">
                  Long Imbalance: Desk over-contracted expensive thermal energy
                </span>
              )}
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <section className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-7 shadow-xl space-y-5">
      {/* Header with human-centred explanations */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Procurement Volume Exposure: Forecast Error (MW)
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Deviation = <code className="text-slate-300 font-mono">Day-Ahead Forecast − Physical Actuals</code>. Amber bars indicate intervals where the forecast exceeded generation (creating volume deficits). Blue bars indicate surplus generation.
          </p>
        </div>

        {/* Filter / Filter chips */}
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => setFilterMode('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
              filterMode === 'all'
                ? 'bg-slate-800 text-white border-slate-600'
                : 'bg-slate-950 text-slate-500 border-slate-800'
            }`}
          >
            All Errors ({totalMatched})
          </button>

          <button
            type="button"
            onClick={() => setFilterMode('over')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
              filterMode === 'over'
                ? 'bg-amber-950/80 text-amber-300 border-amber-700/80 shadow-sm'
                : 'bg-slate-950 text-slate-500 border-slate-800'
            }`}
          >
            <ArrowUpRight className="w-3.5 h-3.5 text-amber-400" />
            <span>Overforecast ({overPercent}%)</span>
          </button>

          <button
            type="button"
            onClick={() => setFilterMode('under')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
              filterMode === 'under'
                ? 'bg-blue-950/80 text-blue-300 border-blue-700/80 shadow-sm'
                : 'bg-slate-950 text-slate-500 border-slate-800'
            }`}
          >
            <ArrowDownRight className="w-3.5 h-3.5 text-blue-400" />
            <span>Underforecast ({underPercent}%)</span>
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="h-72 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 15, left: 5, bottom: 25 }}>
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
            <ReferenceLine y={0} stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="3 3" />
            <Bar dataKey="errorMw" name="Forecast Error" isAnimationActive={false}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.errorMw === null ? 'transparent' : entry.errorMw >= 0 ? '#f59e0b' : '#3b82f6'}
                  opacity={0.88}
                />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Insight Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 pt-3 gap-2">
        <div className="flex items-center space-x-2">
          <Info className="h-3.5 w-3.5 text-slate-500" />
          <span>
            Dashed baseline at 0 GW represents a zero-error perfect forecast.
          </span>
        </div>
        <div className="text-slate-400 font-sans">
          Physical Exposure: <strong className="text-amber-400 font-semibold">{overCount}</strong> deficit intervals vs <strong className="text-blue-400 font-semibold">{underCount}</strong> surplus intervals
        </div>
      </div>
    </section>
  );
}
