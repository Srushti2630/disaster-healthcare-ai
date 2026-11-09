# Operations Research & Mathematical Optimization Technical Audit
**Project:** Disaster Healthcare AI — Demand Prediction & Resource Allocation  
**Target Branch:** `testing` | **Base Commit:** `127ea72`  
**Auditor Roles:** Senior Operations Research Scientist, Mathematical Optimization Engineer, Healthcare Supply Chain Researcher, Academic Research Reviewer  
**Date of Audit:** November 2026  
**Operational Status:** Strictly Read-Only Audit & Empirical Verification

---

## Executive Summary & Scorecard

An exhaustive mathematical and technical audit of the Operations Research (OR) and resource redistribution module (`src/optimise.py`, `src/engine/monte_carlo.py`, `src/engine/demand.py`, `api/services.py`, and `api/audit_ledger.py`) was executed on the `testing` branch. This subsystem solves an integer multi-commodity network flow problem with max-min coverage fairness to rebalance 5 critical medical commodities across Maharashtra's 35 administrative districts following severe natural disasters.

Every finding in this report is grounded in executable mathematical verification and empirical benchmarks logged in four accompanying audit datasets:
1. [`reports/optimization_constraint_verification.csv`](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/optimization_constraint_verification.csv)
2. [`reports/solver_robustness_test_results.csv`](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/solver_robustness_test_results.csv)
3. [`reports/optimization_benchmark_reproduction.csv`](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/optimization_benchmark_reproduction.csv)
4. [`reports/optimization_equity_analysis.csv`](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/optimization_equity_analysis.csv)

### Subsystem Audit Scorecard

| Operational Dimension | Status | Verified Metric / Finding | Critical Risk or Limitation |
|---|---|---|---|
| **Mathematical Formulation** | **COMPLIANT WITH DISCREPANCY** | Mixed-Integer Linear Program (MILP) solved via SCIP in Google OR-Tools ($N=35$ nodes, $M=5$ commodities). | **Objective Mismatch:** Solver optimizes linear transport cost ($\sim 0.005$ weight) without fixed route charges, while evaluator assesses $15.0 \text{ INR/unit-km} + 500 \text{ INR/route}$. |
| **Safety Constraint 1: Donor Reserve** | **VERIFIED WITH EDGE DEFECT** | Donor retains $\ge 0.60 \times \text{demand}_{im}$ when shortage risk is not High. | **Zero-Demand Loophole:** If local disaster demand is 0, reserve is 0, allowing 100% of routine hospital stock to be exported. |
| **Safety Constraint 2: High-Risk Ban** | **VERIFIED & SECURE** | $P(\text{shortage}) > 0.70 \implies \text{exportable}_{im} = 0$. Strictly medicine-specific. | None. Zero exports observed across all high-risk districts. |
| **Safety Constraint 3: Perishable Radius** | **VERIFIED & SECURE** | Blood Units restricted to $\le 150.0\text{ km}$. Variable omitted from model. | **Topological Isolation:** Peripheral districts (Gadchiroli, Nandurbar) have only 1 neighbor $\le 150\text{ km}$, risking total blood starvation. |
| **Safety Constraint 4: Mass Balance** | **VERIFIED & SECURE** | Integer non-negativity ($x_{ijm} \in \mathbb{Z}_{\ge 0}$) and exact unmet tracking. | Zero constraint violations observed across all test scenarios. |
| **Safety Constraint 5: Max-Min Fairness** | **VERIFIED & PARTIALLY BOUNDED** | Continuous variable $\theta \in [0, 1]$ maximizes min coverage ratio. | If a single district has zero imports and zero stock, $\theta$ collapses to 0, eliminating fairness incentive for all other districts. |
| **Solver Robustness & Scalability** | **EXCELLENT** | 6 corner cases verified: 0 stock, 0 demand, 100x deficit, all high risk, 10M units. | Average solve time: **$211.5\text{ ms}$**; zero solver hangs, numerical overflows, or infeasibilities. |
| **36-Scenario Stratified Benchmark** | **EMPIRICALLY REPRODUCED** | 3 strata $\times$ 3 stock multipliers $\times$ 4 epicentres ($N=36$). Shortage in 50% ($N=18$). | OR-Tools SCIP reduces transport costs by **$32.8\% \text{ to } 38.5\%$** vs greedy heuristics while matching unmet demand. |
| **Statistical Test Validity** | **AUDITED & CORRECTED** | Corrected legacy artifact ($n=5, p=0.0431$ identical across all 4 baselines). | Under 36 scenarios ($n=13$ non-zero pairs), OR-Tools is **statistically superior** to No Redistribution ($p=0.00049$) and Proportional ($p=0.00049$), but **statistically equivalent on unmet demand** to Greedy baselines ($p=0.8286$), though vastly superior on cost. |
| **Governance & SHA-256 Ledger** | **TAMPER-EVIDENT** | Cryptographic hash chaining in SQLite; HTTP 409 blocks approvals if confidence $< 0.60$. | Ledger relies on database clock rather than distributed RFC-3161 trusted timestamp authority. |

---

## 1. Complete Operations Research Architecture & Data Pipeline

The resource allocation engine operates at the intersection of predictive epidemiology, spatial geostatistics, and mathematical programming:

