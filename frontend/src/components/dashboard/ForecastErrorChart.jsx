import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts';
import { Activity, AlertCircle } from 'lucide-react';

export default function ForecastErrorChart({ intervals, loading }) {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg h-72 flex items-center justify-center animate-pulse">
        <div className="text-center text-slate-500 text-sm">
          <Activity className="h-6 w-6 text-cyan-500 animate-spin mx-auto mb-2" />
          <span>Calculating forecast errors...</span>
        </div>
      </div>
    );
  }

  if (!intervals || intervals.length === 0) {
    return null; // Parent will handle or show empty banner
  }

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
      errorMw: interval.forecast_error_mw,
      isMatched: interval.is_matched,
    };
  });

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      if (data.errorMw === null) return null;
      const isOver = data.errorMw > 0;
      return (
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 shadow-xl text-xs space-y-1.5 z-50">
          <div className="font-semibold text-slate-200 border-b border-slate-800 pb-1 flex justify-between gap-4">
            <span>{data.timeLabel} UTC</span>
            <span className="text-cyan-400 font-mono">SP {data.settlementPeriod}</span>
          </div>
          <div className="flex items-center justify-between space-x-4">
            <span className="text-slate-400">Forecast Error (FC − Act):</span>
            <span
              className={`font-mono font-bold ${
                isOver ? 'text-amber-400' : 'text-blue-400'
              }`}
            >
              {data.errorMw > 0 ? `+${data.errorMw.toLocaleString()} MW` : `${data.errorMw.toLocaleString()} MW`}
            </span>
          </div>
          <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-800/80">
            {isOver ? (
              <span className="text-amber-400/90 font-medium">Overforecasting: Actual was below forecast</span>
            ) : (
              <span className="text-blue-400/90 font-medium">Underforecasting: Actual exceeded forecast</span>
            )}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <span>Forecast Error Distribution (MW)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Error convention: <code className="text-cyan-300 font-mono">forecast_error = forecast − actual</code>
          </p>
        </div>
        <div className="flex items-center space-x-4 text-xs">
          <div className="flex items-center space-x-1.5 text-amber-400 font-medium">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400"></span>
            <span>+ Overforecast</span>
          </div>
          <div className="flex items-center space-x-1.5 text-blue-400 font-medium">
            <span className="h-2.5 w-2.5 rounded-full bg-blue-400"></span>
            <span>− Underforecast</span>
          </div>
        </div>
      </div>

      <div className="h-64 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis
              dataKey="timeLabel"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
              unit=" MW"
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="3 3" />
            <Bar dataKey="errorMw" name="Forecast Error" isAnimationActive={false}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.errorMw === null ? 'transparent' : entry.errorMw >= 0 ? '#f59e0b' : '#3b82f6'}
                  opacity={0.85}
                />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="text-[11px] text-slate-500 flex items-center justify-between border-t border-slate-800/60 pt-2">
        <span>* Reference dashed line at 0 MW represents exact forecast delivery</span>
        <span>Missing values render as empty gaps</span>
      </div>
    </div>
  );
}
