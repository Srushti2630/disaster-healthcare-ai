#!/usr/bin/env python3
"""
scripts/generate_claim_verification_reports.py

Generates the five required verification CSV reports for Prompt 10:
1. reports/master_claim_verification.csv
2. reports/clinical_model_metric_reconciliation.csv
3. reports/cqr_calculation_reconciliation.csv
4. reports/optimization_benchmark_reconciliation.csv
5. reports/defect_implementation_status.csv
"""

import csv
import math
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def generate_master_claim_verification():
    path = REPORTS_DIR / "master_claim_verification.csv"
    claims = [
        {
            "claim_id": "CLM-01",
            "topic": "CQR Uncertainty Margin vs Multiplicative Ratio",
            "master_audit_statement": "Margin is strictly +-0.9314 in log-space (~6.44x span). x518.4 was an extreme catalog casualty ratio conflated with CQR margin.",
            "empirical_ground_truth": "Both 6.44x and 518.4x are mathematically derived from CQR. 0.9314 is the one-sided margin E. exp(2*E) = 6.44x is the conformal calibration expansion. median(q0.95 - q0.05) is 4.3879. Total calibrated log width is 4.3879 + 2*0.9314 = 6.2507. exp(6.2507) = 518.38x (~518.4x). 518.4x was NOT a catalog casualty ratio, but the exponentiated total median interval width.",
            "verification_status": "CONTRADICTED_AND_CORRECTED",
            "citation": "EXPLAINABILITY_UNCERTAINTY_VERIFICATION.md:40-75; reports/cqr_log_margin_verification.csv"
        },
        {
            "claim_id": "CLM-02",
            "topic": "Clinical Model Champion MAE 43.14",
            "master_audit_statement": "PureHybridForecaster (models/final_model.joblib) selected as champion with MAE=43.14.",
            "empirical_ground_truth": "No model has MAE 43.14. Tuned Ridge has walk-forward MAE 12.87. Hybrid Seasonal Ridge has walk-forward MAE 15.38 and untouched holdout MAE 17.54. General Medicine holdout RMSE is 43.48. MAE 43.14 was a hallucination/conflation in backend audit report. Serialized artifact is in repo root (./final_model.joblib), not models/.",
            "verification_status": "CONTRADICTED_AND_CORRECTED",
            "citation": "final_model_metadata.json:30-45; model_comparison.csv:2-6; FASTAPI_BACKEND_TECHNICAL_AUDIT.md:156"
        },
        {
            "claim_id": "CLM-03",
            "topic": "OR-Tools Solver Logistics Cost Savings (22% vs 32.8-38.5%)",
            "master_audit_statement": "OR-Tools achieves a 22% reduction in total logistics cost (p < 0.001) vs greedy heuristics.",
            "empirical_ground_truth": "OR-Tools SCIP achieves 32.8% to 34.4% cost savings vs Greedy Nearest (3.57B vs 5.32B INR overall; 7.15B vs 10.65B INR in shortage scenarios), and 38.5% savings vs Proportional. The 22% figure was an unsupported drafting error.",
            "verification_status": "CONTRADICTED_AND_CORRECTED",
            "citation": "reports/optimization_benchmark_reproduction.csv:2-6; OR_OPTIMIZATION_TECHNICAL_AUDIT.md:38"
        },
        {
            "claim_id": "CLM-04",
            "topic": "OR-Tools Binary Route Variables & Fixed Cost Mismatch",
            "master_audit_statement": "SCIP solver minimizes unmet demand + linear distance only, ignoring fixed route charges ($500 * active_routes) used in benchmark evaluator.",
            "empirical_ground_truth": "Confirmed. src/optimise.py:155-165 defines variables x[i, j, m] (continuous/integer quantity) with no binary route variables u_ij. evaluate_allocation_plan() in line 285 penalizes active_routes with FIXED_ROUTE_COST=500.0.",
            "verification_status": "CONFIRMED_VERIFIED",
            "citation": "src/optimise.py:155-165, 280-287"
        },
        {
            "claim_id": "CLM-05",
            "topic": "Donor Safety Reserve Zero-Demand Loophole",
            "master_audit_statement": "When donor district has demand=0, reserve=0, allowing solver to drain 100% of routine baseline hospital inventory.",
            "empirical_ground_truth": "Confirmed. src/optimise.py:119-120: reserve = safety_reserve_ratio * dem. If dem=0, reserve=0, and exportable = floor(stk - 0) = stk.",
            "verification_status": "CONFIRMED_VERIFIED",
            "citation": "src/optimise.py:119-120"
        },
        {
            "claim_id": "CLM-06",
            "topic": "Implementation Status of Audit Remediations",
            "master_audit_statement": "Reconciled/resolved items A through K in master report.",
            "empirical_ground_truth": "None of the code fixes have been implemented in application source code. The repository is on branch testing in strictly read-only audit mode. Proposed remediations remain pending implementation in Phases 1 through 6.",
            "verification_status": "PROPOSED_NOT_IMPLEMENTED",
            "citation": "src/optimise.py:119; api/config.py:26; frontend/.env:1; git log -n 5"
        },
        {
            "claim_id": "CLM-07",
            "topic": "Facility Dataset Counts and Coordinate Coverage",
            "master_audit_statement": "Exactly 4,767 records in cleaned_facilities.csv (4,677 public, 90 private). 4,458 was historical active bed subcohort.",
            "empirical_ground_truth": "Confirmed. Exactly 4,767 facilities exist. 2,952 have exact GPS coordinates, while 1,815 are pincode-level geocoded centroids.",
            "verification_status": "CONFIRMED_VERIFIED",
            "citation": "data/processed/cleaned_facilities.csv; scripts/audit_and_preprocess_data.py:110"
        },
        {
            "claim_id": "CLM-08",
            "topic": "Cold-Start Docker Failure on Fresh Clone",
            "master_audit_statement": ".gitignore excludes models/*.joblib, causing empty models/ directory on fresh clone and HTTP 503 crash on container startup.",
            "empirical_ground_truth": "Confirmed. .gitignore line 15 excludes models/*.joblib. api/lifespan.py fails to load demand and impact models if missing, leaving models unloaded.",
            "verification_status": "CONFIRMED_VERIFIED",
            "citation": ".gitignore:15; api/lifespan.py:45-60; docker-compose.yml:18-22"
        }
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(claims[0].keys()))
        w.writeheader()
        w.writerows(claims)
    print(f"✓ Saved {path}")

