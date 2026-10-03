# Real Data Layer & Data Quality Report

## 1. Executive Summary
This document records the provenance, schema validations, and data quality metrics for the **Explainable & Uncertainty-Aware Disaster Healthcare AI Framework**. Synthetic data generation has been replaced with real, verifiable public datasets wherever real data exists.

---

## 2. Dataset Provenance Summary

| Dataset | Granularity | Records | Provenance Tag | Source / Citation |
|---|---|---|---|---|
| **EM-DAT Disaster Events** | Event-level (India) | 810 | `REAL` | CRED EM-DAT International Disaster Database (1900–2026) |
| **Hospital Directory** | Facility-level (MH) | 4,767 | `REAL` | National Health Portal India (data.gov.in) |
| **Statewise ICU Beds** | State-level anchor | 36 states | `REAL` | Kapoor et al. (2020) / NHP ICU Bed Audit |
| **WorldPop Population** | 1km raster / Zonal | 35 districts | `REAL` | WorldPop 2020 Constrained Population Grid |
| **District Bed Capacity** | District-level (MH) | 35 districts | `ESTIMATED` | Scaled from ICU Audit + Facility Count + Pop Weighting |
| **Event Weather** | Event-date window | 810 events | `ESTIMATED` | Open-Meteo Archive / Physics Climatology |
| **Epidemiological Demand** | Per patient / day | 5 drug classes | `ASSUMED` | WHO IEHK 2017 & Sphere Handbook |

---

## 3. Real Data Quality Breakdown

### A. WorldPop Population Zonal Sums (`district_population.csv`)
- **Districts Covered**: 35 administrative districts of Maharashtra.
- **Total Population**: **124,499,982** (aligned with Census 2011 baseline of 112.37M and 2020 projection of 124.5M, error < 0.1%).
- **Top 3 Districts by Population**: Thane, Pune, Mumbai.

### B. National Hospital Directory (`cleaned_facilities.csv` & `district_facilities.csv`)
- **Total Facilities Cleaned**: 4,767 records across Maharashtra.
- **Coordinate Precision**:
  - `exact` ("lat, lon" parsed from registry): **2952** (61.9%)
  - `pincode` (pincode centroid fallback): **1815** (38.1%)
  - `district` (district centroid fallback): **0** (0.0%)
- **Public vs Private Facilities**:
  - Public facilities: **4,677** (98.1%)
  - Private facilities: **90** (1.9%)
- **Bed Field Disclosure**: `Total_Num_Beds` is populated and valid (1–5000) for only ~32 facilities in Maharashtra. Direct use of `Total_Num_Beds` as district bed count is strictly prohibited due to sparsity; bed capacity is estimated via state-level ICU bed anchoring.

### C. District Healthcare & ICU Capacity (`district_capacity.csv`)
- **State ICU Anchor**: **11,587 total ICU beds** (2,572 public / 9,015 private).
- **Total State Hospital Beds**: **144,981 beds**.
- **District Capacity Range (P10 Low / P50 Mid / P90 High)**:
  - Total Beds: 115,971 (Low) to 173,964 (High)
  - Total ICU Beds: 9,240 (Low) to 13,870 (High)

### D. EM-DAT Historical Disaster Catalogue (`emdat_events.csv`)
- **Total India Disaster Events**: 810
- **Casualty Target Coverage (Strict Non-Imputation Policy)**:
  - `total_affected`: 512 / 810 (63.2%)
  - `no_injured`: 136 / 810 (16.8%)
  - `total_deaths`: 746 / 810 (92.1%)
- **Disaster Types**: Flood (335), Storm (225), Epidemic (69), Extreme temperature (65), Mass movement (wet) (62).

---

## 4. Integrity and Leakage Guarantees
- Raw input datasets in `data/raw/` are strictly read-only.
- All spatial and population joins are validated to achieve $\ge 95\%$ district coverage.
- Casualty targets in EM-DAT are never imputed. Missing targets remain `NaN` and are excluded from loss calculation.
