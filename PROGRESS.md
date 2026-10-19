# Project Progress & Implementation Record

> **Verified State**: October 2026  
> **Status**: Full-Stack production-style prototype Complete (55 Python Tests + 5 Frontend Tests Passing)

---

## 1. What is Real, Estimated, Assumed

| Item | Tag | Notes |
|---|---|---|
| **EM-DAT Disaster Events** (810 total; 512 with targets; 136 injured) | `REAL` | Raw targets never imputed. Historical events spanning 1900–2026 (`data/processed/emdat_events.csv`). |
| **District Polygons** (35 districts¹, median 899 vertices) | `REAL` | Real boundaries in `data/raw/boundaries/`. Legacy 5-vertex rectangles archived. |
| **District Population** (Raw WorldPop zonal sum) | `REAL` | Total 131,936,179 vs ~124.5M official projection (5.97% gap documented as sanity check). Extracted at 0.00083333° pixel scale (3 arc-seconds / ~100m, EPSG:4326). |
| **Hospital Directory** (4,767 Maharashtra facilities) | `REAL` | Sourced from National Health Portal India. Bed counts valid for ~0.67% of rows, so used only for spatial weighting. |
| **District Hospital & ICU Beds** | `ESTIMATED` | Sourced from state ICU bed audit (11,587 ICU beds; provided dataset; original publisher not stated) and analyst-specified ESTIMATED total of 144,983 state hospital beds (`api/services.py`) weighted by facility counts. |
| **Medicine Consumption Rates** | `ASSUMED` | WHO IEHK 2017 & Sphere Project standards (`config/demand_params.yaml`). |
| **Road Distances** | `ASSUMED` | Haversine distance $\times$ 1.3 circuity factor over 35 centroids. |
| **Logistics Transport Cost** | `ASSUMED` | Standardized unitless **Cost Index** ($\text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$). Never currency. |
| **Weather Features** | `NOT USED` | Excluded from impact training to prevent noise injection. Open-Meteo API used only for live What-If scenario queries. |

---

## 2. Core Analytical Pipeline (Phase 1 to Phase 4)

- **Phase 1 (Data Layer)**: Real Maharashtra district boundaries, raw zonal population extraction at 0.00083333° resolution, facility classification, non-imputed EM-DAT processing (1900–2026).
- **Phase 2 (Impact Model)**:
  - Time-split evaluation (Train $\le 2012$, Val $2013-2018$, Test $2019+$; $N=363 / 71 / 78$).
  - Ridge regression achieved MAE 2.8812 (log-scale), $R^2 = 0.2780$ ([0.0787, 0.4331]), Spearman $\rho = 0.5199$ ([0.3657, 0.6472]).
  - Conformalized Quantile Regression (CQR 90%) achieves 94.9% empirical test coverage (conservative intervals with median 6.25 order-of-magnitude log width).
  - Historical Leave-One-Event-Out backtest by `DisNo.` across 5 benchmark disasters (`2005-0409-IND`, `2005-0541-IND`, `2001-0033-IND`, `1993-0074-IND`, `2019-0331-IND`). Actual/predicted casualty ratios range from 7.7x to 1024.6x (median 68.8x).
- **Phase 3 (Demand Engine & ML Surrogate)**:
  - WHO IEHK / Sphere 2,000-draw Monte-Carlo engine under single event sampling ($W_d = \text{pop}_d \times \exp(-D_d / \text{decay\_km})$ spatial decay).
  - Simulated casualties strictly capped at resident district population: $\min(\text{affected}, \text{population})$.
  - Surrogate Random Forest classifier trained on 500 stratified scenarios split BY SCENARIO ID across balanced risk regimes (Low, Medium, High each $\ge 15\%$ of rows). Evaluates held-out scenario generalization fidelity: balanced accuracy, macro-F1, per-class precision/recall/F1, and multiclass ECE with per-class reliability curves, benchmarked against a majority-class baseline. (Measures fidelity to the simulator, not to unobserved real-world shortages).
