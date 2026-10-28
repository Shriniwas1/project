# Implementation Plan: Wind Procurement Intelligence

## Overview & Methodology
This plan adheres strictly to the phased delivery model prescribed in `README.md` (Section 19). Execution progresses sequentially from Phase 0 to Phase 9. Under no circumstances will implementation leap ahead without testing, inspection, documentation updates, and explicit user sign-off.

---

## Phase Breakdown

### Phase 0: Domain Understanding, Architecture & Planning (Current Phase)
- **Objectives**:
  - In-depth analysis of UK energy utility business requirements, Elexon BMRS datasets (`FUELHH`, `WINDFOR`), and January 2026 temporal scope.
  - Probe and verify live Elexon OpenAPI specifications and endpoint query parameter behavior.
  - Formulate mathematical accuracy definitions and look-ahead bias mitigation rules.
  - Author core architectural and domain documentation:
    - `docs/architecture.md`
    - `docs/domain_assumptions.md`
    - `docs/data_dictionary.md`
    - `docs/implementation_plan.md`
  - Identify API uncertainties, empirical assumptions, and present for user sign-off.
- **Verification / Acceptance**:
  - Documents generated, technical architecture fully articulated, API nuances proven via live requests, user sign-off obtained before Phase 1 code setup.

---

### Phase 1: Project Setup & Environment Baseline
- **Objectives**:
  - Initialize directory skeleton: `backend/app/`, `backend/tests/`, `frontend/src/`, `docs/`.
  - Configure backend virtual environment, dependencies (`fastapi`, `uvicorn`, `httpx`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `aiosqlite`, `pandas`, `numpy`, `pytest`, `pytest-asyncio`).
  - Configure frontend Vite project with React, Tailwind CSS, Lucide React icons, Axios, and Recharts.
  - Setup `.env.example` and initial config loader.
  - Write test harness verifying imports, environment variables, and timezone utilities.
- **Verification / Acceptance**:
  - Baseline tests pass (`pytest backend/tests`).
  - Frontend development server compiles without warnings.

---

### Phase 2: Elexon API Integration & Client Implementation
- **Objectives**:
  - Build `ElexonClient` in `backend/app/clients/elexon_client.py` using `httpx.AsyncClient`.
  - Implement streaming endpoint handlers for:
    - `/datasets/FUELHH/stream` (filters: `settlementDateFrom`, `settlementDateTo`, `fuelType=WIND`).
    - `/datasets/WINDFOR/stream` (filters: `publishDateTimeFrom`, `publishDateTimeTo`).
  - Build date-range windowing/chunking to safely pull large ranges without HTTP timeouts.
  - Implement retry with exponential backoff on transient 429/500/503 responses.
  - Provide fallback / local seed dataset loader for offline or firewalled environments.
- **Verification / Acceptance**:
  - Unit tests using mocked HTTP responses (`pytest backend/tests/test_elexon_client.py`).
  - Integration test verifying retrieval of actual records for January 2026 from Elexon or offline seed fixtures.

---

### Phase 3: Data Ingestion, Validation & Persistence
- **Objectives**:
  - Define SQLAlchemy ORM models: `ActualGeneration`, `ForecastGeneration`, `IngestionLog`.
  - Setup SQLite database connection with asynchronous engine (`aiosqlite`) and table creation.
  - Build `IngestionService`:
    - Strict validation: numeric MW checks, null rejection, timezone-aware ISO timestamp normalization.
    - Idempotent upsert logic with unique constraints:
      - Actuals: `(delivery_timestamp, source)`
      - Forecasts: `(delivery_timestamp, publish_timestamp, source)`
  - Implement ingestion CLI / runner to populate January 2026 data.
- **Verification / Acceptance**:
  - Ingestion tests verify duplicate handling, corrupted record rejection, and proper index creation (`pytest backend/tests/test_ingestion.py`).
  - Ingestion run confirms 1,488 expected actual intervals for January 2026 in SQLite.

---

### Phase 4: Day-Ahead Forecast Selection Engine
- **Objectives**:
  - Implement `ForecastService`:
    - Given delivery date $D$ and configurable decision cutoff $T_{\text{cutoff}}$ (default `11:00` UK local time on $D-1$).
    - Select latest eligible forecast published $\le T_{\text{cutoff}}$ for each delivery interval.
    - Strictly reject any forecast published after $T_{\text{cutoff}}$ (zero look-ahead bias).
    - Flag missing intervals explicitly as `MISSING_FORECAST` without silent substitution.
  - Implement vintage discovery: list all distinct publication timestamps available for a delivery date.
