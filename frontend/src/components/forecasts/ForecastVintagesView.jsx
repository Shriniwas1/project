import React, { useState, useEffect } from 'react';
import { getForecasts } from '../../services/api';
import { Wind, Calendar, Clock, Filter, AlertCircle, RefreshCw, CheckCircle, Info } from 'lucide-react';

export default function ForecastVintagesView({ initialStartDate = '2026-01-01', initialEndDate = '2026-01-02' }) {
  const [startDate, setStartDate] = useState(initialStartDate);
  const [endDate, setEndDate] = useState(initialEndDate);
  const [latestOnly, setLatestOnly] = useState(false);
  const [publishBefore, setPublishBefore] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getForecasts(
        startDate,
        endDate,
        latestOnly,
        publishBefore.trim() || null
      );
      setData(res);
    } catch (err) {
      setData(null);
      setError(err.response?.data?.detail || err.message || 'Failed to fetch forecasts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [latestOnly]);

  return (
    <div className="space-y-6">
      {/* Title & Explainer */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center space-x-2">
              <Wind className="h-5 w-5 text-amber-400" />
              <span>Forecast Publication Vintages (WINDFOR)</span>
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Multi-vintage inspection engine preserving all historical publication revisions for UK national wind generation
            </p>
          </div>
          <div className="flex items-center space-x-2 text-xs text-slate-400 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Resolution: Native 1-Hour</span>
          </div>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 items-end mt-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Filter Publish Before (Optional)</label>
            <input
              type="text"
              placeholder="e.g. 2025-12-31T11:00:00Z"
              value={publishBefore}
              onChange={(e) => setPublishBefore(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-amber-500 font-mono"
            />
          </div>

          <div className="flex items-center pb-2">
            <label className="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={latestOnly}
                onChange={(e) => setLatestOnly(e.target.checked)}
                className="rounded bg-slate-950 border-slate-700 text-amber-500 focus:ring-amber-500 h-4 w-4"
              />
              <span>Latest Vintage Only</span>
            </label>
          </div>

          <div>
            <button
              type="button"
              onClick={fetchData}
              disabled={loading}
              className="w-full bg-amber-600 hover:bg-amber-500 text-slate-950 font-semibold px-4 py-2 rounded-lg text-xs transition-all flex items-center justify-center space-x-2 shadow-md shadow-amber-900/20 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Fetching...' : 'Query Vintages'}</span>
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between text-xs text-slate-400 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
          <div className="flex items-center space-x-2">
            <Info className="h-3.5 w-3.5 text-amber-400" />
            <span>
              {latestOnly
                ? 'Displaying only the single latest publication vintage per 1-hour interval.'
                : 'Displaying all historical publication vintages stored for each delivery interval.'}
            </span>
          </div>
          <div className="font-mono text-slate-300">
            Records: <span className="text-amber-400 font-bold">{data?.record_count ?? 0}</span> | Distinct Intervals:{' '}
            <span className="text-cyan-400 font-bold">{data?.unique_delivery_intervals_count ?? 0}</span>
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 text-xs text-rose-300 flex items-center space-x-3">
          <AlertCircle className="h-5 w-5 text-rose-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Table / Empty State */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm">
            <RefreshCw className="h-6 w-6 text-amber-500 animate-spin mx-auto mb-2" />
            <span>Loading forecast vintages...</span>
          </div>
        ) : !data || data.records.length === 0 ? (
          <div className="p-12 text-center">
            <Wind className="h-10 w-10 text-slate-600 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-slate-300">No Forecast Records Found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              No WINDFOR forecasts match the requested delivery date range. Ensure January 2026 data has been ingested into SQLite.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800 sticky top-0 backdrop-blur z-10">
                <tr>
                  <th className="px-4 py-3">Delivery Interval (UTC)</th>
                  <th className="px-4 py-3">Delivery Date</th>
                  <th className="px-4 py-3">Publication Timestamp (UTC)</th>
                  <th className="px-4 py-3 text-right">Forecast (MW)</th>
                  <th className="px-4 py-3 text-right">Lead Time</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                {data.records.map((r, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-2.5 text-cyan-400 font-semibold">{r.delivery_timestamp}</td>
                    <td className="px-4 py-2.5 text-slate-400">{r.delivery_date}</td>
                    <td className="px-4 py-2.5 text-amber-300">{r.publish_timestamp}</td>
                    <td className="px-4 py-2.5 text-right font-bold text-white">
                      {Number(r.generation_mw).toLocaleString(undefined, { minimumFractionDigits: 1 })} MW
                    </td>
                    <td className="px-4 py-2.5 text-right text-slate-400">
                      {r.lead_time_hours !== null ? `${r.lead_time_hours.toFixed(1)} hrs` : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          r.is_ex_ante
                            ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/60'
                            : 'bg-amber-950/80 text-amber-400 border border-amber-800/60'
                        }`}
                      >
                        {r.is_ex_ante ? 'Ex-Ante' : 'Retrospective'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 text-[11px]">{r.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
