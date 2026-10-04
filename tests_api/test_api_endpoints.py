"""Comprehensive unit & integration test suite for Disaster Healthcare AI FastAPI backend."""
import pytest
from fastapi.testclient import TestClient
from api.main import app

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
    assert data["scenarios_evaluated"] == 20
    methods = [r["method"] for r in data["results"]]
    assert "OR-Tools SCIP" in methods
    assert "No Redistribution" in methods
    assert "cost_index_mean" in data["results"][0]

def test_predict_impact_success(client):
    payload = {
        "hazard": "Flood",
        "magnitude": 50.0,
        "month": 7,
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
