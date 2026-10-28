# Data Dictionary: Wind Procurement Intelligence

## 1. Raw Elexon BMRS Source Datasets

### 1.1 Actual Wind Outturn (`FUELHH`)
- **API Endpoint**: `https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`
- **Description**: Half-hourly generation outturn broken down by fuel type for Great Britain.

| Field Name | Source JSON Type | Nullable | Example Value | Description |
|---|---|---|---|---|
| `dataset` | string | No | `"FUELHH"` | Constant dataset identifier. |
| `publishTime` | string (ISO 8601 UTC) | No | `"2026-01-02T00:00:00Z"` | Timestamp when settlement run was published by Elexon. |
| `startTime` | string (ISO 8601 UTC) | No | `"2026-01-01T23:30:00Z"` | Start of the 30-minute settlement period in UTC. |
| `settlementDate` | string (`YYYY-MM-DD`) | No | `"2026-01-01"` | Calendar settlement date in Great Britain (`Europe/London`). |
| `settlementPeriod` | integer (1–50) | No | `48` | GB half-hour settlement period number (1 to 48 on normal days). |
| `fuelType` | string | No | `"WIND"` | Primary fuel category. Filtered strictly to `"WIND"`. |
| `generation` | integer / float | No | `15538` | Average active power generation during the 30-minute interval in Megawatts (MW). |

---

### 1.2 Forecast Wind Generation (`WINDFOR`)
- **API Endpoint**: `https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`
- **Description**: National wind power generation forecasts published at regular intervals by National Grid ESO / NESO.

| Field Name | Source JSON Type | Nullable | Example Value | Description |
|---|---|---|---|---|
| `dataset` | string | No | `"WINDFOR"` | Constant dataset identifier. |
| `publishTime` | string (ISO 8601 UTC) | No | `"2025-12-31T09:30:00Z"` | Forecast publication timestamp when ESO released this vintage. |
| `startTime` | string (ISO 8601 UTC) | No | `"2026-01-01T14:00:00Z"` | Start of the target delivery interval being forecasted. |
| `generation` | integer / float | No | `18250` | Forecasted aggregate wind power output for the interval in Megawatts (MW). |

---

## 2. Relational Database Schema (SQLite)

### 2.1 Table: `actual_generation`
Stores verified actual outturn wind generation for GB.

| Column Name | SQL Type | Nullable | PK / Unique / Index | Description |
|---|---|---|---|---|
| `id` | `INTEGER` | No | Primary Key | Auto-incrementing surrogate identifier. |
| `delivery_timestamp` | `DATETIME` | No | Index, Unique (`delivery_timestamp`, `source`) | Delivery interval start time stored in UTC. |
| `delivery_date` | `DATE` | No | Index | Calendar date of delivery in `Europe/London`. |
| `settlement_period` | `INTEGER` | Yes | - | Settlement period number (1–50). |
| `generation_mw` | `FLOAT` | No | - | Actual average wind generation in Megawatts (MW). |
| `source` | `VARCHAR(32)` | No | Unique (`delivery_timestamp`, `source`) | Data origin identifier (e.g., `"ELEXON_FUELHH"`). |
| `created_at` | `DATETIME` | No | - | Record insertion timestamp (UTC). |

---

### 2.2 Table: `forecast_generation`
Stores multi-vintage wind generation forecasts published at various points in time.

| Column Name | SQL Type | Nullable | PK / Unique / Index | Description |
|---|---|---|---|---|
| `id` | `INTEGER` | No | Primary Key | Auto-incrementing surrogate identifier. |
| `delivery_timestamp` | `DATETIME` | No | Index, Unique (`delivery_timestamp`, `publish_timestamp`, `source`) | Target delivery interval start time in UTC. |
| `delivery_date` | `DATE` | No | Index | Calendar date of delivery in `Europe/London`. |
| `publish_timestamp` | `DATETIME` | No | Index, Unique (`delivery_timestamp`, `publish_timestamp`, `source`) | Vintage publication timestamp in UTC. |
| `generation_mw` | `FLOAT` | No | - | Forecasted wind generation in Megawatts (MW). |
| `source` | `VARCHAR(32)` | No | Unique (`delivery_timestamp`, `publish_timestamp`, `source`) | Data origin identifier (e.g., `"ELEXON_WINDFOR"`). |
| `created_at` | `DATETIME` | No | - | Record insertion timestamp (UTC). |

---

### 2.3 Table: `ingestion_log`
Provides an audit log of all automated or manual data ingestion events.

