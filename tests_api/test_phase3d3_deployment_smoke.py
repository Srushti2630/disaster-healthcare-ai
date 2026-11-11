"""
Phase 3D-3: Complete Workflow Smoke Test & Deployment Verification Harness.

Validates the full lifecycle in an isolated, production-like test harness:
1. Health & readiness probes (/ready, /health, and /api/* aliases)
2. Authentication and role-based coordinator session
3. Simulation generation -> simulation_id & simulation_hash
4. Linked Allocation generation -> allocation_id, plan_hash, status PENDING_REVIEW
5. Pending governance queue retrieval (/api/allocations/pending)
6. Detailed allocation inspection (/api/allocations/{id})
7. Governance decision submission (/api/audit/decision -> APPROVE)
8. Terminal-state protection (repeated decision on terminal allocation returns 409 Conflict)
9. Cryptographic audit ledger verification (/api/audit/verify confirms intact chain)
"""
import uuid
import pytest
from starlette.testclient import TestClient

from api.main import app
from api.database import SessionLocal
from api.models import User
from api.auth import hash_password, create_access_token

@pytest.fixture
def smoke_client():
    """Create a test client with lifespan context initialized."""
    with TestClient(app) as client:
        yield client

@pytest.fixture
def coordinator_auth_header(smoke_client):
    """Register and log in as coordinator through HTTP endpoints to test genuine client authentication."""
    email = f"coord_smoke_{uuid.uuid4().hex[:8]}@example.com"
    password = "CoordPassword123!"
    smoke_client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "role": "coordinator"
    })
    res = smoke_client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_01_readiness_and_liveness_probes(smoke_client):
    """Verify both /health and /ready endpoints return 200 and report all models loaded."""
    # Liveness check
    r_health = smoke_client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json() == {"status": "ok"}

    r_api_health = smoke_client.get("/api/health")
    assert r_api_health.status_code == 200

    # Readiness check
    r_ready = smoke_client.get("/ready")
    assert r_ready.status_code == 200
    data = r_ready.json()
    assert data["status"] == "ready"
    assert "artifacts_loaded" in data
    assert data["artifacts_loaded"]["districts_data"] is True
    assert data["artifacts_loaded"]["geojson"] is True
    assert data["artifacts_loaded"]["impact_model"] is True
    assert data["artifacts_loaded"]["distance_matrix"] is True
    assert data["artifacts_loaded"]["clinical_model"] is True

    r_api_ready = smoke_client.get("/api/ready")
    assert r_api_ready.status_code == 200
    assert r_api_ready.json()["status"] == "ready"

def test_02_complete_end_to_end_governance_workflow_smoke(smoke_client, coordinator_auth_header):
    """
    Execute full workflow:
    Simulate -> Allocate -> Queue -> Detail -> Approve -> Terminal Lock -> Ledger Verify.
    """
    # Step 1: Run Simulation
    sim_payload = {
        "epicentre": "Kolhapur",
        "hazard": "Flood",
        "severity": 1.0,
        "planning_level": "P50"
    }
    r_sim = smoke_client.post("/api/simulate", json=sim_payload, headers=coordinator_auth_header)
    assert r_sim.status_code == 200, f"Simulate failed: {r_sim.text}"
    sim_data = r_sim.json()
    sim_id = sim_data.get("simulation_id")
    assert sim_id is not None

    # Step 2: Run Linked Allocation
    alloc_payload = {
        "simulation_id": sim_id,
        "epicentre": "Kolhapur",
        "hazard": "Flood",
        "severity": 1.0,
        "planning_level": "P50",
        "safety_reserve_ratio": 0.60
    }
    r_alloc = smoke_client.post("/api/allocate", json=alloc_payload, headers=coordinator_auth_header)
    assert r_alloc.status_code == 200, f"Allocate failed: {r_alloc.text}"
    alloc_data = r_alloc.json()
    alloc_id = alloc_data.get("allocation_id")
    plan_hash = alloc_data.get("plan_hash")
    assert alloc_id is not None
    assert plan_hash is not None
    assert alloc_data.get("status") == "PENDING_REVIEW"
    assert alloc_data.get("simulation_id") == sim_id

    # Step 3: Verify allocation appears in pending queue
    r_pending = smoke_client.get("/api/allocations/pending", headers=coordinator_auth_header)
    assert r_pending.status_code == 200
    pending_items = r_pending.json()
    assert isinstance(pending_items, list)
    matching = [item for item in pending_items if item["id"] == alloc_id]
    assert len(matching) == 1, "Submitted allocation must be visible in pending queue"
    assert matching[0]["status"] == "PENDING_REVIEW"
    assert matching[0]["simulation_id"] == sim_id
    assert matching[0]["plan_hash"] == plan_hash

    # Step 4: Verify detailed allocation retrieval
    r_detail = smoke_client.get(f"/api/allocations/{alloc_id}", headers=coordinator_auth_header)
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert detail["id"] == alloc_id
    assert detail["simulation_id"] == sim_id
    assert detail["plan_hash"] == plan_hash
    assert detail["status"] == "PENDING_REVIEW"
    assert "shipments" in detail
    assert isinstance(detail["shipments"], list)

    # Step 5: Submit coordinator governance decision (APPROVE)
    decision_payload = {
        "allocation_id": alloc_id,
        "simulation_id": sim_id,
        "action": "APPROVE",
        "reason_code": "OPERATIONAL_NEED_CONFIRMED",
        "confidence": 0.95,
        "plan_hash": plan_hash
    }
    r_dec = smoke_client.post("/api/audit/decision", json=decision_payload, headers=coordinator_auth_header)
    assert r_dec.status_code == 201, f"Decision failed: {r_dec.text}"
    dec_data = r_dec.json()
    assert dec_data["action"] == "APPROVE"
    assert dec_data["block_version"] == 2
    assert len(dec_data["current_hash"]) == 64
    assert dec_data["allocation_id"] == alloc_id
    assert "id" in dec_data

    # Step 6: Allocation should no longer be pending
    r_pending_after = smoke_client.get("/api/allocations/pending", headers=coordinator_auth_header)
    assert r_pending_after.status_code == 200
    pending_after = r_pending_after.json()
    assert all(item["id"] != alloc_id for item in pending_after)

    # Step 7: Allocation detail now reflects terminal APPROVED status
    r_detail_after = smoke_client.get(f"/api/allocations/{alloc_id}", headers=coordinator_auth_header)
    assert r_detail_after.status_code == 200
    assert r_detail_after.json()["status"] == "APPROVED"

    # Step 8: Terminal-state protection check: repeated decision must be rejected with HTTP 409
    repeat_payload = {
        "allocation_id": alloc_id,
        "simulation_id": sim_id,
        "action": "REJECT",
        "reason_code": "DUPLICATE_DECISION_ATTEMPT",
        "confidence": 0.90,
        "plan_hash": plan_hash
    }
    r_repeat = smoke_client.post("/api/audit/decision", json=repeat_payload, headers=coordinator_auth_header)
    assert r_repeat.status_code == 409, f"Expected 409 Conflict, got {r_repeat.status_code}"
    err_msg = r_repeat.json()["message"].lower()
    assert "finalized" in err_msg or "duplicate" in err_msg or "terminal" in err_msg

    # Step 9: Verify cryptographic audit ledger integrity
    r_verify = smoke_client.get("/api/audit/verify", headers=coordinator_auth_header)
    assert r_verify.status_code == 200
    verify_data = r_verify.json()
    assert verify_data["is_valid"] is True
    assert verify_data["total_blocks_verified"] >= 1