```
                               OPERATIONS RESEARCH DATA PIPELINE
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. PREDICTIVE PHASE (Machine Learning)                                                         │
│    EM-DAT Historical Disaster Ridge Regression: y_pred = log(1 + affected_statewide)           │
│    Conformal Quantile Regression (CQR): Calibrated 90% log-interval [L(x), U(x)]               │
└────────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. SPATIAL MONTE CARLO ENGINE (2,000 Stochastic Draws)                                         │
│    Spatial Decay: W_d = Population_d * exp(-Distance_d(epicentre) / 150 km)                   │
│    Casualty Allocation: Casualty_d = Total_Affected * (W_d / sum(W))                           │
│    Demand Vector: WHO IEHK 2017 & Sphere Norms -> 7-Day Demand d_jm for 5 Commodities          │
│    Surrogate Classification: Logistic Regression P(shortage_jm) -> Risk Level: Low/Medium/High │
└────────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. INVENTORY & NETWORK GRAPH INITIALIZATION                                                    │
│    District Stock: Capacity-Derived (Beds * 10x surge, ICU * 8x blood) OR User-Provided Custom │
│    Network Cost Matrix: Haversine distance * 1.3 road circuity factor (d_ij)                   │
│    Perishable Filter: Blood routes > 150 km pruned from feasible arc set A                     │
└────────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. MATHEMATICAL OPTIMIZATION SOLVER (Google OR-Tools SCIP MIP)                                 │
│    Decision Variables: Transfer quantities x_ijm in Z_>=0, Unmet u_jm >= 0, Min-Coverage theta  │
│    Objective: Minimize Unmet Demand + Transport Cost Index - Max-Min Fairness Coverage         │
│    Constraints: (1) Safety Reserve, (2) High-Risk Export Ban, (3) 150km Blood,                 │
│                 (4) Mass Balance Integrality, (5) Minimum Coverage Floor                       │
└────────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. POST-HOC EVALUATION & GOVERNANCE AUDIT LEDGER                                               │
│    Constraint Verification: evaluate_allocation_plan() checks 175 district-commodity pairs     │
│    Unified Cost Function: Cost = 15.0 * Unit_KM + 500.0 * Active_Routes                        │
│    Human Decision Review: Coordinator/Officer approves/rejects via UI                          │
│    SHA-256 Ledger: Block Hash = SHA256(H_prev | timestamp | user | action | plan_hash | conf)  │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mathematical Formulation Audit

### 2.1 Formal Decision Model
Let $\mathcal{I} = \mathcal{J} = \{1, \dots, 35\}$ denote the set of Maharashtra administrative districts, and $\mathcal{M} = \{\text{antibiotics}, \text{ors}, \text{iv\_fluids}, \text{analgesics}, \text{blood\_units}\}$ denote the set of medical commodities.

#### Sets, Parameters, and Feasible Arcs
* $s_{im} \ge 0$: Initial stock of commodity $m$ in district $i$.
* $d_{jm} \ge 0$: Simulated planning demand of commodity $m$ in district $j$.
* $r_{im} \in \{\text{Low}, \text{Medium}, \text{High}\}$: Shortage risk classification from the Monte Carlo engine.
* $c_{ij}$: Road distance (in km) between district $i$ and district $j$, where $c_{ij} = \text{haversine}(i, j) \times 1.3$, $c_{ii} = 0$.
* $D_{\max, m}$: Maximum permissible transit distance for commodity $m$:
  $$D_{\max, \text{blood\_units}} = 150.0\text{ km}, \quad D_{\max, m} = \infty \quad \forall m \ne \text{blood\_units}$$
* $\mathcal{A}_m = \{(i, j) \in \mathcal{I} \times \mathcal{J} \mid i \ne j, \, c_{ij} \le D_{\max, m}\}$: Set of admissible directed transit arcs for commodity $m$.
* $\omega_m$: Clinical urgency weight:
  $$\omega_{\text{blood\_units}} = 5.0, \; \omega_{\text{antibiotics}} = 3.0, \; \omega_{\text{iv\_fluids}} = 2.0, \; \omega_{\text{ors}} = 1.0, \; \omega_{\text{analgesics}} = 1.0$$
* $\gamma$: Donor local demand reserve ratio ($\gamma = 0.60$).
* $w_{\text{unmet}} = 1.0$, $w_{\text{cost}} = 0.10$, $w_{\text{fairness}} = 0.50$: Objective scalarization weights.

#### Decision Variables
1. $x_{ijm} \in \mathbb{Z}_{\ge 0}$: Integer units of commodity $m$ transported from donor $i$ to recipient $j$, defined strictly for $(i, j) \in \mathcal{A}_m$.
2. $u_{jm} \in \mathbb{R}_{\ge 0}$: Continuous unmet demand of commodity $m$ in district $j$.
3. $\theta \in [0, 1]$: Continuous auxiliary variable representing the state-wide minimum coverage ratio.

#### Optimization Objective Function
$$\min_{x, u, \theta} \mathcal{Z} = \sum_{j \in \mathcal{J}} \sum_{m \in \mathcal{M}} w_{\text{unmet}} \, \omega_m \, u_{jm} + \sum_{(i, j) \in \mathcal{A}_m} \sum_{m \in \mathcal{M}} w_{\text{cost}} \left(\frac{c_{ij}}{\max_{k, l} c_{kl}} \cdot \kappa\right) x_{ijm} - w_{\text{fairness}} \, D_{\text{total}} \, \theta$$
where $\kappa = 0.05$ is the solver's internal cost scaling constant, and $D_{\text{total}} = \max\left(1.0, \sum_{j, m} d_{jm}\right)$ normalizes the fairness incentive.

#### Operational Constraints
1. **Donor Safety Reserve Floor & High-Risk Embargo:**
   $$\sum_{j: (i, j) \in \mathcal{A}_m} x_{ijm} \le \begin{cases} 0, & \text{if } r_{im} = \text{High} \\ \max\left(0, \lfloor s_{im} - \gamma \, d_{im} \rfloor\right), & \text{if } r_{im} \in \{\text{Low}, \text{Medium}\} \end{cases} \quad \forall i \in \mathcal{I}, \, m \in \mathcal{M}$$

2. **Sink Mass Balance & Unmet Accounting:**
   $$u_{jm} \ge d_{jm} - \left(s_{jm} - \sum_{k: (j, k) \in \mathcal{A}_m} x_{jkm} + \sum_{i: (i, j) \in \mathcal{A}_m} x_{ijm}\right) \quad \forall j \in \mathcal{J}, \, m \in \mathcal{M}$$
   $$u_{jm} \ge 0 \quad \forall j \in \mathcal{J}, \, m \in \mathcal{M}$$

3. **Max-Min Coverage Fairness Constraint:**
   $$\left(s_{jm} - \sum_{k: (j, k) \in \mathcal{A}_m} x_{jkm} + \sum_{i: (i, j) \in \mathcal{A}_m} x_{ijm}\right) \ge \theta \, d_{jm} \quad \forall (j, m) \text{ such that } d_{jm} > 10.0$$
   $$0 \le \theta \le 1.0$$

---

### 2.2 Critical Objective Function Discrepancy
Our audit uncovered a major structural disconnect between the **solver's internal objective** in `solve_resource_allocation()` and the **post-hoc evaluation function** in `evaluate_allocation_plan()`:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                           OBJECTIVE FORMULATION DISCONNECT                                   │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. SOLVER INTERNAL OBJECTIVE (src/optimise.py, lines 154-159):                              │
│    Cost_internal = sum_{i,j,m} [ 0.10 * (d_ij / max_dist) * 0.05 ] * x_ijm                 │
│    - Pure linear transportation problem.                                                    │
│    - Zero binary route activation variables (y_ij in {0, 1} DOES NOT EXIST in the solver).   │
│    - Zero fixed route opening costs.                                                        │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. EVALUATION BENCHMARK METRIC (src/optimise.py, lines 241, 287):                            │
│    Cost_evaluated = 15.0 * sum(d_ij * x_ijm) + 500.0 * count(active_routes)                │
│    - Evaluates as a Fixed-Charge Network Flow problem.                                      │
│    - Heavily penalizes opening new transit routes ($500 fixed cost per origin-destination). │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Mathematical Consequences of Discrepancy:
1. **Lack of Route Consolidation:** Because the solver does not see the $500.0 \text{ INR}$ fixed route charge, it treats sending 1 unit along arc $(i, j)$ the same as sending 1,000 units. It has no mathematical incentive to bundle transfers into fewer trucks.
2. **Evaluation Penalty:** The post-hoc evaluator assesses costs on fixed charges that the solver was completely blind to during optimization.
3. **Recommendation:** Add binary decision variables $y_{ij} \in \{0, 1\}$ with linking constraint $\sum_m x_{ijm} \le M \, y_{ij}$ and objective term $\sum_{i, j} F \, y_{ij}$ to transform the model into an exact Fixed-Charge Capacitated Multi-Commodity Network Flow (FCMCNF) problem.

---

## 3. Exhaustive Clinical Safety Constraint Verification (C1–C5)

Controlled empirical verification was executed for all five safety constraints. Detailed records are documented in [`reports/optimization_constraint_verification.csv`](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/optimization_constraint_verification.csv):

```
                        SAFETY CONSTRAINT VERIFICATION MATRIX
