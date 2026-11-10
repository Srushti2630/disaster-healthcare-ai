"""
Integration and RBAC unit test suite for Backend Allocation Retrieval APIs.
Phase 3D-1: GET /api/allocations/pending and GET /api/allocations/{allocation_id}.
"""
import json
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.main import app
import api.database
from api.models import User, UserRole, SimulationRecord, AllocationRecord
from api.audit_ledger import compute_canonical_plan_hash

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture(scope="module")
def admin_token(client):
    """Register and log in as administrator."""
    client.post("/api/auth/register", json={
        "email": "retrieval_admin@mahadisaster.gov.in",
        "password": "AdminPassword123!",
        "role": "admin"
    })
    res = client.post("/api/auth/login", json={
        "email": "retrieval_admin@mahadisaster.gov.in",
        "password": "AdminPassword123!"
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def coordinator_token(client, admin_token):
    """Register and log in as coordinator."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    client.post("/api/auth/register", json={
        "email": "retrieval_coord@mahadisaster.gov.in",
        "password": "CoordPassword123!",
        "role": "coordinator"
    }, headers=headers)
    res = client.post("/api/auth/login", json={
        "email": "retrieval_coord@mahadisaster.gov.in",
        "password": "CoordPassword123!"
    })
    assert res.status_code == 200, f"Coord login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def officer_token(client, admin_token):
    """Register and log in as officer."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    client.post("/api/auth/register", json={
        "email": "retrieval_officer@mahadisaster.gov.in",
        "password": "OfficerPassword123!",
        "role": "officer"
    }, headers=headers)
    res = client.post("/api/auth/login", json={
        "email": "retrieval_officer@mahadisaster.gov.in",
        "password": "OfficerPassword123!"
    })
    assert res.status_code == 200, f"Officer login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def viewer_token(client, admin_token):
    """Register and log in as viewer."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    client.post("/api/auth/register", json={
        "email": "retrieval_viewer@mahadisaster.gov.in",
        "password": "ViewerPassword123!",
        "role": "viewer"
    }, headers=headers)
    res = client.post("/api/auth/login", json={
        "email": "retrieval_viewer@mahadisaster.gov.in",
        "password": "ViewerPassword123!"
    })
    assert res.status_code == 200, f"Viewer login failed: {res.text}"
    return res.json()["access_token"]

# -------------------------------------------------------------
# 1. EMPTY QUEUE AND UNAUTHORIZED ACCESS
# -------------------------------------------------------------
def test_empty_pending_queue_returns_200_empty_list(client, coordinator_token):
    """Empty governance queue returns HTTP 200 with an empty list."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    res = client.get("/api/allocations/pending", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert res.json() == []

def test_unauthorized_access_rejected(client):
    """Unauthenticated requests without Bearer token must return HTTP 401."""
    # 1. Pending queue
    res_pending = client.get("/api/allocations/pending")
    assert res_pending.status_code == 401

    # 2. Single allocation
    res_detail = client.get(f"/api/allocations/{uuid.uuid4()}")
    assert res_detail.status_code == 401

    # 3. Invalid token
    bad_headers = {"Authorization": "Bearer invalid.token.signature"}
    res_bad = client.get("/api/allocations/pending", headers=bad_headers)
    assert res_bad.status_code == 401