def generate_clinical_model_metric_reconciliation():
    path = REPORTS_DIR / "clinical_model_metric_reconciliation.csv"
    metrics = [
        {
            "metric_id": "MET-01",
            "reported_metric_name": "Tuned Ridge Walk-Forward MAE",
            "reported_value": "12.87",
            "model_architecture": "Tuned Ridge (L2 alpha=1.0)",
            "target_scale": "Monthly District Service Demand (Mean ~100 units)",
            "dataset_split": "144 Periods (4 Expanding Folds, 12-month test steps)",
            "evaluation_protocol": "Expanding-Window Walk-Forward Cross Validation",
            "source_provenance": "model_comparison.csv:2; ML_RESEARCH_AND_OPTIMIZATION_AUDIT.md",
            "is_serialized_champion": "NO",
            "reconciliation_verdict": "Confirmed empirical baseline metric. Lowest CV MAE among linear models, but lacked explicit seasonal decomposition."
        },
        {
            "metric_id": "MET-02",
            "reported_metric_name": "Hybrid Seasonal Ridge Walk-Forward MAE",
            "reported_value": "15.38",
            "model_architecture": "Two-Stage Hybrid (Seasonal Naive Base + Ridge Residuals)",
            "target_scale": "Monthly District Service Demand (Mean ~100 units)",
            "dataset_split": "144 Periods (4 Expanding Folds, 12-month test steps)",
            "evaluation_protocol": "Expanding-Window Walk-Forward Cross Validation",
            "source_provenance": "final_model_metadata.json:28; model_comparison.csv:6",
            "is_serialized_champion": "YES (Trained & Evaluated)",
            "reconciliation_verdict": "Confirmed empirical cross-validation score for the operational champion architecture."
        },
        {
            "metric_id": "MET-03",
            "reported_metric_name": "Hybrid Seasonal Ridge Untouched Holdout MAE",
            "reported_value": "17.54",
            "model_architecture": "Two-Stage Hybrid (Seasonal Naive Base + Ridge Residuals)",
            "target_scale": "Monthly District Service Demand across 4 Services (ICU, Emerg, GenMed, Surg)",
            "dataset_split": "Periods 145..156 (Final 12 Months, N=48 observations)",
            "evaluation_protocol": "Strictly Untouched Temporal Holdout (Zero Contamination)",
            "source_provenance": "final_model_metadata.json:36; residual_analysis.csv",
            "is_serialized_champion": "YES (Serialized in ./final_model.joblib)",
            "reconciliation_verdict": "Confirmed empirical holdout metric. Reflects true generalization error on unseen future year."
        },
        {
            "metric_id": "MET-04",
            "reported_metric_name": "Newly Reported Champion MAE 43.14",
            "reported_value": "43.14",
            "model_architecture": "Purported PureHybridForecaster",
            "target_scale": "Unknown / Conflated",
            "dataset_split": "Unspecified in backend audit",
            "evaluation_protocol": "Erroneous transcription in FASTAPI_BACKEND_TECHNICAL_AUDIT.md:156",
            "source_provenance": "FASTAPI_BACKEND_TECHNICAL_AUDIT.md:156; reports/cross_audit_contradiction_register.csv",
            "is_serialized_champion": "NO (Fictitious / Typo)",
            "reconciliation_verdict": "Contradicted by source artifacts. No model has MAE 43.14. Conflated with General Medicine holdout RMSE of 43.48."
        },
        {
            "metric_id": "MET-05",
            "reported_metric_name": "General Medicine Holdout RMSE",
            "reported_value": "43.48",
            "model_architecture": "Hybrid Seasonal Ridge (Service-Specific Subcohort)",
            "target_scale": "General Medicine Attendance (Mean 163.2 units, highest volume tier)",
            "dataset_split": "Periods 145..156 (N=12 months)",
            "evaluation_protocol": "Service-Specific Holdout Evaluation",
            "source_provenance": "final_model_metadata.json:62; ML_RESEARCH_AND_OPTIMIZATION_AUDIT.md",
            "is_serialized_champion": "YES (Sub-metric of final_model.joblib)",
            "reconciliation_verdict": "Confirmed source of the ~43 numeric value misattributed as overall MAE in backend audit."
        }
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(metrics[0].keys()))
        w.writeheader()
        w.writerows(metrics)
    print(f"✓ Saved {path}")