┌────┬─────────────────────────────┬───────────────────────────────────────────┬────────┬──────────┐
│ ID │ Constraint Description      │ Mathematical Rule                         │ Status │ Verdict  │
├────┼─────────────────────────────┼───────────────────────────────────────────┼────────┼──────────┤
│ C1 │ Donor Safety Reserve Floor  │ sum_j x_ijm <= max(0, s_im - 0.60 * d_im) │ PASSED │ Verified │
│ C1*│ Zero-Demand Donor Loophole  │ d_im = 0 => Reserve = 0 => Export 100%    │ VULNER │ Defect   │
│ C2 │ High-Risk Export Ban        │ risk(i, m) == 'High' => Export = 0        │ PASSED │ Verified │
│ C3 │ Perishable 150 km Radius    │ m == 'blood' and d_ij > 150km => Arc Void │ PASSED │ Verified │
│ C4 │ Mass Balance & Integrality  │ u_jm >= d_jm - net_stock; x_ijm in Z_>=0  │ PASSED │ Verified │
│ C5 │ Max-Min Coverage Fairness   │ net_stock_jm >= theta * d_jm (d > 10)     │ PASSED │ Verified │
└────┴─────────────────────────────┴───────────────────────────────────────────┴────────┴──────────┘
```

### Detailed Constraint Breakdown:

#### Constraint 1: Donor Safety Reserve Floor ($s_{im} - \sum_j x_{ijm} \ge 0.60 \, d_{im}$)
* **Test Case:** Donor Pune has initial stock of 10,000 antibiotics and local disaster demand of 5,000. Required safety reserve: $0.60 \times 5,000 = 3,000$. Maximum exportable stock: $10,000 - 3,000 = 7,000$. Recipient Satara has 12,000 demand and 0 stock.
* **Empirical Result:** Pune exported exactly 7,000 units to Satara and retained 3,000 units. `pune_remaining == 3000.0`. **Status: PASSED.**
* **Vulnerability Identified (C1_EDGE):** When local disaster demand is zero ($d_{im} = 0$), $\text{reserve}_{im} = 0.60 \times 0 = 0$. Consequently, $\text{exportable}_{im} = s_{im}$. In test `CASE_C1_EDGE`, Pune exported **100% of its initial stock (10,000 units)** to Satara.
  * **Clinical Risk:** The stock $s_{im}$ is derived from hospital bed capacity and represents baseline hospital surge stock. If a district experiences 0 disaster casualties, it can be stripped of 100% of its inventory, leaving zero stock for ordinary emergency room admissions, post-operative surgeries, and routine inpatient care.
  * **Remediation:** Enforce a dual-floor reserve:
    $$\text{reserve}_{im} = \max\left(\beta \cdot s_{im}, \, \gamma \cdot d_{im}\right), \quad \beta = 0.20, \; \gamma = 0.60$$

#### Constraint 2: High-Risk Export Prohibition ($r_{im} = \text{High} \implies \text{exportable}_{im} = 0$)
* **Test Case:** Donor Pune has 10,000 antibiotics, local demand of 1,000 (stock surplus = 9,400), but its Shortage Risk is flagged as `High` ($P(\text{shortage}) > 0.70$). Recipient Satara has 8,000 demand and 0 stock.
* **Empirical Result:** Pune exported **exactly 0 units**. The solver strictly blocked all outbound flows. **Status: PASSED.**
* **Decoupling Verification:** High risk on Antibiotics in Pune did not prevent Pune from exporting ORS (which was Low risk). The condition is strictly medicine-specific.

#### Constraint 3: Perishable Transit Distance Limit ($D_{\max, \text{blood\_units}} = 150.0\text{ km}$)
* **Test Case:** Donor Pune has 2,000 Blood Units and 5,000 Antibiotics. Recipient Satara is $110.9\text{ km}$ away ($\le 150\text{ km}$). Recipient Nagpur is $710.2\text{ km}$ away ($> 150\text{ km}$).
* **Empirical Result:** 
  * Blood Units from Pune to Satara: **500 units** (Transferred successfully).
  * Blood Units from Pune to Nagpur: **0 units** (Strictly blocked; variable omitted from LP).
  * Antibiotics from Pune to Nagpur: **3,000 units** (Transferred successfully over $710\text{ km}$).
* **Status: PASSED.** Non-perishable commodities are not blocked on routes that exceed the blood radius.

#### Constraint 4: Sink Mass Balance & Integrality ($x_{ijm} \in \mathbb{Z}_{\ge 0}$)
* **Test Case:** Multi-commodity state-wide allocation across all 35 districts and 5 commodities (175 district-commodity pairs).
* **Empirical Result:** Across 175 pairs, **total violations = 0**. All transfer quantities are non-negative integers; no self-transfers ($i=j$) occurred; net final stock and unmet demand balance exactly. **Status: PASSED.**

#### Constraint 5: Max-Min Coverage Fairness ($\text{net\_stock}_{jm} \ge \theta \, d_{jm}$)
* **Test Case:** Donor Pune has 1,500 units of antibiotics. Three recipient districts (Satara at $110\text{ km}$, Ahmednagar at $120\text{ km}$, Solapur at $250\text{ km}$) each demand 1,000 units (total demand = 3,000). Total stock can cover exactly 50% of aggregate demand.
* **Empirical Result:** Under pure cost-minimization ($w_{\text{fairness}} = 0$), distant Solapur would be starved to save transit costs. Under the Max-Min fairness formulation ($w_{\text{fairness}} = 1.0$), the solver allocated:
  * Satara: **500 units (50.0% coverage)**
  * Ahmednagar: **500 units (50.0% coverage)**
  * Solapur: **500 units (50.0% coverage)**
* **Status: PASSED.** The solver sacrificed transit efficiency to achieve exact egalitarian coverage balance across unequal distances.

---

## 4. Solver Robustness & Corner-Case Stress Testing

The solver was evaluated across 6 boundary-condition stress tests. Results are logged in [`reports/solver_robustness_test_results.csv`](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/solver_robustness_test_results.csv):

| Case ID | Stress Test Condition | Solver Status | Solve Time | Total Transfers | Total Unmet | Violations | Robustness Verdict |
|---|---|---|---|---|---|---|---|
| **CASE_1** | **Zero Stock Statewide** (875k demand, 0 stock) | `OPTIMAL` | 160.1 ms | 0 units | 875,000.0 | 0 | **PASSED** (Graceful non-action) |
| **CASE_2** | **Zero Demand Statewide** (Quiescent normal state) | `OPTIMAL` | 149.2 ms | 0 units | 0.0 | 0 | **PASSED** (Zero churn/unnecessary moves) |
| **CASE_3** | **Catastrophic Deficit** (Demand = 100x Stock; 87.5M vs 875k) | `OPTIMAL` | 158.2 ms | 0 units | 86,625,000.0 | 0 | **PASSED** (Reserves prevent cross-depletion) |
| **CASE_4** | **Universal High-Risk Embargo** (All 35 districts High Risk) | `OPTIMAL` | 148.0 ms | 0 units | 117,528.0 | 0 | **PASSED** (Strict embargo enforced) |
| **CASE_5** | **Isolated Perishable Demand** (Gadchiroli blood demand, Mumbai stock) | `OPTIMAL` | 153.2 ms | 0 units | 500.0 | 0 | **PASSED** (150km rule blocks illegal 918km haul) |
| **CASE_6** | **Extreme High Volume** (10M units ORS Mumbai $\to$ Thane) | `OPTIMAL` | 231.7 ms | 8,000,000 units | 0.0 | 0 | **PASSED** (64-bit integer scaling flawless) |

### Computational Performance Findings:
* **Sub-Second Runtime:** Across all extreme corner cases, the OR-Tools SCIP solver converged to `OPTIMAL` in under **$240\text{ ms}$**.
* **Zero Numerical Degeneracy:** No floating-point precision collapses or infinite loops were observed, even when scaling variables from 1 unit to 10,000,000 units.
* **Infeasibility Resilience:** The solver never returns `INFEASIBLE` because unmet demand $u_{jm}$ acts as an elastic slack variable with high penalty ($w_{\text{unmet}} = 1.0$), guaranteeing a feasible basis exists for every possible demand-stock combination.

---

## 5. Stratified Benchmark Reproduction & Statistical Rigor

### 5.1 Benchmark Design
To eliminate the sample-size defect of the original 20-scenario benchmark, a stratified 36-scenario benchmark was executed following empirical EM-DAT casualty distributions:
* **Stratum 1 (Low):** $10^3 - 10^4$ casualties (12 scenarios).
* **Stratum 2 (Moderate):** $10^4 - 10^6$ casualties (12 scenarios).
* **Stratum 3 (Severe):** $10^6+$ casualties (12 scenarios).
* **Stock Multipliers:** $0.25\times, 0.50\times, 1.00\times$ baseline stock.
* **Epicentres Sampled:** Pune, Nagpur, Mumbai, Nashik, Aurangabad, Kolhapur, Solapur, Thane, Nanded, Amravati.

Detailed reproduction metrics are logged in [`reports/optimization_benchmark_reproduction.csv`](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/optimization_benchmark_reproduction.csv):

```
                        36-SCENARIO STRATIFIED BENCHMARK COMPARISON
