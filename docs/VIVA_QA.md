# Disaster Healthcare AI: Comprehensive Viva & Technical Review Q&A

This document prepares project authors for academic viva voce examinations, technical code reviews, and panel defenses for **"An Explainable and Uncertainty-Aware AI Framework for Disaster Healthcare Demand Prediction and Multi-Objective Resource Allocation"**.

---

### Q1: Why is the $R^2$ of the impact prediction model on EM-DAT (~0.28) relatively low compared to synthetic benchmarks (~0.88)?
**Answer**: High $R^2$ ($\approx 0.88–0.91$) reported on synthetic datasets was a circular artifact: the labels were exact deterministic mathematical functions of the synthetic inputs, so ML models simply recovered the synthetic generator formula. CRED EM-DAT contains real, noisy historical disaster reports spanning 810 events across India over a century (1900–2026). Real disaster casualty reporting is influenced by unobserved socio-economic infrastructure, local topography, reporting biases, and event-specific management. An $R^2$ of 0.2780 on a strict time-split test set (2019+, $N=78$) represents genuine predictive signal over baseline ($R^2 = -0.0952$ for median baseline) without circular data leakage.

### Q2: Where does medical supply demand come from, and why is it not directly trained from EM-DAT?
**Answer**: EM-DAT records macro casualty figures (`Total Deaths`, `No. Injured`, `Total Affected`), but does not contain pharmaceutical or medical supply consumption. Training ML models directly on invented demand labels creates fake learning. In our framework, macro casualties are converted into daily supply demand using WHO Interagency Emergency Health Kit (IEHK 2017) and Sphere Handbook standards (`config/demand_params.yaml`), which define clinical consumption rates per patient/injured day (e.g., 2.5 antibiotic doses/day, 4.0 ORS sachets/day, 0.5 blood units/injured day).

### Q3: What is the data provenance methodology (`REAL`, `ESTIMATED`, `ASSUMED`), and why is it enforced?
**Answer**: To eliminate data fabrication and maintain scientific integrity, every dataset and figure is explicitly tagged:
- **`REAL`**: Raw public data cited directly from authoritative databases (CRED EM-DAT 1900–2026, WorldPop 2020 1km / 3 arc-sec grid at 0.00083333° pixel scale, National Health Portal India). Never imputed or altered.
- **`ESTIMATED`**: Quantities derived from real data using documented mathematical methods (e.g., district hospital bed capacity allocated from state-level 144,983 hospital bed anchors [`api/services.py`] weighted by facility counts).
- **`ASSUMED`**: Parameters sourced from WHO/Sphere literature, transport physics norms (e.g., Haversine $\times 1.3$ road circuity factor, clinical supply consumption rates), or unverified citations (e.g., Kapoor et al. (2020) state ICU bed audit citation, which is unverified from local raw files).

### Q4: Why is `Total_Num_Beds` from the National Hospital Directory CSV (`hospital_directory (1).csv`) not used directly?
**Answer**: Thorough data auditing revealed that while the National Hospital Directory contains 4,767 healthcare facilities in Maharashtra, the `Total_Num_Beds` column is non-null and valid (1–5000) for only **32 facilities** in Maharashtra (~0.67% completeness). Using this column directly would severely distort district bed capacity. Instead, we use facility counts and public/private classifications from the directory as spatial weighting factors (`REAL`), and anchor district capacities to the official state-level 11,587 ICU bed audit (`ASSUMED` citation) and 144,983 total hospital bed anchor (`ESTIMATED`).

### Q5: Why were weather features removed from impact-model training?
**Answer**: The legacy weather script generated synthetic precipitation and wind features using `numpy.random` (gamma/normal distributions), which injected uncorrelated random noise into training. When trained on time-split real EM-DAT data, adding simulated weather degraded generalization (Ridge $R^2$ dropped from 0.278 to 0.262). Removing weather features improved both $R^2$ and Spearman rank correlation ($\rho: 0.504 \rightarrow 0.520$). Real-time Open-Meteo archive fetching is retained exclusively for live What-If simulation queries (returning `NaN` on network failure, never random numbers).

