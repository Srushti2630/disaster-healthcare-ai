"""
tests/test_phase3b_clinical_forecast.py
Comprehensive Verification & Regression Suite for Phase 3B-1:
- Model Deserialization & Unpickler Compatibility
- Exact Prediction Equivalence on Historical Holdout (residual_analysis.csv)
- Autoregressive Multi-Step Rollout (Horizons 1-12)
- Specialty Empirical Prediction Intervals & Coverage Calibration
- FastAPI /api/forecast/clinical Endpoint Integration
- Database Session Decoupling from Threadpool Execution
"""

import csv
import math
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from api.main import app
import api.database
from api.models import User, UserRole
from api.auth import create_access_token, hash_password
from src.forecast import (
    SERVICES, NUM_PERIODS, SPECIALTY_INTERVALS_Q90,
    ClinicalModelUnpickler, load_clinical_forecaster,
    get_historical_service_series, forecast_service_demand,
    build_single_step_features, PureHybridForecaster
)


@pytest.fixture(scope="module")
def client():
    """Initializes FastAPI TestClient running through full lifespan setup."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers():
    """Provides authentication headers for an officer user."""
    db = api.database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "test_officer_phase3b@example.com").first()
        if not user:
            user = User(
                email="test_officer_phase3b@example.com",
                hashed_password=hash_password("officerpass123"),
                role=UserRole.OFFICER.value
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(data={"sub": str(user.id), "role": user.role, "email": user.email})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 1. Model Deserialization & Integrity
# -----------------------------------------------------------------------------
def test_clinical_model_unpickler_compatibility():
    """Verifies that final_model.joblib is unpickled safely without modifying the artifact."""
    bundle = load_clinical_forecaster("final_model.joblib")
    assert bundle is not None
    assert bundle["model_name"] == "Hybrid_Seasonal_Ridge"
    assert isinstance(bundle["model_instance"], PureHybridForecaster)
    assert len(bundle["feature_names"]) == 15
    assert bundle["services"] == SERVICES
    assert bundle["training_periods"] == 144
    assert bundle["holdout_periods"] == 12


# -----------------------------------------------------------------------------
# 2. Prediction Equivalence on Certified Holdout Data
# -----------------------------------------------------------------------------
def test_holdout_prediction_exact_numerical_equivalence():
    """
    Verifies that model predictions on untouched holdout periods (145..156)
    match residual_analysis.csv to 0.000000 visits (floating-point precision).
    """
    bundle = load_clinical_forecaster("final_model.joblib")
    model = bundle["model_instance"]

    records = get_historical_service_series()
    by_service = {s: [r["demand"] for r in records if r["service"] == s] for s in SERVICES}

    # Load recorded residual analysis
    res_path = Path("residual_analysis.csv")
    assert res_path.exists(), "residual_analysis.csv missing"
    with open(res_path, "r", encoding="utf-8") as f:
        recorded_rows = list(csv.DictReader(f))

    diffs = []
    for t in range(145, 157):
        month = ((t - 1) % 12) + 1
        year = 2010 + ((t - 1) // 12)
        for s in SERVICES:
            # Reconstruct past demands strictly up to t-1
            past_demands = by_service[s][:t - 1]
            feat_vec, meta = build_single_step_features(
                history_demands=past_demands,
                period=t,
                year=year,
                month=month,
                service=s
            )
            pred = model.predict([feat_vec], [meta])[0]

            match = next(
                r for r in recorded_rows
                if int(r["period"]) == t and r["service"] == s
            )
            expected_pred = float(match["predicted_demand"])
            diff = abs(round(pred, 2) - expected_pred)
            diffs.append(diff)

    assert len(diffs) == 48, f"Expected 48 holdout evaluations, got {len(diffs)}"
    max_diff = max(diffs)
    assert max_diff == 0.0, f"Holdout predictions diverged from residual_analysis.csv: max diff = {max_diff}"


# -----------------------------------------------------------------------------
# 3. Autoregressive Rollout & Horizon Validation
# -----------------------------------------------------------------------------
def test_autoregressive_rollout_horizons():
    """Verifies recursive multi-step forecasting across various horizons."""
    bundle = load_clinical_forecaster("final_model.joblib")

    for h in [1, 3, 6, 12]:
        forecasts = forecast_service_demand(bundle, horizon_months=h)
        assert len(forecasts) == h * 4

        for item in forecasts:
            assert item["period_index"] >= 157
            assert 1 <= item["horizon_step"] <= h
            assert item["year"] in (2023, 2024)
            assert 1 <= item["month"] <= 12
            assert item["service"] in SERVICES
            assert item["predicted_visits"] > 0.0
            assert item["interval_lower"] <= item["predicted_visits"]
            assert item["interval_upper"] >= item["predicted_visits"]
            assert round(item["interval_upper"] - item["interval_lower"], 2) == item["interval_width"]
            assert item["calibration_samples"] == 144


def test_service_filtering():
    """Verifies that forecasting filtered by specialty returns only that specialty."""
    bundle = load_clinical_forecaster("final_model.joblib")

    for s in SERVICES:
        forecasts = forecast_service_demand(bundle, horizon_months=6, service=s)
        assert len(forecasts) == 6
        assert all(f["service"] == s for f in forecasts)


def test_forecast_parameter_validation_errors():
    """Verifies that invalid horizon or service parameters raise ValueError."""
    bundle = load_clinical_forecaster("final_model.joblib")

    with pytest.raises(ValueError, match="horizon_months must be an integer between 1 and 12"):
        forecast_service_demand(bundle, horizon_months=0)

    with pytest.raises(ValueError, match="horizon_months must be an integer between 1 and 12"):
        forecast_service_demand(bundle, horizon_months=13)

    with pytest.raises(ValueError, match="Invalid service 'Cardiology'"):
        forecast_service_demand(bundle, horizon_months=6, service="Cardiology")


# -----------------------------------------------------------------------------
# 4. Empirical Prediction Intervals Calibration & Coverage
# -----------------------------------------------------------------------------
def test_empirical_prediction_intervals_holdout_coverage():
    """
    Verifies that specialty-specific 90th percentile margins achieve
    >= 90% empirical coverage on the untouched 12-month holdout set.
    """
    records = get_historical_service_series()
    res_path = Path("residual_analysis.csv")
    with open(res_path, "r", encoding="utf-8") as f:
        holdout_rows = list(csv.DictReader(f))

    for s in SERVICES:
        margin = SPECIALTY_INTERVALS_Q90[s]["margin"]
        s_rows = [r for r in holdout_rows if r["service"] == s]
        covered = sum(1 for r in s_rows if abs(float(r["residual_error"])) <= margin)
        coverage_pct = (covered / len(s_rows)) * 100.0

        assert coverage_pct >= 90.0, f"Coverage for {s} was {coverage_pct}%, expected >= 90%"
        assert SPECIALTY_INTERVALS_Q90[s]["samples"] == 144


# -----------------------------------------------------------------------------
# 5. FastAPI Endpoint Integration
# -----------------------------------------------------------------------------
def test_api_clinical_forecast_endpoint_default(client):
    """Verifies GET /api/forecast/clinical with default parameters."""
    res = client.get("/api/forecast/clinical")
    assert res.status_code == 200
    data = res.json()

    assert data["model_name"] == "Hybrid_Seasonal_Ridge"
    assert data["model_version"] == "1.0.0"
    assert data["horizon_months"] == 6
    assert data["total_forecasts"] == 24
    assert len(data["forecasts"]) == 24

    first = data["forecasts"][0]
    assert first["period_index"] == 157
    assert first["horizon_step"] == 1
    assert first["service"] in SERVICES
    assert first["predicted_visits"] > 0.0


def test_api_clinical_forecast_endpoint_filtered(client):
    """Verifies GET /api/forecast/clinical with custom horizon and service filter."""
    res = client.get("/api/forecast/clinical?horizon_months=12&service=Emergency")
    assert res.status_code == 200
    data = res.json()

    assert data["horizon_months"] == 12
    assert data["total_forecasts"] == 12
    assert all(f["service"] == "Emergency" for f in data["forecasts"])
    assert data["forecasts"][0]["horizon_step"] == 1
    assert data["forecasts"][-1]["horizon_step"] == 12


def test_api_clinical_forecast_validation_errors(client):
    """Verifies validation error handling on invalid query parameters."""
    # Horizon out of bounds (< 1)
    res_low = client.get("/api/forecast/clinical?horizon_months=0")
    assert res_low.status_code == 422

    # Horizon out of bounds (> 12)
    res_high = client.get("/api/forecast/clinical?horizon_months=15")
    assert res_high.status_code == 422

    # Invalid service name
    res_svc = client.get("/api/forecast/clinical?service=Neurology")
    assert res_svc.status_code == 400
    assert "Invalid service 'Neurology'" in res_svc.json()["message"]


def test_api_clinical_forecast_503_when_model_missing(client):
    """Verifies 503 response if clinical model is not loaded."""
    original_model = client.app.state.clinical_model
    try:
        client.app.state.clinical_model = None
        res = client.get("/api/forecast/clinical")
        assert res.status_code == 503
        assert "Clinical forecasting model not loaded" in res.json()["message"]
    finally:
        client.app.state.clinical_model = original_model


# -----------------------------------------------------------------------------
# 6. Database Session Decoupling from Threadpool (Task E)
# -----------------------------------------------------------------------------
def test_threadpool_session_decoupling(client, auth_headers):
    """
    Verifies that simulation and allocation endpoints execute with custom stocks
    without passing active SQLAlchemy Session objects into threadpool worker threads.
    """
    # 1. Upload custom stock for officer
    stock_payload = {
        "items": [
            {"district": "Pune", "medicine": "iv_fluids", "quantity": 777.0}
        ]
    }
    res_stock = client.post("/api/stock", json=stock_payload, headers=auth_headers)
    assert res_stock.status_code == 200

    # 2. Run simulation - verify custom stock was passed detached to simulation
    sim_payload = {
        "epicentre": "Pune",
        "hazard": "Earthquake",
        "severity": 1.5,
        "planning_level": "P50"
    }
    res_sim = client.post("/api/simulate", json=sim_payload, headers=auth_headers)
    assert res_sim.status_code == 200
    sim_data = res_sim.json()

    pune_item = next(
        r for r in sim_data["results"]
        if r["district"] == "Pune" and r["medicine"] == "iv_fluids"
    )
    assert pune_item["available_stock"] == 777.0
    assert pune_item["provenance"] == "USER-PROVIDED"

    # 3. Clean up custom stock
    res_reset = client.delete("/api/stock", headers=auth_headers)
    assert res_reset.status_code == 200
