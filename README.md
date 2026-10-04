# Disaster Healthcare AI: Demand Prediction & Resource Allocation

> **An Explainable and Uncertainty-Aware AI Framework for Disaster Healthcare Demand Prediction and Multi-Objective Resource Allocation**  
> *Final-Year BTech Engineering Capstone Project* (Python 3.13 | XGBoost | scikit-learn | SHAP | Google OR-Tools SCIP | Streamlit)

---

## 1. Abstract & Executive Summary

Disaster healthcare logistics in developing countries face critical challenges due to sudden casualty surges, uncertain disease propagation, and spatial resource disparities. This project establishes an **end-to-end, reproducible, and verifiable AI decision-support framework** for disaster healthcare demand prediction and inter-district medical resource allocation across Maharashtra's 35 administrative districts.

Unlike legacy synthetic pipelines that evaluate models on deterministic formulas, this framework operates on **real public datasets** (CRED EM-DAT, WorldPop 2020 High-Resolution Grid, National Health Portal India, State ICU Audit) and transparent WHO Interagency Emergency Health Kit (IEHK 2017) and Sphere Handbook epidemiological consumption standards.

```mermaid
flowchart TD
    subgraph Data Layer [1. Real Public Data Layer]
        A1["EM-DAT India Disasters (REAL)"] --> B1["Data Layer (src/data/)"]
        A2["WorldPop 2020 Grid (REAL)"] --> B1
        A3["National Health Portal (REAL)"] --> B1
        A4["State ICU Audit (REAL)"] --> B1
    end

    subgraph Modeling Layer [2. Impact & Uncertainty Models]
        B1 --> C1["Ridge Impact Model (log1p affected)"]
        B1 --> C2["Conformalized Quantile Regression (CQR 90%)"]
        C1 --> D1["TreeExplainer SHAP Attribution"]
    end

    subgraph Simulation Layer [3. Monte-Carlo & ML Surrogate]
        C2 --> E1["WHO IEHK / Sphere Monte-Carlo Engine (2,000 draws)"]
    subgraph Simulation Layer [3. Monte-Carlo & ML Surrogate]
        C2 --> E1["WHO IEHK / Sphere Monte-Carlo Engine (2,000 draws)"]
        E1 --> E2["Fast ML Surrogate Classifier (500 Scenarios, 91.3% Fidelity)"]
    end

    subgraph Optimization Layer [4. Operations Research Solver]
        E1 --> F1["Google OR-Tools SCIP MIP Solver (35 District Nodes)"]
        F1 --> F2["Shared Evaluator (Safety Reserves, Blood 150km Limit)"]
    end

    subgraph UI & Governance [5. Decision Support & Audit Log]
        F2 --> G1["Streamlit Multi-Page Dashboard (app.py)"]
        G1 --> G2["SHA-256 Hash-Chained Cryptographic Audit Log"]
        G1 --> G3["One-Click PDF/Excel Situation Reports"]
    end
```

---

## 2. Real Data Provenance & Registry

Every dataset and output figure carries a strict, machine-readable provenance tag (`REAL`, `ESTIMATED`, `ASSUMED` tracked in `data/provenance.yaml`):

