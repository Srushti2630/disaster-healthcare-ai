# Project Progress & Implementation Record

> **Verified State**: October 2026  
> **Status**: Full-Stack Production Upgrade Complete (48 Python Tests + 5 Frontend Tests Passing)

---

## 1. What is Real, Estimated, Assumed

| Item | Tag | Notes |
|---|---|---|
| **EM-DAT Disaster Events** (810 total; 512 with targets; 136 injured) | `REAL` | Raw targets never imputed. Historical events spanning 1920–2023. |
| **District Polygons** (35 districts, median 899 vertices) | `REAL` | Real boundaries in `data/raw/boundaries/`. Legacy 5-vertex rectangles archived. |
| **District Population** (Raw WorldPop zonal sum) | `REAL` | Total 131,936,179 vs ~124.5M official projection (5.97% gap documented as sanity check). No artificial scaling. |
| **Hospital Directory** (4,767 Maharashtra facilities) | `REAL` | Sourced from National Health Portal India. Bed counts valid for ~0.67% of rows, so used only for spatial weighting. |
| **District Hospital & ICU Beds** | `ESTIMATED` | Sourced from official State ICU bed audit (11,587 ICU beds / 144,983 total beds) weighted by facility counts. |
| **Medicine Consumption Rates** | `ASSUMED` | WHO IEHK 2017 & Sphere Project standards (`config/demand_params.yaml`). |
| **Road Distances** | `ASSUMED` | Haversine distance $\times$ 1.3 circuity factor over 35 centroids. |
| **Logistics Transport Cost** | `ASSUMED` | Standardized unitless **Cost Index** ($\text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$). Never currency. |
| **Weather Features** | `NOT USED` | Excluded from impact training to prevent noise injection. Open-Meteo API used only for live What-If scenario queries. |

---

## 2. Core Analytical Pipeline (Phase 1 to Phase 4)

- **Phase 1 (Data Layer)**: Real Maharashtra district boundaries, raw zonal population extraction, facility classification, non-imputed EM-DAT processing.
- **Phase 2 (Impact Model)**:
  - Time-split evaluation (Train $\le 2012$, Val $2013-2018$, Test $2019+$; $N=363 / 71 / 78$).
  - Ridge regression achieved MAE 2.8812, $R^2 = 0.2780$, Spearman $\rho = 0.5199$.
  - Conformalized Quantile Regression (CQR 90%) achieves 94.9% empirical test coverage (conservative intervals).
  - Historical Leave-One-Event-Out backtest by `DisNo.` across 5 benchmark disasters.
- **Phase 3 (Demand Engine & ML Surrogate)**:
  - WHO IEHK / Sphere 2,000-draw Monte-Carlo engine under full residual uncertainty ($\sigma \approx 3.7186$).
  - Simulated casualties strictly capped at resident district population: $\min(\text{affected}, \text{population})$.
  - Surrogate Random Forest classifier trained on 500 scenarios split BY SCENARIO ID: 91.28% fidelity, 0.9085 macro F1, 0.0490 ECE.
- **Phase 4 (Operations Research Solver)**:
  - Google OR-Tools SCIP MIP solver over 35 district nodes and 5 medicine classes.
  - 5 safety constraints enforced: 60% source reserve, high-risk export ban, 150 km blood transit limit, integer packs, non-negativity.
  - 20-scenario benchmark: OR-Tools SCIP achieved lowest mean unmet demand (248.35M units), lowest transport cost index (25.17B units), lowest active route distance (7,148.6 km), and zero rule violations.
- **Core Tests**: All 25 original pytest unit tests in `tests/test_core.py` pass without modifying protected directories.

---

## 3. Full-Stack Production Upgrade (Prompts 1 to 4)

### Prompt 1: FastAPI REST Backend (`api/`)
- Created production FastAPI service structure in `api/`: `config.py`, `logging_utils.py`, `middleware.py` (Request-ID and latency headers), `schemas.py` (Pydantic v2), `lifespan.py`, `services.py`, `routes.py`, `main.py`.
- Exposed endpoints: `/health`, `/api/districts`, `/api/predict-impact`, `/api/simulate`, `/api/allocate`, `/api/backtest`.
- Enforced honest scientific framing, population capping, and Cost Index reporting.
- Verified with 14 unit and integration tests in `tests_api/test_api_endpoints.py`.