### Q6: How are prediction intervals generated and validated via Conformalized Quantile Regression (CQR)?
**Answer**: Standard regression models provide only point predictions. We use CQR (Conformalized Quantile Regression) with Gradient Boosting quantiles ($q_{0.05}$ and $q_{0.95}$) calibrated on a held-out validation set ($N=71$). The non-conformity score $E_i = \max(q_{0.05}(x_i) - y_i, y_i - q_{0.95}(x_i))$ is used to compute the conformal calibration margin $Q_{1-\alpha}(E_{\text{val}})$. This guarantees finite-sample coverage distributionally. On the held-out test set ($N=78$), CQR achieves 94.9% empirical coverage for a 90% nominal target.

### Q7: Does 94.9% empirical coverage vs a 90% target mean "better calibration"?
**Answer**: No. An empirical coverage of 94.9% on a 90% nominal target indicates that the prediction intervals are **conservative** (slightly wider than strictly necessary), not better calibrated. This occurs because disaster casualties have high variance and fat-tailed distributions. A conservative interval is desirable in disaster healthcare logistics to prevent underestimating surge demand.

### Q8: What do the historical backtest ratios and CQR interval widths tell us about model capability?
**Answer**: In historical Leave-One-Event-Out backtests across 5 benchmark disasters, actual/predicted casualty ratios range from **7.7x to 1024.6x** with a median ratio of **68.8x** (predicted/actual ratios range from 0.0010 to 0.1292, median 0.0145). Log prediction interval widths span **5.58 to 6.46 orders of magnitude** (median 6.25 orders of magnitude; multiplicative factor $\approx 9.96 \times 10^5$). This demonstrates that historical disaster data exhibits high intrinsic variance. The ML model serves as a **relative risk ranker across districts and hazard types**, rather than an exact point-estimator of casualty counts.

### Q9: Why is a Random Forest surrogate classifier trained, and what does its fidelity measure?
**Answer**: The full Monte-Carlo simulation engine executes 2,000 stochastic draws per district $\times$ medicine (7,000+ calculations), taking ~1.2 to 2.5 seconds per scenario. For interactive dashboard sliders, multi-second latencies degrade user experience. The Random Forest surrogate classifier is trained on 500 Monte-Carlo scenarios to predict shortage risk levels in $< 5\text{ ms}$. Crucially, the surrogate's 91.28% accuracy measures **fidelity to the Monte-Carlo surge simulator**, NOT accuracy against unobserved real-world hospital shortages.

### Q10: How was the surrogate classifier validated to avoid optimistic bias?
**Answer**: Splitting surrogate training datasets by row causes data leakage because rows from the same disaster scenario share identical hazard parameters. We implemented **scenario-based splitting**: 500 diverse disaster scenarios were sampled, and split 80% (400 scenarios) for training and 20% (100 scenarios) for testing by `scenario_id`. On held-out scenarios under full residual model uncertainty ($\sigma \approx 3.7186$), the surrogate achieved **91.28% simulator fidelity accuracy**, **0.9085 macro F1**, and **0.0490 Expected Calibration Error (ECE)**.

### Q11: How does the OR-Tools SCIP Mixed-Integer Programming (MIP) optimization solver work?
**Answer**: The allocation problem is modeled as a multi-commodity network flow MIP solver over 35 district nodes¹ and 5 medicine classes. Integer decision variables $x_{ijm} \in \mathbb{Z}_{\ge 0}$ represent the quantity of medicine $m$ transferred from source district $i$ to destination district $j$. Slacks $u_{jm} \ge 0$ represent unmet demand, and $\theta \in [0, 1]$ represents minimum regional coverage. The solver minimizes a multi-objective function:
$$\min \sum w_{\text{unmet}} \cdot c_m \cdot u_{jm} + \sum w_{\text{cost}} \cdot d_{ij} \cdot x_{ijm} - w_{\text{fairness}} \cdot \theta$$

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

All 5 methods were evaluated through **ONE shared constraint checker** and **ONE unified cost function** ($\text{Cost Index} = \text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$).