| Dataset / Asset | Provenance Tag | Source / Citation | Records / Details |
|---|---|---|---|
| **EM-DAT Disaster Catalogue** | `REAL` | CRED EM-DAT International Disaster Database ([public.emdat.be](https://public.emdat.be/)) | 810 India disaster events (512 with recorded targets); casualty targets never imputed. |
| **WorldPop Population Raster** | `REAL` | WorldPop 2020 1km Constrained Grid ([worldpop.org](https://www.worldpop.org/)) | Raw zonal sum per district using `rasterio.mask`; total 131.9M vs 124.5M projection. |
| **National Hospital Directory** | `REAL` | Open Government Data Portal India ([data.gov.in](https://data.gov.in/)) | 4,767 Maharashtra facilities classified by public/private mix and coordinate quality. |
| **State ICU Beds Audit** | `REAL` | National Health Profile / Kapoor et al. (2020) | 11,587 total state ICU beds (2,572 public / 9,015 private). |
| **District Hospital Bed Capacity** | `ESTIMATED` | Derived from State Bed Anchor + Facility Counts | Allocated from 144,983 state total hospital bed anchor across 35 districts. |
| **Epidemiological Consumption** | `ASSUMED` | WHO IEHK 2017 & Sphere Handbook Norms | Per-patient daily medicine consumption rates (`config/demand_params.yaml`). |
| **Distance Matrix** | `ASSUMED` | Haversine Distance $\times$ 1.3 Circuity Factor | Road transport circuity matrix across 35 district centroids. |

---

## 3. Before vs. After Rigor Upgrade

The framework was completely transformed from a circular semi-synthetic prototype into a scientifically rigorous, empirical AI system:

| Aspect | Legacy Semi-Synthetic Prototype | Upgraded Real-Data AI Framework |
|---|---|---|
| **Data Basis** | Formulaic synthetic generator (`synthetic_demand.py`) | Real CRED EM-DAT events, WorldPop rasters, NHP directory, State ICU audit |
| **Impact Model Target** | Synthetic label generated from input features ($R^2 \approx 0.88$) | Real EM-DAT casualties ($R^2 = 0.2780$, MAE = 2.8812, Spearman $\rho = 0.5199$) |
| **Prediction Uncertainty** | Fixed $\pm 10\%$ heuristic margin (86.1% empirical coverage) | CQR 90% Nominal ($94.9\%$ empirical test coverage, 95% CI: $[89.7\%, 98.7\%]$) |
| **Surrogate Classifier** | Single-scenario split ($100\%$ unvalidated accuracy claim) | 500-scenario sampling, split BY SCENARIO ($91.28\%$ held-out fidelity under residual $\sigma$) |
| **Optimizer Benchmarking** | Single scenario vs unconstrained heuristic | 20 Monte-Carlo scenarios evaluated across 5 methods through a shared constraint checker |
| **Unit Test Coverage** | 4 basic tests | 25 comprehensive pytest unit and integration tests (100% pass rate) |

---

## 4. Benchmark Results

### A. Impact Prediction Model (Time-Split Test Set $N=78$, 2019+)

| Model | Test MAE (log) | Test $R^2$ (95% CI) | Test Spearman $\rho$ (95% CI) | Order-of-Magnitude Acc ($\le 0.5 \text{ dex}$) |
|---|---|---|---|---|
| **Median Baseline** | 3.5717 | -0.0952 | 0.0000 | 19.2% |
| **Ridge Regression** | **2.8812** | **0.2780** ([0.0787, 0.4331]) | **0.5199** ([0.3657, 0.6472]) | 20.5% |
| **XGBoost Regressor** | 3.0908 | 0.1403 | 0.4454 | 24.4% |
| **Random Forest** | 3.3204 | -0.0174 | 0.3078 | 23.1% |

*Note*: CQR empirical test coverage is **94.9%** for nominal 90% target, indicating **conservative prediction intervals** (median interval width factor $\approx \times 9.96 \times 10^5$). Historical disaster backtesting uses Leave-One-Event-Out validation by `DisNo.` across fixed benchmark events (`2005-0409-IND`, `2005-0541-IND`, `2001-0033-IND`, `1993-0074-IND`, `2019-0331-IND`).

### B. Operations Research Optimizer (20 Monte-Carlo Scenarios Benchmark)

All methods evaluated using the single, unified cost function: $\text{Cost} = \text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$.

| Method | Mean Unmet Demand (units) | Mean Cost (Billion INR) | Mean Unit-KM | Mean Route-KM | Mean Min Coverage | Rule Violations |
|---|---|---|---|---|---|---|
| **OR-Tools SCIP** | **248,346,216.7** | **25.17** | 1,677,992,118.3 | **7,148.6 km** | **0.387** | **0** |
| **Greedy Largest Surplus** | 248,376,227.5 | 36.55 | 2,436,798,987.5 | 10,227.2 km | 0.321 | 0 |
| **Greedy Nearest** | 248,477,931.4 | 34.71 | 2,313,966,111.0 | 8,878.7 km | 0.321 | 0 |
| **Proportional Population** | 250,984,266.5 | 18.91 | 1,260,831,552.0 | 60,311.4 km | 0.283 | 0 |
| **No Redistribution** | 251,923,593.5 | 0.0 *(Excluded)* | 0.0 | 0.0 km | 0.270 | 0 |

---

## 5. Methodological Limitations

1. **Weather Features Excluded from Training**: Artificial rng weather degraded time-split generalization and was deleted from training features. Real-time Open-Meteo archive fetching is retained exclusively for live What-If simulation queries.
2. **Epidemiological Demand Rates (`ASSUMED`)**: Daily consumption rates per patient/injured day are taken from WHO IEHK 2017 and Sphere Handbook standards.
3. **Hospital Bed Capacities (`ESTIMATED`)**: District bed capacities are allocated from state-level ICU bed audit anchors (11,587 ICU beds / 144,983 total beds) weighted by facility counts.
4. **Population Raster Sum Gap**: WorldPop 2020 1km constrained raster zonal sum across 35 districts totals 131,936,179, showing a ~5.97% gap to the official 124.5M state government population projection (reported as a raw sanity check without artificial scaling).

---

## 6. Reproducibility & Quickstart

```bash
# 1. Environment Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run Full Pipeline End-to-End (Data Build -> Training -> Monte-Carlo -> Optimization -> Tests)
python run_all.py

# 3. Execute Unit Test Suite
pytest -q

# 4. Launch Interactive Streamlit Decision Dashboard
streamlit run app.py
```
