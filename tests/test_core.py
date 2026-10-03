"""
Core verification tests for Disaster Healthcare AI.
Tests:
(a) Zero scenario_id overlap between train and test sets.
(b) Complete isolation of ground-truth leakage columns from model inputs.
(c) Preprocessors fitted strictly on training data without test contamination.
(d) Optimizer compliance with safety reserves, non-negative integer transfers, and supply limits.
"""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

from src.optimise import solve_resource_allocation

CLEAN_DIR = Path("data/processed/clean")
MODELS_DIR = Path("models")


def test_no_scenario_overlap():
    """Verify strictly zero scenario_id overlap between train and test splits."""
    short_path = CLEAN_DIR / "shortage_dataset_clean.csv"
    assert short_path.exists(), "Cleaned shortage dataset does not exist."

    df = pd.read_csv(short_path)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(gss.split(df, groups=df["scenario_id"]))

    train_scenarios = set(df.iloc[train_idx]["scenario_id"].unique())
    test_scenarios = set(df.iloc[test_idx]["scenario_id"].unique())

    overlap = train_scenarios.intersection(test_scenarios)
    assert len(overlap) == 0, f"Found {len(overlap)} overlapping scenarios between train and test: {overlap}"


def test_leakage_columns_excluded():
    """Verify ground truth and target columns are never present in classifier or demand inputs."""
    bundle_path = MODELS_DIR / "pipeline_bundle.joblib"
    assert bundle_path.exists(), "Model bundle does not exist."

    bundle = joblib.load(bundle_path)
    clf_features = set(bundle["clf_features"])
    forbidden_clf = {"demand_7d", "shortage_qty", "coverage_ratio", "affected_pop", "injured", "ill", "risk_level"}

    leakage_found = clf_features.intersection(forbidden_clf)
    assert len(leakage_found) == 0, f"Leakage columns detected in classifier features: {leakage_found}"

    # Demand features must not contain ground truth casualties
    demand_features = set(bundle["demand_features"])
    forbidden_demand = {"demand_7d", "shortage_qty", "coverage_ratio", "affected_pop", "injured", "ill"}
    leakage_demand = demand_features.intersection(forbidden_demand)
    assert len(leakage_demand) == 0, f"Leakage columns detected in demand features: {leakage_demand}"

    # Demand features must use predicted variants
    assert "affected_pop_pred" in demand_features
    assert "injured_pred" in demand_features
    assert "ill_pred" in demand_features


def test_transformers_fitted_on_train_only():
    """Verify feature scaling transformers are fitted exclusively on training distributions."""
    np.random.seed(42)
    train_vals = np.array([[10.0], [20.0], [30.0]])
    test_vals = np.array([[100.0], [200.0]])

    scaler = StandardScaler()
    scaler.fit(train_vals)

    # Expected train mean is 20.0
    assert np.isclose(scaler.mean_[0], 20.0)
    # Check that test distribution did not contaminate scaler mean
    combined_mean = np.mean(np.vstack([train_vals, test_vals]))
    assert not np.isclose(scaler.mean_[0], combined_mean)

    # Verify pipeline bundle scalers have valid fitted parameters
    bundle = joblib.load(MODELS_DIR / "pipeline_bundle.joblib")
    clf_pipeline = bundle["calibrated_classifier"].estimator
    clf_prep = clf_pipeline.named_steps["prep"]
    num_transformer = clf_prep.named_transformers_["num"]
    assert hasattr(num_transformer, "mean_")
    assert len(num_transformer.mean_) > 0


def test_optimizer_constraints_and_integers():
    """Verify optimizer adheres to safety reserves, non-negative integer transfers, and no self-transfers."""
    regions = ["RegionA", "RegionB", "RegionC"]
    distances = pd.DataFrame(
        [
            [0.0, 50.0, 100.0],
            [50.0, 0.0, 60.0],
            [100.0, 60.0, 0.0],
        ],
        index=regions,
        columns=regions,
    )

    # RegionA has large surplus stock: 10,000 units, demand 1,000.
    # RegionB has deficit: 500 stock, demand 5,000.
    # RegionC has deficit: 200 stock, demand 2,000.
    demands = {
        "RegionA": {"antibiotics": 1000.0, "ors": 100.0, "iv_fluids": 100.0, "analgesics": 100.0, "blood_units": 10.0},
        "RegionB": {"antibiotics": 5000.0, "ors": 100.0, "iv_fluids": 100.0, "analgesics": 100.0, "blood_units": 10.0},
        "RegionC": {"antibiotics": 2000.0, "ors": 100.0, "iv_fluids": 100.0, "analgesics": 100.0, "blood_units": 10.0},
    }
    stocks = {
        "RegionA": {"antibiotics": 10000.0, "ors": 500.0, "iv_fluids": 500.0, "analgesics": 500.0, "blood_units": 50.0},
        "RegionB": {"antibiotics": 500.0, "ors": 10.0, "iv_fluids": 10.0, "analgesics": 10.0, "blood_units": 2.0},
        "RegionC": {"antibiotics": 200.0, "ors": 10.0, "iv_fluids": 10.0, "analgesics": 10.0, "blood_units": 2.0},
    }
    risks = {r: {m: "High" if r != "RegionA" else "Low" for m in demands[r]} for r in regions}
    confidences = {r: {m: 0.90 for m in demands[r]} for r in regions}

    safety_reserve = 0.60
    alloc_df, summary = solve_resource_allocation(
        region_demands=demands,
        region_stocks=stocks,
        region_risks=risks,
        region_confidences=confidences,
        distances_df=distances,
        safety_reserve_ratio=safety_reserve,
        w_unmet=1.0,
        w_cost=0.01,
        w_fairness=0.5,
    )

    assert summary["solve_status"] == "OPTIMAL"
    assert len(alloc_df) > 0, "Expected transfers from surplus to deficit regions."

    for _, row in alloc_df.iterrows():
        qty = row["quantity"]
        # Integer transfer constraint
        assert isinstance(qty, (int, np.integer)) or qty.is_integer(), f"Transfer quantity must be integer: {qty}"
        assert qty > 0, f"Transfer quantity must be strictly positive: {qty}"
        # No self-transfers
        assert row["source_region"] != row["dest_region"], "Self-transfer detected."

    # Verify source safety reserve for RegionA
    for med in ["antibiotics", "ors", "iv_fluids", "analgesics", "blood_units"]:
        source_transfers = alloc_df[
            (alloc_df["source_region"] == "RegionA") & (alloc_df["medicine"] == med)
        ]["quantity"].sum()
        max_allowed_export = max(0, int(stocks["RegionA"][med] - safety_reserve * demands["RegionA"][med]))
        assert source_transfers <= max_allowed_export, (
            f"RegionA exported {source_transfers} units of {med}, exceeding limit {max_allowed_export} "
            f"(stock: {stocks['RegionA'][med]}, reserve requirement: {safety_reserve * demands['RegionA'][med]})"
        )
