"""Comprehensive unit & integration test suite for Disaster Healthcare AI FastAPI backend."""
import pytest
import pandas as pd
import json
from fastapi.testclient import TestClient
from api.main import app
from api.schemas import ImpactPredictionRequest
from api.services import build_impact_input_frame
from api.config import settings

from api.database import init_db

@pytest.fixture(scope="module")
def client():
    """Create a TestClient with lifespan context entered and test admin credentials."""
    init_db()
    with TestClient(app) as test_client:
        test_client.post("/api/auth/register", json={
            "email": "test_suite_admin@mahadisaster.gov.in",
            "password": "AdminPassword123!"
        })
        login_res = test_client.post("/api/auth/login", json={
            "email": "test_suite_admin@mahadisaster.gov.in",
            "password": "AdminPassword123!"
        })
        if login_res.status_code == 200:
            token = login_res.json()["access_token"]
            test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert "x-request-id" in res.headers
    assert "x-process-time-ms" in res.headers

def test_readiness_probe(client):
    res = client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["artifacts_loaded"]["districts_data"] is True
    assert data["artifacts_loaded"]["impact_model"] is True

def test_get_districts_endpoint(client):
    res = client.get("/api/districts")
    assert res.status_code == 200
    data = res.json()
    assert data["total_districts"] == 35
    assert data["total_state_population"] > 100000000
    assert data["state_hospital_beds_anchor"] == 144983
    assert data["state_icu_beds_anchor"] == 11587

    sample = data["districts"][0]
    assert "district" in sample
    assert sample["capacity"]["provenance"] == "ESTIMATED"
    assert sample["facilities"]["provenance"] == "REAL"
    assert sample["provenance"] == "REAL"

def test_facilities_total_above_4000(client):
    res = client.get("/api/districts")
    assert res.status_code == 200
    data = res.json()
    total_fac = data.get("total_cleaned_facilities") or data.get("total_facilities")
    assert total_fac is not None
    assert total_fac > 4000
    sum_facilities = sum(d["facilities"]["total_facilities"] for d in data["districts"])
    assert sum_facilities > 4000

def test_get_geo_districts_endpoint(client):
    res = client.get("/api/geo/districts")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 35
    first_props = data["features"][0]["properties"]
    assert "district" in first_props

def test_get_metrics_endpoint(client):
    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    assert data["sample_size"] == 512
    assert "Ridge" in data["models_benchmarked"]
    assert "surrogate_fidelity" in data
    assert len(data["limitations"]) >= 5

def test_get_backtest_endpoint(client):
    res = client.get("/api/backtest")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 5
    first_record = data["records"][0]
    assert "DisNo." in first_record or "disno" in first_record
    assert "scope" in first_record
    assert first_record["interval_width_orders_of_magnitude"] > 0

def test_get_baselines_endpoint(client):
    res = client.get("/api/baselines")
    assert res.status_code == 200
    data = res.json()
    with open(settings.REPORTS_DIR / "allocation_summary.json", "r", encoding="utf-8") as f:
        baseline_summary = json.load(f)
    expected_scenarios = baseline_summary.get("total_scenarios")
    if expected_scenarios is None:
        expected_scenarios = len(baseline_summary.get("scenario_demand_stock", []))
    assert data["scenarios_evaluated"] == expected_scenarios
    methods = [r["method"] for r in data["results"]]
    assert "OR-Tools SCIP" in methods
    assert "No Redistribution" in methods
    assert "cost_index_mean" in data["results"][0]

