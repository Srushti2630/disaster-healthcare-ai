"""
Model training, evaluation, calibration, explainability and bias checking.
Trains Module 3.1 (Impact), Module 3.2 (Demand), Module 3.3 (Shortage Risk), and SHAP explainers.
"""
import os
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

from pathlib import Path
import json
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
import xgboost as xgb

MODEL_VERSION = "v1.0.0"
CLEAN_DIR = Path("data/processed/clean")
MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

RISK_MAP = {"Low": 0, "Medium": 1, "High": 2}
REV_RISK_MAP = {0: "Low", 1: "Medium", 2: "High"}


def compute_multiclass_ece(probs, y_true, n_bins=10):
    """Compute Expected Calibration Error (ECE) for multi-class classification."""
    confidences = np.max(probs, axis=1)
    predictions = np.argmax(probs, axis=1)
    accuracies = predictions == y_true

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        bin_lower = bins[i]
        bin_upper = bins[i + 1]
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = np.mean(in_bin)

        if prop_in_bin > 0:
            bin_acc = np.mean(accuracies[in_bin])
            bin_conf = np.mean(confidences[in_bin])
            ece += np.abs(bin_acc - bin_conf) * prop_in_bin

    return float(ece)


def train_emdat_benchmark():
    """Train benchmark regression on real EM-DAT India records for affected population."""
    emdat_path = CLEAN_DIR / "disaster_events_clean.csv"
    if not emdat_path.exists():
        return {"status": "missing"}

    df = pd.read_csv(emdat_path)
    real_df = df[df["has_affected"]].copy()

    if len(real_df) < 50:
        return {"status": "too_sparse", "count": len(real_df)}

    real_df["type"] = real_df["type"].fillna("unknown")
    real_df["month"] = real_df["month"].fillna(6)
    real_df["intensity"] = real_df["intensity"].fillna(real_df["intensity"].median())

    y = real_df["log1p_affected"].values
    X = real_df[["type", "month", "intensity"]]

    split_idx = int(len(real_df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["type"]),
            ("num", StandardScaler(), ["month", "intensity"]),
        ]
    )

    mean_val = np.mean(y_train)
    y_pred_base = np.full_like(y_test, mean_val)
    base_mae = float(mean_absolute_error(y_test, y_pred_base))
    base_r2 = float(r2_score(y_test, y_pred_base))

    rf = Pipeline([
        ("prep", preprocessor),
        ("reg", RandomForestRegressor(n_estimators=50, random_state=42, max_depth=6)),
    ])
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    rf_mae = float(mean_absolute_error(y_test, y_pred_rf))
    rf_r2 = float(r2_score(y_test, y_pred_rf))

    return {
        "dataset": "EM-DAT India (Real)",
        "samples_used": len(real_df),
        "mean_baseline_mae": base_mae,
        "mean_baseline_r2": base_r2,
        "rf_mae": rf_mae,
        "rf_r2": rf_r2,
        "note": "Trained on log1p(affected). Targets were never imputed; only rows with recorded affected count were evaluated.",
    }


