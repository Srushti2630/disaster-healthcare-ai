"""
Comprehensive test suite for Phase 3C-2:
Backend Governance Persistence & Deployment Foundation.
Covers:
1. SQLite Foreign Key Enforcement (DEF-3C-08)
2. Simulation Record Persistence & Canonical Hashing (DEF-3C-01)
3. Allocation Record Persistence & Deterministic Plan Hashing (DEF-3C-02)
4. Allocation Lifecycle & Audit Decision Binding (DEF-3C-02 / Lifecycle)
5. Transaction-Safe Concurrent Ledger Append (DEF-3C-07)
6. Clinical Model Readiness Probe (DEF-3C-05)
"""
import uuid
import threading
import pytest
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from api.main import app
import api.database
from api.models import User, UserRole, SimulationRecord, AllocationRecord, AuditEvent
from api.audit_ledger import (
    compute_canonical_simulation_hash,
    compute_canonical_plan_hash,
    record_decision,
    verify_chain,
    GENESIS_HASH
)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture(scope="module")
def admin_token(client):
    """Ensure an admin exists and return auth token."""
    res_reg = client.post("/api/auth/register", json={
        "email": "gov_admin@mahadisaster.gov.in",
        "password": "AdminPassword123!",
        "role": "admin"
    })
    res = client.post("/api/auth/login", json={
        "email": "gov_admin@mahadisaster.gov.in",
        "password": "AdminPassword123!"
    })
    assert res.status_code == 200, f"Admin login failed: {res.status_code} {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def coordinator_token(client, admin_token):
    """Ensure a coordinator exists and return auth token."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    client.post("/api/auth/register", json={
        "email": "gov_coord@mahadisaster.gov.in",
        "password": "CoordPassword123!",
        "role": "coordinator"
    }, headers=headers)

    res = client.post("/api/auth/login", json={
        "email": "gov_coord@mahadisaster.gov.in",
        "password": "CoordPassword123!"
    })
    return res.json()["access_token"]


# ============================================================================
# 1. DEF-3C-08: SQLite Foreign Key Enforcement
# ============================================================================
def test_sqlite_foreign_key_enforcement():
    """Verify PRAGMA foreign_keys = ON rejects invalid references with IntegrityError."""
    db = api.database.SessionLocal()
    try:
        # Attempt to insert an AuditEvent referencing a nonexistent user_id
        invalid_event = AuditEvent(
            user_id=9999999,  # Nonexistent
            action="APPROVE",
            reason_code="TEST_FK",
            plan_hash="a" * 64,
            confidence=0.85,
            prev_hash=GENESIS_HASH,
            current_hash="b" * 64
        )
        db.add(invalid_event)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # Attempt to insert an AllocationRecord referencing a nonexistent simulation_id
        invalid_alloc = AllocationRecord(
            id=str(uuid.uuid4()),
            simulation_id=str(uuid.uuid4()),  # Nonexistent
            plan_hash="c" * 64,
            transfers_json="[]",
            status="PENDING_REVIEW"
        )
        db.add(invalid_alloc)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


# ============================================================================
# 2. DEF-3C-01: Simulation Record Persistence & Canonical Hashing
# ============================================================================
def test_simulate_scenario_persists_simulation_record(client, coordinator_token):
    """Verify POST /api/simulate persists exactly one SimulationRecord with matching UUID and hash."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    payload = {
        "epicentre": "Pune",
        "hazard": "Flood",
        "severity": 1.2,
        "planning_level": "P50",
        "stock_adjustment_pct": 0.0
    }

    res = client.post("/api/simulate", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    sim_id = data["simulation_id"]
    assert sim_id is not None

    db = api.database.SessionLocal()
    try:
        sim = db.query(SimulationRecord).filter(SimulationRecord.id == sim_id).first()
        assert sim is not None, f"SimulationRecord {sim_id} was not found in DB."
        assert sim.id == sim_id
        assert len(sim.results_hash) == 64
        assert "Pune" in sim.inputs_json
        assert "Flood" in sim.inputs_json
    finally:
        db.close()

def test_canonical_simulation_hash_determinism():
    """Verify canonical simulation hashing is deterministic and sensitive to input/result differences."""
    inputs_1 = {"epicentre": "Pune", "hazard": "Flood", "severity": 1.0}
    inputs_2 = {"hazard": "Flood", "severity": 1.0, "epicentre": "Pune"}  # Different dict order
    results_mock = [
        {"district": "Pune", "medicine": "antibiotics", "demand_p50": 100.0, "shortage_probability": 0.25},
        {"district": "Satara", "medicine": "ors", "demand_p50": 50.0, "shortage_probability": 0.10}
    ]

    json1, hash1 = compute_canonical_simulation_hash(inputs_1, results_mock)
    json2, hash2 = compute_canonical_simulation_hash(inputs_2, results_mock)
    assert json1 == json2
    assert hash1 == hash2

    # Different inputs produce different hashes
    inputs_diff = {"epicentre": "Mumbai", "hazard": "Flood", "severity": 1.0}
    _, hash_diff = compute_canonical_simulation_hash(inputs_diff, results_mock)
    assert hash1 != hash_diff


# ============================================================================
# 3. DEF-3C-02: Allocation Persistence & Deterministic Plan Hashing
# ============================================================================
def test_canonical_plan_hash_determinism():
    """Verify transfer plan hash is invariant to item list ordering and dict ordering."""
    t1 = {"source_region": "Satara", "dest_region": "Pune", "medicine": "antibiotics", "quantity": 50, "cost_index": 120.0, "distance_km": 110.0}
    t2 = {"source_region": "Kolhapur", "dest_region": "Sangli", "medicine": "ors", "quantity": 100, "cost_index": 80.0, "distance_km": 45.0}

    # Different list order
    _, hash_a = compute_canonical_plan_hash([t1, t2])
    _, hash_b = compute_canonical_plan_hash([t2, t1])
    assert hash_a == hash_b

def test_allocate_with_valid_simulation_persists_allocation(client, coordinator_token):
    """Verify POST /api/allocate links to simulation, computes plan_hash, and saves AllocationRecord."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    # 1. Create a simulation first
    sim_res = client.post("/api/simulate", json={
        "epicentre": "Kolhapur",
        "hazard": "Flood",
        "severity": 1.0,
        "planning_level": "P50"
    }, headers=headers)
    assert sim_res.status_code == 200
    sim_id = sim_res.json()["simulation_id"]

    # 2. Run allocation referencing that simulation
    alloc_res = client.post("/api/allocate", json={
        "simulation_id": sim_id,
        "epicentre": "Kolhapur",
        "hazard": "Flood",
        "severity": 1.0,
        "planning_level": "P50",
        "safety_reserve_ratio": 0.60
    }, headers=headers)
    assert alloc_res.status_code == 200, alloc_res.text
    alloc_data = alloc_res.json()

    assert alloc_data["simulation_id"] == sim_id
    assert alloc_data["allocation_id"] is not None
    assert len(alloc_data["plan_hash"]) == 64
    assert alloc_data["status"] == "PENDING_REVIEW"

    # 3. Verify AllocationRecord row in database
    db = api.database.SessionLocal()
    try:
        alloc_row = db.query(AllocationRecord).filter(AllocationRecord.id == alloc_data["allocation_id"]).first()
        assert alloc_row is not None
        assert alloc_row.simulation_id == sim_id
        assert alloc_row.plan_hash == alloc_data["plan_hash"]
        assert alloc_row.status == "PENDING_REVIEW"
    finally:
        db.close()

def test_allocate_with_invalid_simulation_rejected(client, coordinator_token):
    """Verify allocating with a nonexistent simulation_id returns 404 Not Found."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    fake_sim_id = str(uuid.uuid4())

    res = client.post("/api/allocate", json={
        "simulation_id": fake_sim_id,
        "epicentre": "Pune"
    }, headers=headers)
    assert res.status_code == 404
    assert "not found" in res.json()["message"].lower()

def test_allocate_legacy_without_simulation_id_marked_unlinked(client, coordinator_token):
    """Verify legacy allocation without simulation_id succeeds but is marked UNLINKED_LEGACY."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    res = client.post("/api/allocate", json={
        "epicentre": "Pune"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["simulation_id"] is None
    assert data["status"] == "UNLINKED_LEGACY"


# ============================================================================
# 4. Allocation Lifecycle & Audit Decision Binding
# ============================================================================
def test_audit_decision_approves_allocation_and_updates_status(client, coordinator_token):
    """Verify officer approving an allocation validates hash, updates status to APPROVED, and appends to ledger."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    # 1. Simulate
    sim_res = client.post("/api/simulate", json={"epicentre": "Pune", "severity": 1.0}, headers=headers)
    sim_id = sim_res.json()["simulation_id"]

    # 2. Allocate
    alloc_res = client.post("/api/allocate", json={"simulation_id": sim_id, "epicentre": "Pune"}, headers=headers)
    alloc_id = alloc_res.json()["allocation_id"]
    plan_hash = alloc_res.json()["plan_hash"]

    # 3. Submit APPROVE decision
    decision_res = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id,
        "simulation_id": sim_id,
        "action": "APPROVE",
        "reason_code": "SURGE_DEMAND_SATISFIED",
        "plan_hash": plan_hash,
        "confidence": 0.88
    }, headers=headers)
    assert decision_res.status_code == 201, decision_res.text
    event_data = decision_res.json()
    assert event_data["allocation_id"] == alloc_id
    assert event_data["action"] == "APPROVE"

    # 4. Assert allocation status transitioned to APPROVED in database
    db = api.database.SessionLocal()
    try:
        alloc = db.query(AllocationRecord).filter(AllocationRecord.id == alloc_id).first()
        assert alloc.status == "APPROVED"
    finally:
        db.close()

