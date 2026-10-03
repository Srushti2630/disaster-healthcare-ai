# Project Progress

## Status Overview
- Current Stage Completed: **Phase 4 (OR-Tools SCIP Multi-Objective Optimization, Pareto Sweep, 3-Baseline Comparison)**
- Overall Status: **IN PROGRESS (Phase 4 Complete, Phase 5 Dashboard Next)**

## Phase Summaries
### Phase 0: Audit & Hygiene
- **Baseline Preserved**: Archived old synthetic metrics to `reports/baseline_synthetic_metrics.json`.
- **Dependencies Cleaned**: Trimmed `requirements.txt` to verified direct dependencies.
- **Config & Automation**: Created state-agnostic `config.yaml`, `run_all.py`, and `Makefile`.
- **Repo Hygiene & Data Docs**: Updated `.gitignore` to track data structures while ignoring large raw binaries (>50 MB). Created `data/README.md` and `docs/DATA_NEEDED.md`.

### Phase 1: Real Data Layer (`src/data/`)
- **District Boundaries**: Constructed canonical 35 Maharashtra district geometries (`src/data/boundaries.py`).
- **WorldPop Zonal Population (REAL)**: Calculated 1km raster zonal sum population for 35 districts (`data/processed/district_population.csv`, total MH Pop = 124.5M, error < 0.1%).
- **National Hospital Directory (REAL)**: Cleaned 4,767 Maharashtra healthcare facilities (`data/processed/district_facilities.csv` and `cleaned_facilities.csv`), classified public/private breakdown and lat/lon coordinate quality.
- **District Capacity (ESTIMATED)**: Anchored to 11,587 state ICU beds and 145,000 state hospital beds (`data/processed/district_capacity.csv`).
- **EM-DAT Disaster Events (REAL)**: Processed 810 real EM-DAT India disaster events (`data/processed/emdat_events.csv`, 512 with recorded casualty targets) adhering strictly to a **non-imputation policy**.
- **Event-Date Weather (ESTIMATED)**: Extracted 1/3/7-day rolling precipitation, max wind, and temperature extremes for event dates (`data/processed/weather_events.csv`).
- **Governance & Audit**: Created machine-readable `data/provenance.yaml` and `reports/data_quality.md`.

### Phase 2: Real Impact Model & CQR (`src/models/`)
- **Time-Split Evaluation**: Trained on 512 real EM-DAT events using strict time-based splits (Train <= 2012, Val 2013-2018, Test 2019+). Ridge ($R^2 = 0.262$, MAE = 2.900, Spearman $\rho = 0.504$) and XGBoost ($R^2 = 0.155$, MAE = 3.136, Spearman $\rho = 0.442$) beat Median Baseline (MAE = 3.572).
- **Conformalized Quantile Regression (CQR)**: Replaced split conformal with CQR; achieved **91.0% empirical test coverage** for nominal 90% target.
- **SHAP Explainability**: Fitted TreeExplainer on XGBoost impact model; exported global summary plot (`reports/shap_summary.png`) and local feature attribution.
- **Historical Back-Test**: Replayed 4 major real disasters (2005 MH Floods, 2019 Kolhapur Floods, 2001 Bhuj Earthquake, 1993 Latur Earthquake) with 90% CQR prediction intervals (`reports/historical_backtest.csv`).

### Phase 3: Transparent Demand & Shortage Engine (`src/engine/`)
- **Epidemiological Demand Engine**: Implemented WHO IEHK 2017 & Sphere Handbook consumption standards (`config/demand_params.yaml`, tagged `ASSUMED`).
- **Monte-Carlo Uncertainty Propagation**: Executed 2,000 stochastic draws per district $\times$ medicine, generating P10/P50/P90 demand bands and exact shortage probabilities $P(\text{demand} > \text{surge stock})$.
- **Fast ML Surrogate**: Trained Random Forest surrogate classifier (`models/shortage_classifier.joblib`) achieving 100% fidelity accuracy and low ECE (0.0085) for instant dashboard slider interaction.
- **Legacy Cleanup**: Archived `scripts/synthetic_demand.py` to `archive/legacy_synthetic/synthetic_demand.py` with an explicit warning README.

### Phase 4: OR-Tools SCIP Optimization & Benchmarking (`src/optimise.py`)
- **35 District Node Network**: Upgraded MIP solver to 35 Maharashtra district nodes with real coordinates and $1.3\times$ circuity factor road distance matrix.
- **Multi-Objective & Constraints**: Implemented safety reserves, integer pack sizes, perishables max transit distance (blood units $\le 150$ km), medicine criticality weighting, and high-risk export prohibitions.
- **Baseline Benchmarking**: Achieved **99.8% unmet demand reduction** vs No Redistribution baseline, outperforming Proportional Population (69.3%) and Greedy Nearest baselines.
- **Artifacts**: Exported allocation plan (`reports/sample_allocation_plan.csv`) and Pareto curve summary (`reports/allocation_summary.json`).





### Stage 2: Models, Uncertainty & Explainability
- **Built**: `src/train.py`, `models/pipeline_bundle.joblib`, `reports/metrics.json`, `reports/calibration.png`, `reports/shap_summary.png`, and `reports/bias_table.csv`.
- **Results**:
  - Module 3.1 Impact: Real EM-DAT Benchmark ($R^2=0.129$, MAE=2.896) vs Synthetic Impact XGBoost ($R^2 \approx 0.88$).
  - Module 3.2 Demand: XGBoost $R^2=0.907$, Conformal 90% margin $\pm 394.2$ units, empirical test coverage 86.1%.
  - Module 3.3 Shortage Classifier: Logistic Baseline (Acc: 80.3%) vs Calibrated Random Forest (Acc: 90.1%, ECE: 0.0177). Conservative decision rule boosts High-risk recall to **92.4%**.
  - Module 3.4 SHAP: Global TreeExplainer and dynamic plain-English administrative explanation sentences.

### Stage 3: Multi-Objective Resource Allocation
- **Built**: `src/optimise.py`, `reports/sample_allocation_plan.csv`, `reports/pareto_sweep.png`, and `reports/allocation_summary.json`.
- **Results**: Google OR-Tools SCIP solver executed in 33.6 ms, transferring 584,608 units across 24 routes, reducing unmet demand by 30.4% and improving min regional coverage from 16.2% to 22.0% under a 60% source safety reserve.

### Stage 4: Decision-Support Dashboard
- **Built**: `app.py` (single-file Streamlit application) with Regional Overview Map, What-If Simulation, Multi-Objective Allocation with Pareto figures, and Model Governance reporting.
- **Safety**: Human-in-the-loop approval workflow logging to `reports/audit_log.csv` with mandatory review blocks when model confidence < 0.60.

### Stage 5: Unit Tests & Honest Documentation
- **Built**: `tests/test_core.py` (4/4 tests passing in 3.5s), `pytest.ini`, `requirements.txt` (pinned), `.gitignore`, and `README.md` (architecture diagram, real benchmark results, honest ethical/methodological disclosures).

## How to Resume / Run Entire System
```bash
# 1. Clean data and build climatology
.venv/bin/python -m src.clean

# 2. Train ML pipeline and generate reports
.venv/bin/python -m src.train

# 3. Run OR-Tools allocation optimizer and Pareto sweep
.venv/bin/python -m src.optimise

# 4. Run test suite
.venv/bin/pytest -q

# 5. Launch interactive Streamlit decision dashboard
.venv/bin/streamlit run app.py
```
