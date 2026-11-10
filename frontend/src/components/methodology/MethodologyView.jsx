import React from 'react';
import { BookOpen, Clock, Layers, Target, CheckCircle2, AlertTriangle, ShieldCheck, HelpCircle, FileText } from 'lucide-react';

export default function MethodologyView() {
  return (
    <div className="space-y-7">
      {/* Title */}
      <section className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-7 shadow-xl space-y-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-cyan-950/80 border border-cyan-800/60 text-cyan-400">
            <BookOpen className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Procurement Methodology & Market Framework
            </h1>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
              Standard operating definitions, timestamp alignment logic, error formulations, and operational boundaries governing this intelligence platform.
            </p>
          </div>
        </div>
      </section>

      {/* Scope Disclaimer Box */}
      <section className="bg-amber-950/20 border border-amber-800/60 rounded-2xl p-6 text-xs text-amber-200/90 space-y-3 shadow-lg">
        <div className="flex items-center space-x-2 text-amber-400 font-bold text-sm">
          <AlertTriangle className="h-5 w-5 flex-shrink-0" />
          <span>Operational Boundary Notice for Procurement Desks</span>
        </div>
        <p className="leading-relaxed text-[12px]">
          This application is a <strong>specialized wind generation forecast evaluation and verification intelligence platform</strong> built for electricity procurement analysts. Its mission is to quantify the historical accuracy and directional bias of day-ahead forecasts issued by National Grid ESO.
        </p>
        <p className="leading-relaxed text-[12px] text-amber-300/80">
          <strong>Explicit Boundary:</strong> It does <em>not</em> forecast customer electricity demand, model thermal/hydro plant dispatch, or execute financial trades. Total procurement volumes and net system cash-out exposure depend on total utility load and other generation assets outside this platform's wind-only scope.
        </p>
      </section>

      {/* 4 Core Pillars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        {/* 1. D-1 Decision Cutoff & Zero Look-Ahead Bias */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center space-x-2.5 font-bold text-slate-200 text-sm border-b border-slate-800 pb-3">
            <Clock className="h-5 w-5 text-amber-400" />
            <span>1. Day-Ahead Decision Gate & Look-Ahead Prevention</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-[12px]">
            To provide an honest evaluation of real-world procurement decisions, the platform reproduces the exact information environment available to traders when day-ahead auction bids were submitted:
          </p>
          <ul className="space-y-2.5 text-slate-300 text-[11px]">
            <li className="flex items-start space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400 mt-1.5 flex-shrink-0"></span>
              <span>
                <strong className="text-white">Day-Ahead Decision Gate (D-1):</strong> Order books on major wholesale power exchanges (EPEX SPOT and Nord Pool) close during the late morning on the day preceding delivery. The platform defaults to an <strong>11:00 Europe/London (GMT)</strong> decision cutoff.
              </span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400 mt-1.5 flex-shrink-0"></span>
              <span>
                <strong className="text-white">Strict Vintage Selection Rule:</strong> For any delivery hour on date $D$, the engine queries all WINDFOR publication vintages and selects the latest revision satisfying <code className="text-amber-300 font-mono">publish_timestamp &le; decision_cutoff(D-1)</code> and <code className="text-amber-300 font-mono">publish_timestamp &le; delivery_timestamp</code>.
              </span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400 mt-1.5 flex-shrink-0"></span>
              <span>
                <strong className="text-white">Zero Look-Ahead Bias:</strong> Revisions published after the cutoff (or during physical delivery) are strictly disqualified. If no forecast was published prior to cutoff, the interval is reported as unavailable—never forward-substituted.
              </span>
            </li>
          </ul>
        </div>

        {/* 2. Error Sign Convention & Imbalance Impact */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center space-x-2.5 font-bold text-slate-200 text-sm border-b border-slate-800 pb-3">
            <Target className="h-5 w-5 text-cyan-400" />
            <span>2. Forecast Error Convention & Balancing Exposure</span>
          </div>
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center font-mono font-bold text-cyan-300 text-sm">
            forecast_error_mw = forecast_generation_mw − actual_generation_mw
          </div>
          <p className="text-slate-300 leading-relaxed text-[12px]">
            The mathematical sign of the forecast error directly reflects the physical position of a procurement portfolio:
          </p>
          <div className="space-y-3 pt-1">
            <div className="bg-amber-950/30 border border-amber-800/50 p-3.5 rounded-xl space-y-1">
              <span className="font-bold text-amber-400 text-xs flex items-center space-x-1.5">
                <span>Positive Error (+MW) = Overforecasting</span>
              </span>
              <p className="text-slate-300 text-[11px] leading-relaxed">
                National Grid predicted more wind than actually materialized. A procurement desk relying on this forecast will experience a <strong>short volume position</strong> in real time, forcing them to buy emergency balancing power at potentially exorbitant System Buy Prices.
              </p>
            </div>
            <div className="bg-blue-950/30 border border-blue-800/50 p-3.5 rounded-xl space-y-1">
              <span className="font-bold text-blue-400 text-xs flex items-center space-x-1.5">
                <span>Negative Error (−MW) = Underforecasting</span>
              </span>
              <p className="text-slate-300 text-[11px] leading-relaxed">
                Physical wind output exceeded expectations. The desk over-contracted expensive thermal generation, resulting in a <strong>long volume position</strong> that must "spill" back onto the system.
              </p>
            </div>
          </div>
        </div>

        {/* 3. Resolution Bridge */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center space-x-2.5 font-bold text-slate-200 text-sm border-b border-slate-800 pb-3">
            <Layers className="h-5 w-5 text-indigo-400" />
            <span>3. Hourly to Half-Hourly Resolution Alignment</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-[12px]">
            In the Great Britain market, physical electricity generation is measured and settled in <strong>48 half-hour settlement periods</strong> (FUELHH). In contrast, National Grid's day-ahead forecasts (WINDFOR) are published at <strong>1-hour intervals</strong>.
          </p>
          <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 font-mono text-[11px] space-y-1.5">
            <div className="text-slate-400 font-sans font-medium">Standard Resolution Mapping:</div>
            <div className="text-amber-400">WINDFOR 14:00 Forecast (1 Hour Block) ──────┐</div>
            <div className="text-cyan-400 pl-4">├── Settlement Period 29 (14:00–14:30 Actual Outturn)</div>
            <div className="text-cyan-400 pl-4">└── Settlement Period 30 (14:30–15:00 Actual Outturn)</div>
          </div>
          <p className="text-slate-400 text-[11px] leading-relaxed">
            Our alignment bridge floors each 30-minute interval to its enclosing forecast hour. Accuracy metrics (MAE, RMSE, Bias, MAPE) operate on matched 30-minute settlement rows to preserve exact alignment with balancing cash-out timeframes.
          </p>
        </div>

        {/* 4. Safe MAPE & Zero Imputation Policy */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center space-x-2.5 font-bold text-slate-200 text-sm border-b border-slate-800 pb-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            <span>4. Safe Percentage Error & Missing Data Policy</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-[12px]">
            Statistical integrity is maintained through rigorous edge-case handling:
          </p>
          <ul className="space-y-2.5 text-slate-300 text-[11px]">
            <li className="flex items-start space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0"></span>
              <span>
                <strong className="text-white">Safe MAPE (Zero-Actual Protection):</strong> Calculating percentage error requires dividing by actual generation (<code className="font-mono text-cyan-300">|error| / actual</code>). When wind drops to zero (0 MW outturn), division by zero is mathematically undefined. The platform safely excludes zero-actual intervals from percentage summation, while fully maintaining them in MAE and RMSE.
              </span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0"></span>
              <span>
                <strong className="text-white">Never Coerce Missing Data to Zero:</strong> If an interval is missing from the Elexon feed, it remains <code className="text-slate-400 font-mono">null</code>. It is never replaced with 0 MW or smoothed over with synthetic interpolation.
              </span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0"></span>
              <span>
                <strong className="text-white">Transparent Denominators:</strong> Every API response and UI card explicitly states the exact number of evaluated intervals and excluded observations.
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