def explain_shortage_prediction(feature_dict, clf_pipeline, explainer, top_k=3):
    """
    Generate plain-English explanation of top drivers for hospital administrators.
    """
    clf_features = [
        "predicted_demand", "stock_units", "medicine", "disaster_type",
        "severity", "month", "hazard_intensity", "distance_km", "population", "beds"
    ]
    row_df = pd.DataFrame([feature_dict])[clf_features]
    prep_step = clf_pipeline.named_steps["prep"]
    X_trans = prep_step.transform(row_df)
    feat_names = [f.replace("cat__", "").replace("num__", "") for f in prep_step.get_feature_names_out()]

    shap_vals = explainer.shap_values(X_trans)
    if isinstance(shap_vals, list):
        class_shap = shap_vals[2][0]  # High risk class
    elif len(shap_vals.shape) == 3:
        class_shap = shap_vals[0, :, 2]
    else:
        class_shap = shap_vals[0]

    ranked_idx = np.argsort(np.abs(class_shap))[::-1][:top_k]
    drivers = []
    readable_names = {
        "stock_units": "current inventory stock",
        "predicted_demand": "projected 7-day demand",
        "distance_km": "distance from disaster epicentre",
        "hazard_intensity": "hazard intensity level",
        "population": "regional catchment population",
        "beds": "hospital bed capacity",
        "severity": "disaster severity rating",
        "month": "seasonal month",
    }

    for idx in ranked_idx:
        fname = feat_names[idx]
        val = feature_dict.get(fname, None)
        impact = "increases" if class_shap[idx] > 0 else "reduces"
        label = readable_names.get(fname, fname.replace("_", " "))
        val_str = f" ({val:.0f} units)" if ("stock" in fname or "demand" in fname) and val is not None else f" ({val})" if val is not None else ""
        drivers.append(f"{label}{val_str} which {impact} shortage risk")

    if len(drivers) >= 3:
        sentence = f"Shortage drivers: Primarily influenced by {drivers[0]}, followed by {drivers[1]}, and {drivers[2]}."
    else:
        sentence = f"Shortage drivers: Primarily influenced by {', '.join(drivers)}."
    return sentence


