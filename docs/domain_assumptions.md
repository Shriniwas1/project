# Domain Assumptions & Market Rules

## 1. Industry Context & Business Problem

Electricity cannot be stored cost-effectively at national scale in Great Britain (GB) without substantial battery capacity and pumped storage; therefore, the Great Britain power system operated by the National Energy System Operator (NESO) must maintain instantaneous supply-demand balance at 50 Hz.

Energy utilities participating in the GB wholesale electricity market (governed by the Balancing and Settlement Code - BSC, administered by Elexon) must forecast customer demand and procure sufficient power ahead of physical delivery. A major component of the GB supply stack is renewable wind generation (both onshore and offshore). Because wind power is weather-dependent and intermittent, procurement teams rely on day-ahead wind generation forecasts published by the transmission system operator to determine:
1. Expected zero-marginal-cost renewable volume available in the day-ahead auction (e.g. EPEX SPOT or Nord Pool GB Day-Ahead Auctions).
2. The residual electricity volume that must be contracted via thermal generation (CCGT), nuclear, biomass, interconnectors, or peaker plants.
3. The exposure risk to balancing mechanism imbalance settlement cash-out prices if actual wind generation deviates from day-ahead contracts.

---

## 2. Elexon Datasets & Physical Settlement Conventions

### 2.1 Settlement Periods
- In the GB electricity market, the trading day is divided into **48 half-hour settlement periods** (numbered 1 to 48):
  - Settlement Period 1: 00:00 to 00:30 UK local time.
  - Settlement Period 48: 23:30 to 24:00 (00:00 next day) UK local time.
- On clock change days (not applicable in January, but accounted for in system design):
  - Short day (Spring clock change): 46 settlement periods.
  - Long day (Autumn clock change): 50 settlement periods.

### 2.2 FUELHH: Actual Half-Hourly Outturn Generation
- **Source**: Elexon BMRS Insights Solution dataset `FUELHH`.
- **Filtering**: `fuelType = 'WIND'`.
- **Physical Meaning**: Average active electrical power delivered to the national transmission grid across the 30-minute settlement period, expressed in Megawatts (MW).
- **Delivery Interval Identification**: The `startTime` field marks the start of the 30-minute interval (in UTC ISO 8601, e.g., `2026-01-01T00:00:00Z`).

### 2.3 WINDFOR: Wind Generation Forecast
- **Source**: Elexon BMRS Insights Solution dataset `WINDFOR`.
- **Physical Meaning**: Aggregated forecast of national wind generation output (MW) across GB.
- **Dual Timestamps**:
  - `startTime`: The start of the physical delivery interval (e.g., `2026-01-01T14:00:00Z`).
  - `publishTime`: The exact timestamp when National Grid ESO / NESO generated and published this forecast revision (e.g., `2025-12-31T09:30:00Z`).
- **Forecast Vintages (Revisions) & 72-Hour Sliding Batch Windows**:
  - NESO updates and publishes wind forecasts up to 8 times daily (e.g., 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC).
  - Each publication batch contains a sliding 72-hour horizon (73 intervals) starting from a fixed anchor at 21:00 UTC of the preceding day.
  - **Retrospective Anchor Records**: Because the batch file starts at 21:00 of the prior evening, the initial 6 to 26 intervals in a daytime batch represent intervals that have already physically delivered (`publishTime > startTime`). These records have negative lead times (`lead_time_hours < 0`) and represent retrospective model anchors, **NOT ex-ante forecasts**.
  - **Resolution Finding**: In the raw Elexon BMRS dataset, `FUELHH` outturn is provided at 30-minute settlement period resolution (48 intervals/day), whereas `WINDFOR` forecasts are issued at hourly resolution (24 intervals/day, `:00` timestamps).
- **Forecast Preservation Policy**: All distinct `(startTime, publishTime)` pairs are preserved in database models; earlier vintages are never overwritten.

---

## 3. January 2026 Temporal Scope & Timezone Handling

### 3.1 Date Boundaries
- **Delivery Period**: January 1, 2026 00:00:00 through January 31, 2026 23:59:59 UK Local Time (`Europe/London`).
- **Total Expected Intervals**:
  - Actual Generation (`FUELHH`): $31 \text{ days} \times 48 \text{ periods/day} = 1,488 \text{ half-hour settlement intervals}$.
  - Hourly Forecast Generation (`WINDFOR`): $31 \text{ days} \times 24 \text{ hours/day} = 744 \text{ hourly forecast intervals}$.

### 3.2 Timezone Policy
- While the UK is in Greenwich Mean Time (GMT, UTC+00:00) during January, **all internal timestamps, database storage, and comparisons are strictly UTC-aware ISO 8601 strings or UTC datetime objects**.
- Timestamps displayed to users on the dashboard are localized to `Europe/London`.
- No naive datetime string operations are permitted. The delivery date of an interval is derived from `startTime` converted to `Europe/London`.

---

## 4. Day-Ahead Decision Cutoff & Look-Ahead Bias Prevention

### 4.1 Day-Ahead Decision Timing Rule
For any physical delivery date $D$:
- **Decision Date**: $D - 1$ (the day immediately preceding delivery).
- **Default Cutoff Time**: 11:00 Europe/London on $D - 1$.
- **Cutoff Timestamp ($T_{\text{cutoff}}$)**:
  $$T_{\text{cutoff}}(D) = \text{DateTime}(D - 1 \text{ day}, 11:00:00 \text{ Europe/London})$$

