# Disaster Healthcare AI: Comprehensive Viva & Technical Review Q&A

This document prepares project authors for academic viva voce examinations, technical code reviews, and panel defenses for **"An Explainable and Uncertainty-Aware AI Framework for Disaster Healthcare Demand Prediction and Multi-Objective Resource Allocation"**.

---

### Q1: Why is the $R^2$ of the impact prediction model on EM-DAT (~0.28) relatively low compared to synthetic benchmarks (~0.88)?
**Answer**: High $R^2$ ($\approx 0.88–0.91$) reported on synthetic datasets was a circular artifact: the labels were exact deterministic mathematical functions of the synthetic inputs, so ML models simply recovered the synthetic generator formula. CRED EM-DAT contains real, noisy historical disaster reports spanning 810 events across India over a century. Real disaster casualty reporting is influenced by unobserved socio-economic infrastructure, local topography, reporting biases, and event-specific management. An $R^2$ of 0.2780 on a strict time-split test set (2019+) represents genuine predictive signal over baseline ($R^2 = -0.0952$ for median baseline) without circular data leakage.

### Q2: Where does medical supply demand come from, and why is it not directly trained from EM-DAT?
**Answer**: EM-DAT records macro casualty figures (`Total Deaths`, `No. Injured`, `Total Affected`), but does not contain pharmaceutical or medical supply consumption. Training ML models directly on invented demand labels creates fake learning. In our framework, macro casualties are converted into daily supply demand using WHO Interagency Emergency Health Kit (IEHK 2017) and Sphere Handbook standards (`config/demand_params.yaml`), which define clinical consumption rates per patient/injured day (e.g., 2.5 antibiotic doses/day, 4.0 ORS sachets/day, 0.5 blood units/injured day).

### Q3: What is the data provenance methodology (`REAL`, `ESTIMATED`, `ASSUMED`), and why is it enforced?
**Answer**: To eliminate data fabrication and maintain scientific integrity, every dataset and figure is explicitly tagged:
- **`REAL`**: Raw public data cited directly from authoritative databases (CRED EM-DAT, WorldPop 2020 Grid, National Health Portal India, State ICU Audit). Never imputed or altered.
- **`ESTIMATED`**: Quantities derived from real data using documented mathematical methods (e.g., district hospital bed capacity allocated from state-level 144,983 bed anchors weighted by facility counts).
- **`ASSUMED`**: Parameters sourced from WHO/Sphere literature or transport physics norms (e.g., Haversine $\times 1.3$ road circuity factor, clinical supply consumption rates).

### Q4: Why is `Total_Num_Beds` from the National Hospital Directory CSV (`hospital_directory (1).csv`) not used directly?
**Answer**: Thorough data auditing revealed that while the National Hospital Directory contains 4,767 healthcare facilities in Maharashtra, the `Total_Num_Beds` column is non-null and valid (1–5000) for only **32 facilities** in Maharashtra (~0.67% completeness). Using this column directly would severely distort district bed capacity. Instead, we use facility counts and public/private classifications from the directory as spatial weighting factors (`REAL`), and anchor district capacities to the official state-level 11,587 ICU bed audit and 144,983 total hospital bed anchor (`ESTIMATED`).

### Q5: Why were weather features removed from impact-model training?
**Answer**: The legacy weather script generated synthetic precipitation and wind features using `numpy.random` (gamma/normal distributions), which injected uncorrelated random noise into training. When trained on time-split real EM-DAT data, adding simulated weather degraded generalization (Ridge $R^2$ dropped from 0.278 to 0.262). Removing weather features improved both $R^2$ and Spearman rank correlation ($\rho: 0.504 \rightarrow 0.520$). Real-time Open-Meteo archive fetching is retained exclusively for live What-If simulation queries (returning `NaN` on network failure, never random numbers).

### Q6: How are prediction intervals generated and validated via Conformalized Quantile Regression (CQR)?
**Answer**: Standard regression models provide only point predictions. We use CQR (Conformalized Quantile Regression) with Gradient Boosting quantiles ($q_{0.05}$ and $q_{0.95}$) calibrated on a held-out validation set ($N=71$). The non-conformity score $E_i = \max(q_{0.05}(x_i) - y_i, y_i - q_{0.95}(x_i))$ is used to compute the conformal calibration margin $Q_{1-\alpha}(E_{\text{val}})$. This guarantees finite-sample coverage distributionally. On the held-out test set ($N=78$), CQR achieves 94.9% empirical coverage for a 90% nominal target.