def generate_cqr_calculation_reconciliation():
    path = REPORTS_DIR / "cqr_calculation_reconciliation.csv"
    cqr_rows = [
        {
            "parameter_name": "Calibration Margin (E)",
            "mathematical_formula": "Quantile_(1-alpha)(s_i, N=71)",
            "log_space_value": 0.9314,
            "natural_space_multiplier": "exp(0.9314) = 2.538x one-sided shift",
            "empirical_coverage_pct": "94.9% (EM-DAT test set, N=71)",
            "interpretation": "Conformal adjustment added to q_high (0.95) and subtracted from q_low (0.05)."
        },
        {
            "parameter_name": "Conformal Calibration Expansion Factor",
            "mathematical_formula": "exp(2 * E)",
            "log_space_value": round(2 * 0.9314, 4),
            "natural_space_multiplier": "exp(1.8628) = 6.442x ratio expansion",
            "empirical_coverage_pct": "94.9% (Marginal guarantee >= 90%)",
            "interpretation": "Ratio by which conformal calibration widens the prediction interval relative to raw quantiles."
        },
        {
            "parameter_name": "Uncalibrated Quantile Model Spread",
            "mathematical_formula": "median(q_0.95(x) - q_0.05(x))",
            "log_space_value": 4.3879,
            "natural_space_multiplier": "exp(4.3879) = 80.47x raw quantile spread",
            "empirical_coverage_pct": "78.2% (Uncalibrated, under-covers nominal 90%)",
            "interpretation": "Raw inter-quantile range produced by Gradient Boosting Quantile Regressors before CQR."
        },
        {
            "parameter_name": "Total Calibrated Median Interval Width",
            "mathematical_formula": "(q_0.95 - q_0.05) + 2 * E",
            "log_space_value": round(4.3879 + 2 * 0.9314, 4),
            "natural_space_multiplier": "exp(6.2507) = 518.38x (~518.4x)",
            "empirical_coverage_pct": "94.9% (Fully calibrated test coverage)",
            "interpretation": "Total ratio between upper and lower casualty bounds: Upper/Lower = exp(Delta_log) = 518.4x."
        },
        {
            "parameter_name": "Clinical Demand Conformal Global Margin",
            "mathematical_formula": "Quantile_0.90(abs(y - y_hat), N=144)",
            "log_space_value": "N/A (Additive units)",
            "natural_space_multiplier": "+-34.1 units additive buffer",
            "empirical_coverage_pct": "93.75% (Overall holdout across 4 services, N=48)",
            "interpretation": "Additive conformal margin. ICU: 100%, Surgery: 100%, GenMed: 91.7%, Emergency: 83.3%."
        }
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cqr_rows[0].keys()))
        w.writeheader()
        w.writerows(cqr_rows)
    print(f"✓ Saved {path}")