### Q14: What were the key benchmarking results from the 20-scenario optimization study?
**Answer**: Across 20 scenarios under full residual model uncertainty ($\sigma \approx 3.7186$):
- **Unmet Demand (% of total demand across all 20 scenarios)**:
  - **OR-Tools SCIP**: Median = **0.00%**, P75 = **0.03%**, P90 = **0.39%**, Mean = **2.09%**; Cost Index = 3.41B; Route-KM = 2,451.7 km; Min Coverage = 0.812; Violations = 0.
  - **Greedy Largest Surplus**: Median = 0.00%, P75 = 0.04%, P90 = 1.93%, Mean = 2.25%; Cost Index = 6.54B; Route-KM = 3,081.3 km; Min Coverage = 0.812; Violations = 0.
  - **Greedy Nearest**: Median = 0.00%, P75 = 0.68%, P90 = 11.14%, Mean = 3.45%; Cost Index = 5.08B; Route-KM = 3,132.8 km; Min Coverage = 0.812; Violations = 0.
  - **Proportional Population**: Median = 0.00%, P75 = 3.27%, P90 = 15.97%, Mean = 5.25%; Cost Index = 17.08B; Route-KM = 20,436.5 km; Min Coverage = 0.804; Violations = 0.
  - **No Redistribution**: Median = 0.00%, P75 = 0.77%, P90 = 20.33%, Mean = 5.32%; Cost Index = 0.00; Route-KM = 0.0 km; Min Coverage = 0.800; Violations = 0.
- **Wilcoxon Signed-Rank Test Results (paired vs. OR-Tools SCIP)**:
  - vs. No Redistribution: $W = 0.0, p = 0.043114$ ($p < 0.05$)
  - vs. Proportional Population: $W = 0.0, p = 0.043114$ ($p < 0.05$)
  - vs. Greedy Nearest: $W = 0.0, p = 0.043114$ ($p < 0.05$)
  - vs. Greedy Largest Surplus: $W = 0.0, p = 0.043114$ ($p < 0.05$)
- **Restricted Scenarios (Active Shortage: No Redistribution Unmet > 0, $N=5$)**:
  - **OR-Tools SCIP**: Median = **0.20%**, P75 = **2.11%**, P90 = **24.35%**, Mean = **8.36%**; Cost Index = 13.63B; Route-KM = 9,807.0 km; Min Coverage = 0.247; Violations = 0.
  - **Greedy Largest Surplus**: Median = 1.72%, P75 = 3.84%, P90 = 25.05%, Mean = 9.02%; Cost Index = 26.15B; Route-KM = 12,325.4 km; Min Coverage = 0.247; Violations = 0.
  - **Greedy Nearest**: Median = 11.05%, P75 = 11.95%, P90 = 28.29%, Mean = 13.81%; Cost Index = 20.33B; Route-KM = 12,531.1 km; Min Coverage = 0.247; Violations = 0.
  - **Proportional Population**: Median = 15.71%, P75 = 18.28%, P90 = 32.67%, Mean = 20.99%; Cost Index = 68.32B; Route-KM = 81,746.2 km; Min Coverage = 0.215; Violations = 0.
  - **No Redistribution**: Median = 19.61%, P75 = 26.83%, P90 = 38.62%, Mean = 21.27%; Cost Index = 0.00; Route-KM = 0.0 km; Min Coverage = 0.199; Violations = 0.
- **Cost Clarification**: OR-Tools SCIP is NOT lowest cost overall (No Redistribution has 0 cost). However, OR-Tools SCIP achieves the lowest unmet demand (2.09% mean) and lowest cost index *among active greedy redistribution heuristics* (cheaper than Greedy Nearest 5.08B and Greedy Largest Surplus 6.54B).

### Q15: What is the difference between `unit_km` and `route_km`?
**Answer**:
- `unit_km`: The sum of $(\text{quantity} \times \text{distance\_km})$ over all transferred medical items. Measures total freight-distance work done.
- `route_km`: The sum of distinct physical route distances $\text{distance\_km}(i, j)$ for active dispatch routes ($x_{ij} > 0$). Measures total road network coverage.

