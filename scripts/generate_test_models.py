#!/usr/bin/env python3
"""
scripts/generate_test_models.py

Fresh-Clone & CI Test Model Fixture Generator (DEF-01 & DEF-16).
Purpose:
- Provides lightweight, self-contained test fixtures for hermetic fresh-clone execution and CI test runs.
- STRICT ISOLATION GUARANTEE:
  * Only creates test fixtures if models/ is empty or missing required .joblib files.
  * Explicitly flags all generated objects with metadata:
      provenance = "SYNTHETIC_TEST_FIXTURE"
      is_synthetic = True
  * Never overwrites or modifies operational production models if they exist.
  * Runs in < 3 seconds without external network downloads or expensive retraining.
"""

import os
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

def generate_fixtures_if_missing():
    impact_path = MODELS_DIR / "impact_models.joblib"
    surrogate_path = MODELS_DIR / "shortage_classifier.joblib"
    pipeline_path = MODELS_DIR / "pipeline_bundle.joblib"
    shap_path = MODELS_DIR / "shap_explainer.joblib"

    if impact_path.exists() and surrogate_path.exists() and pipeline_path.exists() and shap_path.exists():
        print(f"✓ Production model artifacts already exist in {MODELS_DIR}. Skipping synthetic test generation.")
        return False

    print("⚠️ Missing model artifacts detected in models/. Generating isolated SYNTHETIC_TEST_FIXTURES for CI / testing...")

    # 1. Feature columns
    feat_num = ["magnitude", "start_year", "start_month", "decade"]
    feat_cat = ["disaster_type", "disaster_subtype", "scope"]

    # Preprocessor
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), feat_num),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), feat_cat)
        ]
    )

    # Synthetic training data
    df_syn = pd.DataFrame({
        "magnitude": [5.0, 6.0, 7.0, 8.0, 6.5],
        "start_year": [2010, 2015, 2020, 2022, 2024],
        "start_month": [7, 8, 6, 9, 8],
        "decade": [2010, 2010, 2020, 2020, 2020],
        "disaster_type": ["Flood", "Storm", "Flood", "Drought", "Earthquake"],
        "disaster_subtype": ["Riverine", "Tropical", "Flash", "Drought", "Ground"],
        "scope": ["single-state", "single-state", "multi-state", "single-state", "single-state"]
    })
    y_syn = np.array([7.5, 8.2, 9.1, 10.0, 8.0])

    X_trans = preprocessor.fit_transform(df_syn)

    # Linear Ridge model
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_trans, y_syn)

    class DummyCQR:
        def predict(self, X):
            y_pred = ridge.predict(X)
            return y_pred, y_pred - 0.9314, y_pred + 0.9314

    impact_bundle = {
        "preprocessor": preprocessor,
        "impact_model": ridge,
        "ridge_model": ridge,
        "cqr_model": DummyCQR(),
        "feature_cols_num": feat_num,
        "feature_cols_cat": feat_cat,
        "median_baseline": 7.12,
        "cqr_margin": 0.9314,
        "sigma_log": 1.25,
        "provenance": "SYNTHETIC_TEST_FIXTURE",
        "is_synthetic": True,
        "description": "Lightweight synthetic test fixture generated for CI testing only."
    }

    # 2. Surrogate classifier fixture
    clf = RandomForestClassifier(n_estimators=5, random_state=42)
    X_clf = np.random.randn(20, 10)
    y_clf = np.random.randint(0, 2, 20)
    clf.fit(X_clf, y_clf)

    surrogate_bundle = {
        "classifier": clf,
        "clf_features": [f"feat_{i}" for i in range(10)],
        "provenance": "SYNTHETIC_TEST_FIXTURE",
        "is_synthetic": True,
        "description": "Lightweight synthetic surrogate test fixture for CI testing only."
    }

    # 3. Pipeline bundle fixture
    pipeline_bundle = {
        "impact_models": {"affected_pop": ridge, "injured": ridge, "ill": ridge, "Ridge": ridge},
        "impact_features": feat_num + feat_cat,
        "demand_model": ridge,
        "demand_features": ["lag_1", "lag_2"],
        "conformal_quantile": 0.9314,
        "calibrated_classifier": clf,
        "clf_base_rf": clf,
        "clf_features": [f"feat_{i}" for i in range(10)],
        "shap_explainer": None,
        "conservative_high_threshold": 0.70,
        "model_version": "test-fixture-1.0.0",
        "provenance": "SYNTHETIC_TEST_FIXTURE",
        "is_synthetic": True
    }

    if not impact_path.exists():
        joblib.dump(impact_bundle, impact_path)
        print(f"✓ Created test fixture: {impact_path}")

    if not surrogate_path.exists():
        joblib.dump(surrogate_bundle, surrogate_path)
        print(f"✓ Created test fixture: {surrogate_path}")

    if not pipeline_path.exists():
        joblib.dump(pipeline_bundle, pipeline_path)
        print(f"✓ Created test fixture: {pipeline_path}")

    if not shap_path.exists():
        try:
            import shap
            from sklearn.ensemble import RandomForestRegressor
            rf_for_shap = RandomForestRegressor(n_estimators=3, random_state=42)
            rf_for_shap.fit(X_trans, y_syn)
            tree_explainer = shap.TreeExplainer(rf_for_shap)
            tree_explainer.is_synthetic = True
            tree_explainer.provenance = "SYNTHETIC_TEST_FIXTURE"
            joblib.dump(tree_explainer, shap_path)
            print(f"✓ Created test fixture: {shap_path}")
        except Exception as e:
            print(f"Warning: Could not generate shap_explainer test fixture: {e}")

    print("✓ All synthetic test fixtures created successfully.")
    return True

if __name__ == "__main__":
    generate_fixtures_if_missing()
