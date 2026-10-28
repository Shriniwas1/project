import React, { useState, useEffect } from 'react';
import { getActuals } from '../../services/api';
import { Database, Calendar, RefreshCw, AlertCircle, Info, Activity } from 'lucide-react';

export default function ActualsView({ initialStartDate = '2026-01-01', initialEndDate = '2026-01-02' }) {
  const [startDate, setStartDate] = useState(initialStartDate);
  const [endDate, setEndDate] = useState(initialEndDate);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getActuals(startDate, endDate);
      setData(res);
    } catch (err) {
      setData(null);
      setError(err.response?.data?.detail || err.message || 'Failed to fetch actual records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="space-y-6">
      {/* Title & Explainer */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center space-x-2">
              <Database className="h-5 w-5 text-cyan-400" />
              <span>Actual Wind Outturn Generation (FUELHH)</span>
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Verified half-hourly national wind generation outturn records delivered to the GB transmission network
            </p>
          </div>
          <div className="flex items-center space-x-2 text-xs text-slate-400 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse"></span>
            <span>Resolution: 30-Minute Settlement Periods</span>
          </div>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end mt-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            />
          </div>

          <div>
            <button
              type="button"
              onClick={fetchData}
              disabled={loading}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-semibold px-4 py-2 rounded-lg text-xs transition-all flex items-center justify-center space-x-2 shadow-md shadow-cyan-900/20 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Fetching...' : 'Query Actuals'}</span>
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between text-xs text-slate-400 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
          <div className="flex items-center space-x-2">
            <Info className="h-3.5 w-3.5 text-cyan-400" />
            <span>
              Each day comprises up to 48 half-hourly settlement periods. Missing intervals are excluded, never zero-filled.
            </span>
          </div>
          <div className="font-mono text-slate-300">
            Total Records: <span className="text-cyan-400 font-bold">{data?.record_count ?? 0}</span>
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
            <RefreshCw className="h-6 w-6 text-cyan-500 animate-spin mx-auto mb-2" />
            <span>Loading actual generation records...</span>
          </div>
        ) : !data || data.records.length === 0 ? (
          <div className="p-12 text-center">
            <Database className="h-10 w-10 text-slate-600 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-slate-300">No Actual Generation Records Found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              No FUELHH outturn records match the requested delivery date range. Ensure January 2026 data has been ingested into SQLite.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800 sticky top-0 backdrop-blur z-10">
                <tr>
                  <th className="px-4 py-3">Delivery Interval (UTC)</th>
                  <th className="px-4 py-3">Settlement Date</th>
                  <th className="px-4 py-3 text-center">Settlement Period</th>
                  <th className="px-4 py-3 text-right">Actual Generation (MW)</th>
                  <th className="px-4 py-3 text-center">Fuel Type</th>
                  <th className="px-4 py-3">Source Dataset</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                {data.records.map((r, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-2.5 text-cyan-400 font-semibold">{r.delivery_timestamp}</td>
                    <td className="px-4 py-2.5 text-slate-400">{r.delivery_date}</td>
                    <td className="px-4 py-2.5 text-center">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-200 text-[11px] font-bold">
                        SP {r.settlement_period}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-bold text-white">
                      {Number(r.generation_mw).toLocaleString(undefined, { minimumFractionDigits: 1 })} MW
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
                        {r.fuel_type}
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
