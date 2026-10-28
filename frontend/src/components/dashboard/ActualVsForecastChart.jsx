import React from 'react';
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
import { Wind, AlertCircle } from 'lucide-react';

export default function ActualVsForecastChart({ intervals, loading }) {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg h-96 flex items-center justify-center animate-pulse">
        <div className="text-center text-slate-500 text-sm">
          <Wind className="h-8 w-8 text-cyan-500 animate-spin mx-auto mb-2" />
          <span>Loading forecast and actual generation data...</span>
        </div>
      </div>
    );
  }

  if (!intervals || intervals.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-lg h-96 flex flex-col items-center justify-center text-center">
        <AlertCircle className="h-10 w-10 text-slate-500 mb-3" />
        <h3 className="text-base font-semibold text-slate-300">No Comparison Data Available</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-md">
          No records were found for the selected delivery date range. Ensure January 2026 data has been ingested into SQLite via the Ingestion engine.
        </p>
      </div>
    );
  }

  // Format data for Recharts without filling missing data
  const chartData = intervals.map((interval) => {
    // Format delivery timestamp for display: "DD/MM HH:mm"
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

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 shadow-xl text-xs space-y-1.5 z-50">
          <div className="font-semibold text-slate-200 border-b border-slate-800 pb-1 flex justify-between gap-4">
            <span>{data.timeLabel} UTC</span>
            <span className="text-cyan-400 font-mono">SP {data.settlementPeriod}</span>
          </div>
          <div className="flex items-center justify-between space-x-4 text-cyan-400">
            <span>Actual Outturn (FUELHH):</span>
            <span className="font-mono font-semibold">
              {data.actualMw !== null ? `${Number(data.actualMw).toLocaleString()} MW` : 'Missing'}
            </span>
          </div>
          <div className="flex items-center justify-between space-x-4 text-amber-400">
            <span>Day-Ahead Forecast (WINDFOR):</span>
            <span className="font-mono font-semibold">
              {data.forecastMw !== null ? `${Number(data.forecastMw).toLocaleString()} MW` : 'Missing'}
            </span>
          </div>
          {data.errorMw !== null && (
            <div className="flex items-center justify-between space-x-4 pt-1 border-t border-slate-800 text-slate-300">
              <span>Forecast Error (FC − Act):</span>
              <span className={`font-mono font-semibold ${data.errorMw > 0 ? 'text-amber-300' : 'text-blue-300'}`}>
                {data.errorMw > 0 ? `+${data.errorMw.toLocaleString()} MW` : `${data.errorMw.toLocaleString()} MW`}
              </span>
            </div>
          )}
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
            <span>Actual vs. Day-Ahead Forecast Generation</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Half-hourly FUELHH outturn compared with day-ahead selected WINDFOR forecast (D-1 cutoff)
          </p>
        </div>
        <div className="flex items-center space-x-4 text-xs">
          <div className="flex items-center space-x-1.5 text-cyan-400 font-medium">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-400"></span>
            <span>Actual (30-min)</span>
          </div>
          <div className="flex items-center space-x-1.5 text-amber-400 font-medium">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400"></span>
            <span>Forecast (1-hour matched)</span>
          </div>
        </div>
      </div>

      <div className="h-80 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
            <defs>
              <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
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
            <Legend verticalAlign="top" height={36} wrapperStyle={{ display: 'none' }} />
            <Area
              type="monotone"
              dataKey="actualMw"
              name="Actual Generation"
              stroke="#06b6d4"
              strokeWidth={2}
              fill="url(#actualGradient)"
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="stepAfter"
              dataKey="forecastMw"
              name="Selected Forecast"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="text-[11px] text-slate-500 flex items-center justify-between border-t border-slate-800/60 pt-2">
        <span>* Gaps in lines represent missing data intervals (never coerced to zero)</span>
        <span>Resolution: 30-min actuals vs. 1-hour stepped forecast</span>
      </div>
    </div>
  );
}
