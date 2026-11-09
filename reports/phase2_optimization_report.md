# Phase 2 — OR-Tools Optimization & Resource Allocation Hardening Report

**Project:** Disaster Healthcare AI — Demand Prediction & Resource Allocation  
**Implementation Branch:** `finalBr`  
**Protected Baseline Branch:** `testing` at commit `660f873`  
**Phase 0 Commit:** `661e0a0`  
**Phase 1 Final Acceptance Commit:** `d7b28f5`  
**Phase:** Phase 2 — Mathematical Optimization, Constraint Hardening & Statistical Verification  

---

## 1. Executive Summary

In Phase 2, we conducted a rigorous mathematical redesign and empirical hardening of the Google OR-Tools SCIP Mixed-Integer Programming (MIP) resource allocation engine (`src/optimise.py`). Prior to this intervention, the optimization formulation suffered from four structural defects:
1. **DEF-04 (Zero-Demand Stock Depletion)**: The legacy reserve formulation `max(0, floor(stk - 0.60 * dem))` computed zero reserve when forecast demand was zero (`dem == 0`), exposing donor districts to 100% stock liquidation during multi-region disasters.
2. **DEF-08 (Route Activation & Fixed Transport Costs Disconnect)**: The solver minimized unmet demand and normalized distance without modeling binary route activation variables $y_{ij} \in \{0, 1\}$. Meanwhile, the post-hoc evaluation function penalized active routes with a fixed activation fee ($F = ₹500/\text{route}$) and variable transport costs ($k = ₹15/\text{unit-km}$), producing a severe objective mismatch.
3. **DEF-FAIR (Min-Coverage Fairness Collapse)**: The global fairness parameter $\theta$ collapsed to zero whenever isolated nodes or zero-demand districts existed, or was arbitrarily bypassed for demands $\le 10$ units.
4. **DEF-BLOOD (Perishable Distance Limit Boundary Validation)**: The strict 150 km maximum distance for `blood_units` required formal boundary testing (at 149 km, 150.0 km, and 151 km) and complete parity across solver and evaluator.

Following controlled implementation on `finalBr`, all four defects have been fully resolved with zero constraint violations across all benchmarks and 100% test pass rates across 103 automated tests (96 Python backend tests and 7 Vitest frontend tests).

---

## 2. Mathematical Formulation Comparison (Before vs. After)

### A. Source Safety Reserve Constraints (DEF-04)
* **Legacy Formulation**:
  $$\text{Reserve}_{i, c} = 0.60 \times \text{Demand}_{i, c}$$
  $$\text{Exportable}_{i, c} = \max\left(0, \lfloor \text{Stock}_{i, c} - \text{Reserve}_{i, c} \rfloor\right)$$
  * *Failure Mode*: If $\text{Demand}_{i, c} = 0$, $\text{Reserve}_{i, c} = 0$, allowing $\text{Exportable}_{i, c} = \text{Stock}_{i, c}$ (100% depletion).
* **Hardened Formulation**:
  $$\text{Reserve}_{i, c} = \max\left(\alpha \cdot \text{Demand}_{i, c}, \; \beta \cdot \text{Stock}_{i, c}\right) \quad (\alpha = 0.60, \; \beta = 0.30)$$
  $$\text{Exportable}_{i, c} = \begin{cases} 0 & \text{if Risk}_{i, c} = \text{"High"} \\ \max\left(0, \lfloor \text{Stock}_{i, c} - \text{Reserve}_{i, c} \rfloor\right) & \text{otherwise} \end{cases}$$
  $$\sum_{j \neq i} x_{i, j, c} \le \text{Exportable}_{i, c} \quad \forall i \in \mathcal{D}, \; c \in \mathcal{C}$$
  * *Guarantee*: Even with zero forecast demand, a minimum of 30% of existing physical stock is strictly locked on-site as an emergency contingency reserve.

### B. Route Activation & Big-M Linking Constraints (DEF-08)
* **Legacy Formulation**:
  * Continuous/integer flow variables $x_{i, j, c} \ge 0$ only.
  * No route binary variables $y_{i, j} \in \{0, 1\}$.
  * Solver objective used heuristic normalized distance $w_{\text{cost}} \cdot \frac{d_{ij}}{d_{\max}} \cdot 0.05 \cdot x_{i, j, c}$.
  * Post-hoc evaluator charged $15 \cdot d_{ij} \cdot x_{i, j, c} + 500 \cdot |\mathcal{R}_{\text{active}}|$.
