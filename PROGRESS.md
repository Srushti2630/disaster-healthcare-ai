# Project Progress

## Status Overview
- Current Stage Completed: **Stage 3 (OR-Tools Multi-Objective Resource Allocation Optimiser)**
- Next Stage: **Stage 4 (Single-File Streamlit Decision-Support Dashboard)**

## Stage 3 Summary
- **Built**: `src/optimise.py`, `reports/sample_allocation_plan.csv`, `reports/pareto_sweep.png`, and `reports/allocation_summary.json`.
- **How to Run**:
  ```bash
  .venv/bin/python -m src.optimise
  ```
- **Key Numbers**:
  - Evaluated on acute disaster scenario (Scenario #4: Severity 5 Earthquake).
  - Solve time: **33.6 ms** to global optimality via Google OR-Tools SCIP MIP solver.
  - Recommended transfers: 24 routes across 10 regions, moving **584,608 medicine units**.
  - Unmet demand reduced from 1,920,883 to 1,336,397 units (**30.4% reduction**).
  - Fairness improved: Minimum regional coverage lifted from 16.2% to 22.0% while strictly enforcing source safety reserves.
  - Pareto sweep completed across 6 operational weight configurations (Demand Priority, High Urgency, Balanced Standard, Fair Distribution, Cost-Conscious, Maximum Fairness).
- **Key Decisions**:
  - Source regions are constrained to keep at least 60% of their own predicted demand as emergency safety reserve.
  - Priority tagged as CRITICAL (High risk destination), HIGH (Medium risk), or STANDARD (Low risk), paired with calibrated confidence scores.
- **Open Problems / Notes**:
  - In extreme severity disasters, regional supply limits cap total demand satisfaction; this demonstrates why safety reserve policies are critical to prevent source region depletion.

## How to Resume
```bash
# Clean data
.venv/bin/python -m src.clean

# Train models
.venv/bin/python -m src.train

# Run optimizer
.venv/bin/python -m src.optimise

# Run tests
.venv/bin/pytest -q
```