# -------------------------------------------------------------
# 2. PENDING QUEUE FUNCTIONALITY & SENSITIVE FIELD PROTECTION
# -------------------------------------------------------------
def test_pending_allocations_returned_correctly_with_metadata(client, coordinator_token):
    """Verify that persisted PENDING_REVIEW allocations are returned newest-first with creator metadata."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    db = api.database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "retrieval_coord@mahadisaster.gov.in").first()
        assert user is not None

        # Create simulation record
        sim_id = str(uuid.uuid4())
        sim = SimulationRecord(
            id=sim_id,
            user_id=user.id,
            inputs_json=json.dumps({"epicentre": "Satara", "hazard": "Flood"}),
            results_hash="a" * 64
        )
        db.add(sim)

        # Create 2 pending allocations
        sample_transfers_1 = [
            {"source_region": "Pune", "dest_region": "Satara", "medicine": "antibiotics", "quantity": 100, "distance_km": 110.5, "cost_index": 2157.5, "priority": "HIGH", "confidence": 0.88}
        ]
        transfers_json_1, plan_hash_1 = compute_canonical_plan_hash(sample_transfers_1)
        alloc_1 = AllocationRecord(
            id=str(uuid.uuid4()),
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash=plan_hash_1,
            transfers_json=transfers_json_1,
            status="PENDING_REVIEW",
            cost_index=2157.5,
            unmet_demand_after=120.0,
            created_at=datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
        )

        sample_transfers_2 = [
            {"source_region": "Mumbai", "dest_region": "Satara", "medicine": "iv_fluids", "quantity": 250, "distance_km": 250.0, "cost_index": 4250.0, "priority": "CRITICAL", "confidence": 0.92}
        ]
        transfers_json_2, plan_hash_2 = compute_canonical_plan_hash(sample_transfers_2)
        alloc_2 = AllocationRecord(
            id=str(uuid.uuid4()),
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash=plan_hash_2,
            transfers_json=transfers_json_2,
            status="PENDING_REVIEW",
            cost_index=4250.0,
            unmet_demand_after=40.0,
            created_at=datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        db.add_all([alloc_1, alloc_2])
        db.commit()

        # Query pending allocations
        res = client.get("/api/allocations/pending", headers=headers)
        assert res.status_code == 200
        items = res.json()
        assert len(items) >= 2

        # Verify newest-first ordering (alloc_2 created at 12:00 should precede alloc_1 at 10:00)
        found_ids = [item["allocation_id"] for item in items]
        assert alloc_2.id in found_ids
        assert alloc_1.id in found_ids
        idx_2 = found_ids.index(alloc_2.id)
        idx_1 = found_ids.index(alloc_1.id)
        assert idx_2 < idx_1, "Newer allocation must precede older allocation in governance queue."

        # Verify summary metrics and metadata for alloc_2
        target_item = items[idx_2]
        assert target_item["allocation_id"] == alloc_2.id
        assert target_item["id"] == alloc_2.id
        assert target_item["simulation_id"] == sim_id
        assert target_item["plan_hash"] == plan_hash_2
        assert target_item["status"] == "PENDING_REVIEW"
        assert target_item["cost_index"] == 4250.0
        assert target_item["unmet_demand_after"] == 40.0
        assert target_item["transfers_count"] == 1
        assert target_item["total_transferred_units"] == 250
        assert target_item["creator"] is not None
        assert target_item["creator"]["email"] == "retrieval_coord@mahadisaster.gov.in"
        assert target_item["creator"]["role"] == "coordinator"

        # Strictly verify sensitive user fields are NOT exposed
        assert "hashed_password" not in target_item["creator"]
        assert "hashed_password" not in res.text
        assert "password" not in res.text.lower() or "hashed_password" not in res.text
    finally:
        db.close()

def test_approved_and_rejected_allocations_excluded_from_pending_queue(client, coordinator_token):
    """Allocations in APPROVED, REJECTED, or UNLINKED_LEGACY status must never appear in pending queue."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    db = api.database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "retrieval_coord@mahadisaster.gov.in").first()
        sim_id = str(uuid.uuid4())
        sim = SimulationRecord(id=sim_id, user_id=user.id, inputs_json="{}", results_hash="b" * 64)
        db.add(sim)

        # 1. Approved allocation
        alloc_approved = AllocationRecord(
            id=str(uuid.uuid4()),
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash="1" * 64,
            transfers_json="[]",
            status="APPROVED",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        # 2. Rejected allocation
        alloc_rejected = AllocationRecord(
            id=str(uuid.uuid4()),
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash="2" * 64,
            transfers_json="[]",
            status="REJECTED",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        # 3. Unlinked legacy allocation
        alloc_unlinked = AllocationRecord(
            id=str(uuid.uuid4()),
            simulation_id=None,
            user_id=user.id,
            plan_hash="3" * 64,
            transfers_json="[]",
            status="UNLINKED_LEGACY",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add_all([alloc_approved, alloc_rejected, alloc_unlinked])
        db.commit()

        # Query pending queue
        res = client.get("/api/allocations/pending", headers=headers)
        assert res.status_code == 200
        pending_ids = [item["allocation_id"] for item in res.json()]
        assert alloc_approved.id not in pending_ids
        assert alloc_rejected.id not in pending_ids
        assert alloc_unlinked.id not in pending_ids
    finally:
        db.close()

# -------------------------------------------------------------
# 3. SINGLE ALLOCATION RETRIEVAL & SHIPMENT ROW PARSING
# -------------------------------------------------------------
def test_single_allocation_retrieval_returns_correct_shipment_rows(client, coordinator_token):
    """Retrieve one persisted allocation and verify its constituent shipment rows."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    db = api.database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "retrieval_coord@mahadisaster.gov.in").first()
        sim_id = str(uuid.uuid4())
        sim = SimulationRecord(id=sim_id, user_id=user.id, inputs_json="{}", results_hash="c" * 64)
        db.add(sim)

        shipments_data = [
            {"source_region": "Pune", "dest_region": "Satara", "medicine": "antibiotics", "quantity": 120, "distance_km": 110.5, "cost_index": 2157.5, "priority": "HIGH", "confidence": 0.88},
            {"source_region": "Thane", "dest_region": "Raigad", "medicine": "blood_units", "quantity": 30, "distance_km": 85.2, "cost_index": 1778.0, "priority": "CRITICAL", "confidence": 0.95}
        ]
        transfers_json, plan_hash = compute_canonical_plan_hash(shipments_data)
        alloc_id = str(uuid.uuid4())
        alloc = AllocationRecord(
            id=alloc_id,
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash=plan_hash,
            transfers_json=transfers_json,
            status="PENDING_REVIEW",
            cost_index=3935.5,
            unmet_demand_after=55.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(alloc)
        db.commit()

        # Call GET /api/allocations/{allocation_id}
        res = client.get(f"/api/allocations/{alloc_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert data["allocation_id"] == alloc_id
        assert data["id"] == alloc_id
        assert data["simulation_id"] == sim_id
        assert data["plan_hash"] == plan_hash
        assert data["status"] == "PENDING_REVIEW"
        assert data["cost_index"] == 3935.5
        assert data["unmet_demand_after"] == 55.0
        assert data["transfers_count"] == 2
        assert data["total_transferred_units"] == 150

        # Verify shipment rows
        shipments = data["shipments"]
        assert len(shipments) == 2
        for s in shipments:
            assert "source_region" in s
            assert "dest_region" in s
            assert "medicine" in s
            assert "quantity" in s
            assert "distance_km" in s
            assert "cost_index" in s
            assert "priority" in s
            assert "confidence" in s
    finally:
        db.close()

def test_deterministic_shipment_ordering(client, coordinator_token):
    """Constituent shipment rows must be returned stably sorted by (source_region, dest_region, medicine)."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    db = api.database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "retrieval_coord@mahadisaster.gov.in").first()
        sim_id = str(uuid.uuid4())
        sim = SimulationRecord(id=sim_id, user_id=user.id, inputs_json="{}", results_hash="d" * 64)
        db.add(sim)

        # Insert shipments in reverse/random alphabetical order
        unsorted_shipments = [
            {"source_region": "Solapur", "dest_region": "Osmanabad", "medicine": "paracetamol", "quantity": 50, "distance_km": 70.0, "cost_index": 1550.0, "priority": "STANDARD", "confidence": 0.85},
            {"source_region": "Ahmednagar", "dest_region": "Nashik", "medicine": "antibiotics", "quantity": 80, "distance_km": 155.0, "cost_index": 2825.0, "priority": "HIGH", "confidence": 0.90},
            {"source_region": "Ahmednagar", "dest_region": "Kolhapur", "medicine": "bandages", "quantity": 100, "distance_km": 310.0, "cost_index": 5150.0, "priority": "STANDARD", "confidence": 0.80}
        ]
        # Store as raw uncanonical JSON to verify server sorts upon retrieval
        transfers_json = json.dumps(unsorted_shipments)
        alloc_id = str(uuid.uuid4())
        alloc = AllocationRecord(
            id=alloc_id,
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash="e" * 64,
            transfers_json=transfers_json,
            status="PENDING_REVIEW"
        )
        db.add(alloc)
        db.commit()

        res = client.get(f"/api/allocations/{alloc_id}", headers=headers)
        assert res.status_code == 200
        shipments = res.json()["shipments"]

        # Expected sort order:
        # 1. ("Ahmednagar", "Kolhapur", "bandages")
        # 2. ("Ahmednagar", "Nashik", "antibiotics")
        # 3. ("Solapur", "Osmanabad", "paracetamol")
        assert shipments[0]["source_region"] == "Ahmednagar" and shipments[0]["dest_region"] == "Kolhapur"
        assert shipments[1]["source_region"] == "Ahmednagar" and shipments[1]["dest_region"] == "Nashik"
        assert shipments[2]["source_region"] == "Solapur" and shipments[2]["dest_region"] == "Osmanabad"
    finally:
        db.close()

def test_missing_allocation_returns_404(client, coordinator_token):
    """Querying a nonexistent allocation ID must return HTTP 404."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    random_id = str(uuid.uuid4())
    res = client.get(f"/api/allocations/{random_id}", headers=headers)
    assert res.status_code == 404
    assert f"Allocation '{random_id}' not found" in res.json()["message"]

def test_historical_unlinked_legacy_allocation_retrieval(client, coordinator_token):
    """Historical UNLINKED_LEGACY allocation can be retrieved without fabricating simulation ID."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    db = api.database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "retrieval_coord@mahadisaster.gov.in").first()
        alloc_id = str(uuid.uuid4())
        alloc = AllocationRecord(
            id=alloc_id,
            simulation_id=None,
            user_id=user.id,
            plan_hash="f" * 64,
            transfers_json="[]",
            status="UNLINKED_LEGACY",
            cost_index=1500.0,
            unmet_demand_after=200.0
        )
        db.add(alloc)
        db.commit()

        res = client.get(f"/api/allocations/{alloc_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["allocation_id"] == alloc_id
        assert data["status"] == "UNLINKED_LEGACY"
        assert data["simulation_id"] is None
        assert data["transfers_count"] == 0
        assert data["shipments"] == []
    finally:
        db.close()

def test_linked_allocation_missing_simulation_returns_404(client, coordinator_token):
    """If an allocation claims to be linked to a simulation that does not exist in DB, retrieval returns 404."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}
    db = api.database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "retrieval_coord@mahadisaster.gov.in").first()
        # Create simulation and allocation, then delete simulation behind the scenes
        sim_id = str(uuid.uuid4())
        sim = SimulationRecord(id=sim_id, user_id=user.id, inputs_json="{}", results_hash="0" * 64)
        alloc_id = str(uuid.uuid4())
        alloc = AllocationRecord(
            id=alloc_id,
            simulation_id=sim_id,
            user_id=user.id,
            plan_hash="0" * 64,
            transfers_json="[]",
            status="PENDING_REVIEW"
        )
        db.add_all([sim, alloc])
        db.commit()

        # Delete simulation directly bypassing FK cascading for test purpose
        db.execute(text("PRAGMA foreign_keys = OFF;"))
        db.execute(text(f"DELETE FROM simulations WHERE id = '{sim_id}'"))
        db.execute(text("PRAGMA foreign_keys = ON;"))
        db.commit()

        res = client.get(f"/api/allocations/{alloc_id}", headers=headers)
        assert res.status_code == 404
        assert f"Referenced simulation '{sim_id}' not found" in res.json()["message"]
    finally:
        db.close()

# -------------------------------------------------------------
# 4. PAGINATION PARAMETERS VALIDATION
# -------------------------------------------------------------
def test_pagination_validation(client, coordinator_token):
    """Pagination parameters must be strictly validated (limit 1-100, offset >= 0)."""
    headers = {"Authorization": f"Bearer {coordinator_token}"}

    # Limit = 0 (below minimum 1) -> 422
    res_zero = client.get("/api/allocations/pending?limit=0", headers=headers)
    assert res_zero.status_code == 422

    # Limit = 101 (above maximum 100) -> 422
    res_excess = client.get("/api/allocations/pending?limit=101", headers=headers)
    assert res_excess.status_code == 422

    # Offset = -1 (negative offset) -> 422
    res_neg = client.get("/api/allocations/pending?offset=-1", headers=headers)
    assert res_neg.status_code == 422

    # Valid pagination parameters -> 200
    res_valid = client.get("/api/allocations/pending?limit=10&offset=0", headers=headers)
    assert res_valid.status_code == 200

# -------------------------------------------------------------
# 5. ROLE-BASED ACCESS CONTROL (RBAC) COMPREHENSIVE VERIFICATION
# -------------------------------------------------------------
def test_rbac_read_access_for_all_authenticated_roles(client, admin_token, coordinator_token, officer_token, viewer_token):
    """Under documented RBAC policy, viewer, officer, coordinator, and admin can read allocations."""
    # 1. Admin
    res_admin = client.get("/api/allocations/pending", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200

    # 2. Coordinator
    res_coord = client.get("/api/allocations/pending", headers={"Authorization": f"Bearer {coordinator_token}"})
    assert res_coord.status_code == 200

    # 3. Officer
    res_officer = client.get("/api/allocations/pending", headers={"Authorization": f"Bearer {officer_token}"})
    assert res_officer.status_code == 200

    # 4. Viewer
    res_viewer = client.get("/api/allocations/pending", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_viewer.status_code == 200

def test_viewer_and_officer_cannot_approve_or_reject(client, officer_token, viewer_token):
    """Verifies existing governance safeguard: viewers and officers are strictly forbidden from submitting decisions."""
    payload = {
        "action": "APPROVE",
        "reason_code": "OPERATIONAL_ACCEPTANCE",
        "plan_hash": "a" * 64,
        "confidence": 0.85
    }

    # Officer -> 403 Forbidden
    res_officer = client.post("/api/audit/decision", json=payload, headers={"Authorization": f"Bearer {officer_token}"})
    assert res_officer.status_code == 403

    # Viewer -> 403 Forbidden
    res_viewer = client.post("/api/audit/decision", json=payload, headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_viewer.status_code == 403
