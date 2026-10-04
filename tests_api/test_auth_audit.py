"""Comprehensive tests for Authentication, Role Enforcement, and Tamper-Evident Cryptographic Audit Ledger."""
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.database import SessionLocal, init_db, Base, engine
from api.models import User, AuditEvent

@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """Ensure database tables exist and clean up test data before and after test module."""
    init_db()
    db = SessionLocal()
    try:
        db.query(AuditEvent).delete()
        db.query(User).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AuditEvent).delete()
        db.query(User).delete()
        db.commit()
    finally:
        db.close()

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

# -------------------------------------------------------------
# 1. AUTH FLOWS & FIRST-USER ADMIN RULE
# -------------------------------------------------------------
def test_first_user_registration_becomes_admin(client):
    """The very first registered user in the system automatically gets the 'admin' role."""
    res = client.post("/api/auth/register", json={
        "email": "admin@mahadisaster.gov.in",
        "password": "AdminPassword123!",
        "role": "viewer"  # Requesting viewer, but must become admin
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "admin@mahadisaster.gov.in"
    assert data["role"] == "admin"

def test_subsequent_registration_blocked_without_admin_token(client):
    """Subsequent registrations must be blocked if unauthenticated or not admin."""
    res = client.post("/api/auth/register", json={
        "email": "intruder@domain.com",
        "password": "Password123!"
    })
    assert res.status_code == 403
    assert "administrator privileges" in res.json()["message"].lower()

def test_admin_can_register_officer_and_coordinator(client):
    """Admin logs in and successfully creates officer, coordinator, and viewer accounts."""
    # 1. Login as admin
    login_res = client.post("/api/auth/login", json={
        "email": "admin@mahadisaster.gov.in",
        "password": "AdminPassword123!"
    })
    assert login_res.status_code == 200
    admin_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Register Officer
    res_officer = client.post("/api/auth/register", json={
        "email": "officer@mahadisaster.gov.in",
        "password": "OfficerPass123!",
        "role": "officer"
    }, headers=headers)
    assert res_officer.status_code == 201
    assert res_officer.json()["role"] == "officer"

    # 3. Register Coordinator
    res_coord = client.post("/api/auth/register", json={
        "email": "coordinator@mahadisaster.gov.in",
        "password": "CoordPass123!",
        "role": "coordinator"
    }, headers=headers)
    assert res_coord.status_code == 201
    assert res_coord.json()["role"] == "coordinator"

    # 4. Register Viewer
    res_viewer = client.post("/api/auth/register", json={
        "email": "viewer@mahadisaster.gov.in",
        "password": "ViewerPass123!",
        "role": "viewer"
    }, headers=headers)
    assert res_viewer.status_code == 201
    assert res_viewer.json()["role"] == "viewer"

def test_login_invalid_credentials(client):
    """Login with wrong password must return 401 Unauthorized."""
    res = client.post("/api/auth/login", json={
        "email": "admin@mahadisaster.gov.in",
        "password": "WrongPassword!"
    })
    assert res.status_code == 401

# -------------------------------------------------------------
# 2. ROLE-BASED ACCESS CONTROL (RBAC)
# -------------------------------------------------------------
def test_role_enforcement_on_audit_decision(client):
    """Only coordinator and admin can submit decision logs; viewers and officers are forbidden."""
    # 1. Login as Viewer
    res_v = client.post("/api/auth/login", json={
        "email": "viewer@mahadisaster.gov.in",
        "password": "ViewerPass123!"
    })
    v_token = res_v.json()["access_token"]

    # 2. Viewer attempts to record an audit decision -> 403 Forbidden
    payload = {
        "action": "APPROVE",
        "reason_code": "RESOURCE_CRITICALITY_MET",
        "plan_hash": "a" * 64,
        "confidence": 0.85
    }
    res_v_attempt = client.post("/api/audit/decision", json=payload, headers={"Authorization": f"Bearer {v_token}"})
    assert res_v_attempt.status_code == 403

    # 3. Login as Officer
    res_o = client.post("/api/auth/login", json={
        "email": "officer@mahadisaster.gov.in",
        "password": "OfficerPass123!"
    })
    o_token = res_o.json()["access_token"]

    # 4. Officer attempts to record decision -> 403 Forbidden
    res_o_attempt = client.post("/api/audit/decision", json=payload, headers={"Authorization": f"Bearer {o_token}"})
    assert res_o_attempt.status_code == 403

# -------------------------------------------------------------
# 3. CONFIDENCE THRESHOLD GOVERNANCE (HTTP 409)
# -------------------------------------------------------------
def test_low_confidence_approval_blocked_with_409(client):
    """Plan approval with confidence < 0.60 must be blocked with HTTP 409 Conflict."""
    res_c = client.post("/api/auth/login", json={
        "email": "coordinator@mahadisaster.gov.in",
        "password": "CoordPass123!"
    })
    c_token = res_c.json()["access_token"]
    headers = {"Authorization": f"Bearer {c_token}"}

    # Low confidence approval attempt (0.42 < 0.60 threshold)
    low_conf_payload = {
        "action": "APPROVE",
        "reason_code": "URGENT_TRIAGE",
        "plan_hash": "b" * 64,
        "confidence": 0.42
    }
    res = client.post("/api/audit/decision", json=low_conf_payload, headers=headers)
    assert res.status_code == 409
    assert "safety threshold" in res.json()["message"].lower()

def test_rejection_of_low_confidence_plan_allowed(client):
    """Rejecting a plan with low confidence is valid governance and must succeed."""
    res_c = client.post("/api/auth/login", json={
        "email": "coordinator@mahadisaster.gov.in",
        "password": "CoordPass123!"
    })
    headers = {"Authorization": f"Bearer {res_c.json()['access_token']}"}

    reject_payload = {
        "action": "REJECT",
        "reason_code": "CONFIDENCE_BELOW_THRESHOLD",
        "plan_hash": "b" * 64,
        "confidence": 0.42
    }
    res = client.post("/api/audit/decision", json=reject_payload, headers=headers)
    assert res.status_code == 201
    assert res.json()["action"] == "REJECT"

# -------------------------------------------------------------
# 4. CRYPTOGRAPHIC HASH CHAIN & INTEGRITY VERIFICATION
# -------------------------------------------------------------
def test_audit_hash_chain_creation_and_verification(client):
    """Successive decisions form a verifiable SHA-256 hash chain linking to previous blocks."""
    res_c = client.post("/api/auth/login", json={
        "email": "coordinator@mahadisaster.gov.in",
        "password": "CoordPass123!"
    })
    headers = {"Authorization": f"Bearer {res_c.json()['access_token']}"}

    # Add 3 valid decision events
    for idx in range(3):
        res = client.post("/api/audit/decision", json={
            "action": "APPROVE",
            "reason_code": f"OPERATION_PHASE_{idx+1}",
            "plan_hash": f"plan_hash_{idx}_{'f' * 50}",
            "confidence": 0.75 + (idx * 0.05)
        }, headers=headers)
        assert res.status_code == 201

    # Verify audit chain integrity
    verify_res = client.get("/api/audit/verify", headers=headers)
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["is_valid"] is True
    assert v_data["total_blocks_verified"] >= 4  # 1 reject + 3 approves
    assert v_data["broken_block"] is None

def test_tamper_detection_flags_modified_record(client):
    """Mutating a record in the database directly breaks the cryptographic chain and is detected."""
    res_c = client.post("/api/auth/login", json={
        "email": "coordinator@mahadisaster.gov.in",
        "password": "CoordPass123!"
    })
    headers = {"Authorization": f"Bearer {res_c.json()['access_token']}"}

    # Deliberately tamper with the second audit event in the database
    db = SessionLocal()
    try:
        events = db.query(AuditEvent).order_by(AuditEvent.id.asc()).all()
        assert len(events) >= 2
        tampered_event = events[1]
        # Modify the action directly in SQL behind the back of the application
        tampered_event.action = "TAMPERED_ACTION"
        db.commit()
    finally:
        db.close()

    # Run verification - MUST detect tampering
    verify_res = client.get("/api/audit/verify", headers=headers)
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["is_valid"] is False
    assert v_data["broken_block"] is not None
    assert v_data["broken_block"]["row_index"] == 2
    assert v_data["broken_block"]["error_type"] in ["BLOCK_TAMPERING_DETECTED", "PREV_HASH_MISMATCH"]