* **Hardened Formulation**:
  * Explicit binary route activation decision variables:
    $$y_{i, j} \in \{0, 1\} \quad \forall (i, j) \in \mathcal{D} \times \mathcal{D}, \; i \neq j$$
  * Defensible, tight Big-M bound per commodity and route:
    $$M_{i, j, c} = \min\left(\text{Exportable}_{i, c}, \; \text{Shortage}_{j, c}\right)$$
    $$M_{i, j} = \sum_{c \in \mathcal{C}} M_{i, j, c}$$
    $$\sum_{c \in \mathcal{C}} x_{i, j, c} \le M_{i, j} \cdot y_{i, j} \quad \forall i \neq j$$
  * *Guarantee*: $y_{i, j} = 1$ if and only if at least one unit of any commodity flows from $i$ to $j$. Fixed charge of ₹500 is charged exactly once per active route regardless of the number of commodities.

### C. Unified Objective Function (DEF-08 & DEF-FAIR)
* **Unified Objective**:
  $$\min Z = \sum_{j \in \mathcal{D}} \sum_{c \in \mathcal{C}} W_{\text{unmet}} \cdot \omega_c \cdot \text{Unmet}_{j, c} + \sum_{i, j} \sum_c W_{\text{cost}} \cdot k_c \cdot d_{i, j} \cdot x_{i, j, c} + \sum_{i, j} W_{\text{cost}} \cdot F \cdot y_{i, j} - W_{\text{fairness}} \cdot \theta$$
  * Parameters:
    - $W_{\text{unmet}} = 10^6$ (Strict life-saving priority)
    - $\omega_c \in \{5.0, 3.0, 2.0, 1.0, 1.0\}$ (Commodity clinical criticality weights)
    - $W_{\text{cost}} = 1.0$ (Cost penalty weight)
    - $k_c = ₹15.0/\text{unit-km}$ (Variable transport rate)
    - $F = ₹500.0$ (Fixed route activation charge)
    - $W_{\text{fairness}} = 10^5$ (Min-coverage equity incentive)
  * *Cost Parity*: The solver's reported transport cost matches the evaluator's cost function to within $< 0.05$ numerical precision across all scenarios.

### D. Eligibility-Aware Min-Coverage Fairness (DEF-FAIR)
* **Legacy Formulation**:
  $$\text{FinalStock}_{j, c} \ge \theta \cdot \text{Demand}_{j, c} \quad \text{if } \text{Demand}_{j, c} > 10.0$$
  * If any district had zero donor or isolated distance, $\theta$ collapsed to 0. Demands $\le 10$ were arbitrarily excluded.
* **Hardened Formulation**:
  * Defined eligibility set $\mathcal{E} \subseteq \mathcal{D} \times \mathcal{C}$:
    $$\mathcal{E} = \left\{(j, c) \;\middle|\; \text{Demand}_{j, c} > 0, \; \text{Demand}_{j, c} - \text{Stock}_{j, c} > 0, \; \exists i \neq j \text{ s.t. } (i, j, c) \in \text{FeasibleRoutes}\right\}$$
  * Fairness constraint applied strictly over eligible pairs:
    $$\text{FinalStock}_{j, c} \ge \theta \cdot \text{Demand}_{j, c} \quad \forall (j, c) \in \mathcal{E}$$
  * *Guarantee*: Districts with zero demand or without feasible donors cannot collapse system fairness; small-demand districts with donors are actively protected.

### E. Perishable Blood-Product Distance Limit (DEF-BLOOD)
* Constraint:
  $$x_{i, j, \text{"blood\_units"}} = 0 \quad \forall (i, j) \text{ where } d_{i, j} > 150.0\text{ km}$$
* Boundary Behavior:
  - $d_{i, j} = 149.0\text{ km}$: Allowed.
  - $d_{i, j} = 150.0\text{ km}$: Allowed (exact closed upper bound).
  - $d_{i, j} = 151.0\text{ km}$: Strictly excluded ($x_{i, j, \text{blood}}$ variable omitted from solver model).