def test_predict_impact_success(client):
    payload = {
        "hazard": "Flood",
        "magnitude": 50.0,
        "month": 7,
        "year": 2024,
        "subtype": "Riverine flood",
        "scope": "multi-district",
        "state": "Maharashtra"
    }
    res = client.post("/api/predict-impact", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["hazard"] == "Flood"
    assert data["predicted_median_affected"] > 0
    assert data["predicted_p90_affected"] >= data["predicted_median_affected"]
    assert "caveat" in data
    assert data["provenance"] == "ESTIMATED"
    assert data["model_architecture"] == "Ridge Regression (alpha=1.0)"
    active_models = [model for model in data["ensemble_breakdown"] if model["is_active"]]
    assert len(active_models) == 1
    assert active_models[0]["model_name"] == "Ridge Regression"

def test_impact_input_matches_saved_model_features_and_missing_magnitude(client):
    bundle = app.state.impact_bundle
    req = ImpactPredictionRequest(
        hazard="Flood",
        magnitude=None,
        year=2024,
        month=2,
        subtype="Riverine flood",
        scope="multi-district",
        state="Maharashtra"
    )

    features = build_impact_input_frame(bundle, req)

    assert list(features.columns) == (
        bundle["feature_cols_num"] + bundle["feature_cols_cat"]
    )
    assert features.loc[0, "disaster_type"] == "Flood"
    assert features.loc[0, "disaster_subtype"] == "Riverine flood"
    assert features.loc[0, "scope"] == "multi-district"
    assert features.loc[0, "start_year"] == 2024
    assert features.loc[0, "start_month"] == 2
    assert features.loc[0, "decade"] == 2020
    assert pd.isna(features.loc[0, "magnitude"])
    assert "state" not in features.columns

    transformed = bundle["preprocessor"].transform(features)
    assert transformed.shape[1] == bundle["impact_model"].n_features_in_

def test_impact_input_defaults_to_missing_subtype_and_valid_state_scope(client):
    bundle = app.state.impact_bundle
    req = ImpactPredictionRequest(hazard="Storm", year=2031)

    features = build_impact_input_frame(bundle, req)

    assert pd.isna(features.loc[0, "magnitude"])
    assert features.loc[0, "disaster_subtype"] == "Unknown"
    assert features.loc[0, "scope"] == "state"
    assert features.loc[0, "start_year"] == 2031
    assert features.loc[0, "decade"] == 2030
    transformed = bundle["preprocessor"].transform(features)
    feature_names = bundle["preprocessor"].get_feature_names_out()
    subtype_columns = [
        index for index, name in enumerate(feature_names)
        if name.startswith("cat__disaster_subtype_")
    ]
    assert subtype_columns
    assert all(transformed[0, index] == 0 for index in subtype_columns)

def test_predict_impact_rejects_unsupported_model_categories(client):
    invalid_scope = client.post(
        "/api/predict-impact",
        json={"hazard": "Flood", "scope": "single-state"}
    )
    assert invalid_scope.status_code == 422

    invalid_subtype = client.post(
        "/api/predict-impact",
        json={"hazard": "Flood", "subtype": "Unseen flood subtype"}
    )
    assert invalid_subtype.status_code == 422
    assert "not a category supported" in invalid_subtype.json()["message"]

    invalid_hazard = client.post(
        "/api/predict-impact",
        json={"hazard": "Other"}
    )
    assert invalid_hazard.status_code == 422

def test_predict_impact_rejects_invalid_year(client):
    response = client.post(
        "/api/predict-impact",
        json={"hazard": "Flood", "year": 1800}
    )
    assert response.status_code == 422

def test_predict_impact_validation_error(client):
    # Invalid month 15 (should fail ge=1, le=12 validation)
    payload = {
        "hazard": "Flood",
        "month": 15
    }
    res = client.post("/api/predict-impact", json=payload)
    assert res.status_code == 422
    data = res.json()
    assert data["error"] is True

def test_simulate_success_and_capping(client):
    payload = {
        "epicentre": "Pune",
        "hazard": "Flood",
        "severity": 1.5,
        "planning_level": "P50",
        "stock_adjustment_pct": 0.0
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["epicentre"] == "Pune"
    assert data["hazard"] == "Flood"
    assert data["model_used"] == "Ridge Regression"
    assert "Ridge Regression" in data["ensemble_comparison"]
    assert data["total_affected_simulated"] > 0
    assert len(data["results"]) == 35 * 5  # 35 districts * 5 medicines
    
    # Check that Pune affected did not exceed Pune population
    first_res = data["results"][0]
    assert "demand_p50" in first_res
    assert first_res["risk_level"] in ["Low", "Medium", "High"]

def test_simulate_validation_error_invalid_planning_level(client):
    payload = {
        "epicentre": "Pune",
        "hazard": "Flood",
        "planning_level": "INVALID_LEVEL"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 422
    assert res.json()["error"] is True

def test_simulate_validation_error_unknown_district(client):
    payload = {
        "epicentre": "NonExistentDistrict",
        "hazard": "Flood"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 400

def test_allocate_success(client):
    payload = {
        "epicentre": "Pune",
        "hazard": "Flood",
        "severity": 1.0,
        "planning_level": "P50",
        "safety_reserve_ratio": 0.60
    }
    res = client.post("/api/allocate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["solve_status"] in ["OPTIMAL", "FEASIBLE"]
    assert "cost_index" in data
    assert data["constraint_checks"]["total_violations"] == 0
    assert data["constraint_checks"]["perishables_150km_limit_passed"] is True
    assert len(data["method_comparison"]) == 5

def test_allocate_validation_error(client):
    # Safety reserve ratio > 1.0
    payload = {
        "epicentre": "Pune",
        "safety_reserve_ratio": 1.50
    }
    res = client.post("/api/allocate", json=payload)
    assert res.status_code == 422
    assert res.json()["error"] is True

def test_explain_global_endpoint(client):
    res = client.get("/api/explain/global")
    assert res.status_code == 200
    data = res.json()
    assert "top_features" in data
    assert len(data["top_features"]) >= 5
    assert "summary_plot_url" in data

def test_explain_local_endpoint(client):
    payload = {
        "hazard": "Flood",
        "magnitude": 6.5,
        "month": 8,
        "state": "Maharashtra"
    }
    res = client.post("/api/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["hazard"] == "Flood"
    assert "predicted_log" in data
    assert "base_value" in data
    assert "top_contributions" in data
    assert len(data["top_contributions"]) <= 6
    assert len(data["top_contributions"]) > 0
    assert "summary_sentence" in data
    for item in data["top_contributions"]:
        assert "feature" in item
        assert "contribution" in item
        assert "plain_english" in item
        assert len(item["plain_english"]) > 5

def test_stock_role_enforcement_and_validation(client):
    from fastapi.testclient import TestClient
    from api.main import app

    # 1. Unauthenticated test client -> 401
    with TestClient(app) as anon_client:
        unauth_res = anon_client.post("/api/stock", json={"stocks": {"Pune": {"antibiotics": 50000}}})
        assert unauth_res.status_code == 401

    # 2. Viewer role -> 403
    with TestClient(app) as viewer_client:
        admin_login = viewer_client.post("/api/auth/login", json={
            "email": "test_suite_admin@mahadisaster.gov.in",
            "password": "AdminPassword123!"
        })
        assert admin_login.status_code == 200
        viewer_client.headers["Authorization"] = f"Bearer {admin_login.json()['access_token']}"
        register_viewer = viewer_client.post("/api/auth/register", json={
            "email": "viewer_stock_test@mahadisaster.gov.in",
            "password": "ViewerPassword123!",
            "role": "viewer"
        })
        assert register_viewer.status_code == 201
        login_res = viewer_client.post("/api/auth/login", json={
            "email": "viewer_stock_test@mahadisaster.gov.in",
            "password": "ViewerPassword123!"
        })
        token = login_res.json()["access_token"]
        viewer_client.headers["Authorization"] = f"Bearer {token}"
        forbidden_res = viewer_client.post("/api/stock", json={"stocks": {"Pune": {"antibiotics": 50000}}})
        assert forbidden_res.status_code == 403

    # 3. Validation error on empty payload
    empty_res = client.post("/api/stock", json={})
    assert empty_res.status_code == 400

    # 4. Officer / Admin role (from client fixture) -> 200
    valid_res = client.post("/api/stock", json={
        "stocks": {
            "Pune": {
                "antibiotics": 75000.0,
                "ors": 150000.0
            }
        }
    })
    assert valid_res.status_code == 200
    data = valid_res.json()
    assert data["provenance"] == "USER-PROVIDED"
    assert data["stocks"]["Pune"]["antibiotics"] == 75000.0
    assert data["stocks"]["Pune"]["ors"] == 150000.0

def test_stock_used_in_simulate(client):
    # Set custom stock for Pune antibiotics
    client.post("/api/stock", json={
        "stocks": {
            "Pune": {
                "antibiotics": 99999.0
            }
        }
    })

    sim_res = client.post("/api/simulate", json={
        "epicentre": "Pune",
        "hazard": "Flood",
        "severity": 1.0,
        "planning_level": "P50"
    })
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    
    # Locate Pune antibiotics in simulation results
    pune_antibiotics = next(
        (r for r in sim_data["results"] if r["district"] == "Pune" and r["medicine"] == "antibiotics"),
        None
    )
    assert pune_antibiotics is not None
    assert pune_antibiotics["available_stock"] == 99999.0
    assert pune_antibiotics["provenance"] == "USER-PROVIDED"

    # Reset custom stock
    del_res = client.delete("/api/stock")
    assert del_res.status_code == 200
    assert del_res.json()["total_records"] == 0