### Q16: How is Haversine distance adjusted for real-world road networks?
**Answer**: Direct lat/lon distance (great-circle Haversine) underestimates actual road driving distance due to terrain, river crossings, and road winding. We multiply Haversine distance by a **1.3 circuity factor** ($\text{distance\_km} = \text{Haversine} \times 1.3$), tagged as `ASSUMED` transport physics.

### Q17: How does the SHA-256 audit log ensure tamper-evident governance?
**Answer**: Every human officer review action (Approve/Reject decision, reviewer role, reason code, scenario summary) is appended to the audit ledger as a cryptographically hash-chained entry. The current entry hash $H_k = \text{SHA256}(H_{k-1} \mid \text{timestamp} \mid \text{user} \mid \text{action} \mid \text{reason} \mid \text{summary})$. If any historical record is modified or deleted, $H_k \neq H_{k-1}$ checks fail during automated validation (`verify_audit_log_integrity()`), immediately flagging content tampering.

### Q18: What is the raw zonal sum population gap (~5.97%), and why is it not artificially rescaled?
**Answer**: Summing WorldPop 2020 1km / 3 arc-sec constrained population raster pixels (resolution 0.00083333° in EPSG:4326) across Maharashtra's 35 district polygons yields **131,936,179**, whereas the official government projected population for 2020 is ~124,500,000 (~5.97% difference). Artificial rescaling alters raw data telemetry. Per Rule 1 (Never fabricate/alter raw data), we output raw raster sums tagged `REAL` and document the 5.97% gap as an open data sanity check.

### Q19: What would change if real-time hospital pharmacy ERP inventory data were provided?
**Answer**: Currently, baseline hospital surge stock is `ESTIMATED` from state hospital bed anchors (144,983 beds) and facility counts, and consumption rates are `ASSUMED` from WHO/Sphere literature. If real pharmacy ERP inventory records were connected:
1. Baseline surge stocks $\text{stock}_{im}$ would update to real-time physical inventory counts.
2. Consumption rates would be empirically fitted per facility/bed using historical billing logs.
3. The optimization solver would operate on live inventory levels without requiring WHO proxy assumptions.

### Q20: How does the framework demonstrate full end-to-end reproducibility?
**Answer**: The entire pipeline is fully automated and state-agnostic:
1. `python run_all.py` executes data cleaning, real boundary verification, WorldPop zonal extraction, impact model training, CQR calibration, Monte-Carlo scenario surrogate training, OR-Tools 20-scenario optimization benchmarking, and report generation in a single command.
2. `pytest -q` runs 52 automated Python tests verifying dataset integrity, non-leakage, solver constraints, audit log hash chaining, security validation, and REST endpoints.
3. Environment and dependencies are pinned in `requirements.txt` and `requirements-api.txt`.

---

### Q21: Why was a decoupled FastAPI + React architecture chosen over a monolithic dashboard?
**Answer**: While a monolithic Streamlit dashboard is effective for quick prototypes, real-world emergency logistics systems require:
1. **Decoupled Client-Server Separation**: Multiple emergency coordination nodes (mobile units, district control rooms, state disaster headquarters) can consume the same centralized optimization engine via REST APIs.
2. **Stateless Scalability**: Heavy ML and MIP solving workloads can be scaled independently of static UI asset delivery.
3. **Strict Type Safety & Frontend Performance**: React 18 + TypeScript + Vite provides instant UI state transitions, component-level caching, and compile-time contract validation against backend OpenAPI schemas.

### Q22: How does the JWT authentication and Role-Based Access Control (RBAC) work?
**Answer**: The backend implements JSON Web Tokens (JWT) using HMAC-SHA256 (`HS256`) with salted `bcrypt` password hashing:
- Users log in via `POST /api/auth/login` with credentials and receive a signed Bearer token containing user ID, email, and role.
- FastAPI dependency injection (`require_role(["coordinator", "admin"])`) enforces fine-grained RBAC: `viewer` accounts can query simulation and allocation data, while only `coordinator` and `admin` accounts can append decisions to the audit ledger.
- Sliding-window in-memory rate limiters protect sensitive auth endpoints (20 req/min) and computationally intensive simulation endpoints (10 req/min).

