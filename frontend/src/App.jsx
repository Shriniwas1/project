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
import { AlertCircle, Database, Wind, Sparkles, TrendingUp, ShieldAlert, ArrowRight } from 'lucide-react';

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

  // High-level narrative summary for procurement analysts
  const getExecutiveSummary = () => {
    if (!analytics || analytics.matched_interval_count === 0) return null;
    const isOver = analytics.bias_mw > 0;
    const biasMw = Math.abs(analytics.bias_mw).toLocaleString(undefined, { maximumFractionDigits: 0 });
    const maeMw = analytics.mae_mw?.toLocaleString(undefined, { maximumFractionDigits: 0 });
    const mapeVal = analytics.mape_pct?.toFixed(1);

    return {
      title: isOver ? 'Systemic Overforecasting Detected (Volume Deficit)' : 'Systemic Underforecasting Detected (Volume Surplus)',
      description: isOver
        ? `Across ${analytics.matched_interval_count} evaluated settlement intervals, day-ahead forecasts over-predicted physical delivery by an average of +${biasMw} MW (+${mapeVal}%). If your desk contracted 100% of day-ahead volume without hedging haircuts, you experienced short physical imbalances requiring emergency balancing purchases.`
        : `Across ${analytics.matched_interval_count} evaluated intervals, physical wind outturn exceeded day-ahead expectations by an average of ${biasMw} MW. Your desk over-procured expensive dispatchable thermal power.`,
      isOver,
      maeMw,
      biasMw,
    };
  };

  const execSummary = getExecutiveSummary();

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100 font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      <Header activeTab={activeTab} setActiveTab={setActiveTab} health={health} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <StatusBanner health={health} loading={loadingHealth} error={healthError} />

        {/* Tab 1: Dashboard Overview */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Filter Panel */}
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
              <div className="bg-rose-950/40 border border-rose-800 rounded-2xl p-5 text-xs text-rose-300 flex items-center space-x-3.5 shadow-lg">
                <AlertCircle className="h-5 w-5 text-rose-400 flex-shrink-0" />
                <span className="leading-relaxed">{dataError}</span>
              </div>
            )}

            {/* Empty database notice */}
            {isDatabaseEmpty && !loadingData && (
              <div className="bg-slate-900 border border-amber-800/60 rounded-2xl p-6 shadow-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5">
                <div className="flex items-start space-x-4">
                  <div className="p-2.5 bg-amber-950/80 border border-amber-800/80 rounded-xl text-amber-400 flex-shrink-0 mt-0.5">
                    <Database className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-200">Database Ready • Awaiting Ingestion for Selected Range</h3>
                    <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
                      No forecast or actual generation records were found for {startDate} to {endDate}. Ensure January 2026 data is ingested via <code className="text-cyan-400 font-mono">POST /api/ingestion/trigger</code>.
                    </p>
                  </div>
                </div>
                <div className="text-xs font-mono bg-slate-950 px-3.5 py-2 rounded-xl text-amber-400 border border-slate-800 whitespace-nowrap">
                  Matched Intervals: 0 / {analytics.expected_interval_count}
                </div>
              </div>
            )}

            {/* Executive Intelligence Narrative Callout */}
            {execSummary && !loadingData && (
              <div className={`rounded-2xl p-6 border shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-5 ${
                execSummary.isOver
                  ? 'bg-gradient-to-r from-amber-950/30 via-slate-900 to-slate-900 border-amber-800/50'
                  : 'bg-gradient-to-r from-blue-950/30 via-slate-900 to-slate-900 border-blue-800/50'
              }`}>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <span className="p-1 rounded-lg bg-amber-500/20 text-amber-400">
                      <TrendingUp className="h-4 w-4" />
                    </span>
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                      Procurement Risk Verdict
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-white tracking-tight">
                    {execSummary.title}
                  </h3>
                  <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
                    {execSummary.description}
                  </p>
                </div>

                <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center border-t sm:border-t-0 sm:border-l border-slate-800 pt-3 sm:pt-0 sm:pl-6 text-right whitespace-nowrap gap-1">
                  <span className="text-xs text-slate-400">Net Volume Variance</span>
                  <span className="text-2xl font-extrabold text-amber-300 font-mono">
                    +{execSummary.biasMw} MW
                  </span>
                  <span className="text-[11px] text-slate-500">Mean Bias / Period</span>
                </div>
              </div>
            )}

            {/* KPI Cards */}
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                  Verification Scorecard
                </h2>
                <span className="text-xs text-slate-500">
                  Click any metric card for procurement guidance
                </span>
              </div>
              <KpiCards analytics={analytics} loading={loadingData} />
            </div>

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

      {/* Human-Centered Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/60 py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between text-xs text-slate-400 gap-4">
          <div className="space-y-1 text-center md:text-left">
            <p className="font-semibold text-slate-200">
              Wind Procurement Intelligence • UK Balancing Mechanism Insights
            </p>
            <p className="text-[11px] text-slate-500">
              Authoritative datasets: Elexon BMRS FUELHH outturn & WINDFOR forecast vintage streams
            </p>
          </div>
          <div className="flex items-center space-x-4 text-[11px] text-slate-500">
            <span>D-1 Gate Closure Assumption: 11:00 UK Local</span>
            <span>•</span>
            <span>Zero Look-Ahead Bias Verified</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