### Prompt 2: Auth, Database & Tamper-Evident Ledger (`api/routes_auth.py`, `api/audit_ledger.py`)
- Configured SQLAlchemy 2.0 SQLite database in `api/database.py` with automatic schema creation and user seeding.
- Defined relational models in `api/models.py`: `User`, `SimulationRecord`, `AuditEvent`.
- Implemented native `bcrypt` password hashing and JWT `HS256` token handling in `api/auth.py`.
- Implemented sliding-window rate limiters (20 req/min for auth, 10 req/min for compute-heavy MIP endpoints).
- Implemented SHA-256 cryptographic hash-chained audit ledger with genesis block linking and verification.
- Enforced automated safety guard: blocks `APPROVE` actions with **HTTP 409 Conflict** if prediction confidence is $< 0.60$.
- Verified with 8 tests in `tests_api/test_auth_audit.py` (all 23 tests in `tests_api/` pass).

### Prompt 3: React + TypeScript + Tailwind CSS Frontend (`frontend/`)
- Scaffolded modern React 18 SPA with TypeScript and Vite.
- Implemented Tailwind CSS styling with responsive emergency command center theme (slate, blue, emerald, amber, rose).
- Created reusable components: `ProvenanceBadge`, `KPICard`, `Navbar`, `DistrictMap` (Leaflet GeoJSON choropleth), `LoadingSpinner`, `ErrorAlert`.
- Created pages: `LoginPage`, `OverviewPage`, `SimulatorPage`, `AllocationPage`, `BacktestPage`, `GovernancePage`, `LimitationsPage`.
- Configured client-side routing, JWT session context, and full type safety against backend schemas.
- Verified with Vitest suite (`npm test`, 5/5 tests passing) and production build (`npm run build`).

### Prompt 4: DevOps, Docker, CI & Academic Documentation
- Created multi-stage production Dockerfiles:
  - `deploy/Dockerfile.api`: Python 3.13-slim, multi-stage builder, non-root `appuser`, healthcheck probe.
  - `deploy/Dockerfile.frontend`: Node 20-alpine builder + Nginx-alpine runtime, healthcheck probe.
  - `deploy/nginx.conf`: Gzip compression, SPA client-side routing, reverse proxying `/api/` and `/docs` to FastAPI container.
  - `docker-compose.yml`: Multi-container orchestration with healthy dependency chains and volume bindings.
  - `.dockerignore`: Lean image context ignoring local virtual environments and caches.
- Modernized root `Makefile` with cross-platform targets (`dev-api`, `dev-frontend`, `test`, `test-core`, `test-api`, `test-frontend`, `build`, `up`, `down`).
- Modernized `.github/workflows/ci.yml`: Parallel backend testing, frontend testing, and Docker build verification.
- Authored comprehensive documentation:
  - `docs/API.md`: Complete REST reference table, payloads, response schemas, and RBAC roles.
  - `docs/DEMO_SCRIPT_FULLSTACK.md`: 5-minute structured live presentation script with talking points.
  - `docs/VIVA_QA.md`: 28 comprehensive viva voce and technical review questions.
  - `README.md`: System architecture diagram, quickstart guides, and scientific disclosures.

---

## 4. Test Verification Summary

| Test Suite | Location | Test Count | Status | Notes |
|---|---|---|---|---|
| **Core Analytical Tests** | `tests/test_core.py` | 25 | **PASS** | Original analytical constraints, CQR coverage, MIP solver |
| **API & Service Tests** | `tests_api/test_api_endpoints.py` | 14 | **PASS** | REST endpoints, schemas, population capping, error handling |
| **Auth & Ledger Tests** | `tests_api/test_auth_audit.py` | 9 | **PASS** | JWT RBAC, bcrypt passwords, SHA-256 chaining, HTTP 409 safety block |
| **Frontend Component Tests**| `frontend/src/test/*.test.tsx` | 5 | **PASS** | ProvenanceBadge, SimulatorValidation, GovernancePage |
| **Total Test Count** | | **53** | **100% PASS** | Zero failures |