### Q23: Why does the system enforce an automated safety interlock blocking `APPROVE` decisions below 0.60 confidence with HTTP 409?
**Answer**: In safety-critical disaster healthcare management, AI recommendations with low confidence (e.g., severe data scarcity or extreme tail hazard values) must not be rubber-stamped. When an officer attempts to record an `APPROVE` action on a scenario where the model confidence score is $< 0.60$, the API immediately aborts with **HTTP 409 Conflict**. The officer is forced by policy to either select `MODIFY` (with clinical adjustments) or `REJECT` (escalating to manual command protocols).

### Q24: How does the simulator prevent impossible casualty numbers in low-population districts?
**Answer**: In earlier synthetic prototypes, high-magnitude disaster draws could generate simulated casualty counts exceeding the actual resident population of a district. Our engine strictly enforces a physical invariant:
$$\text{Simulated Casualties} = \min(\text{Sampled Casualties}, \text{District Population})$$
This guarantees that no district can ever simulate more patients than its actual WorldPop resident count, preserving physical realism.

### Q25: Why is logistics cost strictly reported as a "Cost Index" rather than currency (₹ / INR)?
**Answer**: Actual monetary costs for emergency medical transport involve complex, fluctuating variables: negotiated government carrier rates, cold-chain electricity surcharges, toll waivers, and dynamic fuel prices. Claiming exact rupee figures without verified commercial contracts would be scientifically ungrounded. We compute a standardized, unitless **Cost Index** ($\text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$) which weights physical freight work ($15.0$ per unit-km) and dispatch route fixed overhead ($500.0$ per active route) to compare solver policies fairly.

---

### Q26: How are contributors divided across project modules?
**Answer**:
- **[YOUR NAME]**: ML pipeline, data layer, optimiser, validation
- **[TEAMMATE NAME]**: API, authentication, React frontend, Docker

### Q27: What are the primary scientific limitations of this system?
**Answer**:
1. **Centroid-Level Resolution**: Inter-district transportation is computed over 35 district centroid nodes rather than individual facility lat/lon coordinates.
2. **Circuity Distance Proxy**: Haversine $\times 1.3$ factor is an assumed geometric multiplier (`ASSUMED`) rather than live GPS / OpenStreetMap network routing telemetry.
3. **State Bed Anchor Scaling**: District hospital bed capacity is estimated by scaling analyst-specified ESTIMATED total of 144,983 state hospital beds by facility counts, rather than live hospital ERP inventory tracking.
4. **Interval Widths**: Multiplicative log interval widths ($\sim 10^6$) reflect high intrinsic historical variance; the model acts as a risk ranker rather than exact casualty predictor.
5. **Tail Underestimation**: Point predictions underestimate severe tail disasters (historical actual/predicted casualty ratios up to 1024x).

### Q28: How does the current verified framework compare against legacy synthetic claims?
**Answer**:
- **Data Foundation**: Replaced synthetic random arrays with real CRED EM-DAT (1900–2026), WorldPop 2020 1km grid, and National Health Portal facilities.
- **Predictive Performance**: Replaced circular synthetic $R^2 \approx 0.88–0.99$ claims with honest time-split real metrics ($R^2 = 0.2780$, MAE $= 2.8812$, Spearman $\rho = 0.5199$).
- **Optimiser Claims**: Replaced "OR-Tools lowest cost overall" with honest multi-objective benchmarking (OR-Tools SCIP achieves lowest mean unmet demand [2.09%] and lowest Cost Index among active greedy heuristics [3.41B Cost Index units]).
- **Surrogate Scope**: Clarified that RF surrogate accuracy (93.11%) measures fidelity to the Monte-Carlo surge simulator, NOT accuracy against unobserved real shortages.

---

¹ *Footnote on District Count*: Maharashtra officially comprises 36 administrative districts. In this analytical framework, Mumbai City and Mumbai Suburban are consolidated into a single "Mumbai" spatial node, yielding 35 analytical district nodes.