### Q7: Does 94.9% empirical coverage vs a 90% target mean "better calibration"?
**Answer**: No. An empirical coverage of 94.9% on a 90% nominal target indicates that the prediction intervals are **conservative** (slightly wider than strictly necessary), not better calibrated. This occurs because disaster casualties have high variance and fat-tailed distributions. A conservative interval is desirable in disaster healthcare logistics to prevent underestimating surge demand.

### Q8: What does the median CQR interval width factor $\approx \times 9.96 \times 10^5$ tell us about model capability?
**Answer**: Log-scale prediction intervals span $\approx 13.8$ log units, which translates to a multiplicative factor of $\approx 10^5$ to $10^6$ in raw casualty counts. This demonstrates that historical disaster data exhibits high intrinsic variance ($W_i$ varies by orders of magnitude). The ML model serves as a **relative risk ranker across districts and hazard types**, rather than an exact point-estimator of casualty counts.

### Q9: Why is a Random Forest surrogate classifier trained, and why not call the Monte-Carlo engine directly?
**Answer**: The full Monte-Carlo simulation engine executes 2,000 stochastic draws per district $\times$ medicine (7,000+ calculations), taking ~1.2 to 2.5 seconds per scenario. For interactive Streamlit dashboard sliders, 2-second latencies degrade user experience. The Random Forest surrogate classifier is trained on 500 Monte-Carlo scenarios to predict shortage risk levels in $< 5\text{ ms}$, providing instant visual feedback.

### Q10: How was the surrogate classifier validated to avoid optimistic bias?
**Answer**: Splitting surrogate training datasets by row causes data leakage because rows from the same disaster scenario share identical hazard parameters. We implemented **scenario-based splitting**: 500 diverse disaster scenarios (varying hazard type, magnitude, epicentre, month) were sampled, and split 80% (400 scenarios) for training and 20% (100 scenarios) for testing by `scenario_id`. On held-out scenarios under full residual model uncertainty ($\sigma \approx 3.7186$), the surrogate achieved **91.28% fidelity accuracy**, **0.9085 macro F1**, and **0.0490 Expected Calibration Error (ECE)**.

### Q11: How does the OR-Tools SCIP Mixed-Integer Programming (MIP) optimization solver work?
**Answer**: The allocation problem is modeled as a multi-commodity network flow MIP solver over 35 district nodes and 5 medicine classes. Integer decision variables $x_{ijm} \in \mathbb{Z}_{\ge 0}$ represent the quantity of medicine $m$ transferred from source district $i$ to destination district $j$. Slacks $u_{jm} \ge 0$ represent unmet demand, and $\theta \in [0, 1]$ represents minimum regional coverage. The solver minimizes a multi-objective function: $\min \sum w_{\text{unmet}} \cdot c_m \cdot u_{jm} + \sum w_{\text{cost}} \cdot d_{ij} \cdot x_{ijm} - w_{\text{fairness}} \cdot \theta$.

### Q12: What constraints are enforced during resource allocation optimization?
**Answer**:
1. **Safety Reserve Constraint**: Source districts must retain at least 60% of their own local demand ($\sum_j x_{ijm} \le \max(0, \text{stock}_{im} - 0.60 \cdot \text{demand}_{im})$).
2. **High-Risk Export Prohibition**: Districts classified at High Shortage Risk for medicine $m$ are barred from exporting any stock ($\sum_j x_{ijm} = 0$).
3. **Perishables Transit Limit**: Blood units (`blood_units`) cannot be transported over routes exceeding 150 km ($d_{ij} \le 150\text{ km}$).
4. **Integrality & Non-Negativity**: All transfer quantities $x_{ijm}$ must be non-negative integers.
5. **No Self-Transfers**: $x_{iim} = 0$.

### Q13: How were baseline allocation methods constructed and compared?
**Answer**: We benchmarked 5 allocation methods across 20 Monte-Carlo demand scenarios:
1. **OR-Tools SCIP**: Optimal MIP solver plan.
2. **No Redistribution**: Zero transfers baseline.
3. **Proportional Population**: Distributes available surplus stock proportionally to destination district population weights.
4. **Greedy Nearest Surplus**: Allocates surplus from the nearest available non-High-risk surplus district.
5. **Greedy Largest Surplus**: Allocates surplus from the non-High-risk district holding the largest available surplus stock.