- **Verification / Acceptance**:
  - Unit tests asserting cutoff edge cases: forecasts published at 10:59 (accepted), 11:00 (accepted), 11:01 (rejected).
  - Verify look-ahead bias immunity (`pytest backend/tests/test_forecast_selection.py`).

---

### Phase 5: Forecast Accuracy & Coverage Analytics Engine
- **Objectives**:
  - Build `AnalyticsService`:
    - Compute interval errors: $e_t = \hat{y}_t - y_t$.
    - Compute summary metrics: MAE, RMSE, Bias.
    - Compute MAPE with zero-actual guard ($y_t > 0$) and track excluded count.
    - Generate error distribution histogram bins.
    - Perform complete data coverage audit (expected, available, matched, missing actuals, missing forecasts, MAPE excluded).
- **Verification / Acceptance**:
  - Unit tests comparing metric functions against hand-computed synthetic fixtures.
  - Zero-actual division-by-zero protection verified (`pytest backend/tests/test_analytics.py`).

---

### Phase 6: FastAPI REST API Implementation
- **Objectives**:
  - Implement and wire routes:
    - `GET /api/health`: Database connectivity, counts, status.
    - `GET /api/actuals`: Filtered by start/end dates.
    - `GET /api/forecasts`: Filtered by delivery date and optional publication timestamp.
    - `GET /api/forecast-vintages`: Distinct publication timestamps.
    - `GET /api/comparison`: Day-ahead matched forecast vs actual with interval breakdown.
    - `GET /api/analytics`: Aggregate metrics, distribution, and coverage audit.
  - Configure CORS middleware, error handling, and OpenAPI Swagger documentation tags.
- **Verification / Acceptance**:
  - Full API integration tests via FastAPI `TestClient` / `httpx.AsyncClient` (`pytest backend/tests/test_api_routes.py`).
  - All status codes, error payloads, and schema types validated.

---

### Phase 7: React Frontend Dashboard Implementation
- **Objectives**:
  - Build clean, high-performance UI using Tailwind CSS and Recharts:
    1. **Overview Dashboard**: Date picker, decision cutoff selector, high-level KPI cards (Daily Wind Energy, MAE, RMSE, Bias, Coverage %), 30-minute timeseries chart comparing Day-Ahead Forecast vs Actual Generation.
    2. **Forecast Vintage Analysis**: Comparison chart showing how wind forecasts evolved over successive publication runs (07:30, 09:30, 11:30, etc.) for the delivery date.
    3. **Accuracy Analytics**: Error histogram, interval scatter/residuals, hourly box/bar performance, and summary metric table.
    4. **Procurement Planning View**: Net wind availability, historical forecast error uncertainty bands (P10/P50/P90), and over/under-generation risk summary.
  - Implement robust loading, error, and empty states.
- **Verification / Acceptance**:
  - Component rendering and state tests using Vitest / React Testing Library.
  - Visual verification of charts and responsive layout.

---

### Phase 8: End-to-End Testing & Data Validation
- **Objectives**:
  - Full January 2026 validation audit: verify that all 31 days (1,488 half-hour intervals) are accounted for.
  - End-to-end integration test validating the complete path: Ingested DB $\to$ Selection Engine $\to$ Metrics Engine $\to$ API Endpoint $\to$ UI payload.
  - Validate that no mock data remains in production code paths.
- **Verification / Acceptance**:
  - 100% test pass rate across backend pytest suite and frontend test suite.
  - Data audit report confirming zero look-ahead bias and exact coverage numbers.

---

### Phase 9: Docker Containerization & Final Documentation
- **Objectives**:
  - Author production multi-stage `backend/Dockerfile` and `frontend/Dockerfile`.
  - Author `docker-compose.yml` linking frontend, backend, and persistent `sqlite_data` volume.
  - Verify single command startup: `docker compose up --build`.
  - Complete all documentation:
    - `README.md` (incorporating AI disclosure, setup, architecture, and usage instructions).
    - `docs/api_documentation.md`
    - `docs/testing_strategy.md`
    - `docs/presentation.md` (client demonstration outline).
- **Verification / Acceptance**:
  - Clean container startup and verification via curl/browser.
  - All documentation verified against project requirements.