| Column Name | SQL Type | Nullable | PK / Unique / Index | Description |
|---|---|---|---|---|
| `id` | `INTEGER` | No | Primary Key | Auto-incrementing surrogate identifier. |
| `dataset` | `VARCHAR(32)` | No | Index | `"FUELHH"` or `"WINDFOR"`. |
| `date_from` | `DATETIME` | No | - | Range start queried from source API. |
| `date_to` | `DATETIME` | No | - | Range end queried from source API. |
| `records_ingested` | `INTEGER` | No | - | Number of records inserted or updated. |
| `status` | `VARCHAR(16)` | No | - | `"SUCCESS"`, `"PARTIAL"`, or `"FAILED"`. |
| `error_message` | `TEXT` | Yes | - | Exception or error message if status is failed. |
| `created_at` | `DATETIME` | No | - | Timestamp of the ingestion execution. |

---

## 3. Analytical & Derived Metric Fields

| Metric Field | Type | Units | Mathematical Definition | Interpretation |
|---|---|---|---|---|
| `forecast_error` | float | MW | $\hat{y}_t - y_t$ | Signed deviation. Positive = Overforecast, Negative = Underforecast. |
| `absolute_error` | float | MW | $\|\hat{y}_t - y_t\|$ | Magnitude of forecast error. |
| `percentage_error` | float | % | $\frac{\|\hat{y}_t - y_t\|}{y_t} \times 100$ | Relative error (null when $y_t = 0$). |
| `mae` | float | MW | $\frac{1}{N} \sum \|\hat{y}_t - y_t\|$ | Mean Absolute Error across evaluated intervals. |
| `rmse` | float | MW | $\sqrt{\frac{1}{N} \sum (\hat{y}_t - y_t)^2}$ | Root Mean Squared Error across evaluated intervals. |
| `bias` | float | MW | $\frac{1}{N} \sum (\hat{y}_t - y_t)$ | Systematic average directional bias across intervals. |
| `mape` | float | % | $\frac{100}{M} \sum_{y_t > 0} \frac{\|\hat{y}_t - y_t\|}{y_t}$ | Mean Absolute Percentage Error on non-zero actuals. |
| `expected_intervals` | integer | count | $48 \times \text{days}$ | Expected 30-min settlement intervals in period. |
| `actual_intervals` | integer | count | Count of valid actual records | Actual intervals retrieved. |
| `forecast_intervals` | integer | count | Count of eligible forecast intervals | Intervals with at least one eligible forecast vintage. |
| `matched_intervals` | integer | count | Count of intervals with both | Number of intervals with both actual and forecast data ($N$). |
| `missing_actuals` | integer | count | $\text{expected} - \text{actual}$ | Expected intervals missing actual outturn. |
| `missing_forecasts`| integer | count | $\text{expected} - \text{forecast}$ | Expected intervals missing pre-cutoff forecast. |
| `mape_excluded` | integer | count | Count of $y_t = 0$ intervals | Intervals excluded from MAPE to prevent division by zero ($K$). |

---

## 4. REST API Schema Entities

### 4.1 Comparison Interval Item (`ComparisonInterval`)
```json
{
  "delivery_timestamp": "2026-01-01T12:00:00Z",
  "delivery_date": "2026-01-01",
  "settlement_period": 25,
  "actual_generation_mw": 14250.5,
  "forecast_generation_mw": 15100.0,
  "publish_timestamp": "2025-12-31T09:30:00Z",
  "forecast_error_mw": 849.5,
  "absolute_error_mw": 849.5,
  "percentage_error": 5.96,
  "is_overforecast": true,
  "is_underforecast": false,
  "status": "MATCHED"
}
```

### 4.2 Analytics Response (`AnalyticsResponse`)
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "decision_cutoff": "11:00",
  "metrics": {
    "mae_mw": 1120.4,
    "rmse_mw": 1485.2,
    "bias_mw": 315.6,
    "mape_percent": 8.74
  },
  "coverage": {
    "expected_intervals": 1488,
    "actual_intervals": 1488,
    "forecast_intervals": 1488,
    "matched_intervals": 1488,
    "missing_actuals": 0,
    "missing_forecasts": 0,
    "mape_excluded_zero_actuals": 0
  },
  "error_distribution": [
    { "range_mw": "<-2000", "count": 42 },
    { "range_mw": "-2000 to -1000", "count": 180 },
    { "range_mw": "-1000 to 0", "count": 420 },
    { "range_mw": "0 to 1000", "count": 510 },
    { "range_mw": "1000 to 2000", "count": 250 },
    { "range_mw": ">2000", "count": 86 }
  ]
}
```