def test_audit_decision_rejects_unlinked_legacy_allocation(client, coordinator_token):
    """Verify unlinked legacy allocation cannot be approved in governance."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    alloc_res = client.post("/api/allocate", json={"epicentre": "Nashik"}, headers=headers)
    alloc_id = alloc_res.json()["allocation_id"]
    plan_hash = alloc_res.json()["plan_hash"]

    decision_res = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id,
        "action": "APPROVE",
        "reason_code": "TRY_LEGACY",
        "plan_hash": plan_hash,
        "confidence": 0.85
    }, headers=headers)
    assert decision_res.status_code == 400
    assert "unlinked legacy allocation" in decision_res.json()["message"].lower()

def test_audit_decision_mismatched_plan_hash_rejected(client, coordinator_token):
    """Verify decision with wrong plan_hash is rejected with HTTP 400."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    sim_res = client.post("/api/simulate", json={"epicentre": "Pune"}, headers=headers)
    sim_id = sim_res.json()["simulation_id"]
    alloc_res = client.post("/api/allocate", json={"simulation_id": sim_id}, headers=headers)
    alloc_id = alloc_res.json()["allocation_id"]

    decision_res = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id,
        "action": "APPROVE",
        "reason_code": "TEST",
        "plan_hash": "f" * 64,  # Incorrect hash
        "confidence": 0.85
    }, headers=headers)
    assert decision_res.status_code == 400
    assert "does not match" in decision_res.json()["message"].lower()


