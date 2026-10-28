# API Documentation: Elexon BMRS Integration & Backend REST API

## 1. External Elexon BMRS Insights Solution Integration

The Wind Procurement Intelligence backend interfaces directly with the modern RESTful endpoints of the **Elexon BMRS Insights Solution API** (`https://data.elexon.co.uk/bmrs/api/v1`).

### 1.1 Datasets & Endpoints Summary

| Dataset | Physical Meaning | API Endpoint Path | Key Query Parameters | Frequency & Resolution |
|---|---|---|---|---|
| **FUELHH** | Half-hourly generation outturn by fuel type | `/datasets/FUELHH/stream` | `settlementDateFrom` (YYYY-MM-DD), `settlementDateTo` (YYYY-MM-DD) | Half-hourly (30 min), 48 SPs/day |
| **WINDFOR** | National wind generation forecast vintages | `/datasets/WINDFOR/stream` | `publishDateTimeFrom` (ISO 8601 UTC), `publishDateTimeTo` (ISO 8601 UTC) | Published every 2–3 hours |

---

### 1.2 Endpoint Details & Filtering Rules

#### `GET /datasets/FUELHH/stream`
- **Purpose**: Retrieves actual generation outturn across Great Britain.
- **Query Parameters**:
  - `settlementDateFrom` (string, required): Start date (e.g., `2026-01-01`).
  - `settlementDateTo` (string, required): End date (e.g., `2026-01-03`).
- **Client Filtering**:
  - The API returns records for multiple fuel categories (`NUCLEAR`, `CCGT`, `BIOMASS`, `WIND`, `SOLAR`, `NPSHYD`, `INTFR`, etc.).
  - The client filters records strictly where `fuelType.upper() == 'WIND'`.
- **Fields Extracted**:
  - `startTime`: Interval start in UTC (`2026-01-01T00:00:00Z`).
  - `settlementDate`: Calendar date in GB (`2026-01-01`).
  - `settlementPeriod`: GB Settlement period integer (1 to 48).
  - `generation`: Actual active power in Megawatts (MW).
  - `publishTime`: Settlement publishing timestamp.

#### `GET /datasets/WINDFOR/stream`
- **Purpose**: Retrieves forecast national wind power output.
- **Query Parameters**:
  - `publishDateTimeFrom` (ISO 8601 UTC, required): Forecast vintage publish start (e.g., `2025-12-31T00:00:00Z`).
  - `publishDateTimeTo` (ISO 8601 UTC, required): Forecast vintage publish end (e.g., `2025-12-31T23:59:59Z`).
- **Crucial Parameter Discovery**:
  - As verified in the Elexon OpenAPI specification, `/datasets/WINDFOR/stream` **only filters by publish date**, not by settlement delivery date.
  - Therefore, to obtain day-ahead forecasts for January 1, 2026 delivery, queries must retrieve publications from December 31, 2025 (and late December), capturing forecasts that look ahead into January 2026.
- **Fields Extracted & Dual Timestamp Invariant**:
  - `startTime`: Target delivery interval start timestamp in UTC (`2026-01-01T12:00:00Z`).
  - `publishTime`: Exact vintage publication timestamp (`2025-12-31T09:30:00Z`).
  - `generation`: Forecasted wind output in Megawatts (MW).
  - **Preservation Policy**: Both timestamps are preserved in database models; multiple forecast vintages for the same `startTime` are never overwritten.

---

### 1.3 Resiliency, Rate Limiting & Chunking Strategy

1. **Chunking**: To prevent long-lived streaming connection timeouts and excessive response payloads, requests are automatically partitioned into 3-day window chunks (`chunk_days = 3`).
2. **Rate Limiting & Exponential Backoff**:
   - On HTTP 429 (`Too Many Requests`), the client checks the `Retry-After` header or backs off exponentially:
     $$\text{delay} = \text{backoff\_factor} \times 2^{\text{attempt}}$$
   - Retries up to `ELEXON_MAX_RETRIES` (default: 3).
3. **5xx Server Error Retries**:
   - Retries transient 500, 502, 503, and 504 errors using the same exponential backoff strategy.
4. **Offline Fixtures**:
   - `backend/tests/fixtures/fuelhh_sample.json` and `backend/tests/fixtures/windfor_sample.json` provide deterministic offline payloads for CI and sandboxed environments.

---

## 2. Backend REST API Endpoints (FastAPI)

### 2.1 Health Check
- **Endpoint**: `GET /api/health`
- **Description**: Returns operational status, SQLite database connectivity, record counts, and default decision cutoff assumption.
- **Response Format** (`200 OK`):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "database_connected": true,
  "timestamp_utc": "2026-10-26T10:02:31Z",
  "dataset_scope": "January 2026 UK Wind Procurement",
  "actual_records_count": 0,
  "forecast_records_count": 0,
  "default_decision_cutoff": "11:00 Europe/London"
}
```

---

## 3. How to Run Tests

### Run All Backend Unit & Integration Tests (Deterministic / Offline)
```bash
python -m pytest backend/tests -v
```

### Run Elexon Client Tests Only
```bash
python -m pytest backend/tests/test_elexon_client.py -v
```

### Run Live Elexon API Verification (Requires Network Access)
```bash
python -c "import asyncio, datetime; from backend.app.clients.elexon_client import ElexonClient; asyncio.run(ElexonClient().fetch_actual_wind_generation(datetime.date(2026, 1, 1), datetime.date(2026, 1, 1)))"
```