> **Market Context Assumption**: In Great Britain wholesale power trading, day-ahead power exchange auctions (such as EPEX SPOT UK Day-Ahead Auction) have order book closure deadlines around 09:20 or 11:00 UK time. Setting the default cutoff at 11:00 UK time on $D-1$ reflects an assumed procurement decision deadline. This value is configurable in the application and is explicitly documented as a model assumption rather than a statutory regulatory gate closure.

### 4.2 Forecast Selection Algorithm & Ex-Ante Validation
To evaluate the forecast that the procurement team realistically possessed at the time of placing orders:
1. Identify all forecast records where `startTime` falls within delivery date $D$.
2. Filter the records to include only genuine **ex-ante** forecasts published at or before the decision cutoff:
   $$\text{publishTime} \le T_{\text{cutoff}}(D) \quad \text{AND} \quad \text{publishTime} \le \text{startTime}$$
3. Group eligible records by delivery interval `startTime`.
4. For each interval, select the record with the maximum `publishTime`:
   $$\hat{y}_t = \text{generation}(\text{latest eligible vintage published} \le T_{\text{cutoff}})$$
5. Reject all forecasts published after $T_{\text{cutoff}}$ (zero look-ahead bias).
6. Reject any retrospective forecast published after delivery start (`publishTime > startTime`).
7. If no forecast exists for a given interval prior to $T_{\text{cutoff}}$, the interval is flagged as `MISSING_FORECAST`. Under no circumstances is a post-cutoff forecast substituted.

---

## 5. Mathematical Formulations of Forecast Accuracy Metrics

### 5.1 Interval Forecast Error
For delivery interval $t$ with actual generation $y_t$ and day-ahead forecast generation $\hat{y}_t$:
$$e_t = \hat{y}_t - y_t$$

- **$e_t > 0$ (Overforecast / Positive Error)**: The model predicted more wind than actually materialized. In practice, the utility would have under-procured thermal backup or sold too much power, forcing them to buy emergency imbalance power at potentially high system buy prices.
- **$e_t < 0$ (Underforecast / Negative Error)**: The model predicted less wind than was generated. The utility would have over-procured expensive thermal power, incurring unnecessary procurement costs.
- **$e_t = 0$**: Perfect forecast match.

### 5.2 Aggregate Verification Metrics
Across a set of $N$ matched delivery intervals:

#### Mean Absolute Error (MAE)
$$\text{MAE} = \frac{1}{N} \sum_{t=1}^N |e_t| = \frac{1}{N} \sum_{t=1}^N |\hat{y}_t - y_t|$$
Measures average forecast magnitude error in Megawatts (MW).

#### Root Mean Squared Error (RMSE)
$$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{t=1}^N e_t^2} = \sqrt{\frac{1}{N} \sum_{t=1}^N (\hat{y}_t - y_t)^2}$$
Penalizes larger forecast errors more heavily than small errors, reflecting the non-linear risk of large supply deficits.

#### Forecast Bias (Mean Error)
$$\text{Bias} = \frac{1}{N} \sum_{t=1}^N e_t = \frac{1}{N} \sum_{t=1}^N (\hat{y}_t - y_t)$$
Indicates systematic over-forecasting ($\text{Bias} > 0$) or under-forecasting ($\text{Bias} < 0$).

#### Mean Absolute Percentage Error (MAPE) & Zero-Actual Guard
$$\text{MAPE} = \frac{100\%}{M} \sum_{t \in \{t \mid y_t > 0\}} \left| \frac{\hat{y}_t - y_t}{y_t} \right|$$
- If actual generation $y_t = 0$ MW, percentage error is mathematically undefined (division by zero).
- Intervals where $y_t = 0$ are **strictly excluded** from the MAPE summation.
- The platform reports both the evaluated interval count $M$ and the excluded count $K = N - M$.

### 5.3 Data Coverage Audit
No metric is presented without transparent coverage accounting:
- **Expected Intervals**: $48 \times \text{number of delivery days}$.
- **Actual Intervals Available**: Distinct actual outturn intervals ingested.
- **Forecast Intervals Available**: Distinct delivery intervals with at least one eligible forecast.
- **Matched Intervals ($N$)**: Intervals with both valid actual generation and eligible forecast.
- **Missing Actual Intervals**: Expected intervals lacking outturn.
- **Missing Forecast Intervals**: Expected intervals lacking pre-cutoff forecasts.
- **MAPE Excluded Intervals ($K$)**: Matched intervals where $y_t = 0$.

---

## 6. Business Boundaries & Scope Limitations

1. **Wind-Only Scope**: This system evaluates GB national wind generation only. It does not ingest solar, hydro, nuclear, or thermal generation.
2. **No Demand Modeling**: National electricity demand is excluded from this release. Net system balance cannot be derived solely from this application.
3. **No Financial Pricing or Trading Execution**: The system does not ingest wholesale power prices (APX, N2EX) or system imbalance cash-out prices. It provides operational intelligence to human traders and procurement analysts; it does not automatically submit trading bids or place bilateral orders.
4. **National Aggregate Only**: Data represents national transmission-connected wind generation; individual wind farm telemetry is outside the scope of the Elexon `FUELHH` and `WINDFOR` datasets.
