"""
tests/test_phase3a_stability.py
Phase 3A Regression & Verification Suite:
1. GeoJSON District Normalization and Palghar Integration (Task A)
2. FastAPI Event-Loop Protection & Concurrency via Threadpool (Task B)
3. SQLite WAL and 15-second Busy Timeout Verification (Task C)
"""
import pytest
import threading
import json
import time
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from api.main import app
import api.database
from api.database import Base, get_db, configure_sqlite_engine
from api.models import User, UserRole, AuditEvent, SimulationRecord
from api.auth import create_access_token, hash_password
from api.audit_ledger import record_decision, verify_chain
import src.data.boundaries as boundaries

@pytest.fixture(scope="module", autouse=True)
def isolate_stability_test_database(tmp_path_factory):
    """Isolate database for Phase 3A stability tests."""
    tmp_dir = tmp_path_factory.mktemp("stability_db")
    db_file = tmp_dir / "stability_test.db"
    db_url = f"sqlite:///{db_file}"

    test_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "timeout": 15.0},
        echo=False
    )
    configure_sqlite_engine(test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    Base.metadata.create_all(bind=test_engine)

    orig_engine = api.database.engine
    orig_sl = api.database.SessionLocal
    api.database.engine = test_engine
    api.database.SessionLocal = TestingSessionLocal

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield TestingSessionLocal, test_engine

    app.dependency_overrides.clear()
    api.database.engine = orig_engine
    api.database.SessionLocal = orig_sl
    test_engine.dispose()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers():
    db = api.database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "test_admin_phase3a@example.com").first()
        if not user:
            user = User(
                email="test_admin_phase3a@example.com",
                hashed_password=hash_password("adminpass123"),
                role=UserRole.ADMIN.value
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token({"sub": str(user.id), "role": user.role})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()

# =============================================================================
# Task A: GeoJSON District Normalization & Boundary Integration
# =============================================================================

def test_boundaries_normalization_and_palghar_integration():
    """Verify that load_or_create_district_boundaries creates exactly 35 normalized units with Palghar."""
    gdf = boundaries.load_or_create_district_boundaries()
    assert len(gdf) == 35, f"Expected 35 districts, found {len(gdf)}"

    districts = gdf["district"].tolist()
    assert len(districts) == len(set(districts)), "Duplicate district identifiers found in GeoDataFrame"

    # Verify Palghar presence and synthetic bounding geometry provenance
    assert "Palghar" in districts
    palghar_row = gdf[gdf["district"] == "Palghar"].iloc[0]
    assert palghar_row["geometry_provenance"] == "ESTIMATED"
    assert palghar_row["is_synthetic"] is True or palghar_row["is_synthetic"] == 1
    assert "2014 Thane bifurcation" in palghar_row["provenance_note"]

    # Verify Mumbai is unified and not split into Mumbai Suburban
    assert "Mumbai" in districts
    assert "Mumbai Suburban" not in districts

    # Verify 7 normalized spellings
    expected_normalized = ["Ahmednagar", "Beed", "Buldhana", "Gadchiroli", "Gondia", "Raigad"]
    legacy_spellings = ["Ahmadnagar", "Bid", "Buldana", "Garhchiroli", "Gondiya", "Raigarh"]
    for norm in expected_normalized:
        assert norm in districts, f"Expected canonical district '{norm}' not found"
    for leg in legacy_spellings:
        assert leg not in districts, f"Legacy spelling '{leg}' should have been normalized"

def test_api_geo_districts_matches_api_districts(client):
    """Verify that /api/geo/districts matches /api/districts exactly across all 35 operational units."""
    geo_res = client.get("/api/geo/districts")
    assert geo_res.status_code == 200, f"Failed /api/geo/districts: {geo_res.text}"
    geo_json = geo_res.json()
    assert geo_json.get("type") == "FeatureCollection"
    features = geo_json.get("features", [])
    assert len(features) == 35, f"Expected 35 GeoJSON features, got {len(features)}"

    geo_districts = {f["properties"]["district"] for f in features}
    assert len(geo_districts) == 35, "Duplicate district properties found in GeoJSON features"

    dist_res = client.get("/api/districts")
    assert dist_res.status_code == 200, f"Failed /api/districts: {dist_res.text}"
    dist_json = dist_res.json()
    backend_districts = {d["district"] for d in dist_json.get("districts", [])}
    assert len(backend_districts) == 35

    diff_geo_vs_backend = geo_districts - backend_districts
    diff_backend_vs_geo = backend_districts - geo_districts
    assert not diff_geo_vs_backend, f"Districts in GeoJSON but not /api/districts: {diff_geo_vs_backend}"
    assert not diff_backend_vs_geo, f"Districts in /api/districts but not GeoJSON: {diff_backend_vs_geo}"

# =============================================================================
# Task B: FastAPI Event-Loop Protection & Concurrency via Threadpool
# =============================================================================

def test_threadpool_simulation_and_allocation_concurrency(client, auth_headers):
    """Verify that simulate and allocate work cleanly and support concurrent requests via threadpool."""
    sim_payload = {
        "epicentre": "Pune",
        "hazard": "Flood",
        "severity": 1.5,
        "planning_level": "P50",
        "stock_adjustment_pct": 0.0
    }

    # 1. Test single simulate and allocate request
    sim_res = client.post("/api/simulate", json=sim_payload, headers=auth_headers)
    assert sim_res.status_code == 200, f"Simulation failed: {sim_res.text}"
    sim_data = sim_res.json()
    assert "simulation_id" in sim_data
    assert len(sim_data["results"]) > 0

    alloc_payload = {
        "epicentre": "Pune",
        "hazard": "Flood",
        "severity": 1.5,
        "planning_level": "P50",
        "safety_reserve_ratio": 0.60
    }
    alloc_res = client.post("/api/allocate", json=alloc_payload, headers=auth_headers)
    assert alloc_res.status_code == 200, f"Allocation failed: {alloc_res.text}"
    alloc_data = alloc_res.json()
    assert "transfers" in alloc_data
    assert "cost_index" in alloc_data
    assert "solve_status" in alloc_data
    assert "unmet_demand_after" in alloc_data

    # 2. Test concurrent allocations while polling /ready
    def run_allocation():
        return client.post("/api/allocate", json=alloc_payload, headers=auth_headers)

    ready_latencies = []
    def poll_ready():
        for _ in range(5):
            t0 = time.time()
            r = client.get("/ready")
            ready_latencies.append((time.time() - t0) * 1000.0)
            assert r.status_code == 200
            time.sleep(0.01)

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(run_allocation) for _ in range(4)]
        ready_future = executor.submit(poll_ready)

        alloc_results = [f.result() for f in futures]
        ready_future.result()

    for r in alloc_results:
        assert r.status_code == 200

    # Assert readiness probe was responsive (< 200ms)
    assert len(ready_latencies) >= 5
    assert max(ready_latencies) < 200.0, f"Readiness probe exceeded 200ms: {max(ready_latencies)}ms"