- **Phase 4 (Operations Research Solver & Stratified Benchmarks)**:
  - Google OR-Tools SCIP MIP solver over 35 district nodes and 5 medicine classes under 5 safety constraints.
  - Stratified benchmark evaluation across 36 scenarios (12 per stratum: Low $10^3–10^4$, Moderate $10^4–10^6$, Severe $10^6+$ empirical EM-DAT affected quantiles $\times$ stock multipliers 0.25, 0.50, 1.0):
    - **Overall (36 Scenarios)**: OR-Tools SCIP achieves lowest mean unmet demand (2.09% of total demand vs 5.32% No Redistribution, 5.25% Proportional, 3.45% Greedy Nearest, and 2.25% Greedy Largest Surplus), route distance (2,451.7 km), highest minimum regional coverage (0.812), zero rule violations, and lowest Cost Index among active redistribution heuristics (3.41B Cost Index units vs 5.08B Greedy Nearest and 6.54B Greedy Largest Surplus). *(No Redistribution has 0 cost).*
    - **Exact Paired Wilcoxon Signed-Rank Tests (Non-Zero Pairs $n=5$, Holm Step-Down Correction)**: vs No Redistribution $W=0.0, p_{\text{adj}}=0.0431$; vs Proportional $W=0.0, p_{\text{adj}}=0.0431$; vs Greedy Nearest $W=0.0, p_{\text{adj}}=0.0431$; vs Greedy Largest Surplus $W=0.0, p_{\text{adj}}=0.0431$ (all rank-biserial $r = 1.000$).
    - **Statistical Indistinguishability**: In mild and moderate scenarios where shortages are minor, OR-Tools SCIP and Greedy Largest Surplus are statistically indistinguishable ($d_i = 0$ in $>80\%$ of unstratified draws); significant separation appears primarily under severe casualty strata with depleted inventories.
    - **Active Shortage Scenarios ($N=5$, No Redistribution Unmet > 0)**: OR-Tools SCIP mean unmet demand 8.36% (vs 21.27% No Redistribution, 20.99% Proportional, 13.81% Greedy Nearest, 9.02% Greedy Largest Surplus); Cost Index 13.63B (vs 20.33B Greedy Nearest, 26.15B Greedy Largest Surplus).
- **Phase 5 (Audit & Tornado Sensitivity Analysis)**:
  - Rerun on new engine with spatial decay (75 km / 150 km baseline / 300 km), consumption rates ($\pm 25\%$), and stock capacity ($\pm 25\%$), saved to `reports/sensitivity_analysis.csv` and `reports/sensitivity_tornado.png`.
- **Core Tests**: All 31 unit tests in `tests/test_core.py` pass cleanly.

---

## 3. Full-Stack production-style prototype (Prompts 1 to 4)

### Prompt 1: FastAPI REST Backend (`api/`)
- Created FastAPI service structure in `api/`: `config.py`, `logging_utils.py`, `middleware.py` (Request-ID and latency headers), `schemas.py` (Pydantic v2), `lifespan.py`, `services.py`, `routes.py`, `main.py`.
- Exposed endpoints: `/health`, `/api/districts`, `/api/predict-impact`, `/api/simulate`, `/api/allocate`, `/api/backtest`.
- Enforced scientific framing, population capping, and Cost Index reporting.
- Verified with unit and integration tests in `tests_api/test_api_endpoints.py`.

### Prompt 2: Auth, Database & Tamper-Evident Ledger (`api/routes_auth.py`, `api/audit_ledger.py`)
- Configured SQLAlchemy 2.0 SQLite database in `api/database.py` with automatic schema creation and user seeding.
- Defined relational models in `api/models.py`: `User`, `SimulationRecord`, `AuditEvent`.
- Implemented native `bcrypt` password hashing and JWT `HS256` token handling in `api/auth.py`.
- Implemented sliding-window rate limiters (20 req/min for auth, 10 req/min for compute-heavy MIP endpoints).
- Implemented SHA-256 cryptographic hash-chained audit ledger with genesis block linking and verification.
- Enforced automated safety guard: blocks `APPROVE` actions with **HTTP 409 Conflict** if prediction confidence is $< 0.60$.
- Verified with tests in `tests_api/test_auth_audit.py` (all 24 tests in `tests_api/` pass).

### Prompt 3: React + TypeScript + Tailwind CSS Frontend (`frontend/`)
- Scaffolded React 18 SPA with TypeScript and Vite.
- Implemented Tailwind CSS styling with responsive emergency command center theme.
- Created reusable components: `ProvenanceBadge`, `KPICard`, `Navbar`, `DistrictMap` (Leaflet GeoJSON choropleth), `LoadingSpinner`, `ErrorAlert`.
- Created pages: `LoginPage`, `OverviewPage`, `SimulatorPage`, `AllocationPage`, `BacktestPage`, `GovernancePage`, `LimitationsPage`.
- Configured client-side routing, JWT session context, and type safety against backend schemas.
- Verified with Vitest suite (`npm test`, 5/5 tests passing) and production build (`npm run build`).

### Prompt 4: DevOps, Docker, CI & Academic Documentation
- Created multi-stage Dockerfiles:
  - `deploy/Dockerfile.api`: Python 3.13-slim, multi-stage builder, non-root `appuser`, healthcheck probe.
  - `deploy/Dockerfile.frontend`: Node 20-alpine builder + Nginx-alpine runtime, healthcheck probe.
  - `deploy/nginx.conf`: Gzip compression, SPA client-side routing, reverse proxying `/api/` and `/docs` to FastAPI container.
  - `docker-compose.yml`: Multi-container orchestration with healthy dependency chains and volume bindings.
  - `.dockerignore`: Lean image context ignoring local virtual environments and caches.
- Modernized root `Makefile` with cross-platform targets (`dev-api`, `dev-frontend`, `test`, `test-core`, `test-api`, `test-frontend`, `build`, `up`, `down`).
- Modernized `.github/workflows/ci.yml`: Parallel backend testing, frontend testing, and Docker build verification.
- Authored documentation: `docs/API.md`, `docs/DEMO_SCRIPT_FULLSTACK.md`, `docs/VIVA_QA.md`, `README.md`.