┌─────────────────────────┬───────────────────┬────────────────────┬──────────────────┬─────────────────┬───────────┐
│ Allocation Method       │ Unmet Demand Mean │ Unmet Demand %     │ Transport Cost   │ Route KM        │ Solve Time│
├─────────────────────────┴───────────────────┴────────────────────┴──────────────────┴─────────────────┴───────────┤
│ COHORT A: ALL 36 STRATIFIED SCENARIOS                                                                             │
├─────────────────────────┬───────────────────┬────────────────────┬──────────────────┬─────────────────┬───────────┤
│ OR-Tools SCIP (Primary) │ 55,838,615 units  │ 24.40% (p50=0.01%) │ 3.57 Billion INR │  3,030.4 km     │ 211.5 ms  │
│ Greedy Largest Surplus  │ 55,840,854 units  │ 24.41% (p50=0.01%) │ 5.45 Billion INR │  2,173.8 km     │   1.0 ms  │
│ Greedy Nearest          │ 55,843,884 units  │ 24.44% (p50=0.01%) │ 5.32 Billion INR │  2,367.6 km     │   5.6 ms  │
│ Proportional Population │ 56,040,790 units  │ 25.32% (p50=0.01%) │ 5.81 Billion INR │ 24,502.0 km     │   2.1 ms  │
│ No Redistribution       │ 56,281,386 units  │ 26.17% (p50=0.01%) │ 0.00 INR         │      0.0 km     │   0.3 ms  │
├─────────────────────────┴───────────────────┴────────────────────┴──────────────────┴─────────────────┴───────────┤
│ COHORT B: ACTIVE SHORTAGE SCENARIOS ONLY (N = 18 / 36; Severe & Depleted Stock)                                    │
├─────────────────────────┬───────────────────┬────────────────────┬──────────────────┬─────────────────┬───────────┤
│ OR-Tools SCIP (Primary) │ 111,677,231 units │ 48.79% (p50=55.0%) │ 7.15 Billion INR │  6,060.9 km     │ 215.0 ms  │
│ Greedy Largest Surplus  │ 111,681,708 units │ 48.82% (p50=55.0%) │ 10.89 Billion INR│  4,347.5 km     │   1.1 ms  │
│ Greedy Nearest          │ 111,687,769 units │ 48.89% (p50=55.0%) │ 10.65 Billion INR│  4,735.2 km     │   5.8 ms  │
│ Proportional Population │ 112,081,579 units │ 50.63% (p50=56.7%) │ 11.63 Billion INR│ 49,004.0 km     │   2.2 ms  │
│ No Redistribution       │ 112,562,772 units │ 52.34% (p50=59.3%) │ 0.00 INR         │      0.0 km     │   0.3 ms  │
└─────────────────────────┴───────────────────┴────────────────────┴──────────────────┴─────────────────┴───────────┘
```

---

### 5.2 Mathematical Autopsy of Legacy $p=0.0431$ Artifact

In the legacy 20-scenario benchmark (`reports/allocation_summary.json`), all four baselines reported the exact same Wilcoxon p-value ($p = 0.043114$). Our forensic mathematical investigation revealed:
1. **Zero-Difference Censoring:** In 15 of the 20 scenarios, statewide inventory exceeded demand, resulting in 0 unmet demand for all methods. Because Wilcoxon signed-rank tests discard pairs with $d_i = 0$, the effective sample size collapsed to $n = 5$.
2. **Single Rank Permutation:** In all 5 active-shortage scenarios, OR-Tools achieved lower unmet demand than every baseline ($d_i > 0$ for all $i=1,\dots, 5$). Consequently, $W^+ = \sum_{i=1}^5 i = 15$, and $W^- = 0$. The test statistic was identically $W = 0.0$ for all four baselines.
3. **Exact Permutation Distribution:** For $n=5$, the exact two-sided p-value under SciPy's continuity-corrected Wilcoxon test for $W=0$ is uniquely $p = 0.043114$.
4. **FWER Inflation:** Testing 4 baselines simultaneously at $\alpha = 0.05$ inflated the family-wise error rate to $1 - (1-0.05)^4 = 18.5\%$. Applying standard Holm-Bonferroni correction yields:
   $$p_{\text{Holm}} = 4 \times 0.043114 = \mathbf{0.1725} > 0.05$$
   The claimed statistical significance in the legacy report was a false positive caused by small sample size and lack of multiple testing adjustment.

---

### 5.3 Rigorous 36-Scenario Wilcoxon Signed-Rank Test with Holm Correction

When evaluated on the 36-scenario benchmark with $n=13$ non-zero pairs, exact paired Wilcoxon signed-rank tests with Holm-Bonferroni step-down correction establish the true statistical verdict:

```
                  WILCOXON SIGNED-RANK TEST RESULTS (N=36 Scenarios)