def test_threadpool_exception_propagation_and_rbac(client, auth_headers):
    """Verify that threadpool offloaded endpoints correctly propagate 400 errors and enforce RBAC."""
    # 1. Invalid epicentre should raise 400
    bad_payload = {
        "epicentre": "InvalidDistrictXYZ",
        "hazard": "Flood",
        "severity": 1.0
    }
    res = client.post("/api/simulate", json=bad_payload, headers=auth_headers)
    assert res.status_code == 400
    assert "is not a valid Maharashtra district" in res.text

    # 2. Unauthenticated request should raise 401
    res_unauth = client.post("/api/simulate", json={"epicentre": "Pune"})
    assert res_unauth.status_code == 401

# =============================================================================
# Task C: SQLite WAL Mode and Busy Timeout Verification
# =============================================================================

def test_sqlite_pragmas_journal_mode_and_busy_timeout():
    """Verify that SQLite engine connection has WAL mode and 15000ms busy timeout."""
    with api.database.engine.connect() as conn:
        jm = conn.execute(text("PRAGMA journal_mode;")).scalar()
        bt = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        # In file-based SQLite, journal_mode is 'wal'; in in-memory it returns 'memory'
        assert jm.lower() in ("wal", "memory"), f"Expected WAL or memory journal mode, got '{jm}'"
        assert bt == 15000, f"Expected busy_timeout 15000, got '{bt}'"

def test_concurrent_audit_writes_and_ledger_integrity():
    """Verify that concurrent writes to audit ledger do not raise database locked errors and preserve hash chain."""
    db = api.database.SessionLocal()
    user = db.query(User).filter(User.email == "test_admin_phase3a@example.com").first()
    if not user:
        user = User(
            email="test_admin_phase3a@example.com",
            hashed_password=hash_password("adminpass123"),
            role=UserRole.ADMIN.value
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    user_id = user.id

    # Pre-populate SimulationRecords to satisfy SQLite foreign key constraints
    for i in range(12):
        if not db.query(SimulationRecord).filter(SimulationRecord.id == f"sim_{i}").first():
            db.add(SimulationRecord(
                id=f"sim_{i}",
                user_id=user_id,
                inputs_json="{}",
                results_hash="0" * 64
            ))
    db.commit()
    db.close()

    errors = []
    created_events = []

    def perform_write(idx):
        try:
            local_db = api.database.SessionLocal()
            local_user = local_db.query(User).filter(User.id == user_id).first()
            event = record_decision(
                db=local_db,
                user=local_user,
                action="APPROVE",
                reason_code="EMERGENCY_OVERRIDE",
                plan_hash=f"plan_hash_concurrency_{idx}_{int(time.time()*1000)}",
                confidence=0.92,
                simulation_id=f"sim_{idx}"
            )
            created_events.append(event.id)
            local_db.close()
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=perform_write, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent audit writes raised errors: {errors}"
    assert len(created_events) == 12

    # Verify cryptographic hash chain integrity of the ledger
    verify_db = api.database.SessionLocal()
    try:
        is_valid, count, broken_info = verify_chain(verify_db)
        assert is_valid, f"Ledger cryptographic hash chain broken: {broken_info}"
    finally:
        verify_db.close()

def test_transaction_rollback_safety():
    """Verify that failed database transactions cleanly rollback without corrupting the database."""
    db = api.database.SessionLocal()
    initial_count = db.query(AuditEvent).count()
    try:
        # Intentionally create invalid audit event with None required fields
        invalid_event = AuditEvent(
            user_id=None,
            action=None,
            prev_hash="corrupt",
            current_hash=None
        )
        db.add(invalid_event)
        db.commit()
    except Exception:
        db.rollback()

    # Verify rollback succeeded and database remains readable
    final_count = db.query(AuditEvent).count()
    assert final_count == initial_count, "Rollback failed: incomplete transaction was committed"
    db.close()
