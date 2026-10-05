# Disaster Healthcare AI: Demand Prediction & Resource Allocation

> **An Explainable and Uncertainty-Aware Full-Stack AI Framework for Disaster Healthcare Demand Prediction and Multi-Objective Resource Allocation**  
> *Maharashtra 35 Districts*¹ | React 18 & TypeScript | FastAPI & Python 3.13 | Google OR-Tools SCIP | Conformal Quantile Regression | SHA-256 Audit Ledger | Docker

---

## 1. System Architecture

```mermaid
flowchart TD
    subgraph Client [Frontend Layer - React 18 + TypeScript + Vite]
        UI1["Geospatial Overview (Leaflet GeoJSON Choropleth)"]
        UI2["Surge Simulator (Population Capped Monte-Carlo)"]
        UI3["MIP Resource Allocation (OR-Tools SCIP Plan)"]
        UI4["Governance Ledger (SHA-256 Cryptographic Chain)"]
        UI5["Historical Backtest & Scientific Limitations"]
    end

    subgraph Gateway [Reverse Proxy & Web Gateway]
        NGINX["Nginx Web Server / Reverse Proxy (:80)"]
    end

    subgraph API [Backend Layer - FastAPI + Python 3.13]
        MW["Middleware (Request-ID, Latency Timer, CORS)"]
        AUTH["Auth & RBAC (JWT HS256, bcrypt, Rate Limiter)"]
        ROUTES["REST Endpoints (/api/predict-impact, /simulate, /allocate, /audit)"]
    end

    subgraph Engine [Analytical Core & Operational Research]
        IMPACT["Ridge + Conformalized Quantile Regression (CQR 90%)"]
        MC["Monte-Carlo Surge Engine (WHO IEHK / Sphere 2,000 Draws)"]
        SURROGATE["RF Surrogate Classifier (500 Scenarios, 91.3% Simulator Fidelity)"]
        ORTOOLS["Google OR-Tools SCIP Solver (35 Districts, 5 Constraints)"]
    end

    subgraph Storage [Data & Persistence Layer]
        SQLITE["SQLite Database (Users, Simulations, Audit Events)"]
        PROV["Data Registry (data/provenance.yaml - REAL / ESTIMATED / ASSUMED)"]
        MODELS["Serialized Model Weights & Calibration Bounds (models/)"]
    end

    UI1 & UI2 & UI3 & UI4 & UI5 --> NGINX
    NGINX --> MW
    MW --> AUTH
    AUTH --> ROUTES
    ROUTES --> IMPACT & MC & SURROGATE & ORTOOLS
    ROUTES --> SQLITE
    IMPACT & MC & ORTOOLS --> PROV
    IMPACT --> MODELS
```

---

## 2. Executive Overview

Disaster healthcare logistics during extreme natural hazards face severe spatial imbalances, sudden demand spikes, and opaque decision-making. This project delivers an **end-to-end production-style prototype and decision-support system** for disaster healthcare planning across Maharashtra's administrative districts.

### Key Capabilities
- **Strict Data Provenance**: Every metric in the UI and API is explicitly badged as `REAL`, `ESTIMATED`, or `ASSUMED` according to `data/provenance.yaml`.
- **Honest Statistical Bounds**: Impact prediction utilizes Conformalized Quantile Regression (CQR 90%) on CRED EM-DAT India historical events (1900–2026). Discloses that while the model ranks events reasonably well (Spearman $\rho \approx 0.52$), extreme tail events can be underestimated by orders of magnitude (historical backtest actual/predicted ratios range from 7.7x to 1024.6x with a median ratio of 68.8x; CQR interval widths span 5.58 to 6.46 orders of magnitude with a median of 6.25 orders of magnitude).
- **Physical Population Invariants**: Simulated casualties are capped at resident district population ($\min(\text{affected}, \text{population})$), preventing unrealistic synthetic spikes.
- **Multi-Objective Network Optimization**: Solves inter-district medical transfers via Google OR-Tools SCIP Mixed-Integer Programming under 5 hard safety constraints (60% source reserve, high-risk export bans, 150 km blood transit limits, integer packs, non-negativity).
- **Surrogate Classifier Validation**: The Random Forest surrogate classifier measures **fidelity to the Monte-Carlo surge simulator** (91.28% fidelity accuracy across 500 scenario-split scenarios), NOT accuracy against unobserved real-world hospital shortages.
- **Cryptographic Audit Governance**: Human-in-the-loop review actions are sealed in a SHA-256 hash-chained ledger. An automated safety interlock blocks approval if scenario prediction confidence is below 0.60 (**HTTP 409 Conflict**).

