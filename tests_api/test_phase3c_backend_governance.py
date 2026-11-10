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
    compute_block_hash,
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


# ============================================================================
# 7. ACT-3C-01: Atomic Decision and Allocation Status Transitions
# ============================================================================
def test_atomic_decision_and_allocation_status_commit(client, coordinator_token):
    """Verify AuditEvent and AllocationRecord status change commit together in one transaction."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    sim_res = client.post("/api/simulate", json={"epicentre": "Pune"}, headers=headers)
    sim_id = sim_res.json()["simulation_id"]
    alloc_res = client.post("/api/allocate", json={"simulation_id": sim_id, "epicentre": "Pune"}, headers=headers)
    alloc_id = alloc_res.json()["allocation_id"]
    plan_hash = alloc_res.json()["plan_hash"]

    res = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id,
        "simulation_id": sim_id,
        "action": "APPROVE",
        "reason_code": "CLINICAL_CAPACITY_CONFIRMED",
        "plan_hash": plan_hash,
        "confidence": 0.89
    }, headers=headers)
    assert res.status_code == 201
    body = res.json()
    assert body["block_version"] == 2
    assert body["allocation_id"] == alloc_id

    db = api.database.SessionLocal()
    try:
        alloc = db.query(AllocationRecord).filter(AllocationRecord.id == alloc_id).first()
        event = db.query(AuditEvent).filter(AuditEvent.allocation_id == alloc_id).first()
        assert alloc is not None
        assert event is not None
        assert alloc.status == "APPROVED"
        assert event.action == "APPROVE"
        assert event.block_version == 2
    finally:
        db.close()

def test_atomic_rollback_on_failure():
    """Verify that if an error occurs before/during commit, neither the status nor the audit event persists."""
    db = api.database.SessionLocal()
    try:
        user = db.query(User).first()
        sim_id = str(uuid.uuid4())
        sim = SimulationRecord(id=sim_id, user_id=user.id, inputs_json="{}", results_hash="1"*64)
        db.add(sim)
        alloc_id = str(uuid.uuid4())
        alloc = AllocationRecord(
            id=alloc_id,
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash="2"*64,
            transfers_json="[]",
            status="PENDING_REVIEW"
        )
        db.add(alloc)
        db.commit()

        # Monkeypatch db.commit to simulate database failure during commit
        from unittest.mock import patch
        with patch.object(db, "commit", side_effect=RuntimeError("Simulated DB commit crash")):
            with pytest.raises(RuntimeError, match="Simulated DB commit crash"):
                record_decision(
                    db=db,
                    user=user,
                    action="APPROVE",
                    reason_code="TEST_ROLLBACK",
                    plan_hash="2"*64,
                    confidence=0.90,
                    simulation_id=sim_id,
                    allocation_id=alloc_id
                )

        # In a new session, verify that neither status change nor audit event was committed
        verify_db = api.database.SessionLocal()
        try:
            alloc_fresh = verify_db.query(AllocationRecord).filter(AllocationRecord.id == alloc_id).first()
            event_fresh = verify_db.query(AuditEvent).filter(AuditEvent.allocation_id == alloc_id).first()
            assert alloc_fresh.status == "PENDING_REVIEW"
            assert event_fresh is None
        finally:
            verify_db.close()
    finally:
        db.close()


# ============================================================================
# 8. ACT-3C-02: Terminal-State Protection & Duplicate Decision Prevention
# ============================================================================
def test_terminal_state_protection_prevents_duplicate_or_conflicting_decisions(client, coordinator_token):
    """Verify allocations in APPROVED or REJECTED state reject further decisions with HTTP 409 Conflict."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    # Case 1: Finalized as APPROVED
    sim_res1 = client.post("/api/simulate", json={"epicentre": "Satara"}, headers=headers)
    sim_id1 = sim_res1.json()["simulation_id"]
    alloc_res1 = client.post("/api/allocate", json={"simulation_id": sim_id1, "epicentre": "Satara"}, headers=headers)
    alloc_id1 = alloc_res1.json()["allocation_id"]
    plan_hash1 = alloc_res1.json()["plan_hash"]

    # First APPROVE -> succeeds
    res_app1 = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id1,
        "action": "APPROVE",
        "reason_code": "APPROVED_INITIAL",
        "plan_hash": plan_hash1,
        "confidence": 0.85
    }, headers=headers)
    assert res_app1.status_code == 201

    # Repeat APPROVE -> 409 Conflict
    res_app_dup = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id1,
        "action": "APPROVE",
        "reason_code": "APPROVED_AGAIN",
        "plan_hash": plan_hash1,
        "confidence": 0.85
    }, headers=headers)
    assert res_app_dup.status_code == 409
    assert "already been finalized" in res_app_dup.json()["message"].lower()

    # Conflicting REJECT on APPROVED -> 409 Conflict
    res_rej_conflict = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id1,
        "action": "REJECT",
        "reason_code": "REJECT_LATER",
        "plan_hash": plan_hash1,
        "confidence": 0.85
    }, headers=headers)
    assert res_rej_conflict.status_code == 409
    assert "already been finalized" in res_rej_conflict.json()["message"].lower()

    # Case 2: Finalized as REJECTED
    sim_res2 = client.post("/api/simulate", json={"epicentre": "Sangli"}, headers=headers)
    sim_id2 = sim_res2.json()["simulation_id"]
    alloc_res2 = client.post("/api/allocate", json={"simulation_id": sim_id2, "epicentre": "Sangli"}, headers=headers)
    alloc_id2 = alloc_res2.json()["allocation_id"]
    plan_hash2 = alloc_res2.json()["plan_hash"]

    # First REJECT -> succeeds
    res_rej1 = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id2,
        "action": "REJECT",
        "reason_code": "COST_EXCESSIVE",
        "plan_hash": plan_hash2,
        "confidence": 0.85
    }, headers=headers)
    assert res_rej1.status_code == 201

    # Repeat REJECT -> 409 Conflict
    res_rej_dup = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id2,
        "action": "REJECT",
        "reason_code": "REJECT_AGAIN",
        "plan_hash": plan_hash2,
        "confidence": 0.85
    }, headers=headers)
    assert res_rej_dup.status_code == 409
    assert "already been finalized" in res_rej_dup.json()["message"].lower()

    # Conflicting APPROVE on REJECTED -> 409 Conflict
    res_app_conflict = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id2,
        "action": "APPROVE",
        "reason_code": "APPROVE_LATER",
        "plan_hash": plan_hash2,
        "confidence": 0.85
    }, headers=headers)
    assert res_app_conflict.status_code == 409
    assert "already been finalized" in res_app_conflict.json()["message"].lower()

