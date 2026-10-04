# Project Progress (verified state, 2026-10-04)

> This file was corrected by hand after a verification pass. Where it disagrees with older notes, `reports/*.json`, `reports/*.csv` or the code, trust the code and re-check.

## Status
- Pipeline runs end to end: `python run_all.py` (data -> impact model -> Monte-Carlo engine + surrogate -> optimiser -> tests).
- Tests: **24 / 24 passing** (`tests/test_core.py`, committed work; edit in place only).
- Integrity fixes DONE: fake weather removed, real district polygons, raw zonal population, optimiser empty-plan, audit-log migration, ast-based synthetic-import test.
- STILL TO DO: backtest fix, impact-model CIs, Monte-Carlo sigma, optimiser reporting, stale figures, app rewrite, README, viva docs, CI (see "Remaining work").

## What is real, estimated, assumed
| Item | Tag | Notes |
|---|---|---|
| EM-DAT events (810; 512 with Total Affected; 136 injured) | REAL | Targets never imputed. Event-level and often MULTI-STATE. |
| District polygons (35, median 899 vertices) | REAL | Real boundary file in `data/raw/boundaries/`. Old 5-vertex rectangles archived as `*_APPROX.geojson`. |
| District population | REAL (raw WorldPop zonal sum) | Total 131,936,179 vs ~124.5M official projection, gap 5.97%, reported as a sanity check. No rescaling. |
| Hospital directory (4,767 Maharashtra facilities) | REAL | `Total_Num_Beds` is unusable (valid for ~0.2% of rows) and is NOT used as a bed count. |
| District hospital/ICU beds | ESTIMATED | Allocated from state anchors (144,983 beds; ICU anchor 11,587, allocated 11,571). Source of the bed anchor still to be cited. |
| Medicine consumption parameters | ASSUMED | WHO IEHK 2017 / Sphere, in `config/demand_params.yaml`. |
| Distances | ASSUMED | Haversine x 1.3 circuity. |
| Weather | NOT USED in training | The original generator used numpy rng (not real) and was deleted. Open-Meteo is used only for the what-if page (NaN on failure). |

## Phase summaries (corrected)
### Phase 1 Data layer
Real polygons, raw zonal population, cleaned facilities, estimated capacity, cleaned EM-DAT (non-imputation). Weather excluded from training.

### Phase 2 Impact model (512 events, time split Train<=2012 / Val 2013-2018 / Test 2019+; N=363/71/78)
- Median baseline: MAE 3.5717, R2 -0.0952.
- Ridge: MAE 2.8812, R2 0.2780, Spearman 0.5199, within-half-order-of-magnitude 20.5% (baseline 19.2%).
- XGBoost: MAE 3.0908, R2 0.1403, Spearman 0.4454. Random forest: R2 -0.0174.
- CQR 90% nominal gives 94.9% empirical coverage: intervals are CONSERVATIVE, not "better calibrated". Interval widths span several orders of magnitude.
- The model ranks events but cannot size them; very large events are underestimated by about 30-150x.
- SHAP is fitted on XGBoost (not the best model); to be justified or changed.
- **Backtest (reports/historical_backtest.csv) is INVALID as written**: events were matched by year+hazard. "2005 Maharashtra Floods" is DisNo. 2005-0375-IND (Assam/UP/Bihar, no Maharashtra); "2019 Kolhapur-Sangli" is 2019-0331-IND (Bihar, Assam, Maharashtra, Kerala, etc., multi-state); Latur used 1993-0581-IND (525 affected) instead of 1993-0074-IND (9,748 deaths, 30,000 affected). Three events are also inside the training period. Must be rebuilt by DisNo. with leave-one-event-out.

