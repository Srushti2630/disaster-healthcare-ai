"""
Fast ML Surrogate Classifier module.
Trains a fast Random Forest classifier surrogate on Monte-Carlo simulator outputs
to provide instant (<5ms) interactive what-if slider updates in the Streamlit dashboard.
Reports fidelity (accuracy, macro F1, ECE) vs the full Monte-Carlo engine.
"""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, f1_score

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

def expected_calibration_error(y_true, y_prob, n_bins=10):
    """Compute Expected Calibration Error (ECE)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        bin_lower, bin_upper = bin_boundaries[i], bin_boundaries[i + 1]
        in_bin = (y_prob >= bin_lower) & (y_prob < bin_upper)
        prop_in_bin = np.mean(in_bin)
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_confidence_in_bin = np.mean(y_prob[in_bin])
            ece += np.abs(accuracy_in_bin - avg_confidence_in_bin) * prop_in_bin
    return float(ece)

def train_surrogate_classifier(sim_df: pd.DataFrame):
    """Train Random Forest surrogate classifier on Monte-Carlo simulation outputs."""
    df = sim_df.copy()
    
    # Feature columns
    df["log_demand"] = np.log1p(df["demand_p50"].clip(lower=0))
    df["log_stock"] = np.log1p(df["available_stock"].clip(lower=0))
    df["stock_deficit_ratio"] = (df["demand_p50"] - df["available_stock"]) / (df["available_stock"] + 1.0)

    feature_cols_num = ["log_demand", "log_stock", "stock_deficit_ratio", "horizon_days"]
    feature_cols_cat = ["district", "medicine", "hazard_type"]

    X = df[feature_cols_num + feature_cols_cat]
    y = df["risk_level"]

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), feature_cols_num),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), feature_cols_cat)
    ])

    X_prep = preprocessor.fit_transform(X)

    clf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    clf.fit(X_prep, y)

    y_pred = clf.predict(X_prep)
    y_prob = clf.predict_proba(X_prep)

    acc = float(accuracy_score(y, y_pred))
    f1 = float(f1_score(y, y_pred, average="macro"))

    # Compute ECE on high-risk probability
    high_idx = list(clf.classes_).index("High") if "High" in clf.classes_ else 0
    y_true_high = (y == "High").astype(int).values
    ece_val = expected_calibration_error(y_true_high, y_prob[:, high_idx])

    print(f"✓ Trained Monte-Carlo Surrogate Classifier | Fidelity Accuracy: {acc*100:.1f}% | Macro F1: {f1:.4f} | ECE: {ece_val:.4f}")

    # Save artifact
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    bundle = {
        "preprocessor": preprocessor,
        "classifier": clf,
        "classes": list(clf.classes_),
        "fidelity_acc": acc,
        "fidelity_f1": f1,
        "ece": ece_val,
        "model_type": "SURROGATE_APPROXIMATION"
    }
    
    surr_path = MODELS_DIR / "shortage_classifier.joblib"
    joblib.dump(bundle, surr_path)
    print(f"Surrogate model saved to {surr_path}")

    return bundle

if __name__ == "__main__":
    from src.engine.monte_carlo import run_monte_carlo_district_simulation
    from src.data.boundaries import MAHARASHTRA_DISTRICTS
    
    test_preds = {d: {"hazard_type": "Flood", "affected_mean_log": 8.0, "affected_std_log": 0.40} for d in MAHARASHTRA_DISTRICTS.keys()}
    sim_df = run_monte_carlo_district_simulation(test_preds, n_draws=1000)
    train_surrogate_classifier(sim_df)