def generate_optimization_benchmark_reconciliation():
    path = REPORTS_DIR / "optimization_benchmark_reconciliation.csv"
    bench_rows = [
        {
            "comparison_metric": "Total Stratified Benchmark Scenarios",
            "solver_formulation": "SCIP MILP (src/optimise.py)",
            "evaluator_formulation": "evaluate_allocation_plan()",
            "measured_value": "36 Scenarios (3 Strata x 3 Multipliers x 4 Epicentres)",
            "exact_sample_size": "N=36 overall; N=18 active shortage",
            "statistical_test_used": "N/A (Dataset size)",
            "reported_p_value": "N/A",
            "reconciliation_verdict": "Confirmed. Exactly 36 stratified scenarios evaluated."
        },
        {
            "comparison_metric": "Binary Route Activation Decision Variables",
            "solver_formulation": "ABSENT (only continuous x[i, j, m] defined)",
            "evaluator_formulation": "len(active_routes) counted post-hoc",
            "measured_value": "0 Binary Route Variables in Solver",
            "exact_sample_size": "N=36",
            "statistical_test_used": "Code Inspection",
            "reported_p_value": "N/A",
            "reconciliation_verdict": "CONFIRMED DISCONNECT. Evaluator penalizes active routes ($500/route) which solver does not optimize."
        },
        {
            "comparison_metric": "Fixed Route Charge in Objective",
            "solver_formulation": "ABSENT (minimizes unmet demand + unit-km)",
            "evaluator_formulation": "INCLUDED ($500.0 * active_routes)",
            "measured_value": "Fixed Route Cost = 0 in Solver Objective",
            "exact_sample_size": "N=36",
            "statistical_test_used": "Code Inspection",
            "reported_p_value": "N/A",
            "reconciliation_verdict": "CONFIRMED DISCONNECT. Solver produces fragmented multi-stop shipments penalized by evaluator."
        },
        {
            "comparison_metric": "Unmet Demand % vs Greedy Nearest",
            "solver_formulation": "OR-Tools SCIP (24.40% mean)",
            "evaluator_formulation": "Greedy Nearest (24.44% mean)",
            "measured_value": "Difference: -0.04% unmet demand",
            "exact_sample_size": "N=36 (Non-zero differences N=8)",
            "statistical_test_used": "Paired Wilcoxon signed-rank test (two-sided)",
            "reported_p_value": "p = 0.8286 (Unadjusted and Holm-adjusted)",
            "reconciliation_verdict": "STATISTICALLY INDISTINGUISHABLE. OR-Tools matches greedy baselines on unmet demand."
        },
        {
            "comparison_metric": "Unmet Demand % vs No Redistribution",
            "solver_formulation": "OR-Tools SCIP (24.40% mean)",
            "evaluator_formulation": "No Redistribution (26.17% mean)",
            "measured_value": "Difference: -1.77% unmet demand",
            "exact_sample_size": "N=36 (Non-zero differences N=18)",
            "statistical_test_used": "Paired Wilcoxon signed-rank test (two-sided)",
            "reported_p_value": "p = 0.00049 (Holm-adjusted p = 0.00195)",
            "reconciliation_verdict": "STATISTICALLY SUPERIOR. OR-Tools significantly outperforms No Redistribution."
        },
        {
            "comparison_metric": "Logistics Transport Cost vs Greedy Nearest",
            "solver_formulation": "OR-Tools SCIP (3,573M INR overall, 7,146M shortage)",
            "evaluator_formulation": "Greedy Nearest (5,322M INR overall, 10,645M shortage)",
            "measured_value": "32.86% Cost Savings (Shortage) / 32.87% (Overall)",
            "exact_sample_size": "N=36 (N=18 active shortage)",
            "statistical_test_used": "Paired Wilcoxon signed-rank test on cost",
            "reported_p_value": "p < 0.0001",
            "reconciliation_verdict": "DECISIVE SUPERIORITY. Real advantage of OR-Tools is logistics cost reduction (32.8-38.5%), not unmet demand."
        }
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(bench_rows[0].keys()))
        w.writeheader()
        w.writerows(bench_rows)
    print(f"✓ Saved {path}")

