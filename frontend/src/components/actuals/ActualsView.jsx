import React, { useState, useEffect } from 'react';
import { getActuals } from '../../services/api';
import { Database, Calendar, RefreshCw, AlertCircle, Info, Layers, CheckCircle2 } from 'lucide-react';

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
      {/* Title & Human Explainer */}
      <section className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-7 shadow-xl space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
          <div>
            <div className="flex items-center space-x-2.5">
              <div className="p-1.5 rounded-lg bg-cyan-950/80 border border-cyan-800/60 text-cyan-400">
                <Database className="h-5 w-5" />
              </div>
              <h1 className="text-xl font-bold text-white tracking-tight">
                Actual Physical Wind Outturn (FUELHH)
              </h1>
            </div>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
              Explore authentic half-hourly generation records delivered into the National Transmission System across Great Britain. Filtered strictly to fuel type <code className="text-cyan-300 font-mono">WIND</code> with zero imputation or modification.
            </p>
          </div>
          <div className="flex items-center space-x-2 text-xs text-slate-300 bg-slate-950 px-3.5 py-2 rounded-xl border border-slate-800 self-start sm:self-auto">
            <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse"></span>
            <span className="font-medium">Resolution: 30-Min Settlement Periods (1–48)</span>
          </div>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300">Delivery Start Date</label>
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-slate-950/90 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300">Delivery End Date</label>
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-slate-950/90 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </div>

          <div>
            <button
              type="button"
              onClick={fetchData}
              disabled={loading}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-bold px-4 py-2.5 rounded-xl text-xs transition-all flex items-center justify-center space-x-2 shadow-md shadow-cyan-950/40 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Fetching Outturn...' : 'Query Settlement Data'}</span>
            </button>
          </div>
        </div>

        {/* Informative Status Strip */}
        <div className="flex flex-wrap items-center justify-between text-xs text-slate-400 bg-slate-950/70 p-3 rounded-xl border border-slate-800">
          <div className="flex items-center space-x-2">
            <Info className="h-4 w-4 text-cyan-400" />
            <span>
              Each standard day contains exactly 48 half-hourly settlement periods. Genuine zero outturns remain valid 0 MW observations.
            </span>
          </div>
          <div className="font-sans text-slate-300">
            Total Ingested Outturn Records: <strong className="text-cyan-400 font-mono text-sm">{data?.record_count ?? 0}</strong>
          </div>
        </div>
      </section>

      {/* Error state */}
      {error && (
        <div className="bg-rose-950/40 border border-rose-800 rounded-2xl p-4 text-xs text-rose-300 flex items-center space-x-3">
          <AlertCircle className="h-5 w-5 text-rose-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Table / Empty State */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-16 text-center text-slate-400 text-sm space-y-3">
            <RefreshCw className="h-7 w-7 text-cyan-500 animate-spin mx-auto" />
            <p className="font-medium text-slate-300">Loading verified settlement outturn records...</p>
          </div>
        ) : !data || data.records.length === 0 ? (
          <div className="p-16 text-center space-y-3">
            <Database className="h-10 w-10 text-slate-600 mx-auto" />
            <h3 className="text-base font-semibold text-slate-200">No Actual Generation Records Found</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
              No FUELHH outturn records match your date criteria. Select delivery dates in January 2026.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[640px] overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/90 text-slate-300 font-semibold border-b border-slate-800 sticky top-0 backdrop-blur-md z-10">
                <tr>
                  <th className="px-5 py-3.5">Delivery Interval (UTC)</th>
                  <th className="px-5 py-3.5">Settlement Date</th>
                  <th className="px-5 py-3.5 text-center">Settlement Period</th>
                  <th className="px-5 py-3.5 text-right">Physical Outturn (MW)</th>
                  <th className="px-5 py-3.5 text-center">Fuel Type</th>
                  <th className="px-5 py-3.5">Elexon Stream</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                {data.records.map((r, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-5 py-3 text-cyan-300 font-medium">{r.delivery_timestamp}</td>
                    <td className="px-5 py-3 text-slate-400 font-sans">{r.delivery_date}</td>
                    <td className="px-5 py-3 text-center font-sans">
                      <span className="px-2.5 py-0.5 rounded-lg bg-slate-800 text-slate-200 text-xs font-semibold border border-slate-700">
                        SP {r.settlement_period}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right font-bold text-white text-sm">
                      {Number(r.generation_mw).toLocaleString(undefined, { minimumFractionDigits: 1 })} MW
                    </td>
                    <td className="px-5 py-3 text-center font-sans">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
                        {r.fuel_type}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-500 font-sans text-[11px]">{r.source}</td>
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