---

## 3. Benchmark Grid Reconciliation & Empirical Results

We maintain the distinct identities of the two official benchmark artifacts:
- **Experiment A (20-Scenario Precomputed Baseline)**: Preserved in `reports/allocation_summary.json` (indexed 0–19) and served by the `/api/baselines` endpoint.
- **Experiment B (36-Scenario Stratified Optimization Benchmark Grid)**: Evaluated across 3 disaster casualty strata (Low, Moderate, Severe) $\times$ 3 stock multipliers (0.25, 0.5, 1.0) $\times$ 4 epicentres = 36 scenarios, recorded in `reports/phase2_benchmark_results.csv`.

### Benchmark Results Table (All 36 Stratified Scenarios)
| Method | Unmet Demand Mean | Unmet % Mean | Unmet % Median | Unmet % P90 | Mean Cost (INR) | Mean Route-km | Min Coverage Mean | Violations |
|---|---|---|---|---|---|---|---|---|
| **OR-Tools SCIP (Hardened)** | **55,901,852.2** | **24.58%** | **0.01%** | **91.12%** | **₹2,909,406,408.91** | **3,013.0** | **0.595** | **0.0** |
| No Redistribution | 56,281,385.7 | 26.17% | 0.01% | 91.24% | ₹0.00 | 0.0 | 0.595 | 0.0 |
| Proportional Population | 56,062,309.2 | 25.11% | 0.01% | 91.22% | ₹4,509,405,830.21 | 24,550.5 | 0.595 | 0.0 |
| Greedy Nearest | 55,903,509.2 | 24.59% | 0.01% | 91.12% | ₹4,225,366,879.28 | 2,393.7 | 0.595 | 0.0 |
| Greedy Largest Surplus | 55,902,967.2 | 24.59% | 0.01% | 91.12% | ₹4,315,176,762.09 | 2,246.3 | 0.595 | 0.0 |

### Benchmark Results Table (Active Shortage Scenarios, N=18)
| Method | Unmet Demand Mean | Unmet % Mean | Unmet % Median | Unmet % P90 | Mean Cost (INR) | Mean Route-km | Min Coverage Mean | Violations |
|---|---|---|---|---|---|---|---|---|
| **OR-Tools SCIP (Hardened)** | **111,803,704.3** | **49.17%** | **55.33%** | **95.55%** | **₹5,818,812,817.83** | **6,026.0** | **0.191** | **0.0** |
| No Redistribution | 112,562,771.5 | 52.34% | 59.27% | 95.55% | ₹0.00 | 0.0 | 0.191 | 0.0 |
| Proportional Population | 112,124,618.3 | 50.22% | 57.22% | 95.55% | ₹9,018,811,660.42 | 49,100.9 | 0.191 | 0.0 |
| Greedy Nearest | 111,807,018.4 | 49.19% | 55.33% | 95.55% | ₹8,450,733,758.55 | 4,787.5 | 0.191 | 0.0 |
| Greedy Largest Surplus | 111,805,934.4 | 49.18% | 55.33% | 95.55% | ₹8,630,353,524.19 | 4,492.5 | 0.191 | 0.0 |

---

## 4. Statistical Significance Testing & Honest Claims

Paired Wilcoxon signed-rank tests were performed on exact non-zero differences with Holm-Bonferroni step-down correction:

| Comparison | Non-Zero Pairs ($N_{\text{nz}}$) | Wilcoxon $W$ | Unadjusted $p$ | Holm-Adjusted $p$ | Rank-Biserial $r$ | Statistical Verdict |
|---|---|---|---|---|---|---|
| **OR-Tools SCIP vs No Redistribution** | 14 | 0.0 | $0.000122$ | **$0.000488$** | $+1.000$ | **Statistically Superior** ($p < 0.05$) |
| **OR-Tools SCIP vs Proportional Population** | 13 | 0.0 | $0.000244$ | **$0.000732$** | $+1.000$ | **Statistically Superior** ($p < 0.05$) |
| **OR-Tools SCIP vs Greedy Nearest** | 14 | 51.0 | $0.951538$ | **$1.000000$** | $+0.0286$ | **Statistically Indistinguishable on Unmet Demand** |
| **OR-Tools SCIP vs Greedy Largest Surplus** | 14 | 50.0 | $0.903198$ | **$1.000000$** | $-0.0476$ | **Statistically Indistinguishable on Unmet Demand** |