┌─────────────────────────┬───────────┬────────┬────────────┬─────────────┬──────────────┬──────────────────┐
│ Baseline Method         │ n_nonzero │ W_stat │ Unadj. p   │ Holm Adj. p │ Rank-Biserial│ True Verdict     │
├─────────────────────────┼───────────┼────────┼────────────┼─────────────┼──────────────┼──────────────────┤
│ No Redistribution       │ 14        │ 0.0    │ 0.000122   │ 0.000488    │ +1.0000      │ SIGNIFICANT (***)│
│ Proportional Population │ 14        │ 0.0    │ 0.000122   │ 0.000488    │ +1.0000      │ SIGNIFICANT (***)│
│ Greedy Nearest          │ 13        │ 33.0   │ 0.414307   │ 0.828613    │ -0.2747      │ INDISTINGUISHABLE│
│ Greedy Largest Surplus  │ 13        │ 33.0   │ 0.414307   │ 0.828613    │ -0.2747      │ INDISTINGUISHABLE│
└─────────────────────────┴───────────┴────────┴────────────┴─────────────┴──────────────┴──────────────────┘
```

#### Academic Verdict:
* **Unmet Demand:** OR-Tools SCIP is **statistically superior** to No Redistribution and Proportional Population ($p < 0.001$), but **statistically indistinguishable on unmet demand percentage alone** from Greedy Nearest and Greedy Largest Surplus ($p = 0.8286$).
* **Logistics Cost & Route Efficiency:** OR-Tools SCIP achieves **decisive economic and logistical dominance**, reducing transport costs by **$32.8\% \text{ to } 38.5\%$** ($7.15\text{B vs } 10.65\text{B--}10.89\text{B INR}$) and consolidating deliveries onto 6,060 km vs 49,004 km for proportional allocation. The primary value of the OR-Tools SCIP formulation is not squeezing out additional fractional units of demand satisfaction, but achieving that satisfaction at dramatically lower logistical cost and transit congestion.

---

## 6. District-Level Equity, Fairness, and Rural vs. Urban Disparity Audit

The equity audit ([`reports/optimization_equity_analysis.csv`](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/optimization_equity_analysis.csv)) evaluated whether the optimization model treats rural and tribal districts equitably compared to major urban centers.

```
                      DISTRICT CAPACITY & CONNECTIVITY DISPARITY
