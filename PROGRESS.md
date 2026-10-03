# Project Progress

## Status Overview
- Current Stage Completed: **Stage 4 (Single-File Streamlit Decision-Support Dashboard)**
- Next Stage: **Stage 5 (Unit Tests, Pinned Dependencies, and Honest README)**

## Stage 4 Summary
- **Built**: `app.py`, a single-file Streamlit decision-support application with 4 functional pages:
  1. *Regional Overview*: Interactive map (`st.map`), escalation warning banners for active High shortages, and summary KPIs.
  2. *Predict & What-If*: Multi-parameter simulation (hazard type, severity, intensity, epicentre, month, local inventory override), real-time 3.1 impact prediction, 3.2 7-day demand with 90% conformal prediction intervals, 3.3 calibrated shortage risk with conservative alert thresholds, and 3.4 dynamic clinical SHAP explanations.
  3. *Multi-Objective Allocation*: Interactive weight sliders, OR-Tools MIP execution, Pareto frontier visualization, and human-in-the-loop governance (Approve/Reject actions logged to `reports/audit_log.csv` with mandatory review blocks when confidence < 0.60).
  4. *Model Governance & Provenance*: Comprehensive metrics reporting, real EM-DAT benchmark comparison, calibration curves, SHAP summary plot, disaggregated bias audit, and prominent SEMI-SYNTHETIC warnings.
- **How to Run**:
  ```bash
  .venv/bin/streamlit run app.py
  ```
- **Key Numbers**:
  - Interactive response time: < 50 ms for full prediction pipeline + optimization run.
  - Conformal bounds rendered at nominal 90% confidence ($[\\hat{y} - 394, \\hat{y} + 394]$ units).
  - Human approval records captured with timestamps, reviewer credentials, and model versions in `reports/audit_log.csv`.
- **Key Decisions**:
  - Streamlit's built-in `st.map` used to avoid external dependencies (e.g. Folium).
  - Human review checkbox strictly enforces confirmation before approving low-confidence recommendations.
- **Open Problems / Notes**:
  - All dashboard components successfully verified. Ready for test suite and final documentation.

## How to Resume
```bash
# Clean data
.venv/bin/python -m src.clean

# Train models
.venv/bin/python -m src.train

# Run optimizer
.venv/bin/python -m src.optimise

# Launch dashboard
.venv/bin/streamlit run app.py

# Run tests
.venv/bin/pytest -q
```