---

## 4. Contributors & Task Breakdown

- **[YOUR NAME]**: ML pipeline, data layer, optimiser, validation
- **[TEAMMATE NAME]**: API, authentication, React frontend, Docker

---

## 5. Limitations & Scientific Disclosures

1. **Spatial Aggregation**: Network optimization operates across 35 district centroid nodes rather than individual healthcare facilities or sub-district wards.
2. **Road Circuity Multiplier**: Inter-district transport distances use a Haversine $\times 1.3$ circuity approximation (`ASSUMED`), which does not capture real-world traffic jams, bridge collapses, or flood-induced road closures.
3. **Surrogate Scope**: The Random Forest surrogate classifier evaluates fidelity relative to the Monte-Carlo simulation engine, NOT against empirical hospital stockouts (which are unobserved in EM-DAT).
4. **Tail Event Underestimation**: Conformal quantile regression bounds reflect high historical intrinsic variance; point estimates remain prone to severe underestimation during extreme multi-state disasters.
5. **Bed Anchor Proxy**: District hospital bed capacities are estimated by scaling analyst-specified ESTIMATED total of 144,983 state hospital beds by facility counts, rather than live hospital ERP inventory tracking.

---

## 6. Before vs. After Implementation Record

| Dimension | Legacy Synthetic Prototype | Current Verified Framework |
|---|---|---|
| **Data Layer** | Synthetic random data arrays | Real CRED EM-DAT (1900–2026), WorldPop 2020 1km grid, and National Health Portal |
| **Model Performance** | Synthetic $R^2 \approx 0.88–0.99$ (circular generator recovery) | Real Ridge $R^2 = 0.2780$, MAE $= 2.8812$ (log-scale), Spearman $\rho = 0.5199$ on test set ($N=78$) |
| **Uncertainty Bounds** | Narrow synthetic point predictions | CQR 90% conformal intervals (94.9% test coverage) with documented 6.25 order-of-magnitude log width |
| **Resource Allocation** | Claimed OR-Tools was "lowest cost overall" | Verified OR-Tools SCIP achieves lowest unmet demand (2.09% mean) and lowest cost index among active greedy heuristics (3.41B Cost Index units) |
| **Surrogate Validation** | Claimed real shortage prediction | Explicitly badged as fidelity to Monte-Carlo surge simulator under scenario-based splitting across balanced risk regimes ($\ge 15\%$ per class), evaluated on balanced accuracy, macro-F1, multiclass ECE with reliability curves, and majority baseline |

---

## 7. Test Verification Summary

| Test Suite | Location | Test Count | Status | Notes |
|---|---|---|---|---|
| **Core Analytical Tests** | `tests/test_core.py` | 31 | **PASS** | Original analytical constraints, MC allocation/capping, CQR coverage, MIP solver, stratified sampler, class balance, Holm correction |
| **API & Auth Tests** | `tests_api/` | 28 | **PASS** | REST endpoints, schemas, RBAC, SHA-256 ledger, security validation, facilities count > 4000, /api/explain (global & local), /api/stock role enforcement & simulation override |
| **Frontend Component Tests**| `frontend/src/test/*.test.tsx` | 7 | **PASS** | ProvenanceBadge, SimulatorValidation, GovernancePage, PredictionExplanationPanel (SHAP top 6 & plain English), StockEditingTable (custom overrides & reset) |
| **Total Test Count** | | **66** | **100% PASS** | Zero failures |

---

## 8. Recent Operational Enhancements

1. **Facility Mapping & Terminology Integrity**: Resolved Overview facility count mapping to properly reflect > 4,000 public facilities; updated citations to "WorldPop 2020, about 100 m (3 arc-second)" and "State ICU audit (provided dataset; original publisher not stated)".
2. **Exact Ridge Model Interpretability (SHAP)**: Implemented `GET /api/explain/global` and `POST /api/explain` serving exact linear feature decomposition ($\beta_j \cdot z_j$) and summary narrative alongside XGBoost Tree-SHAP comparison. Integrated into the Simulator UI via `PredictionExplanationPanel`.
3. **Editable Stock Inventory (`USER-PROVIDED`)**: Added persistent per-user custom inventory endpoints (`/api/stock`) enforcing officer/coordinator/admin roles, propagated to `/api/simulate` and `/api/allocate` with provenance badging, supported by `StockEditingTable`.
4. **Simulator UX & Stratified Allocation**: Integrated interactive planning level selector (P50/P75/P90), risk threshold legend, interval-width caveats, stratified allocation reporting, and Pareto frontier curve rendering.
5. **Comprehensive Test Suite**: Added 4 backend API tests in `tests_api/test_api_endpoints.py` and unit tests in `frontend/src/test/ExplanationAndStock.test.tsx`.

---

¹ *Footnote on District Count*: Maharashtra officially comprises 36 administrative districts. In this analytical framework, Mumbai City and Mumbai Suburban are consolidated into a single "Mumbai" spatial node, yielding 35 analytical district nodes.