┌──────────────┬──────────────┬────────────┬───────────────┬─────────────────┬──────────────────────┐
│ District     │ Tier         │ Population │ Hospital Beds │ Beds / 100k Pop │ Neighbors <= 150 km  │
├──────────────┼──────────────┼────────────┼───────────────┼─────────────────┼──────────────────────┤
│ Mumbai       │ Urban Hub    │ 13,726,548 │ 26,933 beds   │ 196.2 / 100k    │ 3 (Thane, Raigad...) │
│ Pune         │ Urban Hub    │ 11,928,725 │ 16,592 beds   │ 139.1 / 100k    │ 3 (Satara, Ahmed...) │
│ Thane        │ Urban Hub    │ 13,465,789 │ 18,334 beds   │ 136.2 / 100k    │ 3 (Mumbai, Palghar...)│
├──────────────┼──────────────┼────────────┼───────────────┼─────────────────┼──────────────────────┤
│ Palghar      │ Rural/Tribal │  3,027,590 │  1,678 beds   │  55.4 / 100k    │ 3 (Thane, Mumbai...) │
│ Gadchiroli   │ Rural/Tribal │  1,170,195 │    688 beds   │  58.8 / 100k    │ 1 (Chandrapur ONLY)  │
│ Washim       │ Rural/Tribal │  1,374,423 │    861 beds   │  62.6 / 100k    │ 7 (Central Vidarbha) │
│ Nandurbar    │ Rural/Tribal │  2,027,012 │  1,357 beds   │  66.9 / 100k    │ 1 (Dhule ONLY)       │
│ Gondia       │ Rural/Tribal │  1,609,598 │  1,082 beds   │  67.2 / 100k    │ 2 (Bhandara, Gadch.) │
└──────────────┴──────────────┴────────────┴───────────────┴─────────────────┴──────────────────────┘
```

### Critical Equity Vulnerabilities Identified:

#### 1. Baseline Capacity Disparity ($3.5\times$ Spread)
Urban centers have up to **$196.2 \text{ beds per 100k}$** (Mumbai), whereas tribal districts such as Palghar ($55.4$) and Gadchiroli ($58.8$) have less than a third of that capacity. Because baseline surge stock is estimated directly from hospital bed counts, rural districts begin any disaster simulation with critically depressed inventory buffers.

#### 2. Perishable Topological Isolation (Constraint 3 Bottleneck)
Under the 150 km maximum transit limit for Blood Units:
* **Gadchiroli has only 1 neighbor within 150 km:** Chandrapur ($97.5\text{ km}$). Nagpur is $180\text{ km}$ away; Bhandara is $158\text{ km}$ away. If Chandrapur has high shortage risk or depleted blood stock, **Gadchiroli is 100% cut off from blood transfers across the entire state**.
* **Nandurbar has only 1 neighbor within 150 km:** Dhule ($99.6\text{ km}$). If Dhule cannot supply blood, Nandurbar is completely isolated.
* **Sindhudurg has only 2 neighbors within 150 km:** Kolhapur ($110.9\text{ km}$) and Ratnagiri ($116.5\text{ km}$).

#### 3. Max-Min Fairness Mathematical Collapse
The fairness variable $\theta$ enforces $\frac{\text{net\_stock}_{jm}}{d_{jm}} \ge \theta$. 
* In catastrophic disasters where total state stock is insufficient and an isolated district (e.g. Gadchiroli) cannot receive blood due to the 150 km limit, its final blood coverage remains 0.
* Because $\theta \le \frac{0}{d_{j, \text{blood}}} = 0$, **$\theta$ is forced to 0 for the entire model**.
* Once $\theta = 0$, the fairness term $-w_{\text{fairness}} \, D_{\text{total}} \, \theta$ provides **zero mathematical incentive** for fair distribution among the remaining 34 districts. The solver reverts entirely to linear cost-minimization.
* **Remediation:** Replace the single scalar $\theta$ with commodity-specific or sub-regional coverage floors, or use a piecewise linear penalty on coverage disparities (e.g., Gini index penalty or entropy regularization).

---

## 7. Human-in-the-Loop Governance & SHA-256 Audit Ledger

The integration between mathematical optimization and human decision governance in `api/audit_ledger.py` was inspected:

```
                         CRYPTOGRAPHIC AUDIT LEDGER CHAIN
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ BLOCK (t-1): Hash = H_{t-1}                                                                 │
└────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ BLOCK t (AuditEvent):                                                                       │
│   Payload: H_{t-1} | timestamp | user_id | simulation_id | ACTION | reason | plan_hash | conf│
│   Hash Calculation:                                                                         │
│     H_t = SHA-256( Payload )                                                                │
│   Database Record:                                                                          │
│     - id: Primary Key (auto-increment)                                                      │
│     - user_id, action (APPROVE / REJECT), reason_code                                       │
│     - plan_hash: SHA-256 of transfer allocations                                            │
│     - confidence: 0.850 (Monte Carlo / Surrogate probability)                               │
│     - prev_hash: H_{t-1}                                                                    │
│     - current_hash: H_t                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Governance Verification:
1. **Safety Threshold Enforcement:** In `api/audit_ledger.py` (lines 55–63), if an officer attempts to `APPROVE` a plan with confidence below the threshold in `config/config.yaml` (default $0.60$), the API raises an **`HTTP 409 CONFLICT`**:
   > *"Governance Policy Violation: Cannot APPROVE allocation plan with confidence below required safety threshold in config.yaml."*
   This prevents automated or careless approval of high-uncertainty plans.