### Phase 3 Demand and shortage engine
- Monte-Carlo, 2,000 draws per district x medicine; P10/P50/P90 and P(demand > surge stock).
- Surrogate classifier trained on 500 sampled scenarios, split BY SCENARIO (400/100): held-out fidelity 98.27%, macro F1 0.9538, ECE 0.0393. (The earlier 100% claim came from a single scenario and is invalid.)
- Known issue: the Monte-Carlo uses a hard-coded affected_std_log = 0.40, far smaller than validation RMSE (~3.4 ln units), so shortage probabilities are overconfident. To be fixed.
- Rule for allocating event totals to districts is an ASSUMPTION and must be documented.

### Phase 4 Optimiser (20 Monte-Carlo scenarios, one shared constraint checker and cost function)
- **Shared Evaluator & Unified Cost Function**: Cost = `unit_km * 15.0 + active_routes * 500.0`. Measured both `unit_km` (units $\times$ km) and `route_km` (sum of distinct active route distances).
- **20-Scenario Benchmark (`reports/baseline_comparison.csv`)**: Evaluated 5 methods (OR-Tools SCIP, No Redistribution, Proportional Population, Greedy Nearest, Greedy Largest Surplus) across 10 P50 and 10 P90 demand scenarios.
- **Results**:
  - `OR-Tools SCIP`: Mean unmet demand 20,829.1 units (lowest); Mean transport cost 10.49B INR (lowest among active redistribution methods); Mean route_km 4,008.6 km; Mean min coverage 0.578 (highest); 0 violations.
  - `Greedy Largest Surplus`: Mean unmet demand 21,216.8 units; Mean transport cost 16.64B INR; Mean route_km 6,316.5 km; 0 violations.
  - `Greedy Nearest`: Mean unmet demand 465,298.7 units; Mean transport cost 10.57B INR; Mean route_km 5,103.8 km; 0 violations.
  - `Proportional Population`: Mean unmet demand 1,286,335.9 units; Mean transport cost 30.84B INR; 0 violations.
  - `No Redistribution`: Mean unmet demand 2,104,947.3 units; 0 cost (excluded from lowest cost claim).
- **Visual Tradeoff**: Saved comparison scatter plot to `reports/baseline_comparison_plot.png` and `reports/pareto_sweep.png`.

### Phase 5 App and reporting (needs rework)
- Exists: 4 pages, hash-chained audit log, PDF/Excel export, map.
- Problems: trained models are loaded but not used; what-if ignores severity and stock sliders; sidebar report uses a toy two-district plan; audit log gets hard-coded 0.92 / 15.0 values; allocation page reads stale files; centroid scatter instead of choropleth; `use_container_width` deprecated; no SHAP on the app.

### Phase 6 Audit and stress tests
- `bias_table.csv`, `sensitivity_tornado.png`, `stress_test_results.json`, `calibration.png` PREDATE the weather removal and surrogate retrain (generated ~01:30 vs 12:35 on 2026-10-04). Regenerate or delete.

## Remaining work (do in this order)
1. Backtest rebuilt by fixed DisNo. list in config.yaml (2005-0409-IND, 2005-0541-IND, 2001-0033-IND, 1993-0074-IND, 2019-0331-IND), leave-one-event-out, scope flag, honest labels.
2. Impact metrics: bootstrap CIs, per-hazard and single/multi-state coverage, interval width, SHAP on the best model.
3. Monte-Carlo sigma from validation residuals, P50/P75/P90 planning level, document district allocation rule, re-run sensitivity.
4. Optimiser reporting and a real Pareto sweep.
5. Regenerate stale artifacts.
6. Provenance: cite or tag the bed anchor and reference population.
7. App rewrite (use models, SHAP, real plan, honest audit log, choropleth, badges).
8. Hygiene: tests write to tmp_path; keep fpdf2 or reportlab, not both.
9. Docs: README full rewrite (currently still the OLD synthetic version), docs/VIVA_QA.md, docs/DEMO_SCRIPT.md, CI.

## How to run
```bash
source .venv/bin/activate
python run_all.py
streamlit run app.py
```
