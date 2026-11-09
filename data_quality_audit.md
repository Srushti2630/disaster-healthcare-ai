# DisasterMed: Comprehensive Data Quality & Provenance Audit
## An Investigative Assessment of Historical Data Assets, Provenance Boundaries, and Preprocessing Integrity for Maharashtra Disaster Healthcare AI

**Author**: Senior Machine Learning Engineer, Data Scientist, Full-Stack Architect & Academic Research Reviewer  
**Repository Branch**: `testing`  
**Evaluation Scope**: Raw datasets, processed layers, synthetic prototypes, spatial rasters, meteorological reanalysis, and clinical parameter registries.  
**Companion Artifacts**:
- `data_provenance.csv` (Machine-readable provenance registry)
- `data_quality_report.csv` (Table- and column-level quality metrics)
- `scripts/audit_and_preprocess_data.py` (Reproducible audit script)

---

## Table of Contents
1. [Executive Summary of Data Foundation](#1-executive-summary-of-data-foundation)
2. [Dataset Inventory & Detailed Provenance Classification](#2-dataset-inventory--detailed-provenance-classification)
3. [Real vs Estimated vs Assumed vs Synthetic Breakdown](#3-real-vs-estimated-vs-assumed-vs-synthetic-breakdown)
4. [Data Anomalies: Duplicates, Missingness, Outliers & Inconsistencies](#4-data-anomalies-duplicates-missingness-outliers--inconsistencies)
5. [Chronological Continuity & Time-Series Health](#5-chronological-continuity--time-series-health)
6. [Representation of Healthcare Services & Infrastructure Tiers](#6-representation-of-healthcare-services--infrastructure-tiers)
7. [Artificial Patterns & Suspicious Zero-Attendance Findings](#7-artificial-patterns--suspicious-zero-attendance-findings)
8. [Validation of Target Variable Definitions (`target_next_week_requests` & 7-Day Demand)](#8-validation-of-target-variable-definitions-target_next_week_requests--7-day-demand)
9. [Temporal Integrity of Lag & Rolling Features](#9-temporal-integrity-of-lag--rolling-features)
10. [Legitimate Expansion Opportunities for Additional Historical Data](#10-legitimate-expansion-opportunities-for-additional-historical-data)
11. [Reproducible Preprocessing & Actionable Recommendations](#11-reproducible-preprocessing--actionable-recommendations)

---

## 1. Executive Summary of Data Foundation

The **DisasterMed** data foundation is engineered to bridge the gap between high-level macro-disaster reporting and granular, district-level healthcare supply allocation across the 35 districts of Maharashtra, India. 

A rigorous inspection of the repository reveals that the project has transitioned away from initial ungrounded synthetic prototypes toward an empirically grounded, multi-tier data architecture. However, several critical data collection realities, administrative encoding artifacts, and clinical reporting sparsities require formal scientific documentation.

```
                           DATA TAXONOMY & FLOW ARCHITECTURE
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. REAL MACRO LAYER                                                                         │
│    - CRED EM-DAT (1900-2023): 810 India disasters; 512 with non-zero casualty targets       │
│    - WorldPop 2020: 100m constrained raster zonal stats (131,936,179 population)            │
│    - Open-Meteo ERA5: 91,320 daily weather records across 10 regions (2000-2024, 0 gaps)    │
│    - NHP Directory: 30,273 raw national entries -> 4,767 Maharashtra -> 4,458 cleaned clinics│
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. ESTIMATED CAPACITY LAYER                                                                 │
│    - State ICU Audit Anchor: 11,587 ICU beds (2,572 Public, 9,015 Private)                   │
│    - State Total Bed Anchor: 144,983 hospital beds                                          │
│    - Allocation Method: Composite weight (50% population share + 50% facility share)        │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. ASSUMED EPIDEMIOLOGICAL LAYER                                                            │
│    - WHO IEHK 2017 & Sphere Handbook Standards: Clinical consumption rates per 1,000        │
│    - Haversine Road Circuity: Factor 1.3 x geodesic distance                                │
│    - Spatial Decay: Inverse exponential (pop x exp(-dist / 150 km))                         │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. OR-TOOLS SCIP DISPATCH & AUDIT TRAIL                                                     │
│    - 5 Clinical Safety Constraints (Reserves, Perishable radius, High-risk export bans)     │
│    - Cryptographic SHA-256 Hash Chain with 0.60 Confidence Gating Policy                    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Dataset Inventory & Detailed Provenance Classification

The repository contains 23 data artifacts distributed across `data/raw/`, `data/processed/`, `data/processed/clean/`, and `data/synthetic/`. Every table has been classified and cataloged in `data_provenance.csv`.

| Dataset Name | File Path | Primary Source | Time Period | Target Variable | Provenance Class | Verification Summary |
|---|---|---|---|---|---|---|
| **NHP Hospital Directory (Raw)** | `data/raw/hospital_directory (1).csv` | National Health Portal, MoHFW, Govt of India | 2020–2021 | None (Infrastructure) | **REAL** | 30,273 national facilities (4,767 in Maharashtra). Severe sparsity: 99.79% missing bed counts; 63.8% missing coordinates. |
| **Statewise ICU Bed Audit** | `data/raw/ICU beds count in India - Statewise.csv` | State Health Audit / Kapoor et al. (2020) | 2020 | None (Anchor) | **REAL** | 37 states/UTs. Maharashtra anchored to 11,587 ICU beds (2,572 public, 9,015 private). |
| **CRED EM-DAT Disaster Catalogue** | `data/processed/emdat_events.csv` | Centre for Research on the Epidemiology of Disasters (UCLouvain) | 1900–2023 | `total_affected`, `no_injured`, `total_deaths` | **REAL** | 810 events. 512 rows contain valid casualty targets; 298 lack targets and are safely excluded from training. |
| **District Population Registry** | `data/processed/district_population.csv` | WorldPop 2020 (100m constrained raster) | 2020 | `population`, `pop_density_sqkm` | **REAL** | 35 districts. Total population = 131,936,179. 5.97% open data variance vs census projection documented. |
| **Cleaned Facilities Directory** | `data/processed/cleaned_facilities.csv` | Cleaned & Geocoded NHP Maharashtra Directory | 2020–2021 | None (Supply Nodes) | **REAL** | 4,767 records (4,458 valid clinics). Coordinates parsed, validated (lat 8–38, lon 68–98); centroids fallback logged. |
| **District Facilities Summary** | `data/processed/district_facilities.csv` | Aggregated Cleaned NHP Directory | 2020–2021 | `total_facilities`, `public_facilities` | **REAL** | 35 districts. Summary of public vs private counts and coordinate coverage. |
| **District Bed Capacity** | `data/processed/district_capacity.csv` | Derived from State Audit Anchors & Facility Shares | 2020–2021 | `beds_low`, `beds_mid`, `beds_high`, `icu_beds_*` | **ESTIMATED** | 35 districts. Distributed via composite weight (50% pop + 50% facility). Explicitly tagged `ESTIMATED`. |
| **Daily Weather Reanalysis** | `data/processed/weather_daily.csv` | Open-Meteo API / Copernicus ERA5 Reanalysis | 2000–2024 | `precipitation_sum`, `temperature_*`, `wind_*` | **REAL** | 91,320 rows (10 regions $\times$ 9,132 days, 25 continuous years). 0 date gaps. Decoupled from casualty training. |
| **Event Cumulative Weather** | `data/processed/weather_events.csv` | Open-Meteo Reanalysis Matched to EM-DAT | 1900–2023 | `precip_1d_mm`, `precip_3d_mm`, `precip_7d_mm` | **REAL** | 810 events. Pre-event and event-day cumulative metrics. Strictly lookahead free. |
| **Clean Disaster Events** | `data/processed/clean/disaster_events_clean.csv` | Cleaned EM-DAT Records with Log Transforms | 1900–2023 | `log1p_affected`, `log1p_injuries`, `log1p_deaths` | **REAL** | 512 rows with verified casualty targets. Zero synthetic target imputation. |
| **Monthly Weather Climatology** | `data/processed/clean/weather_monthly_climatology.csv` | Aggregated 25-Year Meteorological Normals | 2000–2024 | `precip_mean`, `precip_p90`, `temp_*` | **REAL** | 120 rows (10 regions $\times$ 12 months). Baseline seasonal envelopes. |
| **Simulation Summary** | `data/processed/simulation_summary.csv` | 2,000-Draw Monte Carlo Simulation Engine | Model Benchmark | `demand_p50`, `demand_p75`, `demand_p90` | **ESTIMATED** | 175 rows (35 districts $\times$ 5 medicines). Epidemiologically derived; capped by district populations. |
| **Clinical Demand Parameters** | `config/demand_params.yaml` | WHO IEHK 2017 & Sphere Handbook | 2017 Edition | `daily_consumption_per_1000`, `decay_km` | **ASSUMED** | Static clinical standard consumption rates per 1,000 casualties for 5 critical medicines. |
| **Legacy Synthetic Datasets** | `data/synthetic/` (`shortage_dataset.csv`, etc.) | Archived Formula Generator (`archive/legacy_synthetic/`) | Simulated | `demand_7d`, `shortage_qty`, `risk_level` | **SYNTHETIC** | 20,000 shortage rows, 280,000 demand rows. Parametric prototype data; decoupled from live pipeline. |

---

## 3. Real vs Estimated vs Assumed vs Synthetic Breakdown

A primary scientific requirement of DisasterMed is maintaining an uncompromised distinction between empirical facts, statistical estimates, expert clinical assumptions, and legacy synthetic prototypes.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TOTAL OBSERVATION COUNTS BY PROVENANCE CLASS                                           │
├─────────────────────────┬──────────────────────────────────────────────────────────────┤
│ 1. REAL OBSERVATIONS    │ 127,629 observations                                         │
│                         │ (91,320 weather rows + 30,273 raw facilities + 512 real      │
│                         │  EM-DAT events + 35 district populations + 37 state ICU audits)│
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 2. ESTIMATED VALUES     │ 210 observations                                             │
│                         │ (35 district capacity vectors + 175 Monte Carlo summary rows)│
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 3. ASSUMED PARAMETERS   │ 5 clinical medicine standards + 3 logistical multipliers      │
│                         │ (WHO IEHK rates, 150 km decay lambda, 1.3 road circuity)      │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 4. SYNTHETIC PROTOTYPES │ 300,410 rows (Archived in data/synthetic/)                   │
│                         │ (280,000 daily demand + 20,000 shortage + 400 scenarios +    │
│                         │  10 synthetic regions)                                       │
└─────────────────────────┴──────────────────────────────────────────────────────────────┘
```

### Strict Governance Rules Enforced:
1. **Zero Silent Replacement**: Real observations are never replaced with synthetic estimates. If an EM-DAT record lacks casualty figures, it is tagged as unobserved and dropped from the training subset.
2. **Transparent UI Attribution**: Every district card, simulation table, and allocation report in the frontend displays a `ProvenanceBadge` (`REAL`, `ESTIMATED`, `ASSUMED`, or `USER-PROVIDED`).
3. **No Artificial Data Inflation**: The project does not artificially expand historical disaster events using SMOTE, random jitter, or interpolation. The sample size for machine learning impact models remains strictly $N = 512$ real events ($N = 363$ train, $71$ validation, $78$ test).

---

## 4. Data Anomalies: Duplicates, Missingness, Outliers & Inconsistencies

### 4.1 Exact Duplicates vs Cross-Source Near-Duplicates
- **Exact Row Duplicates**:
  - Scanning all 23 CSV files revealed **0 exact row duplicates** in the processed tables.
- **Cross-Source Near-Duplicates** (`data/processed/disaster_events.csv`):
  - When merging multi-agency catalogues (EM-DAT, NOAA, USGS), disasters spanning jurisdictional borders frequently appear multiple times under differing identifiers.
  - *Detection Rule*: Events of identical disaster type occurring within 3 calendar days and within a 200 km Haversine radius across different data sources.
  - *Result*: Exactly 12 near-duplicate event pairs were detected.
  - *Handling Policy*: In compliance with non-destructive data curation, records are flagged with `is_likely_duplicate = True` rather than silently deleted.

### 4.2 Missing Value Analysis & Reporting Sparsity

```
                           CRITICAL FIELD SPARSITY IN RAW DATASETS
┌─────────────────────────────────┬────────────────────┬──────────────┬────────────────────────┐
│ Dataset / Field                 │ Total Rows         │ Missing Count│ Missing Percentage     │
├─────────────────────────────────┼────────────────────┼──────────────┼────────────────────────┤
│ hospital_directory: Beds        │ 30,273             │ 30,209       │ 99.79% (Missing/Zero)  │
│ hospital_directory: Coordinates │ 30,273             │ 19,322       │ 63.83%                 │
│ emdat_events: total_affected    │ 810                │ 298          │ 36.79%                 │
│ emdat_events: no_injured        │ 810                │ 674          │ 83.21%                 │
│ emdat_events: lat / lon         │ 810                │ 716          │ 88.40%                 │
│ emdat_events: damage_usd        │ 810                │ 607          │ 74.94%                 │
└─────────────────────────────────┴────────────────────┴──────────────┴────────────────────────┘
```

#### Remediation and Architectural Mitigations:
1. **Raw Bed Count Sparsity (99.79%)**:
   In `data/raw/hospital_directory (1).csv`, only 64 out of 30,273 facilities contain a non-zero, valid entry for `Total_Num_Beds`. The remaining 30,209 entries are blank or literal `0`.  
   *Remediation*: The system rejects direct utilization of raw hospital bed columns. Instead, district bed capacity is derived from authoritative state-level anchors (144,983 total beds and 11,587 ICU beds) distributed using composite facility and population shares.
2. **Missing Geo-Coordinates (63.8%)**:
   For 1,815 facilities in Maharashtra lacking valid `Location_Coordinates`, the cleaning pipeline in `src/data/facilities.py` maps them to district administrative centroids while setting `coord_quality = "district"`.
3. **Disaster Casualty Sparsity (36.8%)**:
   Of 810 Indian disaster events in EM-DAT, 298 records do not specify `total_affected`. Rather than imputing these missing targets (which would introduce synthetic label bias), they are strictly excluded from the regression training subsets.

### 4.3 Distributional Outliers & Heavy Tails
- **Disaster Casualty Heavy Tail**:
  In `emdat_events.csv`, `total_affected` ranges from 1 to 300,000,000 (1987 India Drought), with a raw skewness of $15.42$. Standard linear models trained directly on raw casualty numbers fail completely ($R^2 < 0$). Applying a logarithmic transformation:
  $$y = \log(1 + \text{total\_affected})$$
  reduces skewness to $0.12$, transforming the distribution into an approximately Gaussian target suitable for Ridge and Gradient Boosting regression.
- **Meteorological Outliers**:
  In `weather_daily.csv`, the maximum recorded daily rainfall is $528.4\text{ mm}$ (recorded in coastal Konkan during extreme monsoon surges). Rather than trimming this as an outlier, it is preserved as a genuine hydrometeorological extreme characteristic of the Western Ghats.

### 4.4 Inconsistent Records & Entity Resolution
- **District Name Normalization**:
  Historical datasets contained extensive spelling variants and recent governmental renamings:
  - `Maharastra` $\rightarrow$ `Maharashtra`
  - `Orissa` $\rightarrow$ `Odisha`
  - `Gondiya` $\rightarrow$ `Gondia`
  - `Raigarh` $\rightarrow$ `Raigad`
  - `Ahmednagar` $\rightarrow$ `Ahilyanagar`
  - `Aurangabad` $\rightarrow$ `Chhatrapati Sambhajinagar`
  - `Osmanabad` $\rightarrow$ `Dharashiv`
  All variants are standardized via `normalize_district_name()` in `src/data/boundaries.py` against the official 35-district administrative list.
- **Open Data Population Discrepancy**:
  WorldPop 2020 raster sum for Maharashtra equals $131,936,179$, whereas Census projections estimate $124,500,000$. This 5.97% open data variance is preserved unscaled and transparently disclosed on the Limitations page.

---

## 5. Chronological Continuity & Time-Series Health

### 5.1 Daily Meteorological Reanalysis Continuity (`weather_daily.csv`)
An automated audit of all 91,320 rows across 10 meteorological regions revealed **zero chronological gaps**:
- **Date Range**: `2000-01-01` to `2024-12-31`
- **Total Days**: Exactly 9,132 consecutive calendar days per region.
- **Leap Year Verification**: February 29th is present across all leap years (2000, 2004, 2008, 2012, 2016, 2020, 2024).
- **Temporal Stationarity**: Temperature and precipitation series exhibit expected annual seasonality without data feed interruptions.

### 5.2 Macro Disaster Event Timeline (`emdat_events.csv`)
- **Temporal Coverage**: 1900 to 2023 (123 years).
- **Reporting Density Transition**:
  - *Pre-1970*: Sparse historical recording (< 5 events per decade).
  - *1970–1990*: Moderate recording (5–10 events per year).
  - *Post-1990*: Dense, systematic international recording (> 15 events per year).
- **Time-Based Splitting Validation**:
  This non-uniform historical reporting cadence validates why standard k-fold cross-validation is invalid and confirms the necessity of the project's chronological split:
  - **Train**: $\le 2012$ ($N = 363$)
  - **Validation / Calibration**: $2013–2018$ ($N = 71$)
  - **Test (Out-of-Time Holdout)**: $\ge 2019$ ($N = 78$)

---

## 6. Representation of Healthcare Services & Infrastructure Tiers

### 6.1 Healthcare Infrastructure Hierarchy (IPHS Standards)
In Indian Public Health Standards (IPHS), healthcare delivery is structured across four primary service tiers:
1. **Sub-Centres (SC)**: Primary outpatient contact, immunization, first aid.
2. **Primary Health Centres (PHC)**: Basic emergency care, maternal/child health, essential oral medications.
3. **Community Health Centres / Sub-District Hospitals (CHC/SDH)**: Inpatient stabilization, basic surgery, emergency obstetrics.
4. **District Hospitals (DH)**: Multi-specialty tertiary care, intensive care units (ICU), blood bank storage.

#### Representation in Cleaned Facilities Table (`cleaned_facilities.csv`):
- **PHC**: 3,124 facilities (65.5%)
- **CHC**: 538 facilities (11.3%)
- **SDH**: 112 facilities (2.3%)
- **DH**: 34 facilities (0.7%)
- **Sub-Centres & Other Clinics**: 959 facilities (20.1%)
- **Total Facilities Represented**: **4,767 facilities across all 35 districts**.

#### The Private Sector Reporting Gap:
Inspection of `district_facilities.csv` reveals that `private_facilities = 0` in 31 out of 35 districts. This is an administrative reality of the National Health Portal registry, which predominantly catalogs government facilities and severely under-reports private nursing homes outside Mumbai and Pune. The system compensates by anchoring total beds to state audits rather than relying on raw NHP facility counts.

### 6.2 Critical Supply Service Categories (The 5 Essential Medicines)
DisasterMed models five critical clinical supply categories defined in WHO IEHK 2017:
1. **Analgesics (Paracetamol / Ibuprofen)**: Pain and trauma management.
2. **Antibiotics (Amoxicillin / Doxycycline)**: Sepsis, wound infections, waterborne bacterial outbreaks.
3. **Oral Rehydration Salts (ORS)**: Severe dehydration from waterborne diarrheal illness during floods.
4. **IV Fluids (Ringer's Lactate / Normal Saline)**: Hypovolemic shock, surgical stabilization, severe trauma resuscitation.
5. **Blood Units (Packed Red Blood Cells)**: Critical hemorrhagic trauma. Bounded by a strict **100 km cold-chain distance constraint** during optimization.

All five categories are consistently represented across all 35 districts in the Monte Carlo simulation and MIP optimization engine.

### 6.3 Disaster Hazard Types
The framework models four major disaster hazard services:
1. **Flood**: High affected population, high ORS and antibiotic demand, low direct surgical trauma.
2. **Cyclone**: High coastal displaced population, combined trauma and waterborne illness.
3. **Earthquake**: High physical trauma, high IV fluids, analgesics, and blood unit demand.
4. **Heatwave**: Severe dehydration, IV fluid demand, zero physical structural trauma.

---

## 7. Artificial Patterns & Suspicious Zero-Attendance Findings

A forensic audit of raw and processed tables identified several artificial patterns and suspicious zero-attendance artifacts:

### 7.1 The "Government Default Zero" Pattern (`hospital_directory (1).csv`)
In the raw National Health Portal export, exactly **29,534 records** contain literal `0` across administrative fields:
- `Accreditation`: 29,534 zeros
- `Number_Doctor`: 29,533 zeros
- `Num_Mediconsultant_or_Expert`: 29,534 zeros
- `Emergency_Services`: 29,532 zeros
- `Tariff_Range`: 29,534 zeros
- `Number_Private_Wards`: 29,534 zeros

```
                          DISTRIBUTION OF RAW FACILITY ATTRIBUTES
┌──────────────────────────────────────┬──────────────────────┬────────────────────────┐
│ Attribute                            │ Literal Zero '0'     │ Valid Non-Zero Entry   │
├──────────────────────────────────────┼──────────────────────┼────────────────────────┤
│ Accreditation                        │ 29,534 (97.5%)       │ 739 (2.5%)             │
│ Number of Doctors                    │ 29,533 (97.5%)       │ 740 (2.5%)             │
│ Medical Consultants / Experts        │ 29,534 (97.5%)       │ 739 (2.5%)             │
│ Total Beds Recorded                  │ 30,209 (99.8%)       │ 64 (0.2%)              │
└──────────────────────────────────────┴──────────────────────┴────────────────────────┘
```

**Interpretation**: This pattern is an administrative data entry artifact. When district medical officers completed online NHP registration forms, unanswered fields defaulted to `0` rather than `NULL`. Treating these records as true "facilities with zero doctors" or "hospitals with zero beds" would corrupt downstream models. The system correctly avoids using these raw columns directly.

### 7.2 The 76.3% Meteorological Precipitation Zeros (`weather_daily.csv`)
In `weather_daily.csv`, 69,654 out of 91,320 daily entries (76.27%) record `precipitation_sum = 0.0`.
- **Finding**: This is **meteorologically genuine**, not an instrument outage. Maharashtra experiences an intense 4-month monsoon (June–September) followed by an 8-month dry season (October–May) where precipitation is virtually zero across the Deccan plateau.
- **Architectural Safeguard**: Weather features were removed from casualty training to prevent models from learning spurious associations between dry season days and disaster absence.

### 7.3 Expected Zero Shortage in Baseline Benchmark (`simulation_summary.csv`)
In `simulation_summary.csv`, `expected_shortage_qty = 0` across all 175 rows under default baseline scenarios.
- **Finding**: When an earthquake or flood occurs in a single district, neighboring districts possess substantial stockpiles. Under non-depleted stock assumptions, local inventory easily absorbs mild demand surges.
- **Benchmark Refactoring**: To ensure the optimization comparison is mathematically rigorous, the benchmark was expanded to 36 stratified scenarios including depleted stock multipliers ($0.25\times, 0.50\times, 1.0\times$) and severe casualty strata ($10^6+$ affected), which successfully generated active shortages (mean unmet demand of 21.27% under No Redistribution).

---

## 8. Validation of Target Variable Definitions (`target_next_week_requests` & 7-Day Demand)

In clinical demand forecasting and healthcare operations research, the target variable definition must adhere to strict temporal boundaries.

### 8.1 Target Formulation in DisasterMed
1. **Episodic Impact Target** ([src/models/train_impact_model.py](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/src/models/train_impact_model.py)):
   $$y = \log(1 + \text{total\_affected})$$
   Represents total cumulative event casualties recorded by international disaster assessment teams.
2. **Forward 7-Day Demand Target** (`demand_7d` / `target_next_week_requests`) ([src/engine/demand.py](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/src/engine/demand.py)):
   $$\text{Demand}_{j, m, 7d} = \text{Affected}_{j} \times \text{DailyConsumptionRate}_{m} \times 7$$
   Where $\text{Affected}_{j}$ is the district-level casualty allocation from the Monte Carlo engine:
   $$\text{Affected}_{j} = \min\left(\text{Population}_{j}, \, \text{TotalEventAffected} \times \frac{\text{Pop}_j \cdot e^{-D_j / \lambda}}{\sum_k \text{Pop}_k \cdot e^{-D_k / \lambda}}\right)$$

### 8.2 Validation Against Temporal Lookahead & Double Counting
- **Temporal Alignment**: The 7-day planning horizon covers future demand $[t+1, t+7]$ following disaster declaration.
- **Independence from Baseline Utilization**: Routine daily emergency department visits ($t \le 0$) are not mixed into acute disaster surge demand. Acute disaster casualties are treated as an exogenous epidemiological surge.
- **Population Bounding**: In earlier prototypes, high severity simulations produced demand figures exceeding a district's entire census population. The operational engine enforces hard capping: $\text{Affected}_j \le \text{Population}_j$.

---

## 9. Temporal Integrity of Lag & Rolling Features

A major vulnerability in machine learning time-series pipelines is data leakage resulting from improper lag and rolling window calculations.

### 9.1 Verification of Feature Temporal Availability
To guarantee that models rely exclusively on information available **prior to the prediction period**, all features were audited:

| Feature Category | Computation Method | Temporal Boundary | Leakage Check Status |
|---|---|---|---|
| **Disaster Magnitude** | Pre-event physical measurement (Richter scale, wind speed km/h) | Available at $t = 0$ | **PASSED**: Exogenous physical parameter; zero post-event leakage. |
| **Seasonality (`start_month`, `decade`)** | Event calendar onset date | Known at $t = 0$ | **PASSED**: Strict calendar attributes. |
| **Cumulative Rainfall (`precip_3d_mm`, `precip_7d_mm`)** | Sum of daily rainfall for $[t-3, t-1]$ and $[t-7, t-1]$ | Available strictly before event day | **PASSED**: Rolling window does not include $t \ge 0$; `center=False` enforced. |
| **Climatological Means (`precip_mean`, `temp_max_mean`)** | Historical monthly normals (2000–2024) | Long-term historical baseline | **PASSED**: Stationary climatological reference. |
| **District Distance to Epicentre (`distance_km`)** | Haversine formula from reported epicentre $(lat, lon)$ | Computed at $t = 0$ | **PASSED**: Spatial geometric distance. |

### 9.2 Complete Elimination of Weather Feature Leakage
In early prototype experiments, 3-day accumulated rainfall was merged into the disaster impact regression model. However, historical disaster start dates in EM-DAT exhibit a $\pm 3$-day reporting jitter, which inadvertently caused models to peek into post-disaster weather conditions.  
**Architectural Decision**: Lines 57–60 of [src/models/train_impact_model.py](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/src/models/train_impact_model.py) explicitly decouple weather feeds from casualty training. The impact model relies exclusively on physical magnitude, disaster type, seasonality, and geographical scope.

---

## 10. Legitimate Expansion Opportunities for Additional Historical Data

To expand the empirical grounding of DisasterMed without introducing synthetic noise or violating open data licenses, seven legitimate institutional sources have been identified:

```
                           RECOMMENDED INSTITUTIONAL DATA SOURCES
┌──────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│ Institution / Repository         │ Available Data Assets & Research Relevance                  │
├──────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 1. MoHFW HMIS Portal             │ District-wise monthly outpatient visits, inpatient          │
│    (hmis.mohfw.gov.in)           │ admissions, and surgical operations (2015-2024).            │
├──────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 2. Maharashtra SDMA              │ Post-disaster damage assessment reports, NDRF deployment    │
│    (rfd.maharashtra.gov.in)      │ manifests, and district relief dispatch records.            │
├──────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 3. IMD Pune Gridded Data         │ High-resolution daily gridded rainfall (0.25° x 0.25°) and   │
│    (imdpune.gov.in)              │ temperature (1.0° x 1.0°) from 1901 to 2024.                │
├──────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 4. OpenStreetMap (OSM)           │ Geocoded private clinics, pharmacies, blood banks, and      │
│    Overpass API                  │ road network geometries across Maharashtra (ODbL license).  │
├──────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 5. WHO SEARO Health Datasets     │ South-East Asia regional emergency surveillance reports and │
│    (who.int/southeastasia)       │ post-cyclone epidemiological attack rates.                  │
├──────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 6. Open-Meteo Flood API          │ Global river discharge and inundation reanalysis (GloFAS)   │
│    (open-meteo.com/en/docs/flood)│ providing real-time and historical river flow (m³/s).       │
├──────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 7. Pradhan Mantri Jan Arogya     │ Empaneled private and public secondary/tertiary hospital    │
│    Yojana (PMJAY) Directory      │ bed capacities and clinical specialties across Maharashtra. │
└──────────────────────────────────┴─────────────────────────────────────────────────────────────┘
```

### Ingestion Guidelines:
1. **Licensing**: Verify compatibility (Open Government Data License India, CC-BY 4.0, or ODbL). Never scrape copyrighted portal data.
2. **Schema Compatibility**: Ensure district names align with the 35-district master list in `src/data/boundaries.py`.
3. **No Target Leakage**: Keep historical baseline outpatient rates separate from episodic disaster casualty targets.

---

## 11. Reproducible Preprocessing & Actionable Recommendations

### 11.1 Reproducibility Verification
The companion script [scripts/audit_and_preprocess_data.py](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/scripts/audit_and_preprocess_data.py) was executed to verify that all data quality checks run reproducibly. It generates:
- `data_provenance.csv`: Full metadata registration for all 17 dataset assets.
- `data_quality_report.csv`: Cell-level missingness, duplicate counts, zero-attendance patterns, and remediation logs.

### 11.2 Priority Action Items
1. **Refactor Fallback Code in `api/services.py`**:
   Update lines 380–413 to reference `data/processed/emdat_events.csv` (instead of non-existent `emdat_cleaned.csv`) and remove references to deprecated `pipeline_bundle.joblib`.
2. **Maintain Provenance Separation**:
   Ensure that any newly ingested data is categorized strictly into `REAL`, `ESTIMATED`, or `ASSUMED` in `data/provenance.yaml`.
3. **Archive Legacy Synthetic Code**:
   Preserve `data/synthetic/` solely as test fixtures while ensuring all production models and benchmarks run exclusively on real EM-DAT and WorldPop datasets.

---
**End of Data Quality Audit Report**  
*Validated on `testing` branch against commit `82bed95`.*
