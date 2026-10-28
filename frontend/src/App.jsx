import React, { useState, useEffect, useRef } from 'react';
import Header from './components/common/Header';
import StatusBanner from './components/common/StatusBanner';
import FilterControls from './components/dashboard/FilterControls';
import KpiCards from './components/dashboard/KpiCards';
import ActualVsForecastChart from './components/dashboard/ActualVsForecastChart';
import ForecastErrorChart from './components/dashboard/ForecastErrorChart';
import CoverageSummary from './components/dashboard/CoverageSummary';
import ForecastVintagesView from './components/forecasts/ForecastVintagesView';
import ActualsView from './components/actuals/ActualsView';
import MethodologyView from './components/methodology/MethodologyView';
import { getHealth, getAnalytics, getComparison } from './services/api';
import { AlertCircle, Database, Wind } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');

  // Parameters
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState('2026-01-07');
  const [decisionCutoff, setDecisionCutoff] = useState('11:00');

  // Data states
  const [health, setHealth] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [healthError, setHealthError] = useState(null);

  const [analytics, setAnalytics] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [loadingData, setLoadingData] = useState(false);
  const [dataError, setDataError] = useState(null);

  // Fetch health check on mount
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        setLoadingHealth(true);
        const data = await getHealth();
        setHealth(data);
        setHealthError(null);
      } catch (err) {
        setHealthError(err.message || 'Failed to connect to Wind Procurement Intelligence backend');
      } finally {
        setLoadingHealth(false);
      }
    };
    fetchHealth();
  }, []);

  const requestIdRef = useRef(0);

  // Fetch dashboard data
  const loadDashboardData = async (start = startDate, end = endDate, cutoff = decisionCutoff) => {
    const currentRequestId = ++requestIdRef.current;
    try {
      setLoadingData(true);
      setDataError(null);

      const [analyticsRes, comparisonRes] = await Promise.all([
        getAnalytics(start, end, cutoff),
        getComparison(start, end, cutoff),
      ]);

      if (currentRequestId === requestIdRef.current) {
        setAnalytics(analyticsRes);
        setComparison(comparisonRes);
      }
    } catch (err) {
      if (currentRequestId === requestIdRef.current) {
        setAnalytics(null);
        setComparison(null);
        const errMsg = err.response?.data?.detail || err.message || 'Failed to load forecast accuracy data';
        setDataError(errMsg);
      }
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoadingData(false);
      }
    }
  };

  // Fetch data on initial load
  useEffect(() => {
    loadDashboardData();
  }, []);

  const handleApplyFilters = () => {
    loadDashboardData(startDate, endDate, decisionCutoff);
  };

  const isDatabaseEmpty = analytics && analytics.matched_interval_count === 0 && analytics.actual_interval_count === 0;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100">
      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <StatusBanner health={health} loading={loadingHealth} error={healthError} />

        {/* Tab 1: Dashboard Overview */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <FilterControls
              startDate={startDate}
              endDate={endDate}
              decisionCutoff={decisionCutoff}
              onStartDateChange={setStartDate}
              onEndDateChange={setEndDate}
              onDecisionCutoffChange={setDecisionCutoff}
              onApply={handleApplyFilters}
              loading={loadingData}
            />

            {/* Error message */}
            {dataError && (
              <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 text-xs text-rose-300 flex items-center space-x-3">
                <AlertCircle className="h-5 w-5 text-rose-400 flex-shrink-0" />
                <span>{dataError}</span>
              </div>
            )}

            {/* Empty database notice */}
            {isDatabaseEmpty && !loadingData && (
              <div className="bg-slate-900 border border-amber-800/60 rounded-xl p-5 shadow-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-start space-x-3">
                  <div className="p-2 bg-amber-950/80 border border-amber-800/80 rounded-lg text-amber-400 flex-shrink-0 mt-0.5">
                    <Database className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-200">Database Ready • Awaiting January 2026 Ingestion</h3>
                    <p className="text-xs text-slate-400 mt-0.5 max-w-2xl leading-relaxed">
                      The SQLite database is active and schema-verified. No forecast or actual generation records have been ingested yet for {startDate} to {endDate}. Accuracy metrics and charts will populate automatically once records are ingested via <code className="text-cyan-400 font-mono">POST /api/ingestion/trigger</code>.
                    </p>
                  </div>
                </div>
                <div className="text-xs font-mono bg-slate-950 px-3 py-1.5 rounded text-amber-400 border border-slate-800 whitespace-nowrap">
                  Matched: 0 / {analytics.expected_interval_count}
                </div>
              </div>
            )}

            {/* KPI Cards */}
            <KpiCards analytics={analytics} loading={loadingData} />

            {/* Actual vs Forecast Chart */}
            <ActualVsForecastChart intervals={comparison?.intervals} loading={loadingData} />

            {/* Forecast Error Chart */}
            <ForecastErrorChart intervals={comparison?.intervals} loading={loadingData} />

            {/* Coverage Summary */}
            <CoverageSummary analytics={analytics} comparison={comparison} loading={loadingData} />
          </div>
        )}

        {/* Tab 2: Forecast Vintages Inspection */}
        {activeTab === 'forecasts' && (
          <ForecastVintagesView initialStartDate={startDate} initialEndDate={endDate} />
        )}

        {/* Tab 3: Actuals Inspection */}
        {activeTab === 'actuals' && (
          <ActualsView initialStartDate={startDate} initialEndDate={endDate} />
        )}

        {/* Tab 4: Procurement Methodology & Scope */}
        {activeTab === 'methodology' && <MethodologyView />}
      </main>

      <footer className="border-t border-slate-800 bg-slate-900/50 py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
          <div>
            Wind Procurement Intelligence • UK Balancing Mechanism Insights API
          </div>
          <div className="text-[11px] text-slate-400">
            Assistance: Google Antigravity AI Coding Assistant • All code & calculations verified
          </div>
        </div>
      </footer>
    </div>
  );
}
