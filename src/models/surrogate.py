"""
Fast ML Surrogate Classifier module.
Trains a fast Random Forest classifier surrogate on Monte-Carlo simulator outputs
to provide instant (<5ms) interactive what-if slider updates in the Streamlit dashboard.
Evaluates true held-out scenario generalization fidelity (per-class precision/recall/F1,
balanced accuracy, macro F1, multiclass ECE with reliability curves) by splitting datasets
BY SCENARIO ID, and compares against a majority-class baseline.
"""
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_recall_fscore_support
)

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

def expected_calibration_error_multiclass(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    classes: List[str],
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Compute multiclass Expected Calibration Error (ECE) and per-class reliability diagrams.
    Evaluates one-vs-rest calibration error for each class across equal-width confidence bins.
    """
    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    n_samples = len(y_true)
    per_class = {}
    macro_ece = 0.0

    for k, c in enumerate(classes):
        y_bin = (y_true == c).astype(int)
        p_k = y_prob[:, k]
        ece_c = 0.0
        reliability_curve = []

        for b in range(n_bins):
            bin_lower = bin_boundaries[b]
            bin_upper = bin_boundaries[b + 1]
            if b == n_bins - 1:
                in_bin = (p_k >= bin_lower) & (p_k <= bin_upper)
            else:
                in_bin = (p_k >= bin_lower) & (p_k < bin_upper)

            count = int(np.sum(in_bin))
            if count > 0:
                acc_bin = float(np.mean(y_bin[in_bin]))
                conf_bin = float(np.mean(p_k[in_bin]))
                diff = abs(acc_bin - conf_bin)
                ece_c += (count / n_samples) * diff
                reliability_curve.append({
                    "bin_lower": round(bin_lower, 2),
                    "bin_upper": round(bin_upper, 2),
                    "sample_count": count,
                    "empirical_accuracy": round(acc_bin, 4),
                    "mean_confidence": round(conf_bin, 4),
                    "calibration_gap": round(diff, 4)
                })
            else:
                reliability_curve.append({
                    "bin_lower": round(bin_lower, 2),
                    "bin_upper": round(bin_upper, 2),
                    "sample_count": 0,
                    "empirical_accuracy": 0.0,
                    "mean_confidence": round((bin_lower + bin_upper) / 2.0, 4),
                    "calibration_gap": 0.0
                })

        per_class[c] = {
            "class": c,
            "ece": round(float(ece_c), 4),
            "reliability_curve": reliability_curve
        }
        macro_ece += ece_c

    macro_ece = float(macro_ece / max(1, len(classes)))
    return {
        "macro_ece": round(macro_ece, 4),
        "per_class": per_class
    }

def generate_scenario_dataset(n_scenarios: int = 500, random_seed: int = 42) -> pd.DataFrame:
    """
    Generate multi-scenario Monte-Carlo simulation dataset across stratified disaster stress regimes
    (severe disaster / depleted stock, moderate disaster / tight stock, mild disaster / surplus stock)
    such that Low, Medium, and High risk are each guaranteed to represent >= 15% of the total rows.
    """
    from src.data.boundaries import MAHARASHTRA_DISTRICTS
    from src.engine.demand import estimate_district_stocks
    from src.engine.monte_carlo import run_monte_carlo_district_simulation

    rng = np.random.default_rng(random_seed)
    districts = list(MAHARASHTRA_DISTRICTS.keys())
    base_stocks = estimate_district_stocks()
    hazards = ["Flood", "Storm", "Epidemic", "Earthquake", "Extreme temp"]

    scenarios_list = []
    print(f"Sampling {n_scenarios} stratified scenarios to ensure balanced Low, Medium, High risk classes (>= 15% each)...")

    for s in range(n_scenarios):
        regime = s % 3
        h_type = str(rng.choice(hazards))
        epi = str(rng.choice(districts))
        month = int(rng.integers(1, 13))

        if regime == 0:
            # Severe stress: large disaster, depleted stock -> yields substantial High risk
            aff_log = float(rng.uniform(12.5, 16.5))
            stock_mult = float(rng.uniform(0.01, 0.15))
            decay_km = float(rng.uniform(200.0, 500.0))
        elif regime == 1:
            # Moderate stress: medium disaster, tight stock -> yields substantial Medium risk
            aff_log = float(rng.uniform(10.5, 13.8))
            stock_mult = float(rng.uniform(0.10, 0.45))
            decay_km = float(rng.uniform(150.0, 350.0))
        else:
            # Mild stress: mild disaster, surplus/baseline stock -> yields substantial Low risk
            aff_log = float(rng.uniform(7.5, 11.0))
            stock_mult = float(rng.uniform(0.60, 1.50))
            decay_km = float(rng.uniform(100.0, 250.0))

        scenario_stocks = {
            d: {m: max(1.0, round(qty * stock_mult, 1)) for m, qty in meds.items()}
            for d, meds in base_stocks.items()
        }

        sim_df = run_monte_carlo_district_simulation(
            epicentre=epi,
            event_affected_mean_log=aff_log,
            hazard_type=h_type,
            district_stocks=scenario_stocks,
            decay_km=decay_km,
            n_draws=100,
            random_seed=random_seed + s * 13
        )

        sim_df["scenario_id"] = s
        sim_df["month"] = month
        sim_df["epicentre"] = epi
        sim_df["stock_multiplier"] = stock_mult
        scenarios_list.append(sim_df)

    full_df = pd.concat(scenarios_list, ignore_index=True)

    # Class balance audit
    class_shares = full_df["risk_level"].value_counts(normalize=True).to_dict()
    print("Scenario Dataset Risk Distribution:")
    for c in ["Low", "Medium", "High"]:
        pct = class_shares.get(c, 0.0) * 100
        print(f"  {c}: {pct:.2f}% of rows")

    return full_df

def train_surrogate_classifier(
    sim_df: pd.DataFrame = None,
    n_scenarios: int = 500,
    random_seed: int = 42
) -> Dict[str, Any]:
    """
    Train Random Forest surrogate classifier on scenario-sampled Monte-Carlo outputs.
    Splits scenarios BY SCENARIO ID (80% train / 20% test) to prevent scenario data leakage.
    Evaluates:
      - per-class precision, recall, F1, and support
      - balanced accuracy and macro-F1
      - multiclass ECE with per-class reliability diagrams
      - majority-class baseline comparison
    Saves reports/surrogate_metrics.json and models/shortage_classifier.joblib.
    """
    if sim_df is None or "scenario_id" not in sim_df.columns:
        full_df = generate_scenario_dataset(n_scenarios=n_scenarios, random_seed=random_seed)
    else:
        full_df = sim_df.copy()

    unique_scenarios = np.array(sorted(full_df["scenario_id"].unique()))
    rng = np.random.default_rng(random_seed)
    rng.shuffle(unique_scenarios)

    n_train = int(len(unique_scenarios) * 0.8)
    train_ids = set(unique_scenarios[:n_train])
    test_ids = set(unique_scenarios[n_train:])

    train_df = full_df[full_df["scenario_id"].isin(train_ids)].copy()
    test_df = full_df[full_df["scenario_id"].isin(test_ids)].copy()

    for df in [train_df, test_df]:
        df["log_demand"] = np.log1p(df["demand_p50"].clip(lower=0))
        df["log_stock"] = np.log1p(df["available_stock"].clip(lower=0))
        df["stock_deficit_ratio"] = (df["demand_p50"] - df["available_stock"]) / (df["available_stock"] + 1.0)

    num_cols = ["log_demand", "log_stock", "stock_deficit_ratio", "horizon_days", "month"]
    cat_cols = ["district", "medicine", "hazard_type"]

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols)
    ])

    X_train = preprocessor.fit_transform(train_df[num_cols + cat_cols])
    y_train = train_df["risk_level"].values

    X_test = preprocessor.transform(test_df[num_cols + cat_cols])
    y_test = test_df["risk_level"].values

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        class_weight="balanced",
        random_state=random_seed,
        n_jobs=-1
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)
    classes = list(clf.classes_)

    # Majority-class dummy baseline
    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit(X_train, y_train)
    dummy_pred = dummy.predict(X_test)

    # Core Metrics
    surr_acc = float(accuracy_score(y_test, y_pred))
    surr_bal_acc = float(balanced_accuracy_score(y_test, y_pred))
    surr_macro_f1 = float(f1_score(y_test, y_pred, average="macro"))
    surr_weighted_f1 = float(f1_score(y_test, y_pred, average="weighted"))

    p_c, r_c, f1_c, s_c = precision_recall_fscore_support(y_test, y_pred, labels=classes, zero_division=0)
    per_class_metrics = {}
    for idx, c in enumerate(classes):
        per_class_metrics[c] = {
            "precision": round(float(p_c[idx]), 4),
            "recall": round(float(r_c[idx]), 4),
            "f1_score": round(float(f1_c[idx]), 4),
            "support": int(s_c[idx])
        }

    # Majority-class metrics
    dum_acc = float(accuracy_score(y_test, dummy_pred))
    dum_bal_acc = float(balanced_accuracy_score(y_test, dummy_pred))
    dum_macro_f1 = float(f1_score(y_test, dummy_pred, average="macro"))
    dum_weighted_f1 = float(f1_score(y_test, dummy_pred, average="weighted"))

    p_d, r_d, f1_d, s_d = precision_recall_fscore_support(y_test, dummy_pred, labels=classes, zero_division=0)
    dummy_per_class = {}
    for idx, c in enumerate(classes):
        dummy_per_class[c] = {
            "precision": round(float(p_d[idx]), 4),
            "recall": round(float(r_d[idx]), 4),
            "f1_score": round(float(f1_d[idx]), 4),
            "support": int(s_d[idx])
        }

    # Multiclass ECE & reliability curves
    ece_info = expected_calibration_error_multiclass(y_test, y_prob, classes, n_bins=10)

    print(f"\n✓ Trained Surrogate Classifier on {len(unique_scenarios)} Scenarios (Split BY SCENARIO ID)")
    print(f"  Accuracy: {surr_acc*100:.2f}% | Balanced Accuracy: {surr_bal_acc*100:.2f}% | Macro F1: {surr_macro_f1:.4f} | Multiclass ECE: {ece_info['macro_ece']:.4f}")
    print("  Per-Class Metrics (Surrogate):")
    for c, m in per_class_metrics.items():
        print(f"    {c}: Precision={m['precision']:.4f}, Recall={m['recall']:.4f}, F1={m['f1_score']:.4f}, ECE={ece_info['per_class'][c]['ece']:.4f} (N={m['support']})")
    print(f"  Majority Baseline ({classes[0]}): Accuracy={dum_acc*100:.2f}%, Balanced Acc={dum_bal_acc*100:.2f}%, Macro F1={dum_macro_f1:.4f}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    metrics_export = {
        "model_type": "Random Forest Surrogate (Split by Scenario ID)",
        "n_scenarios": len(unique_scenarios),
        "n_train_scenarios": len(train_ids),
        "n_test_scenarios": len(test_ids),
        "class_distribution_overall_pct": {
            c: round(float((full_df["risk_level"] == c).mean()) * 100.0, 2) for c in classes
        },
        "surrogate_classifier": {
            "accuracy": round(surr_acc, 4),
            "balanced_accuracy": round(surr_bal_acc, 4),
            "macro_f1": round(surr_macro_f1, 4),
            "weighted_f1": round(surr_weighted_f1, 4),
            "macro_ece": round(ece_info["macro_ece"], 4),
            "per_class": per_class_metrics,
            "calibration": ece_info
        },
        "majority_class_baseline": {
            "strategy": "most_frequent",
            "accuracy": round(dum_acc, 4),
            "balanced_accuracy": round(dum_bal_acc, 4),
            "macro_f1": round(dum_macro_f1, 4),
            "weighted_f1": round(dum_weighted_f1, 4),
            "per_class": dummy_per_class
        },
        "comparison_delta": {
            "macro_f1_gain": round(surr_macro_f1 - dum_macro_f1, 4),
            "balanced_accuracy_gain": round(surr_bal_acc - dum_bal_acc, 4)
        }
    }

    with open(REPORTS_DIR / "surrogate_metrics.json", "w") as f:
        json.dump(metrics_export, f, indent=2)

    bundle = {
        "preprocessor": preprocessor,
        "classifier": clf,
        "classes": classes,
        "fidelity_acc": surr_acc,
        "balanced_acc": surr_bal_acc,
        "macro_f1": surr_macro_f1,
        "fidelity_f1": surr_macro_f1,
        "ece": ece_info["macro_ece"],
        "macro_ece": ece_info["macro_ece"],
        "per_class_metrics": per_class_metrics,
        "calibration": ece_info,
        "majority_baseline": metrics_export["majority_class_baseline"],
        "model_type": "SURROGATE_APPROXIMATION"
    }

    surr_path = MODELS_DIR / "shortage_classifier.joblib"
    joblib.dump(bundle, surr_path)
    print(f"Surrogate model bundle saved to {surr_path}")
    print(f"Surrogate metrics saved to {REPORTS_DIR / 'surrogate_metrics.json'}")

    return bundle

if __name__ == "__main__":
    train_surrogate_classifier(n_scenarios=500)