def test_concurrent_competing_decisions_on_same_allocation(client, coordinator_token):
    """Verify that concurrent competing decisions on the same allocation yield exactly one 201 and one 409."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    sim_res = client.post("/api/simulate", json={"epicentre": "Thane"}, headers=headers)
    sim_id = sim_res.json()["simulation_id"]
    alloc_res = client.post("/api/allocate", json={"simulation_id": sim_id, "epicentre": "Thane"}, headers=headers)
    alloc_id = alloc_res.json()["allocation_id"]
    plan_hash = alloc_res.json()["plan_hash"]

    statuses = []

    def make_decision(action, reason):
        try:
            r = client.post("/api/audit/decision", json={
                "allocation_id": alloc_id,
                "action": action,
                "reason_code": reason,
                "plan_hash": plan_hash,
                "confidence": 0.91
            }, headers=headers)
            statuses.append(r.status_code)
        except Exception as e:
            statuses.append(str(e))

    t1 = threading.Thread(target=make_decision, args=("APPROVE", "CONCURRENT_APPROVE"))
    t2 = threading.Thread(target=make_decision, args=("REJECT", "CONCURRENT_REJECT"))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one must succeed (201) and the other must be rejected (409)
    assert sorted(statuses) == [201, 409], f"Unexpected status codes: {statuses}"


# ============================================================================
# 9. ACT-3C-03: Backward-Compatible v2 Hashing & Tamper-Evidence
# ============================================================================
def test_v2_block_hashing_binds_allocation_id_and_detects_tampering(client, coordinator_token):
    """Verify v2 blocks bind allocation_id and tamper-evidence detects allocation_id mutation."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    sim_res = client.post("/api/simulate", json={"epicentre": "Nagpur"}, headers=headers)
    sim_id = sim_res.json()["simulation_id"]
    alloc_res = client.post("/api/allocate", json={"simulation_id": sim_id, "epicentre": "Nagpur"}, headers=headers)
    alloc_id = alloc_res.json()["allocation_id"]
    plan_hash = alloc_res.json()["plan_hash"]

    res = client.post("/api/audit/decision", json={
        "allocation_id": alloc_id,
        "action": "APPROVE",
        "reason_code": "REGIONAL_DISPATCH_AUTHORIZED",
        "plan_hash": plan_hash,
        "confidence": 0.94
    }, headers=headers)
    assert res.status_code == 201
    event_id = res.json()["id"]

    db = api.database.SessionLocal()
    try:
        # 1. Chain must be valid initially
        is_valid, _, _ = verify_chain(db)
        assert is_valid is True

        # Create another valid allocation to test swapping allocation_id without violating foreign key constraints
        user = db.query(User).first()
        other_alloc_id = str(uuid.uuid4())
        other_alloc = AllocationRecord(
            id=other_alloc_id,
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash="b" * 64,
            transfers_json="[]",
            status="PENDING_REVIEW"
        )
        db.add(other_alloc)
        db.commit()

        # 2. Tamper with allocation_id in the newly created v2 block (swap to other_alloc_id)
        event = db.query(AuditEvent).filter(AuditEvent.id == event_id).first()
        original_alloc_id = event.allocation_id
        event.allocation_id = other_alloc_id
        db.commit()

        is_valid, _, broken_info = verify_chain(db)
        assert is_valid is False
        assert broken_info["error_type"] == "BLOCK_TAMPERING_DETECTED"
        assert broken_info["broken_row_id"] == event_id

        # 3. Restore original allocation_id -> chain valid again
        event.allocation_id = original_alloc_id
        db.commit()
        is_valid, _, _ = verify_chain(db)
        assert is_valid is True
    finally:
        db.close()