---

## 3. Data Provenance & Real Foundations

| Asset / Dataset | Provenance Tag | Source / Methodology | Records & Notes |
|---|---|---|---|
| **EM-DAT Disaster Catalogue** | `REAL` | CRED EM-DAT International Disaster Database ([public.emdat.be](https://public.emdat.be/)) | 810 India disaster events spanning 1900–2026 (512 with targets); casualty figures never imputed. |
| **WorldPop Population Raster** | `REAL` | WorldPop 2020 1km / 3 arc-sec Constrained Grid ([worldpop.org](https://www.worldpop.org/)) | Raw raster zonal sum at 0.00083333° resolution (EPSG:4326): 131,936,179 vs 124.5M projection (5.97% gap documented as sanity check). |
| **National Hospital Directory** | `REAL` | Open Government Data Portal India ([data.gov.in](https://data.gov.in/)) | 4,767 Maharashtra health facilities classified by public/private mix. |
| **State ICU Beds Audit** | `ASSUMED` citation | National Health Profile / Kapoor et al. (2020) (*citation unverified from local raw files*) | 11,587 total state ICU beds (2,572 public / 9,015 private). |
| **District Hospital Bed Capacity** | `ESTIMATED` | State Bed Anchor + Facility Count Weighting | Allocated from 144,983 state total hospital bed anchor (`api/services.py`) across 35 districts¹. |
| **Epidemiological Consumption** | `ASSUMED` | WHO IEHK 2017 & Sphere Project Guidelines | Daily consumption rates per patient/injured day (`config/demand_params.yaml`). |
| **Road Transport Circuity** | `ASSUMED` | Haversine Distance $\times$ 1.3 Factor | Terrain circuity multiplier over 35 district centroids. |

> [!IMPORTANT]
> **Logistics Cost Policy**: Transport cost is strictly reported as a unitless **Cost Index** ($\text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$) reflecting physical freight work and route overhead. It is **never** presented as currency (`₹`/`INR`).

---

## 4. Empirical Benchmarks

### A. Impact Prediction Model (Time-Split Test Set $N=78$, 2019+)

| Model | Test MAE (log) | Test $R^2$ (95% CI) | Test Spearman $\rho$ (95% CI) | Order-of-Magnitude Acc ($\le 0.5 \text{ dex}$) |
|---|---|---|---|---|
| **Median Baseline** | 3.5717 | -0.0952 | 0.0000 | 19.2% |
| **Ridge Regression** | **2.8812** | **0.2780** ([0.0787, 0.4331]) | **0.5199** ([0.3657, 0.6472]) | 20.5% |
| **XGBoost Regressor** | 3.0908 | 0.1403 | 0.4454 | 24.4% |
| **Random Forest** | 3.3204 | -0.0174 | 0.3078 | 23.1% |

- **CQR Coverage**: Empirical coverage on held-out test data is **94.9%** for nominal 90% target (conservative intervals).
- **Historical Backtesting**: Leave-One-Event-Out validation by `DisNo.` across benchmark disasters (`2005-0409-IND`, `2005-0541-IND`, `2001-0033-IND`, `1993-0074-IND`, `2019-0331-IND`). Actual/predicted casualty ratios range from 7.7x to 1024.6x (median 68.8x). Log prediction interval widths span 5.58 to 6.46 orders of magnitude (median 6.25 orders of magnitude).

### B. OR-Tools SCIP 20-Scenario Optimization Benchmark

Evaluated across 20 Monte-Carlo demand scenarios under full model uncertainty ($\sigma \approx 3.7186$) through a single shared constraint checker and unified cost function.

#### Table 1: Baseline Comparison (All 20 Monte-Carlo Scenarios)

| Method | Unmet Demand (Median %) | Unmet Demand (P75 %) | Unmet Demand (P90 %) | Unmet Demand (Mean %) | Mean Cost Index | Mean Route-KM | Mean Min Coverage | Mean Violations |
|---|---|---|---|---|---|---|---|---|
| **OR-Tools SCIP** | **0.00%** | **0.03%** | **0.39%** | **2.09%** | 3,406,362,338.27 | **2,451.7 km** | **0.812** | **0.00** |
| **Greedy Largest Surplus** | 0.00% | 0.04% | 1.93% | 2.25% | 6,537,418,272.32 | 3,081.3 km | 0.812 | 0.00 |
| **Greedy Nearest** | 0.00% | 0.68% | 11.14% | 3.45% | 5,082,270,237.46 | 3,132.8 km | 0.812 | 0.00 |
| **Proportional Population** | 0.00% | 3.27% | 15.97% | 5.25% | 17,079,393,521.63 | 20,436.5 km | 0.804 | 0.00 |
| **No Redistribution** | 0.00% | 0.77% | 20.33% | 5.32% | 0.00 | 0.0 km | 0.800 | 0.00 |

*Note: OR-Tools SCIP is NOT the lowest cost method overall (No Redistribution has 0 cost). However, OR-Tools SCIP achieves the lowest unmet demand (2.09% mean) and the lowest Cost Index among active redistribution heuristics (cheaper than Greedy Nearest 5.08B and Greedy Largest Surplus 6.54B).*

#### Wilcoxon Signed-Rank Test Results (Paired Difference vs. OR-Tools SCIP)
- **OR-Tools SCIP vs. No Redistribution**: Wilcoxon $W = 0.0$, $p = 0.043114$ ($p < 0.05$)
- **OR-Tools SCIP vs. Proportional Population**: Wilcoxon $W = 0.0$, $p = 0.043114$ ($p < 0.05$)
- **OR-Tools SCIP vs. Greedy Nearest**: Wilcoxon $W = 0.0$, $p = 0.043114$ ($p < 0.05$)
- **OR-Tools SCIP vs. Greedy Largest Surplus**: Wilcoxon $W = 0.0$, $p = 0.043114$ ($p < 0.05$)

#### Table 2: Restricted Baseline Comparison (Scenarios with Active Shortage: No Redistribution Unmet > 0, $N=5$)

| Method | Unmet Demand (Median %) | Unmet Demand (P75 %) | Unmet Demand (P90 %) | Unmet Demand (Mean %) | Mean Cost Index | Mean Route-KM | Mean Min Coverage | Mean Violations |
|---|---|---|---|---|---|---|---|---|
| **OR-Tools SCIP** | **0.20%** | **2.11%** | **24.35%** | **8.36%** | 13,625,449,353.06 | **9,807.0 km** | **0.247** | **0.00** |
| **Greedy Largest Surplus** | 1.72% | 3.84% | 25.05% | 9.02% | 26,149,673,089.30 | 12,325.4 km | 0.247 | 0.00 |
| **Greedy Nearest** | 11.05% | 11.95% | 28.29% | 13.81% | 20,329,080,949.84 | 12,531.1 km | 0.247 | 0.00 |
| **Proportional Population** | 15.71% | 18.28% | 32.67% | 20.99% | 68,317,574,086.51 | 81,746.2 km | 0.215 | 0.00 |
| **No Redistribution** | 19.61% | 26.83% | 38.62% | 21.27% | 0.00 | 0.0 km | 0.199 | 0.00 |

---

## 5. Quickstart & Installation

### Option A: Local Development (Full-Stack)

#### 1. Backend Setup
```bash
# Activate virtual environment
# Windows: .venv\Scripts\Activate.ps1 | Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-api.txt

# Run analytical pipeline (builds datasets and trains models)
python run_all.py

# Launch FastAPI backend (port 8000)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```
Swagger UI available at `http://localhost:8000/docs`.

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
React web application available at `http://localhost:5173`.

---

### Option B: Docker Compose (production-style prototype)

Deploy both containers (FastAPI + React via Nginx) with a single command:
```bash
# Build and run containers in detached mode
docker compose up --build -d

# Check running status
docker compose ps

# View backend logs
docker compose logs -f api

# Stop containers
docker compose down
```
- Web Application: `http://localhost` (or `http://localhost:5173`)
- REST API / Swagger: `http://localhost:8000/docs`

---

## 6. Testing & Quality Assurance

The codebase includes comprehensive test suites across both backend and frontend layers (100% passing):

```bash
# 1. Run Core Analytical Tests (25 tests: datasets, CQR intervals, SCIP constraints)
pytest tests/test_core.py -v

# 2. Run API, Auth & Cryptographic Audit Tests (23 tests)
pytest tests_api/ -v

# 3. Run Frontend Unit & Component Tests (Vitest)
cd frontend && npm test
```

---

## 7. Security & User Credentials (Environment Seeding)

The application configures authentication secrets and seed users via environment variables defined in `.env` (refer to `.env.example` template):

- **JWT Secret**: Configured via `SECRET_KEY` in `.env` (defaults to development key if unconfigured).
- **Environment Seeding & RBAC Roles**:
  - `admin` role: Full system management, audit chain verification, user creation.
  - `officer` role: Run surge simulations, trigger MIP allocations, submit review decisions.
  - `viewer` role: Read-only inspection of geospatial maps, backtest logs, and governance ledgers.
- User accounts are created via `POST /api/auth/register` (initial account auto-assigned `admin` role; subsequent registrations require `admin` Bearer token authorization).

---

## 8. Contributors

- **[YOUR NAME]**: ML pipeline, data layer, optimiser, validation
- **[TEAMMATE NAME]**: API, authentication, React frontend, Docker

---

## 9. Scientific Limitations

1. **Spatial Aggregation**: Logistics network optimization operates across 35 district centroid nodes rather than individual facility coordinates or sub-district wards.
2. **Road Circuity Multiplier**: Inter-district road distances use a Haversine $\times 1.3$ circuity approximation (`ASSUMED`), which does not capture real-world traffic jams, bridge collapses, or flood-induced road closures.
3. **Surrogate Scope**: The Random Forest surrogate classifier evaluates fidelity relative to the Monte-Carlo simulation engine, NOT against empirical hospital stockouts (which are not reported in public EM-DAT records).
4. **Tail Event Underestimation**: Conformal quantile regression bounds reflect high historical intrinsic variance; point estimates remain prone to severe underestimation during extreme multi-state disasters.
5. **Bed Anchor Proxy**: District hospital bed capacities are estimated by scaling state-level 144,983 hospital bed anchors by facility counts, rather than live hospital ERP inventory tracking.

---

## 10. Before vs. After Framework Evolution

| Dimension | Legacy Synthetic Prototype | Current Verified Framework |
|---|---|---|
| **Data Layer** | Synthetic random data arrays | Real CRED EM-DAT (1900–2026), WorldPop 2020 1km grid, and National Health Portal |
| **Model Performance** | Synthetic $R^2 \approx 0.88–0.99$ (circular generator recovery) | Real Ridge $R^2 = 0.2780$, MAE $= 2.8812$ (log-scale), Spearman $\rho = 0.5199$ on test set ($N=78$) |
| **Uncertainty Bounds** | Narrow synthetic point predictions | CQR 90% conformal intervals (94.9% test coverage) with documented 6.25 order-of-magnitude log width |
| **Resource Allocation** | Claimed OR-Tools was "lowest cost overall" | Verified OR-Tools SCIP achieves lowest unmet demand (37.90% mean) and lowest cost index among active greedy heuristics (25.17B Cost Index units) |
| **Surrogate Validation** | Claimed real shortage prediction | Explicitly badged as 91.28% fidelity to the Monte-Carlo surge simulator under scenario-based splitting |

---

## 11. Documentation Index

- [REST API Reference](docs/API.md): Detailed endpoint definitions, payloads, response codes, and rate limits.
- [5-Minute Full-Stack Viva Demo Script](docs/DEMO_SCRIPT_FULLSTACK.md): Step-by-step viva presentation script with talking points.
- [Comprehensive Viva Q&A Guide](docs/VIVA_QA.md): 28 in-depth questions and answers for viva voce and technical review panels.
- [Project Progress & Audit Trail](PROGRESS.md): Verified implementation timeline and technical audit history.

---

¹ *Footnote on District Count*: Maharashtra officially comprises 36 administrative districts. In this analytical framework, Mumbai City and Mumbai Suburban are consolidated into a single "Mumbai" spatial node, yielding 35 analytical district nodes.