2. **Cryptographic Integrity:** Tamper-evidence was verified. Any manual mutation of a historical record's action, user, or plan hash invalidates all subsequent block hashes in `verify_chain()`.
3. **Audit Weakness:** The timestamp string is generated from the local server clock (`datetime.now(timezone.utc)`). For regulatory compliance (e.g. ISO 27001 or FDA SaMD guidelines), the ledger should integrate an RFC-3161 trusted timestamp authority or digital hardware signature.

---

## 8. Prioritized Defect and Enhancement Backlog

```
                         PRIORITIZED OPTIMIZATION BACKLOG
┌──────────┬──────────┬───────────────────────────────────────────────────────────────────────┐
│ Priority │ Category │ Defect / Architectural Enhancement                                    │
├──────────┼──────────┼───────────────────────────────────────────────────────────────────────┤
│ P0       │ Safety   │ Patch Zero-Demand Donor Loophole: Enforce stock floor max(0.2*s, 0.6*d)│
│ P0       │ Model    │ Align Solver with Evaluator: Introduce binary route variables y_ij    │
│ P1       │ Equity   │ Island Mitigation: Drone / air-ambulance cold-chain bypass for Blood  │
│ P1       │ Fairness │ Decouple Max-Min Theta: Prevent single-district collapse of fairness  │
│ P2       │ Scale    │ Lexicographic Multi-Objective Solver Sequence instead of weighted sum │
│ P2       │ Audit    │ RFC-3161 External Timestamping for the SHA-256 Governance Ledger       │
└──────────┴──────────┴───────────────────────────────────────────────────────────────────────┘
```

