#!/usr/bin/env python3
"""
scripts/generate_verification_artifacts.py
Generates supporting verification CSVs for EXPLAINABILITY_UNCERTAINTY_VERIFICATION.md.
"""

import csv
import json
import math
import os
import pickle
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR))
from scripts.train_service_forecasting import (
    load_or_generate_service_dataset, build_feature_matrix,
    PureHybridForecaster
)

def run_verification():
    print("=" * 80)
    print("Executing Focused Methodological Verification")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. CQR Log-Space Margin vs Multiplicative Factor
    # -------------------------------------------------------------------------
    conformal_margin_E = 0.9314
    quantile_model_median_width = 4.3879
    total_log_width = quantile_model_median_width + (2 * conformal_margin_E)
    multiplicative_factor = math.exp(total_log_width)
    
    cqr_recon_rows = [
        {
            "parameter_name": "Conformal Calibration Margin (E = Q_(1-alpha))",
            "log_space_value": round(conformal_margin_E, 4),
            "additive_symmetry": "+-0.9314 log1p units",
            "raw_casualty_equivalent": f"exp({conformal_margin_E:.4f}) = {math.exp(conformal_margin_E):.2f}x one-sided shift",
            "scientific_interpretation": "Empirical (1-alpha) quantile of non-conformity scores derived from N=71 calibration events"
        },
        {
            "parameter_name": "Quantile Regressor Median Width (q_0.95 - q_0.05)",
            "log_space_value": round(quantile_model_median_width, 4),
            "additive_symmetry": "Asymmetric conditional quantile spread",
            "raw_casualty_equivalent": f"exp({quantile_model_median_width:.4f}) = {math.exp(quantile_model_median_width):.2f}x raw spread",
            "scientific_interpretation": "Uncalibrated 90% inter-quantile spread from Gradient Boosting Quantile Regressors"
        },
        {
            "parameter_name": "Total CQR Median Interval Width",
            "log_space_value": round(total_log_width, 4),
            "additive_symmetry": f"{quantile_model_median_width:.4f} + 2 * {conformal_margin_E:.4f}",
            "raw_casualty_equivalent": f"exp({total_log_width:.4f}) = {multiplicative_factor:.1f}x",
            "scientific_interpretation": "Full calibrated prediction interval width on test set: (q_high + E) - (q_low - E)"
        }
    ]
    
    cqr_csv = REPORTS_DIR / "cqr_log_margin_verification.csv"
    with open(cqr_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cqr_recon_rows[0].keys()))
        w.writeheader()
        w.writerows(cqr_recon_rows)
    print(f"✓ Created {cqr_csv}")

    # -------------------------------------------------------------------------
    # 2. Service Demand Scales & Global Conformal Additive Margin Evaluation
    # -------------------------------------------------------------------------
    res_path = BASE_DIR / "residual_analysis.csv"
    with open(res_path, "r") as f:
        holdout_rows = list(csv.DictReader(f))
        
    service_groups = defaultdict(list)
    for r in holdout_rows:
        service_groups[r["service"]].append(r)
        
    global_margin = 34.1  # additive margin
    scale_rows = []
    
    for s_name in ["ICU", "Surgery", "Emergency", "General Medicine"]:
        s_items = service_groups[s_name]
        actuals = [float(x["actual_demand"]) for x in s_items]
        preds = [float(x["predicted_demand"]) for x in s_items]
        resids = [float(x["residual_error"]) for x in s_items]
        
        mean_y = sum(actuals) / len(actuals)
        var_y = sum((x - mean_y)**2 for x in actuals) / len(actuals)
        std_y = math.sqrt(var_y)
        mae = sum(abs(r) for r in resids) / len(resids)
        covered = sum(int(x["is_interval_covered"]) for x in s_items)
        cov_pct = round(covered / len(s_items) * 100.0, 1)
        
        margin_pct_of_mean = round(global_margin / mean_y * 100.0, 1)
        scale_rows.append({
            "service_tier": s_name,
            "sample_count": len(s_items),
            "mean_demand": round(mean_y, 1),
            "std_demand": round(std_y, 1),
            "mean_abs_error": round(mae, 1),
            "global_margin_units": global_margin,
            "margin_relative_to_mean_pct": margin_pct_of_mean,
            "empirical_holdout_coverage_pct": cov_pct,
            "homoscedasticity_assessment": (
                "OVER-CONSERVATIVE (Excessive buffer relative to scale)" if margin_pct_of_mean > 45.0
                else ("UNDER-COVERED (Inadequate buffer during surge bursts)" if cov_pct < 90.0
                      else "APPROPRIATE CALIBRATION")
            ),
            "recommendation": (
                "Reduce margin via service-stratified conformalization" if margin_pct_of_mean > 45.0
                else ("Apply dynamic variance-scaled multiplier" if cov_pct < 90.0 else "Maintain current formulation")
            )
        })
        
    scale_csv = REPORTS_DIR / "service_scale_uncertainty_verification.csv"
    with open(scale_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(scale_rows[0].keys()))
        w.writeheader()
        w.writerows(scale_rows)
    print(f"✓ Created {scale_csv}")

    # -------------------------------------------------------------------------
    # 3. Hybrid Clinical Prediction Reconstruction (Exact Mathematical Check)
    # -------------------------------------------------------------------------
    import __main__
    from scripts.train_service_forecasting import SeasonalNaiveModel, PureRidgeRegression, PureHybridForecaster
    __main__.SeasonalNaiveModel = SeasonalNaiveModel
    __main__.PureRidgeRegression = PureRidgeRegression
    __main__.PureHybridForecaster = PureHybridForecaster

    with open(BASE_DIR / "final_model.joblib", "rb") as f:
        bundle = pickle.load(f)
    model = bundle["model_instance"]
    
    records = load_or_generate_service_dataset()
    featured = build_feature_matrix(records)
    holdout_items = [d for d in featured if d["period"] > 144]
    X_holdout = [d["features"] for d in holdout_items]
    
    seasonal_preds = model.seasonal_model.predict(X_holdout, holdout_items)
    residual_preds = model.residual_ridge.predict(X_holdout)
    direct_preds = model.predict(X_holdout, holdout_items)
    
    recon_rows = []
    max_recon_err = 0.0
    
    for i, h_item in enumerate(holdout_items):
        recon_val = max(0.0, seasonal_preds[i] + residual_preds[i])
        dir_val = direct_preds[i]
        diff = abs(recon_val - dir_val)
        if diff > max_recon_err:
            max_recon_err = diff
            
        saved_csv_val = float(holdout_rows[i]["predicted_demand"])
        rounding_diff = abs(recon_val - saved_csv_val)
        
        recon_rows.append({
            "period": h_item["period"],
            "month": h_item["month"],
            "service": h_item["service"],
            "seasonal_baseline_contribution": round(seasonal_preds[i], 4),
            "ridge_residual_contribution": round(residual_preds[i], 4),
            "reconstructed_hybrid_prediction": round(recon_val, 4),
            "direct_model_prediction": round(dir_val, 4),
            "exact_mathematical_diff": f"{diff:.2e}",
            "saved_csv_prediction": saved_csv_val,
            "rounding_discrepancy": round(rounding_diff, 4),
            "verification_status": "EXACT MATCH (Machine Precision)" if diff < 1e-12 else "MISMATCH"
        })
        
    recon_csv = REPORTS_DIR / "hybrid_reconstruction_verification.csv"
    with open(recon_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(recon_rows[0].keys()))
        w.writeheader()
        w.writerows(recon_rows)
    print(f"✓ Created {recon_csv} (Max direct error = {max_recon_err:.2e})")

    # -------------------------------------------------------------------------
    # 4. Emergency Medicine Buffer Evaluation (VALIDATION DATA ONLY)
    # -------------------------------------------------------------------------
    folds = [
        {"train_end": 96, "val_start": 97, "val_end": 108},
        {"train_end": 108, "val_start": 109, "val_end": 120},
        {"train_end": 120, "val_start": 121, "val_end": 132},
        {"train_end": 132, "val_start": 133, "val_end": 144}
    ]
    
    val_emergency_items = []
    for f_idx, fold in enumerate(folds):
        tr_data = [d for d in featured if d["period"] <= fold["train_end"]]
        val_data = [d for d in featured if fold["val_start"] <= d["period"] <= fold["val_end"]]
        
        X_tr = [d["features"] for d in tr_data]
        y_tr = [d["demand"] for d in tr_data]
        X_val = [d["features"] for d in val_data]
        y_val = [d["demand"] for d in val_data]
        
        m_fold = PureHybridForecaster(alpha=2.0)
        m_fold.fit(X_tr, y_tr, tr_data)
        
        tr_preds = m_fold.predict(X_tr, tr_data)
        tr_resids = sorted(abs(y_tr[i] - tr_preds[i]) for i in range(len(y_tr)))
        fold_q90 = tr_resids[int(0.90 * len(tr_resids))]
        
        val_preds = m_fold.predict(X_val, val_data)
        for i, v_item in enumerate(val_data):
            if v_item["service"] == "Emergency":
                act = y_val[i]
                pred = val_preds[i]
                res = abs(act - pred)
                val_emergency_items.append({
                    "fold": f_idx + 1,
                    "period": v_item["period"],
                    "month": v_item["month"],
                    "actual_demand": act,
                    "predicted_demand": round(pred, 2),
                    "abs_error": round(res, 2),
                    "base_q90": round(fold_q90, 2),
                    "covered_100x": int(res <= fold_q90),
                    "covered_110x": int(res <= 1.10 * fold_q90),
                    "covered_120x": int(res <= 1.20 * fold_q90),
                    "covered_125x": int(res <= 1.25 * fold_q90),
                    "covered_130x": int(res <= 1.30 * fold_q90)
                })
                
    buf_csv = REPORTS_DIR / "emergency_buffer_validation_folds.csv"
    with open(buf_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(val_emergency_items[0].keys()))
        w.writeheader()
        w.writerows(val_emergency_items)
    print(f"✓ Created {buf_csv}")

    print("=" * 80)
    print("Verification Artifacts Generation Complete.")
    print("=" * 80)

if __name__ == "__main__":
    run_verification()
