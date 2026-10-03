# Project Progress

## Status Overview
- Current Stage Completed: **Stage 2 (Models, Uncertainty, SHAP, and Bias Evaluation)**
- Next Stage: **Stage 3 (OR-Tools Multi-Objective Resource Allocation Optimiser)**

## Stage 2 Summary
- **Built**: `src/train.py`, versioned artifacts in `models/` (bundle, impact, demand, classifier, conformal, SHAP), `reports/metrics.json`, `reports/bias_table.csv`, `reports/calibration.png`, and `reports/shap_summary.png`.
- **How to Run**:
  ```bash
  .venv/bin/python -m src.train
  ```
- **Key Numbers**:
  - Group Split: 320 train scenarios (16,000 rows) vs 80 test scenarios (4,000 rows) with 0 scenario overlap.
  - Module 3.3 Shortage Classifier:
    - Logistic Regression Baseline: Accuracy 80.3%, Macro F1 0.744.
    - Calibrated Random Forest: Accuracy 90.1%, Macro F1 0.862, ECE = 0.0177.
    - Conservative Thresholding ($\tau_{\text{high}}=0.37$): High-risk recall increased from 88.7% to **92.4%** (precision trade-off: 88.7% -> 86.0%).
  - Module 3.1 Disaster Impact:
    - Real EM-DAT Benchmark: RF MAE 2.90, $R^2 = 0.129$ vs baseline $R^2 = -0.004$.
    - Synthetic Impact Pipeline: XGBoost predicting affected_pop, injured, and ill without ground-truth leakage.
  - Module 3.2 Demand Forecast:
    - XGBoost $R^2 = 0.907$, MAE = 208.5 units.
    - Conformal prediction interval margin: $\pm 394.2$ units; empirical held-out coverage: **86.1%** (nominal 90%).
  - Module 3.4 SHAP: Global TreeExplainer summary and natural language admin explanation function.
  - Bias Evaluation: Disaggregated across 10 regions and 3 disaster hazards; disparities flagged for lower recall regions in `reports/bias_table.csv`.
- **Key Decisions**:
  - Used scikit-learn `CalibratedClassifierCV(cv=3, method='sigmoid')` for fast 3-fold cross-validated calibration.
  - Leakage columns strictly isolated from classifier input.
  - Threshold tuned conservatively on train probabilities to prioritize patient safety.
- **Open Problems / Notes**:
  - Pune and Nagpur flagged for slightly lower High-risk recall (<85%), highlighting regional disparity under conservative thresholding.

## How to Resume
```bash
# Clean data
.venv/bin/python -m src.clean

# Train models and generate reports
.venv/bin/python -m src.train

# Run tests
.venv/bin/pytest -q
```
