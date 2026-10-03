# Data Quality and Preprocessing Report

## Executive Summary
This report documents the end-to-end data cleaning, verification, and transformation process for the **Disaster Healthcare Demand Prediction and Resource Allocation** framework.

- **Data Provenance**:
  - **Real Disaster Data**: EM-DAT India historical catalogue (810 records spanning 1980–2024).
  - **Climatological Data**: Daily weather history transformed into regional monthly climatologies (mean and 90th percentile).
  - **Healthcare & Shortage Data**: Semi-synthetic simulated datasets generated from epidemiological disaster response assumptions across 10 Maharashtra administrative zones.

---

## 1. Real Disaster Events (`disaster_events.csv`)
- **Initial Row Count**: 810
- **Exact Duplicates Removed**: 0
- **Likely Cross-Source Duplicates Flagged**: 0
  - *Rule*: Same disaster type, within 3 calendar days, and Haversine distance < 200 km across differing data sources. Flagged via `is_likely_duplicate` without destructive merge.
- **Geographic Attribution**:
  - India: 810 records
- **Target Missingness & Non-Imputation Policy**:
  - `affected` missing: 298 / 810 (36.8%)
  - `injuries` missing: 674 / 810 (83.2%)
  - `deaths` missing: 64 / 810 (7.9%)
  - **Strict Policy**: In compliance with clinical validation standards, target columns (`affected`, `injuries`, `deaths`) are **NEVER imputed**. Records lacking targets are dropped from training subsets rather than synthetically filled.
  - Rows with non-null `affected`: **512** (meets >200 threshold for real-world impact modeling).
- **Transformations**:
  - Logarithmic transform: `log1p(target)` applied to stabilize high-variance, heavy-tailed casualties.
  - Wind speed: Standardized knots to km/h ($1\text{ knot} = 1.852\text{ km/h}$) for marine storm catalogues.

---

## 2. Weather & Climatology (`weather_monthly_climatology.csv`)
- **Underlying Daily Records Processed**: 91,320
- **Regions Modeled**: 10
- **Climatology Aggregation Level**: Region $\times$ Month (12 months $\times$ 10 regions = 120 records).
- **Extracted Indicators**:
  - Rainfall: Mean precipitation and 90th percentile peak rainfall (`precip_mean`, `precip_p90`).
  - Temperature: Max daily temperature mean/p90 and min daily temperature mean.
  - Wind Speed: Mean and 90th percentile wind speed.
- **Identified Limitations**:
  - Disaster events are linked to regional weather via `(region, month)` climatological profiles rather than exact hour-of-event telemetry due to historical observation sparsity in regional stations.

---

## 3. Semi-Synthetic Demand and Shortage Tables
- **Regions Table**: 10 administrative nodes. Latitudes (16.7°–21.15°N), Longitudes (72.88°–79.09°E). All populations and hospital beds strictly positive.
- **Region Distances**: 10$\times$10 symmetric matrix verified with zero diagonal entries.
- **Scenarios Table**: 400 disaster scenarios generated across 3 hazards:
  - flood: 194
  - cyclone: 107
  - earthquake: 99
- **Daily Demand Table**: 280,000 rows covering 14-day horizons across 5 essential medicines:
  - antibiotics, ors, iv_fluids, analgesics, blood_units
- **Shortage Dataset**:
  - Total records: 20,000
  - `coverage_ratio` clipping: Capped at **99.0** (handling division-by-zero when baseline demand is minimal).
  - Risk Level Distribution:
    - Low: 13199 (66.0%)
    - High: 3563 (17.8%)
    - Medium: 3238 (16.2%)

---

## 4. Pipeline Purity & Integrity Guarantees
- No data leakage between simulation runs.
- Transformers and scalers are restricted strictly to training folds.
- Target columns (`shortage_qty`, `coverage_ratio`, `demand_7d`) are completely isolated from feature sets.