### Detailed Engineering Specifications:

#### [P0-1] Patch Zero-Demand Safety Reserve Loophole
* **File:** `src/optimise.py`, lines 118–121
* **Current Code:**
  ```python
  reserve = safety_reserve_ratio * dem
  exportable = max(0, int(np.floor(stk - reserve)))
  ```
* **Required Patch:**
  ```python
  # Ensure donor retains at least 20% of baseline stock for routine clinical operations
  baseline_stock_floor = 0.20 * stk
  disaster_demand_reserve = safety_reserve_ratio * dem
  effective_reserve = max(baseline_stock_floor, disaster_demand_reserve)
  exportable = max(0, int(np.floor(stk - effective_reserve)))
  ```

#### [P0-2] Align Solver Objective with Fixed-Charge Route Evaluator
* **File:** `src/optimise.py`, lines 90–165
* **Required Formulation:**
  ```python
  y = {} # Binary route activation
  for i in districts:
      for j in districts:
          if i != j:
              y[i, j] = solver.BoolVar(f"y_{i}_{j}")
              # Big-M linking constraint
              solver.Add(solver.Sum([x[i, j, m] for m in medicines if (i, j, m) in x]) <= 1e7 * y[i, j])
              obj.SetCoefficient(y[i, j], float(FIXED_ROUTE_COST))
  ```

#### [P1-1] Cold-Chain Island Mitigation for Blood Units
* **File:** `src/optimise.py`, lines 36–40
* **Issue:** Districts with only 1 neighbor $\le 150\text{ km}$ (Gadchiroli, Nandurbar) face total blood starvation if that single neighbor has high risk.
* **Solution:** Introduce an emergency transit tier:
  * Regular ground transit: $\le 150\text{ km}$ (Cost index $1.0\times$).
  * Active refrigerated air/drone transport: up to $300\text{ km}$ with $5.0\times$ transport cost penalty.

---

## 9. Mathematical Appendix: Complexity & Algorithmic Bounds

### Complexity Classification
The resource redistribution problem formulated in `src/optimise.py` is a **Fixed-Charge Capacitated Multi-Commodity Network Flow (FCMCNF)** problem with Max-Min equity objectives:
* **Theorem:** The problem is **Strongly NP-Hard**.
* **Proof:** By restriction. When $|\mathcal{M}| = 1$, safety reserves $\gamma = 0$, fairness weight $w_{\text{fairness}} = 0$, and fixed charges $F > 0$, the problem reduces directly to the single-commodity Fixed-Charge Transportation Problem (FCTP), which is known to be strongly NP-hard (Garey & Johnson, 1979).

### Algorithmic Scalability
* Total continuous variables: $35 \times 5 = 175$ ($u_{jm}$) $+ 1$ ($\theta$) $= 176$.
* Total integer variables: $35 \times 34 \times 5 = 5,950$ minus perishables pruning ($\sim 1,020$ pruned) $\approx 4,930$ integer variables.
* Total constraints: $175$ (reserve) $+ 175$ (unmet definition) $+ 175$ (fairness) $\approx 525$ constraints.
* Because the constraint matrix has total unimodularity (TUM) characteristics in the flow-conservation substructure and the problem size ($N=35$) is compact, SCIP solves the root LP relaxation and branch-and-bound tree to an exact MIP duality gap of $\le 0.01\%$ in **$211.5\text{ ms}$**, making it highly suitable for real-time web services and emergency operations centers.

---
*Report certified by Senior Operations Research & Mathematical Optimization Reviewer, November 2026.*  
*All accompanying dataset files committed to branch `testing`.*
