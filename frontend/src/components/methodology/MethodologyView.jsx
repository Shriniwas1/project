import React from 'react';
import { ShieldAlert, Clock, Layers, Target, HelpCircle, CheckCircle, AlertTriangle } from 'lucide-react';

export default function MethodologyView() {
  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
        <h1 className="text-xl font-bold text-white flex items-center space-x-2">
          <ShieldAlert className="h-5 w-5 text-cyan-400" />
          <span>Procurement Methodology & System Scope</span>
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Architectural principles, mathematical definitions, and operational constraints for UK wind forecast evaluation
        </p>
      </div>

      {/* Scope Disclaimer Box */}
      <div className="bg-amber-950/20 border border-amber-800/60 rounded-xl p-5 text-xs text-amber-200/90 space-y-2">
        <div className="flex items-center space-x-2 text-amber-400 font-bold text-sm">
          <AlertTriangle className="h-4 w-4" />
          <span>Procurement Intelligence System Boundary</span>
        </div>
        <p className="leading-relaxed text-[12px]">
          This application is a <strong>specialized wind forecast evaluation and accuracy verification tool</strong> designed to help utility procurement desks analyze historical day-ahead forecast quality against actual delivery outturns. It does <strong>not</strong> forecast electricity demand, optimize thermal/hydro assets, or calculate net utility procurement positions and market cashout prices.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        {/* 1. Decision Cutoff & Vintage Selection */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-3">
          <div className="flex items-center space-x-2 font-bold text-slate-200 text-sm border-b border-slate-800 pb-2">
            <Clock className="h-4 w-4 text-amber-400" />
            <span>Day-Ahead Decision Cutoff & Zero Look-Ahead Bias</span>
          </div>
          <p className="text-slate-400 leading-relaxed text-[11px]">
            To mirror real-world power procurement decisions, forecasts must be evaluated using only information that was genuinely published and available at the gate closure cutoff.
          </p>
          <ul className="list-disc pl-4 space-y-1.5 text-slate-300 text-[11px]">
            <li>
              <strong>Configurable Cutoff:</strong> Defaults to <code className="text-amber-300 font-mono">11:00 Europe/London</code> on Day Ahead (D-1), representing standard day-ahead procurement deadlines before EPEX/Nord Pool auctions.
            </li>
            <li>
              <strong>Date-Specific Evaluation:</strong> Multi-day ranges evaluate each delivery date under its respective D-1 cutoff (e.g. Jan 1 uses Dec 31 11:00 UTC, Jan 2 uses Jan 1 11:00 UTC).
            </li>
            <li>
              <strong>Strict Selection Rule:</strong> For any delivery interval, the engine selects the latest forecast vintage where <code className="text-cyan-300 font-mono">publish_timestamp &le; decision_cutoff_utc</code>.
            </li>
            <li>
              <strong>Look-Ahead Prevention:</strong> Retrospective vintages and forecasts published after the cutoff are rigorously excluded.
            </li>
          </ul>
        </div>

        {/* 2. Error Sign Convention */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-3">
          <div className="flex items-center space-x-2 font-bold text-slate-200 text-sm border-b border-slate-800 pb-2">
            <Target className="h-4 w-4 text-cyan-400" />
            <span>Error Sign Convention</span>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-center font-mono font-bold text-cyan-300 text-sm">
            forecast_error_mw = forecast_generation_mw − actual_generation_mw
          </div>
          <p className="text-slate-400 leading-relaxed text-[11px]">
            The error sign directly communicates the direction of physical system imbalance:
          </p>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="bg-amber-950/30 border border-amber-800/40 p-2.5 rounded-lg">
              <span className="font-bold text-amber-400">Positive Error (+MW)</span>
              <p className="text-slate-300 mt-0.5">
                <strong>Overforecasting:</strong> Forecast exceeded delivered actuals. Implies potential deficit in real-time if procurement matched forecast.
              </p>
            </div>
            <div className="bg-blue-950/30 border border-blue-800/40 p-2.5 rounded-lg">
              <span className="font-bold text-blue-400">Negative Error (−MW)</span>
              <p className="text-slate-300 mt-0.5">
                <strong>Underforecasting:</strong> Actual generation exceeded forecast. Implies long position in real-time.
              </p>
            </div>
          </div>
        </div>

        {/* 3. Resolution Bridge */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-3">
          <div className="flex items-center space-x-2 font-bold text-slate-200 text-sm border-b border-slate-800 pb-2">
            <Layers className="h-4 w-4 text-indigo-400" />
            <span>Hourly-to-Half-Hourly Resolution Bridge</span>
          </div>
          <p className="text-slate-400 leading-relaxed text-[11px]">
            UK market physical settlement operates on 30-minute settlement periods (SP 1–48), whereas NESO WINDFOR forecasts are published in 1-hour blocks:
          </p>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono text-[11px] space-y-1">
            <div className="text-slate-400">Example matching for 10:00:</div>
            <div className="text-amber-400">WINDFOR 10:00 Forecast (1 hr) ───┐</div>
            <div className="text-cyan-400 pl-4">├── SP 21 (10:00–10:30 Actual)</div>
            <div className="text-cyan-400 pl-4">└── SP 22 (10:30–11:00 Actual)</div>
          </div>
          <p className="text-slate-400 text-[11px]">
            Comparison rows and accuracy metrics operate on the 30-minute half-hourly level. A 2-day period features 48 unique hourly forecasts covering 96 half-hourly comparison rows.
          </p>
        </div>

        {/* 4. Safe MAPE & Missing Data Integrity */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-3">
          <div className="flex items-center space-x-2 font-bold text-slate-200 text-sm border-b border-slate-800 pb-2">
            <CheckCircle className="h-4 w-4 text-emerald-400" />
            <span>Safe MAPE & Missing Data Integrity</span>
          </div>
          <ul className="list-disc pl-4 space-y-2 text-slate-300 text-[11px]">
            <li>
              <strong>Zero-Actual Exclusion:</strong> Mean Absolute Percentage Error (MAPE) divides by actual generation (<code className="font-mono text-cyan-300">|error| / |actual|</code>). Intervals with <code className="font-mono text-cyan-300">actual == 0 MW</code> are safely excluded from MAPE to avoid division by zero.
            </li>
            <li>
              <strong>Retained in MAE & RMSE:</strong> Intervals with 0 MW actual are well-defined in absolute terms and remain fully included in MAE, RMSE, and Bias.
            </li>
            <li>
              <strong>No Zero Coercion:</strong> Intervals missing either actual or forecast data are excluded from metric denominators and never coerced to 0 MW.
            </li>
            <li>
              <strong>Full Vintage Preservation:</strong> Elexon WINDFOR forecasts are stored without overwriting historical publication revisions.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