def generate_defect_implementation_status():
    path = REPORTS_DIR / "defect_implementation_status.csv"
    defects = [
        {
            "defect_id": "DEF-01",
            "title": "Cold-Start Crash on Fresh Clone (Missing Models)",
            "source_location": ".gitignore:15; api/lifespan.py:45-60",
            "exact_line_verified": "models/*.joblib ignored; lifespan.py attempts joblib.load() without fallback",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P0",
            "dependencies": "Phase 1 (scripts/bootstrap_models.py)",
            "blocks_academic_demo": "NO (if models pre-trained)",
            "blocks_fresh_clone": "YES (CRITICAL BLOCKER)",
            "blocks_docker": "YES (CRITICAL BLOCKER)"
        },
        {
            "defect_id": "DEF-02",
            "title": "Silent Hardcoded JWT Secret Fallback",
            "source_location": "docker-compose.yml:25; api/config.py:26",
            "exact_line_verified": "docker-compose sets JWT_SECRET_KEY; config.py reads JWT_SECRET or SECRET_KEY",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P0",
            "dependencies": "Phase 2 (api/config.py alias)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "YES (Security Blocker in Container)"
        },
        {
            "defect_id": "DEF-03",
            "title": "Hardcoded Localhost API Base URL in Frontend",
            "source_location": "frontend/.env:1; frontend/src/api/client.ts:19",
            "exact_line_verified": "BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P0",
            "dependencies": "Phase 5 (Nginx proxy / relative API)",
            "blocks_academic_demo": "NO (Localhost works on single laptop)",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "YES (Remote VM / Container Blocker)"
        },
        {
            "defect_id": "DEF-04",
            "title": "Zero-Demand Routine Inventory Depletion Bug",
            "source_location": "src/optimise.py:119-120",
            "exact_line_verified": "reserve = safety_reserve_ratio * dem; exportable = max(0, int(floor(stk - reserve)))",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P0",
            "dependencies": "Phase 3 (Reserve formula update)",
            "blocks_academic_demo": "YES (Algorithmic Defense Blocker)",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-05",
            "title": "CORS Wildcard Insecure in Production",
            "source_location": "api/main.py:65-72",
            "exact_line_verified": "allow_origins=['*'] configured by default",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P0",
            "dependencies": "Phase 2 (Configurable CORS whitelist)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-06",
            "title": "Containers Running as Root User",
            "source_location": "Dockerfile:1-40; docker-compose.yml",
            "exact_line_verified": "No USER directive in Dockerfile; runs as root UID 0",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P0",
            "dependencies": "Phase 6 (useradd in Dockerfile)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "YES (Production Container Compliance)"
        },
        {
            "defect_id": "DEF-07",
            "title": "Champion Clinical Forecaster Omitted from API",
            "source_location": "final_model.joblib; api/lifespan.py:35-65",
            "exact_line_verified": "final_model.joblib exists in repo root; lifespan.py does not load it; no API endpoint",
            "implementation_status": "PROPOSED_NOT_IMPLEMENTED",
            "is_duplicated": "NO",
            "priority": "P1",
            "dependencies": "Phase 4 (POST /api/forecast/clinical)",
            "blocks_academic_demo": "YES (Academic Capstone Gap)",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-08",
            "title": "Solver Objective Lacks Route Activation Fixed Cost",
            "source_location": "src/optimise.py:155-165, 280-287",
            "exact_line_verified": "Objective minimizes unmet + unit-km; evaluator penalizes 500 * active_routes",
            "implementation_status": "PROPOSED_NOT_IMPLEMENTED",
            "is_duplicated": "NO",
            "priority": "P1",
            "dependencies": "Phase 3 (Binary variables u_ij in SCIP)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-09",
            "title": "District Name Divergence & Missing Facility Geocodes",
            "source_location": "data/processed/cleaned_facilities.csv; src/data/facilities.py:40",
            "exact_line_verified": "1,815 facilities lack GPS coordinates; district centroid fallbacks used",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P1",
            "dependencies": "Phase 5 (Geocoding resolution)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-10",
            "title": "SQLite Concurrency Bottleneck Under High Load",
            "source_location": "api/database.py:15-20",
            "exact_line_verified": "connect_args={'check_same_thread': False} without WAL mode enabled",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P1",
            "dependencies": "Phase 6 (WAL mode / Postgres migration)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-11",
            "title": "Single Global Additive Conformal Margin Across Services",
            "source_location": "scripts/train_service_forecasting.py:705-725; final_model_metadata.json:44",
            "exact_line_verified": "Global additive margin +-34.1 units applied to all services (ICU, Emerg, GenMed, Surg)",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P1",
            "dependencies": "Phase 3 (Service-specific non-conformity)",
            "blocks_academic_demo": "YES (Methodological Academic Defense)",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-12",
            "title": "Unauthenticated Sensitive Incident & Audit Endpoints",
            "source_location": "api/routes.py:120-160",
            "exact_line_verified": "Audit ledger verification endpoints lack Depends(get_current_active_user)",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P1",
            "dependencies": "Phase 2 (Endpoint auth guards)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-13",
            "title": "Silent Error Masking & Synthetic Data Fallback",
            "source_location": "frontend/src/pages/OverviewPage.tsx:90-120",
            "exact_line_verified": "Catches API error and silently binds mock data without error banner",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P2",
            "dependencies": "Phase 5 (Explicit UI error handling)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-14",
            "title": "Missing Docker Healthchecks in Compose",
            "source_location": "docker-compose.yml:10-45",
            "exact_line_verified": "No healthcheck stanzas defined in backend or frontend service blocks",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P2",
            "dependencies": "Phase 6 (docker-compose healthchecks)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "YES (Container Race Conditions)"
        },
        {
            "defect_id": "DEF-15",
            "title": "Test Suite Execution Pathing Dependencies",
            "source_location": "tests/test_core.py:1-40",
            "exact_line_verified": "Relies on os.chdir() and assumes pre-trained models exist in models/",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P2",
            "dependencies": "Phase 0 (Hermetic conftest harness)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "YES (CI/CD Test Runner Failures)",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-16",
            "title": "GitHub Actions Workflow Fails on Empty Model Directory",
            "source_location": ".github/workflows/ci.yml:25-35",
            "exact_line_verified": "Runs pytest without pre-training models; fails on cold-start PR checks",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P2",
            "dependencies": "Phase 1 (CI training step)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "YES (Automated CI Failure)",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-17",
            "title": "Synthetic Surge Scale Factor Disconnect",
            "source_location": "src/models/train_impact_model.py:110",
            "exact_line_verified": "Fixed heuristic multiplier converts EM-DAT affected population to hospital admissions",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P2",
            "dependencies": "Phase 4 (Epidemiological surge tuning)",
            "blocks_academic_demo": "NO",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-18",
            "title": "Leaflet Map CSS Loading & Container Height Glitch",
            "source_location": "frontend/src/components/DistrictMap.tsx:30-45",
            "exact_line_verified": "Leaflet container height computed before CSS stylesheet loads, causing tile gray-out",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P3",
            "dependencies": "Phase 5 (invalidateSize hook)",
            "blocks_academic_demo": "NO (Minor visual glitch)",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        },
        {
            "defect_id": "DEF-19",
            "title": "Academic Paper Metric Inflation & Terminology Mismatch",
            "source_location": "MASTER_TECHNICAL_AUDIT_AND_REMEDIATION_ROADMAP.md:85",
            "exact_line_verified": "Conflated x518.4 with historical catalog casualty ratio instead of calibrated interval width",
            "implementation_status": "CONFIRMED_UNRESOLVED",
            "is_duplicated": "NO",
            "priority": "P3",
            "dependencies": "Phase 7 (Documentation reconciliation)",
            "blocks_academic_demo": "YES (Defense Terminology Precision)",
            "blocks_fresh_clone": "NO",
            "blocks_docker": "NO"
        }
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(defects[0].keys()))
        w.writeheader()
        w.writerows(defects)
    print(f"✓ Saved {path}")

if __name__ == "__main__":
    print("Generating Prompt 10 Claim Verification Reports...")
    generate_master_claim_verification()
    generate_clinical_model_metric_reconciliation()
    generate_cqr_calculation_reconciliation()
    generate_optimization_benchmark_reconciliation()
    generate_defect_implementation_status()
    print("All 5 claim verification CSVs generated successfully.")
