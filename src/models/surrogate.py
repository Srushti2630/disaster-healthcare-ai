"""
Fast ML Surrogate Classifier module.
Trains a fast Random Forest classifier surrogate on Monte-Carlo simulator outputs
to provide instant (<5ms) interactive what-if slider updates in the Streamlit dashboard.
Evaluates true held-out scenario generalization fidelity (accuracy, macro F1, ECE)
by splitting datasets BY SCENARIO ID.
"""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score, f1_score

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

def expected_calibration_error(y_true, y_prob, n_bins=10):
    """Compute Expected Calibration Error (ECE)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        bin_lower, bin_upper = bin_boundaries[i], bin_boundaries[i + 1]
        in_bin = (y_prob >= bin_lower) & (y_prob < bin_upper)
        prop_in_bin = np.mean(in_bin)
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_confidence_in_bin = np.mean(y_prob[in_bin])
            ece += np.abs(accuracy_in_bin - avg_confidence_in_bin) * prop_in_bin
    return float(ece)

def generate_scenario_dataset(n_scenarios: int = 500, random_seed: int = 42) -> pd.DataFrame:
    """Generate multi-scenario Monte-Carlo simulation dataset across 500+ diverse hazard scenarios."""
    from src.data.boundaries import MAHARASHTRA_DISTRICTS, haversine_distance
    from src.engine.monte_carlo import run_monte_carlo_district_simulation
    from src.engine.demand import get_impact_sigma

    rng = np.random.default_rng(random_seed)
    districts = list(MAHARASHTRA_DISTRICTS.keys())
    coords = {d: (MAHARASHTRA_DISTRICTS[d]["lat"], MAHARASHTRA_DISTRICTS[d]["lon"]) for d in districts}
    model_sigma = get_impact_sigma("model_prediction")

    scenarios_list = []
    print(f"Sampling {n_scenarios} diverse scenarios through Monte-Carlo engine...")

    for s in range(n_scenarios):
        h_type = str(rng.choice(["Flood", "Storm", "Epidemic", "Earthquake", "Extreme temp"]))
        epi = str(rng.choice(districts))
        month = int(rng.integers(1, 13))
        base_mag = float(rng.uniform(6.5, 11.5))
        
        district_inputs = {}
        lat1, lon1 = coords[epi]
        for d in districts:
            lat2, lon2 = coords[d]
            dist_km = haversine_distance(lat1, lon1, lat2, lon2)
            aff_log = max(4.0, base_mag - 0.004 * dist_km)
            district_inputs[d] = {
                "hazard_type": h_type,
                "affected_mean_log": aff_log,
                "affected_std_log": model_sigma,
                "injured_mean_log": max(2.0, aff_log - 2.5),
                "injured_std_log": 0.50
            }
        
        sim_df = run_monte_carlo_district_simulation(district_inputs, n_draws=100, random_seed=random_seed + s)
        sim_df["scenario_id"] = s
        sim_df["month"] = month
        sim_df["epicentre"] = epi
        scenarios_list.append(sim_df)

    return pd.concat(scenarios_list, ignore_index=True)

def train_surrogate_classifier(sim_df: pd.DataFrame = None, n_scenarios: int = 500, random_seed: int = 42):
    """
    Train Random Forest surrogate classifier on scenario-sampled Monte-Carlo outputs.
    Splits scenarios BY SCENARIO ID (80% train scenarios / 20% test scenarios) to measure
    true held-out scenario generalization fidelity and Expected Calibration Error (ECE).
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
    y_train = train_df["risk_level"]

    X_test = preprocessor.transform(test_df[num_cols + cat_cols])
    y_test = test_df["risk_level"]

    clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=random_seed)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)

    acc = float(accuracy_score(y_test, y_pred))
    macro_f1 = float(f1_score(y_test, y_pred, average="macro"))

    high_idx = list(clf.classes_).index("High") if "High" in clf.classes_ else 0
    y_true_high = (y_test == "High").astype(int).values
    ece_val = expected_calibration_error(y_true_high, y_prob[:, high_idx])

    print(f"✓ Trained Surrogate Classifier on {n_scenarios} Scenarios (Split BY SCENARIO)")
    print(f"✓ Held-Out Scenario Fidelity Accuracy: {acc*100:.2f}% | Macro F1: {macro_f1:.4f} | ECE: {ece_val:.4f}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    bundle = {
        "preprocessor": preprocessor,
        "classifier": clf,
        "classes": list(clf.classes_),
        "fidelity_acc": acc,
        "fidelity_f1": macro_f1,
        "ece": ece_val,
        "model_type": "SURROGATE_APPROXIMATION"
    }
    
    surr_path = MODELS_DIR / "shortage_classifier.joblib"
    joblib.dump(bundle, surr_path)
    print(f"Surrogate model saved to {surr_path}")

    return bundle

if __name__ == "__main__":
    train_surrogate_classifier(n_scenarios=500)