# ============================================================================
# 5. DEF-3C-07: Transaction-Safe Concurrent Ledger Append
# ============================================================================
def test_concurrent_ledger_appends_form_single_unbroken_chain(client, coordinator_token):
    """Verify concurrent writes serialize via BEGIN IMMEDIATE and maintain an unbroken SHA-256 chain."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    errors = []
    num_threads = 6

    def submit_event(thread_idx):
        try:
            res = client.post("/api/audit/decision", json={
                "action": "APPROVE",
                "reason_code": f"CONCURRENT_STRESS_{thread_idx}",
                "plan_hash": f"stress_plan_{thread_idx}_{'a' * 45}",
                "confidence": 0.75 + (thread_idx * 0.02)
            }, headers=headers)
            if res.status_code != 201:
                errors.append(f"Thread {thread_idx} failed: {res.status_code} - {res.text}")
        except Exception as exc:
            errors.append(f"Thread {thread_idx} exception: {exc}")

    threads = [threading.Thread(target=submit_event, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors during concurrent audit appends: {errors}"

    # Verify chain integrity
    verify_res = client.get("/api/audit/verify", headers=headers)
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["is_valid"] is True, f"Audit chain broke after concurrent writes: {v_data}"
    assert v_data["broken_block"] is None


# ============================================================================
# 6. DEF-3C-05: Clinical Model Readiness Probe
# ============================================================================
def test_readiness_probe_reports_clinical_model_and_fails_when_missing(client):
    """Verify /ready probe inspects and reports clinical_model status."""
    # 1. Normal state: all models loaded
    res = client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert "clinical_model" in data["artifacts_loaded"]
    assert data["artifacts_loaded"]["clinical_model"] is True

    # 2. Simulate clinical_model missing on app.state
    saved_model = app.state.clinical_model
    try:
        app.state.clinical_model = None
        res_missing = client.get("/ready")
        assert res_missing.status_code == 503
        assert "not ready" in res_missing.json()["message"].lower()
    finally:
        app.state.clinical_model = saved_model