### The True Practical Advantage of OR-Tools SCIP
As proven by the empirical data:
1. **Unmet Demand**: Across all 36 scenarios, all three optimization/heuristic methods (OR-Tools, Greedy Nearest, Greedy Largest Surplus) achieve virtually identical unmet demand (~24.58% to 24.59% overall; 49.17% to 49.19% in active shortages). The difference is not statistically significant (Holm $p = 1.00$).
2. **Logistics Transport Cost**: In active shortage scenarios, the hardened OR-Tools SCIP engine incurs a mean logistics cost of **₹5,818,812,817.83**, compared to **₹8,450,733,758.55** for Greedy Nearest (**31.14% cost reduction**) and **₹8,630,353,524.19** for Greedy Largest Surplus (**32.58% cost reduction**).
3. **Conclusion**: The genuine operational value of the mathematical programming approach lies not in an unrealistic reduction of total system casualties or shortages (which are macro-capacity bounded), but in **slashing logistics transport expenditure and vehicle deployment costs by 31.1% to 32.6%** while guaranteeing zero constraint violations.

---

## 5. Constraint & Edge Case Verification

Recorded in `reports/phase2_constraint_validation.csv`:
- **Zero-Demand Buffer**: Stock=1000, Demand=0. Retained 300 units on-site; exported 700 units; 0 violations.
- **Low-Demand Buffer**: Stock=1000, Demand=100. $\beta$ dominates ($300 > 60$); retained 300 units; exported 700 units; 0 violations.
- **High-Demand Buffer**: Stock=1000, Demand=1200. $\alpha$ dominates ($720 > 300$); retained 720 units; exported 280 units; 0 violations.
- **Binary Route Activation**: $y_{ij} = 1 \iff \sum_c x_{ijc} > 0$. Unused routes incur zero fixed cost. Single ₹500 fee charged for multi-commodity shipments.
- **Blood Product Boundary**:
  * 149.0 km: Transfer permitted; 0 violations.
  * 150.0 km: Transfer permitted; 0 violations.
  * 151.0 km: Transfer strictly prohibited ($x_{ij,\text{blood}}$ variable omitted); 0 violations.
  * Non-perishables (antibiotics, ORS, IV fluids, analgesics): Allowed beyond 150 km.
- **Solver-Evaluator Alignment**: Cost error $< 0.05$ across all test scenarios.

---

## 6. Test Suite & Regression Verification

- **New Phase 2 Test Suite**: `tests/test_phase2_optimization.py` (18 tests) covering DEF-04, DEF-08, DEF-FAIR, DEF-BLOOD, and operational invariants.
- **Phase 1 Regression Suite**: `tests/test_phase1_regressions.py` (17 tests) passed.
- **API Test Suite**: `tests_api/` (29 tests) passed.
- **Core Test Suite**: `tests/test_core.py` (32 tests) passed.
- **Frontend Test Suite**: `frontend` Vitest (7 tests) passed.
- **Total Automated Test Count**: **103 passing tests, 0 failures**.

---

## 7. Deliverables & Git Safety Certification

1. `src/optimise.py`: Hardened SCIP formulation, unified objective, binary route activation, robust reserves, eligibility-aware fairness.
2. `tests/test_phase2_optimization.py`: 18 targeted unit and integration tests.
3. `reports/phase2_benchmark_results.csv`: Complete benchmark table across 36 stratified scenarios.
4. `reports/phase2_statistical_comparison.csv`: Wilcoxon signed-rank tests, Holm-adjusted p-values, rank-biserial effect sizes, and cost savings.
5. `reports/phase2_constraint_validation.csv`: Formal test conditions, legacy vs. hardened behavior, and empirical results.
6. `reports/phase2_optimization_report.md`: Authoritative technical report.
7. `reports/phase1_implementation_report.md`: Corrected Tree-SHAP accuracy sentence and documented production artifact checklist.

**Git Rules Adherence**:
- Protected baseline `testing` remains untouched at `660f873`.
- Work conducted exclusively on `finalBr`.