def test_v1_legacy_compatibility_and_mixed_chain():
    """Verify legacy v1 blocks (without allocation_id binding) verify successfully and chain into v2 blocks."""
    db = api.database.SessionLocal()
    try:
        user = db.query(User).first()
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        timestamp_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")

        from sqlalchemy import desc
        latest = db.query(AuditEvent).order_by(desc(AuditEvent.id)).first()
        prev_hash = latest.current_hash if latest else GENESIS_HASH

        # 1. Construct a legacy v1 block manually using version 1 formula
        v1_current_hash = compute_block_hash(
            prev_hash=prev_hash,
            timestamp_str=timestamp_str,
            user_id=user.id,
            simulation_id=None,
            action="APPROVE",
            reason_code="LEGACY_V1_REASON",
            plan_hash="3" * 64,
            confidence=0.88,
            version=1
        )

        v1_event = AuditEvent(
            user_id=user.id,
            simulation_id=None,
            allocation_id=None,
            action="APPROVE",
            reason_code="LEGACY_V1_REASON",
            plan_hash="3" * 64,
            confidence=0.88,
            prev_hash=prev_hash,
            current_hash=v1_current_hash,
            block_version=1,
            created_at=now_utc
        )
        db.add(v1_event)
        db.commit()
        db.refresh(v1_event)

        # 2. Verify chain with legacy v1 block intact
        is_valid, _, _ = verify_chain(db)
        assert is_valid is True

        # 3. Legacy limitation test: mutating allocation_id on v1 block does NOT break v1 hash
        # (This documents why v2 was necessary to bind allocation_id cryptographically)
        other_alloc_id = str(uuid.uuid4())
        other_alloc = AllocationRecord(
            id=other_alloc_id,
            simulation_id=None,
            user_id=user.id,
            plan_hash="c" * 64,
            transfers_json="[]",
            status="PENDING_REVIEW"
        )
        db.add(other_alloc)
        db.commit()

        v1_event.allocation_id = other_alloc_id
        db.commit()
        is_valid, _, _ = verify_chain(db)
        assert is_valid is True, "v1 hash did not bind allocation_id; mutating it should not break v1 verification"

        # 4. Mutating plan_hash on v1 block DOES break verification
        v1_event.plan_hash = "4" * 64
        db.commit()
        is_valid, _, broken_info = verify_chain(db)
        assert is_valid is False
        assert broken_info["error_type"] == "BLOCK_TAMPERING_DETECTED"

        # Restore v1 plan_hash and allocation_id
        v1_event.plan_hash = "3" * 64
        v1_event.allocation_id = None
        db.commit()
        is_valid, _, _ = verify_chain(db)
        assert is_valid is True

        # 5. Append a v2 block linking to the v1 block to verify mixed chain
        v2_event = record_decision(
            db=db,
            user=user,
            action="APPROVE",
            reason_code="V2_CHAINED_TO_V1",
            plan_hash="5" * 64,
            confidence=0.92
        )
        assert v2_event.prev_hash == v1_event.current_hash
        assert v2_event.block_version == 2

        is_valid, _, _ = verify_chain(db)
        assert is_valid is True

    finally:
        db.close()

