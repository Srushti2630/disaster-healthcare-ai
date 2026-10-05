"""Pytest configuration and isolation fixtures for tests_api."""
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from api.config import settings
import api.database
import api.routes_auth
from api.database import Base, get_db
from api.auth import reset_rate_limiters
from api.main import app

@pytest.fixture(autouse=True)
def reset_rate_limiters_fixture():
    """Autouse fixture to reset rate limiters before every single test."""
    reset_rate_limiters()
    yield
    reset_rate_limiters()

@pytest.fixture(scope="module", autouse=True)
def isolate_test_database(tmp_path_factory):
    """
    Module-scoped database isolation fixture:
    Creates a dedicated temporary SQLite DB file for each test module,
    overrides FastAPI get_db dependency and SessionLocal, and cleans up afterwards.
    """
    tmp_dir = tmp_path_factory.mktemp("db")
    db_file = tmp_dir / "isolated_test.db"
    db_url = f"sqlite:///{db_file}"

    test_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    from api import models  # noqa: F401
    Base.metadata.create_all(bind=test_engine)

    # Save original SessionLocal references
    orig_db_sl = api.database.SessionLocal

    # Patch SessionLocal in api.database and tests_api test modules
    api.database.SessionLocal = TestingSessionLocal
    try:
        import tests_api.test_auth_audit
        tests_api.test_auth_audit.SessionLocal = TestingSessionLocal
    except ImportError:
        pass

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield TestingSessionLocal, test_engine

    app.dependency_overrides.clear()
    api.database.SessionLocal = orig_db_sl
    try:
        import tests_api.test_auth_audit
        tests_api.test_auth_audit.SessionLocal = orig_db_sl
    except ImportError:
        pass
    test_engine.dispose()
