# Project Progress

## Status Overview
- Current Stage Completed: **Phase 0 (Audit & Hygiene, Config, Makefile, Dependency Trimming, Data Governance Setup)**
- Overall Status: **IN PROGRESS (Phase 0 Complete, Phase 1 Real Data Layer Next)**

## Phase Summaries
### Phase 0: Audit & Hygiene
- **Baseline Preserved**: Archived old synthetic metrics to `reports/baseline_synthetic_metrics.json`.
- **Dependencies Cleaned**: Trimmed `requirements.txt` to verified direct dependencies.
- **Config & Automation**: Created state-agnostic `config.yaml`, `run_all.py`, and `Makefile`.
- **Repo Hygiene & Data Docs**: Updated `.gitignore` to track data structures while ignoring large raw binaries (>50 MB). Created `data/README.md` and `docs/DATA_NEEDED.md`.

### Stage 1: Data Cleaning & Climatology
- **Built**: `src/clean.py`, producing `data/processed/clean/` and `reports/data_quality.md`.
- **Outputs**: Cleaned EM-DAT disaster catalogue (810 events, 512 non-null casualties), 120 regional monthly climatology profiles, 400 validated synthetic disaster scenarios.

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