def test_unsupported_block_version_detected():
    """Verify an unrecognized block_version is reported as UNSUPPORTED_BLOCK_VERSION."""
    db = api.database.SessionLocal()
    try:
        from sqlalchemy import desc
        latest = db.query(AuditEvent).order_by(desc(AuditEvent.id)).first()
        assert latest is not None

        orig_version = latest.block_version
        latest.block_version = 99  # Invalid version
        db.commit()

        is_valid, _, broken_info = verify_chain(db)
        assert is_valid is False
        assert broken_info["error_type"] == "UNSUPPORTED_BLOCK_VERSION"
        assert broken_info["unsupported_version"] == 99

        # Restore version
        latest.block_version = orig_version
        db.commit()
        is_valid, _, _ = verify_chain(db)
        assert is_valid is True
    finally:
        db.close()


# ============================================================================
# 10. Phase 3C-3 Closeout: P1 — Schema Migration Failure Handling & Safety
# ============================================================================
def test_migration_adds_allocation_id_and_block_version_to_legacy_database(tmp_path):
    """Verify legacy SQLite DB missing allocation_id and block_version is migrated correctly."""
    from sqlalchemy import create_engine, text
    from api.database import init_db

    db_path = tmp_path / "legacy_test.db"
    legacy_engine = create_engine(f"sqlite:///{db_path}")

    # Create legacy audit_events table without allocation_id and block_version
    with legacy_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                created_at DATETIME NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE simulations (
                id VARCHAR(36) PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                inputs_json TEXT NOT NULL,
                results_hash VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE allocations (
                id VARCHAR(36) PRIMARY KEY,
                simulation_id VARCHAR(36) REFERENCES simulations(id),
                user_id INTEGER REFERENCES users(id),
                plan_hash VARCHAR(64) NOT NULL,
                transfers_json TEXT NOT NULL,
                status VARCHAR(50) NOT NULL,
                cost_index FLOAT,
                unmet_demand_after FLOAT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                simulation_id VARCHAR(36) REFERENCES simulations(id),
                action VARCHAR(20) NOT NULL,
                reason_code VARCHAR(100) NOT NULL,
                plan_hash VARCHAR(64) NOT NULL,
                confidence FLOAT NOT NULL,
                prev_hash VARCHAR(64) NOT NULL,
                current_hash VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL
            );
        """))
        conn.execute(text("INSERT INTO users (id, email, hashed_password, role, created_at) VALUES (1, 'hist@test.gov', 'pwd', 'officer', '2026-01-01 00:00:00')"))
        from api.audit_ledger import compute_block_hash
        hist_hash = compute_block_hash(
            prev_hash=GENESIS_HASH,
            timestamp_str="2026-01-01 00:00:00",
            user_id=1,
            simulation_id=None,
            action="APPROVE",
            reason_code="HISTORICAL_LEGACY",
            plan_hash="h" * 64,
            confidence=0.85,
            version=1
        )
        conn.execute(text(f"""
            INSERT INTO audit_events (id, user_id, simulation_id, action, reason_code, plan_hash, confidence, prev_hash, current_hash, created_at)
            VALUES (1, 1, NULL, 'APPROVE', 'HISTORICAL_LEGACY', '{"h"*64}', 0.85, '{GENESIS_HASH}', '{hist_hash}', '2026-01-01 00:00:00')
        """))
        conn.commit()

    # Verify columns absent before migration
    with legacy_engine.connect() as conn:
        cols_before = [r[1] for r in conn.execute(text("PRAGMA table_info(audit_events)")).fetchall()]
        assert "allocation_id" not in cols_before
        assert "block_version" not in cols_before

    # Run init_db with legacy_engine
    init_db(target_engine=legacy_engine)

    # Verify columns added and historical row assigned block_version=1
    with legacy_engine.connect() as conn:
        cols_after = [r[1] for r in conn.execute(text("PRAGMA table_info(audit_events)")).fetchall()]
        assert "allocation_id" in cols_after
        assert "block_version" in cols_after
        row = conn.execute(text("SELECT id, block_version, current_hash FROM audit_events WHERE id=1")).fetchone()
        assert row[1] == 1
        assert row[2] == hist_hash

    # Verify chain with verify_chain
    from sqlalchemy.orm import sessionmaker
    LegacySession = sessionmaker(bind=legacy_engine)
    session = LegacySession()
    try:
        is_valid, count, broken = verify_chain(session)
        assert is_valid is True
        assert count == 1
    finally:
        session.close()

def test_migration_idempotency_on_already_migrated_database(tmp_path):
    """Verify init_db can be called repeatedly without duplicate column errors."""
    from sqlalchemy import create_engine
    from api.database import init_db

    db_path = tmp_path / "idempotent_test.db"
    test_engine = create_engine(f"sqlite:///{db_path}")

    # First call: creates tables and migrations
    init_db(target_engine=test_engine)

    # Second call: must succeed without OperationalError: duplicate column name
    init_db(target_engine=test_engine)

    # Third call: still idempotent
    init_db(target_engine=test_engine)

def test_migration_failure_raises_clear_error_and_preserves_cause(tmp_path):
    """Verify schema migration errors raise RuntimeError with original exception chained."""
    from sqlalchemy import create_engine
    from unittest.mock import patch
    from api.database import init_db

    db_path = tmp_path / "fail_migration.db"
    test_engine = create_engine(f"sqlite:///{db_path}")

    # First initialize tables
    init_db(target_engine=test_engine)

    # Mock engine.connect to raise OperationalError during migration check
    with patch.object(test_engine, "connect", side_effect=Exception("Simulated migration disk failure")):
        with pytest.raises(RuntimeError) as exc_info:
            init_db(target_engine=test_engine)
        assert "Database schema migration failed" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, Exception)
        assert "Simulated migration disk failure" in str(exc_info.value.__cause__)

def test_lifespan_aborts_readiness_on_migration_failure():
    """Verify lifespan startup fails loudly and keeps app.state.ready = False if init_db fails."""
    import asyncio
    from fastapi import FastAPI
    from unittest.mock import patch
    from api.lifespan import lifespan

    test_app = FastAPI()
    test_app.state.ready = False

    with patch("api.database.init_db", side_effect=RuntimeError("Migration failed fatally")):
        with pytest.raises(RuntimeError, match="Migration failed fatally"):
            asyncio.run(lifespan(test_app).__aenter__())
        assert test_app.state.ready is False


# ============================================================================
# 11. Phase 3C-3 Closeout: P2 — Never Suppress SQLite BEGIN IMMEDIATE Failures
# ============================================================================
def test_begin_immediate_failure_aborts_immediately_without_persisting_or_mutating(client, coordinator_token):
    """Verify that if BEGIN IMMEDIATE fails, decision aborts with no event inserted and allocation stays PENDING_REVIEW."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    # Setup allocation
    sim_res = client.post("/api/simulate", json={"epicentre": "Satara"}, headers=headers)
    sim_id = sim_res.json()["simulation_id"]
    alloc_res = client.post("/api/allocate", json={"simulation_id": sim_id, "epicentre": "Satara"}, headers=headers)
    alloc_id = alloc_res.json()["allocation_id"]
    plan_hash = alloc_res.json()["plan_hash"]

    # Mock db.execute to fail on BEGIN IMMEDIATE
    db = api.database.SessionLocal()
    user = db.query(User).first()
    original_execute = db.execute

    def failing_execute(clause, *args, **kwargs):
        if "BEGIN IMMEDIATE" in str(clause):
            raise RuntimeError("Injected BEGIN IMMEDIATE failure")
        return original_execute(clause, *args, **kwargs)

    db.execute = failing_execute

    with pytest.raises(RuntimeError, match="Injected BEGIN IMMEDIATE failure"):
        record_decision(
            db=db,
            user=user,
            action="APPROVE",
            reason_code="SHOULD_ABORT",
            plan_hash=plan_hash,
            confidence=0.90,
            simulation_id=sim_id,
            allocation_id=alloc_id
        )
    db.close()

    # Verify allocation remains PENDING_REVIEW and no audit event was created
    verify_db = api.database.SessionLocal()
    try:
        alloc = verify_db.query(AllocationRecord).filter(AllocationRecord.id == alloc_id).first()
        event = verify_db.query(AuditEvent).filter(AuditEvent.allocation_id == alloc_id).first()
        assert alloc.status == "PENDING_REVIEW"
        assert event is None
    finally:
        verify_db.close()

def test_begin_immediate_lock_timeout_maps_to_http_503(tmp_path):
    """Verify that SQLite lock timeout on BEGIN IMMEDIATE returns HTTP 503 retryable response."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from fastapi import HTTPException
    from api.models import Base, User, SimulationRecord, AllocationRecord, AuditEvent
    from api.audit_ledger import record_decision

    db_path = tmp_path / "lock_contention.db"
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"timeout": 0.5})
    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)

    # Seed user, simulation, allocation
    seed_s = TestSession()
    u = User(email="lock_officer@test.gov", hashed_password="pwd", role="officer")
    seed_s.add(u)
    seed_s.commit()
    user_id = u.id

    sim = SimulationRecord(id="sim_lock", user_id=user_id, inputs_json="{}", results_hash="1"*64)
    alloc = AllocationRecord(id="alloc_lock", simulation_id="sim_lock", user_id=user_id, plan_hash="2"*64, transfers_json="[]", status="PENDING_REVIEW")
    seed_s.add(sim)
    seed_s.add(alloc)
    seed_s.commit()
    seed_s.close()

    # Connection 1: acquire and hold an exclusive lock via raw DBAPI connection
    conn1 = test_engine.connect()
    conn1.execute(text("BEGIN IMMEDIATE"))

    # Connection 2: attempt record_decision with 0.5s timeout; must fail with HTTP 503
    s2 = TestSession()
    user2 = s2.query(User).filter(User.id == user_id).first()

    try:
        with pytest.raises(HTTPException) as exc_info:
            record_decision(
                db=s2,
                user=user2,
                action="APPROVE",
                reason_code="COMPETE_FOR_LOCK",
                plan_hash="2"*64,
                confidence=0.92,
                simulation_id="sim_lock",
                allocation_id="alloc_lock"
            )
        assert exc_info.value.status_code == 503
        assert "Database write lock acquisition timed out" in exc_info.value.detail
    finally:
        s2.close()
        conn1.rollback()
        conn1.close()

    # Verify allocation remains PENDING_REVIEW and no AuditEvent was inserted
    check_s = TestSession()
    try:
        alloc_row = check_s.query(AllocationRecord).filter(AllocationRecord.id == "alloc_lock").first()
        event_row = check_s.query(AuditEvent).filter(AuditEvent.allocation_id == "alloc_lock").first()
        assert alloc_row.status == "PENDING_REVIEW"
        assert event_row is None
    finally:
        check_s.close()
