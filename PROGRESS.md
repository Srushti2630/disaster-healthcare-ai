# Project Progress

## Status Overview
- Current Stage Completed: **Stage 1 (Data Cleaning & Climatology)**
- Next Stage: **Stage 2 (Models, Uncertainty, SHAP, and Bias Evaluation)**

## Stage 1 Summary
- **Built**: `src/clean.py`, producing cleaned and validated tables in `data/processed/clean/` and `reports/data_quality.md`.
- **Key Numbers**:
  - EM-DAT disaster events: 810 records (512 non-null `affected`, suitable for training Module 3.1 real-impact models; 0 exact duplicates; knots converted to km/h).
  - Weather climatology: 91,320 daily weather observations converted to 120 regional monthly climatology profiles across 10 regions.
  - Semi-synthetic data: 400 scenarios, 20,000 shortage rows (risk levels: 66.0% Low, 16.2% Medium, 17.8% High), `coverage_ratio` strictly capped at 99.0.
- **Key Decisions**:
  - Targets (`affected`, `injuries`, `deaths`) are strictly not imputed; missing targets are excluded from training subsets.
  - Climatology joined on `(region, month)` to honor realistic station availability.
- **Open Problems / Notes**:
  - Real disaster events have sparse injury reports (136 non-null), but 512 affected records (>200 threshold). Module 3.1 will train on real EM-DAT affected population and fall back to synthetic scenarios for multi-casualty injury/illness breakdowns.

## How to Resume
```bash
# Run data cleaning
.venv/bin/python -m src.clean

# Run tests (when created)
.venv/bin/pytest -q
```