All 5 methods were evaluated through **ONE shared constraint checker** and **ONE unified cost function** ($\text{Cost} = \text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$).

### Q14: What were the key benchmarking results from the 20-scenario optimization study?
**Answer**: Across 20 scenarios under full residual model uncertainty ($\sigma \approx 3.7186$):
- **OR-Tools SCIP**: Achieved lowest mean unmet demand (**248.35M units**), lowest transport cost among active redistribution methods (**25.17B INR**), lowest active route distance (**7,148.6 km**), highest minimum regional coverage (**0.387**), and **0 rule violations**.
- **Greedy Largest Surplus**: Mean unmet demand 248.38M units; transport cost 36.55B INR (45.2% higher cost than OR-Tools).
- **Greedy Nearest**: Mean unmet demand 248.48M units; transport cost 34.71B INR (37.9% higher cost than OR-Tools).
- **Proportional Population**: Mean unmet demand 250.98M units; transport cost 18.91B INR.
- **No Redistribution**: Mean unmet demand 251.92M units; cost 0.0 INR (excluded from lowest cost claims).

### Q15: What is the difference between `unit_km` and `route_km`?
**Answer**:
- `unit_km`: The sum of $(\text{quantity} \times \text{distance\_km})$ over all transferred medical items. Measures total freight-distance work done.
- `route_km`: The sum of distinct physical route distances $\text{distance\_km}(i, j)$ for active dispatch routes ($x_{ij} > 0$). Measures total road network coverage.

### Q16: How is Haversine distance adjusted for real-world road networks?
**Answer**: Direct lat/lon distance (great-circle Haversine) underestimates actual road driving distance due to terrain, river crossings, and road winding. We multiply Haversine distance by a **1.3 circuity factor** ($\text{distance\_km} = \text{Haversine} \times 1.3$), tagged as `ASSUMED` transport physics.

### Q17: How does the SHA-256 audit log ensure tamper-evident governance?
**Answer**: Every human officer review action (Approve/Reject decision, reviewer role, reason code, scenario summary) is appended to `reports/audit_log.csv` as a cryptographically hash-chained entry. The current entry hash $H_k = \text{SHA256}(H_{k-1} \mid \text{timestamp} \mid \text{user} \mid \text{action} \mid \text{reason} \mid \text{summary})$. If any historical record is modified or deleted, $H_k \neq H_{k-1}$ checks fail during automated validation (`verify_audit_log_integrity()`), immediately flagging content tampering.

### Q18: What is the raw zonal sum population gap (~5.97%), and why is it not artificially rescaled?
**Answer**: Summing WorldPop 2020 1km constrained population raster pixels across Maharashtra's 35 district polygons yields **131,936,179**, whereas the official government projected population for 2020 is ~124,500,000 (~5.97% difference). Artificial rescaling alters raw data telemetry. Per Rule 1 (Never fabricate/alter raw data), we output raw raster sums tagged `REAL` and document the 5.97% gap as an open data sanity check.

### Q19: What would change if real-time hospital pharmacy ERP inventory data were provided?
**Answer**: Currently, baseline hospital surge stock is `ESTIMATED` from state ICU bed anchors and facility counts, and consumption rates are `ASSUMED` from WHO/Sphere literature. If real pharmacy ERP inventory records (`data/raw/pharma_data.csv`) were connected:
1. Baseline surge stocks $\text{stock}_{im}$ would update to real-time physical inventory counts.
2. Consumption rates would be empirically fitted per facility/bed using historical billing logs.
3. The optimization solver would operate on live inventory levels without requiring WHO proxy assumptions.

### Q20: How does the framework demonstrate full end-to-end reproducibility?
**Answer**: The entire pipeline is fully automated and state-agnostic:
1. `python run_all.py` executes data cleaning, real boundary verification, WorldPop zonal extraction, impact model training, CQR calibration, Monte-Carlo scenario surrogate training, OR-Tools 20-scenario optimization benchmarking, and report generation in a single command.
2. `pytest -q` runs 25 automated unit/integration tests verifying dataset integrity, non-leakage, solver constraints, audit log hash chaining, and Streamlit `AppTest` smoke tests for all pages.
3. Environment and dependencies are pinned in `requirements.txt`.