def run_training_pipeline():
    print("=" * 60)
    print(f"Starting Stage 2: Training Pipeline (Version: {MODEL_VERSION})")
    print("=" * 60)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Real EM-DAT Benchmark
    emdat_metrics = train_emdat_benchmark()
    print("✓ Evaluated real EM-DAT benchmark model.")

    # 2. Load Synthetic Datasets
    short_df = pd.read_csv(CLEAN_DIR / "shortage_dataset_clean.csv")

    # 3. Group Split by scenario_id
    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(gss.split(short_df, groups=short_df["scenario_id"]))

    train_df = short_df.iloc[train_idx].copy().reset_index(drop=True)
    test_df = short_df.iloc[test_idx].copy().reset_index(drop=True)

    # Verification: zero overlap
    train_scenarios = set(train_df["scenario_id"].unique())
    test_scenarios = set(test_df["scenario_id"].unique())
    overlap = train_scenarios.intersection(test_scenarios)
    assert len(overlap) == 0, f"DATA LEAKAGE: Scenarios {overlap} present in both train and test!"
    print(f"✓ Split verified: {len(train_scenarios)} train scenarios ({len(train_df)} rows), "
          f"{len(test_scenarios)} test scenarios ({len(test_df)} rows). Zero overlap.")

    # -------------------------------------------------------------
    # 4. MODULE 3.1: Disaster Impact Regression
    # -------------------------------------------------------------
    impact_features = ["disaster_type", "hazard_intensity", "distance_km", "population", "month", "severity"]
    impact_targets = ["affected_pop", "injured", "ill"]

    impact_preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["disaster_type"]),
            ("num", StandardScaler(), ["hazard_intensity", "distance_km", "population", "month", "severity"]),
        ]
    )

    X_impact_train = train_df[impact_features]
    X_impact_test = test_df[impact_features]

    impact_models = {}
    impact_metrics = {}

    for tgt in impact_targets:
        y_tr = np.log1p(train_df[tgt].values)
        y_te = np.log1p(test_df[tgt].values)

        mean_pred = np.mean(y_tr)
        base_mae = float(mean_absolute_error(y_te, np.full_like(y_te, mean_pred)))
        base_r2 = float(r2_score(y_te, np.full_like(y_te, mean_pred)))

        rf_pipe = Pipeline([
            ("prep", impact_preprocessor),
            ("reg", RandomForestRegressor(n_estimators=40, max_depth=8, random_state=42, n_jobs=-1)),
        ])
        rf_pipe.fit(X_impact_train, y_tr)
        rf_pred = rf_pipe.predict(X_impact_test)
        rf_mae = float(mean_absolute_error(y_te, rf_pred))
        rf_r2 = float(r2_score(y_te, rf_pred))

        xgb_pipe = Pipeline([
            ("prep", impact_preprocessor),
            ("reg", xgb.XGBRegressor(n_estimators=40, max_depth=6, learning_rate=0.1, random_state=42)),
        ])
        xgb_pipe.fit(X_impact_train, y_tr)
        xgb_pred = xgb_pipe.predict(X_impact_test)
        xgb_mae = float(mean_absolute_error(y_te, xgb_pred))
        xgb_r2 = float(r2_score(y_te, xgb_pred))

        impact_models[tgt] = xgb_pipe
        impact_metrics[tgt] = {
            "baseline_mean_mae": base_mae,
            "baseline_mean_r2": base_r2,
            "random_forest_mae": rf_mae,
            "random_forest_r2": rf_r2,
            "xgboost_mae": xgb_mae,
            "xgboost_r2": xgb_r2,
        }

        train_df[f"{tgt}_pred"] = np.expm1(xgb_pipe.predict(X_impact_train)).clip(min=0)
        test_df[f"{tgt}_pred"] = np.expm1(xgb_pred).clip(min=0)

    print("✓ Module 3.1 Impact models trained (RF & XGBoost vs Baseline).")

    # -------------------------------------------------------------
    # 5. MODULE 3.2: 7-Day Medicine Demand Forecast
    # -------------------------------------------------------------
    demand_features = [
        "medicine", "disaster_type", "hazard_intensity", "distance_km",
        "population", "beds", "month", "affected_pop_pred", "injured_pred", "ill_pred"
    ]
    y_dem_train = train_df["demand_7d"].values
    y_dem_test = test_df["demand_7d"].values

    demand_preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["medicine", "disaster_type"]),
            ("num", StandardScaler(), ["hazard_intensity", "distance_km", "population", "beds", "month",
                                       "affected_pop_pred", "injured_pred", "ill_pred"]),
        ]
    )

    med_means = train_df.groupby("medicine")["demand_7d"].mean().to_dict()
    base_dem_pred = test_df["medicine"].map(med_means).values
    dem_base_mae = float(mean_absolute_error(y_dem_test, base_dem_pred))
    dem_base_r2 = float(r2_score(y_dem_test, base_dem_pred))

    dem_xgb = Pipeline([
        ("prep", demand_preprocessor),
        ("reg", xgb.XGBRegressor(n_estimators=50, max_depth=6, learning_rate=0.1, random_state=42)),
    ])
    dem_xgb.fit(train_df[demand_features], np.log1p(y_dem_train))

    y_dem_pred_train = np.expm1(dem_xgb.predict(train_df[demand_features])).clip(min=0)
    y_dem_pred_test = np.expm1(dem_xgb.predict(test_df[demand_features])).clip(min=0)

    dem_xgb_mae = float(mean_absolute_error(y_dem_test, y_dem_pred_test))
    dem_xgb_r2 = float(r2_score(y_dem_test, y_dem_pred_test))

    calib_residuals = np.abs(y_dem_train - y_dem_pred_train)
    conformal_alpha = 0.10
    conformal_quantile = float(np.percentile(calib_residuals, 100 * (1 - conformal_alpha)))

    lower_bounds = np.maximum(0.0, y_dem_pred_test - conformal_quantile)
    upper_bounds = y_dem_pred_test + conformal_quantile
    empirical_coverage = float(np.mean((y_dem_test >= lower_bounds) & (y_dem_test <= upper_bounds)))

    demand_metrics = {
        "baseline_mean_mae": dem_base_mae,
        "baseline_mean_r2": dem_base_r2,
        "xgb_mae": dem_xgb_mae,
        "xgb_r2": dem_xgb_r2,
        "conformal_target_coverage": 1.0 - conformal_alpha,
        "conformal_margin_units": conformal_quantile,
        "empirical_test_coverage": empirical_coverage,
    }

    train_df["predicted_demand"] = y_dem_pred_train
    test_df["predicted_demand"] = y_dem_pred_test
    print(f"✓ Module 3.2 Demand forecast trained. Test R2: {dem_xgb_r2:.3f}, Empirical Conformal Coverage: {empirical_coverage*100:.1f}%.")

    # -------------------------------------------------------------
    # 6. MODULE 3.3: Shortage Classifier (Low / Medium / High)
    # -------------------------------------------------------------
    clf_features = [
        "predicted_demand", "stock_units", "medicine", "disaster_type",
        "severity", "month", "hazard_intensity", "distance_km", "population", "beds"
    ]
    leakage_cols = {"demand_7d", "shortage_qty", "coverage_ratio", "affected_pop", "injured", "ill"}
    assert leakage_cols.isdisjoint(set(clf_features)), "LEAKAGE DETECTED: Ground truth targets present in classifier inputs!"

    y_clf_train = train_df["risk_level"].map(RISK_MAP).values
    y_clf_test = test_df["risk_level"].map(RISK_MAP).values

    clf_preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["medicine", "disaster_type"]),
            ("num", StandardScaler(), ["predicted_demand", "stock_units", "severity", "month",
                                       "hazard_intensity", "distance_km", "population", "beds"]),
        ]
    )

    logreg_pipe = Pipeline([
        ("prep", clf_preprocessor),
        ("clf", LogisticRegression(max_iter=500, class_weight="balanced", random_state=42)),
    ])
    logreg_pipe.fit(train_df[clf_features], y_clf_train)
    logreg_pred = logreg_pipe.predict(test_df[clf_features])
    logreg_acc = float(accuracy_score(y_clf_test, logreg_pred))
    logreg_f1 = float(f1_score(y_clf_test, logreg_pred, average="macro"))

    rf_base = Pipeline([
        ("prep", clf_preprocessor),
        ("clf", RandomForestClassifier(
            n_estimators=60, max_depth=10, class_weight="balanced",
            random_state=42, n_jobs=-1
        )),
    ])
    rf_base.fit(train_df[clf_features], y_clf_train)

    calibrated_clf = CalibratedClassifierCV(estimator=rf_base, method="sigmoid", cv=3)
    calibrated_clf.fit(train_df[clf_features], y_clf_train)

    test_probs = calibrated_clf.predict_proba(test_df[clf_features])
    standard_preds = np.argmax(test_probs, axis=1)

    train_probs = calibrated_clf.predict_proba(train_df[clf_features])
    y_train_high = y_clf_train == 2

    candidate_thresholds = np.linspace(0.10, 0.45, 36)
    best_thresh = 0.25
    for th in candidate_thresholds:
        cand_high = train_probs[:, 2] >= th
        rec = np.sum(cand_high & y_train_high) / max(1, np.sum(y_train_high))
        if rec >= 0.95:
            best_thresh = float(th)

    def apply_conservative_rule(probs, high_thresh=best_thresh):
        preds = []
        for p in probs:
            if p[2] >= high_thresh:
                preds.append(2)
            else:
                preds.append(0 if p[0] >= p[1] else 1)
        return np.array(preds)

    conservative_preds = apply_conservative_rule(test_probs, best_thresh)

    y_test_high = y_clf_test == 2
    high_rec_std = float(recall_score(y_test_high, standard_preds == 2))
    high_prec_std = float(precision_score(y_test_high, standard_preds == 2, zero_division=0))

    high_rec_cons = float(recall_score(y_test_high, conservative_preds == 2))
    high_prec_cons = float(precision_score(y_test_high, conservative_preds == 2, zero_division=0))

    ece_value = compute_multiclass_ece(test_probs, y_clf_test)

    clf_metrics = {
        "baseline_logistic_acc": logreg_acc,
        "baseline_logistic_macro_f1": logreg_f1,
        "calibrated_rf_standard_acc": float(accuracy_score(y_clf_test, standard_preds)),
        "calibrated_rf_standard_macro_f1": float(f1_score(y_clf_test, standard_preds, average="macro")),
        "high_risk_standard_recall": high_rec_std,
        "high_risk_standard_precision": high_prec_std,
        "conservative_threshold_high": best_thresh,
        "conservative_rf_acc": float(accuracy_score(y_clf_test, conservative_preds)),
        "conservative_rf_macro_f1": float(f1_score(y_clf_test, conservative_preds, average="macro")),
        "high_risk_conservative_recall": high_rec_cons,
        "high_risk_conservative_precision": high_prec_cons,
        "expected_calibration_error": ece_value,
    }

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for c_idx, c_name in enumerate(["Low", "Medium", "High"]):
        prob_true, prob_pred = calibration_curve(y_clf_test == c_idx, test_probs[:, c_idx], n_bins=8)
        axes[c_idx].plot([0, 1], [0, 1], "k--", label="Perfect Calibration")
        axes[c_idx].plot(prob_pred, prob_true, "s-", color="navy", label="Calibrated RF")
        axes[c_idx].set_title(f"Class: {c_name} (ECE={ece_value:.3f})")
        axes[c_idx].set_xlabel("Mean Predicted Probability")
        axes[c_idx].set_ylabel("Fraction of Positives")
        axes[c_idx].legend(loc="lower right")
        axes[c_idx].grid(True, alpha=0.3)
    plt.tight_layout()
    calib_plot_path = REPORTS_DIR / "calibration.png"
    plt.savefig(calib_plot_path, dpi=150)
    plt.close()
    print(f"✓ Calibration curves saved to {calib_plot_path}. ECE: {ece_value:.4f}")

    # -------------------------------------------------------------
    # 7. SHAP EXPLAINABILITY
    # -------------------------------------------------------------
    rf_model_step = rf_base.named_steps["clf"]
    prep_step = rf_base.named_steps["prep"]

    shap_sample_df = test_df.sample(n=min(2000, len(test_df)), random_state=42)[clf_features]
    X_shap_transformed = prep_step.transform(shap_sample_df)
    transformed_feature_names = prep_step.get_feature_names_out()

    print("Computing TreeExplainer SHAP values (sample size: 2000)...")
    explainer = shap.TreeExplainer(rf_model_step)
    shap_values = explainer.shap_values(X_shap_transformed)

    if isinstance(shap_values, list):
        shap_vals_high = shap_values[2]
    elif len(shap_values.shape) == 3:
        shap_vals_high = shap_values[:, :, 2]
    else:
        shap_vals_high = shap_values

    clean_feature_names = [f.replace("cat__", "").replace("num__", "") for f in transformed_feature_names]

    plt.figure(figsize=(10, 6))
    shap.summary_plot(
        shap_vals_high,
        X_shap_transformed,
        feature_names=clean_feature_names,
        show=False,
        max_display=10,
    )
    plt.title("SHAP Feature Importance (High Shortage Risk)", fontsize=13)
    plt.tight_layout()
    shap_plot_path = REPORTS_DIR / "shap_summary.png"
    plt.savefig(shap_plot_path, dpi=150)
    plt.close()
    print(f"✓ SHAP summary plot saved to {shap_plot_path}.")

    # -------------------------------------------------------------
    # 8. BIAS & SUBGROUP DISAGGREGATED ANALYSIS
    # -------------------------------------------------------------
    test_df["conservative_pred"] = conservative_preds
    test_df["y_true"] = y_clf_test

    bias_rows = []
    region_id_map = {
        0: "Pune", 1: "Mumbai", 2: "Nashik", 3: "Nagpur", 4: "Kolhapur",
        5: "Satara", 6: "Ratnagiri", 7: "Sangli", 8: "Aurangabad", 9: "Solapur"
    }

    for reg_id, g in test_df.groupby("region_id"):
        reg_name = region_id_map.get(reg_id, f"Region_{reg_id}")
        actual_h = g["y_true"] == 2
        pred_h = g["conservative_pred"] == 2
        h_rec = float(recall_score(actual_h, pred_h, zero_division=0))
        h_prec = float(precision_score(actual_h, pred_h, zero_division=0))
        acc = float(accuracy_score(g["y_true"], g["conservative_pred"]))
        f1_m = float(f1_score(g["y_true"], g["conservative_pred"], average="macro", zero_division=0))

        bias_rows.append({
            "dimension": "region",
            "group": reg_name,
            "sample_count": len(g),
            "high_risk_prevalence": float(actual_h.mean()),
            "accuracy": acc,
            "macro_f1": f1_m,
            "high_risk_recall": h_rec,
            "high_risk_precision": h_prec,
            "flag_disparity": "YES (Low High-Recall)" if h_rec < 0.85 else "NO",
        })

    for dtype, g in test_df.groupby("disaster_type"):
        actual_h = g["y_true"] == 2
        pred_h = g["conservative_pred"] == 2
        h_rec = float(recall_score(actual_h, pred_h, zero_division=0))
        h_prec = float(precision_score(actual_h, pred_h, zero_division=0))
        acc = float(accuracy_score(g["y_true"], g["conservative_pred"]))
        f1_m = float(f1_score(g["y_true"], g["conservative_pred"], average="macro", zero_division=0))

        bias_rows.append({
            "dimension": "disaster_type",
            "group": dtype,
            "sample_count": len(g),
            "high_risk_prevalence": float(actual_h.mean()),
            "accuracy": acc,
            "macro_f1": f1_m,
            "high_risk_recall": h_rec,
            "high_risk_precision": h_prec,
            "flag_disparity": "YES (Low High-Recall)" if h_rec < 0.85 else "NO",
        })

    bias_df = pd.DataFrame(bias_rows)
    bias_path = REPORTS_DIR / "bias_table.csv"
    bias_df.to_csv(bias_path, index=False)
    print(f"✓ Saved disaggregated bias table to {bias_path}.")

    # -------------------------------------------------------------
    # 9. SAVE ARTIFACTS AND METRICS
    # -------------------------------------------------------------
    artifacts = {
        "impact_models": impact_models,
        "impact_features": impact_features,
        "demand_model": dem_xgb,
        "demand_features": demand_features,
        "conformal_quantile": conformal_quantile,
        "calibrated_classifier": calibrated_clf,
        "clf_base_rf": rf_base,
        "clf_features": clf_features,
        "shap_explainer": explainer,
        "conservative_high_threshold": best_thresh,
        "model_version": MODEL_VERSION,
    }
    model_bundle_path = MODELS_DIR / "pipeline_bundle.joblib"
    joblib.dump(artifacts, model_bundle_path)

    # Individual joblib files for versioned clarity
    joblib.dump(impact_models, MODELS_DIR / "impact_models.joblib")
    joblib.dump(dem_xgb, MODELS_DIR / "demand_model.joblib")
    joblib.dump(calibrated_clf, MODELS_DIR / "shortage_classifier.joblib")
    joblib.dump(conformal_quantile, MODELS_DIR / "conformal_quantiles.joblib")
    joblib.dump(explainer, MODELS_DIR / "shap_explainer.joblib")

    print(f"✓ Saved model artifacts to {MODELS_DIR}/.")

    all_metrics = {
        "model_version": MODEL_VERSION,
        "real_emdat_benchmark": emdat_metrics,
        "module_3_1_impact": impact_metrics,
        "module_3_2_demand": demand_metrics,
        "module_3_3_shortage_classifier": clf_metrics,
    }
    metrics_path = REPORTS_DIR / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(all_metrics, f, indent=2)
    print(f"✓ Saved comprehensive evaluation metrics to {metrics_path}.")

    print("Stage 2 completed successfully.")
    return all_metrics


if __name__ == "__main__":
    run_training_pipeline()
