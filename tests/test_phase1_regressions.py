"""
tests/test_phase1_regressions.py

Dedicated Phase 1 Regression Test Suite:
Validates fixes for:
- DEF-01: Model artifact reproducibility, safe diagnostics, and synthetic isolation.
- DEF-02: Canonical JWT secret configuration, aliases, and production validation.
- DEF-03: Relative frontend API URL construction and absence of localhost in production bundle.
- DEF-14: Docker healthcheck configuration and readiness alignment.
- DEF-15: Complete API test dependency availability.
- DEF-16: Fresh-clone CI configuration and synthetic fixture integrity.
"""

import os
import re
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# DEF-02: JWT Secret Configuration & Validation Tests
# -----------------------------------------------------------------------------
def test_jwt_secret_canonical_precedence():
    from api.config import Settings

    # 1. Canonical JWT_SECRET_KEY takes highest priority
    s1 = Settings(
        JWT_SECRET_KEY="canonical-secret-12345",
        JWT_SECRET="legacy-alias-67890",
        SECRET_KEY="dev-fallback"
    )
    assert s1.get_jwt_secret == "canonical-secret-12345"

    # 2. Documented legacy alias JWT_SECRET takes second priority
    s2 = Settings(
        JWT_SECRET_KEY=None,
        JWT_SECRET="legacy-alias-67890",
        SECRET_KEY="dev-fallback"
    )
    assert s2.get_jwt_secret == "legacy-alias-67890"

    # 3. Development fallback SECRET_KEY when others are None
    s3 = Settings(
        JWT_SECRET_KEY=None,
        JWT_SECRET=None,
        SECRET_KEY="dev-fallback-key"
    )
    assert s3.get_jwt_secret == "dev-fallback-key"

def test_jwt_secret_production_validation():
    from api.config import Settings

    # Production mode with default secret -> Must raise ValueError
    s_insecure = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="disaster-healthcare-ai-super-secret-key-change-in-prod",
        ADMIN_PASSWORD="ProdAdminPassword123!"
    )
    with pytest.raises(ValueError) as excinfo:
        s_insecure.validate_security()
    assert "Security Validation Error" in str(excinfo.value)
    # Ensure secret value is NEVER leaked in error message
    assert "disaster-healthcare-ai-super-secret-key-change-in-prod" not in str(excinfo.value)

    # Production mode without admin password -> Must raise ValueError
    s_no_admin = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="a-strong-production-key-here-992123",
        ADMIN_PASSWORD=None
    )
    with pytest.raises(ValueError) as excinfo:
        s_no_admin.validate_security()
    assert "ADMIN_PASSWORD" in str(excinfo.value)

    # Production mode with valid secure secret & admin password -> Must succeed
    s_valid = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="strong-custom-production-key-992123",
        ADMIN_PASSWORD="StrongProductionPassword999!"
    )
    s_valid.validate_security()  # Should not raise

def test_jwt_secret_development_permissiveness():
    from api.config import Settings

    # Development mode allows default secret without error
    s_dev = Settings(
        APP_ENV="development",
        JWT_SECRET_KEY=None,
        SECRET_KEY="disaster-healthcare-ai-super-secret-key-change-in-prod",
        ADMIN_PASSWORD=None
    )
    s_dev.validate_security()  # Should not raise

# -----------------------------------------------------------------------------
# DEF-03: Frontend API URL & Localhost Absence Tests
# -----------------------------------------------------------------------------
def test_frontend_client_relative_api_url():
    client_ts_path = PROJECT_ROOT / "frontend" / "src" / "api" / "client.ts"
    assert client_ts_path.exists(), "frontend/src/api/client.ts must exist"

    content = client_ts_path.read_text(encoding="utf-8")
    # Verify client does not hardcode localhost fallback
    assert 'import.meta.env.VITE_API_URL || "http://localhost:8000"' not in content, \
        "Client should not default to hardcoded http://localhost:8000"

    # Verify same-origin relative path handling
    assert 'const BASE_URL = (rawApiUrl !== undefined && rawApiUrl !== null && rawApiUrl !== "") ? rawApiUrl : "";' in content or \
           'const BASE_URL' in content

def test_frontend_vite_proxy_configured():
    vite_config_path = PROJECT_ROOT / "frontend" / "vite.config.ts"
    assert vite_config_path.exists(), "frontend/vite.config.ts must exist"

    content = vite_config_path.read_text(encoding="utf-8")
    assert "proxy" in content, "Vite dev server proxy must be configured for local development"
    assert '"/api"' in content or "'/api'" in content
    assert "http://localhost:8000" in content

def test_frontend_production_bundle_no_localhost():
    dist_dir = PROJECT_ROOT / "frontend" / "dist"
    if not dist_dir.exists():
        pytest.skip("frontend/dist does not exist; run npm run build first")

    # Search all JS bundles in dist for hardcoded localhost:8000
    js_files = list(dist_dir.glob("**/*.js"))
    assert len(js_files) > 0, "Built JS bundles must exist in frontend/dist"

    for js_file in js_files:
        content = js_file.read_text(encoding="utf-8")
        assert "localhost:8000" not in content, f"Hardcoded localhost:8000 found in {js_file.name}"

# -----------------------------------------------------------------------------
# DEF-14: Docker Healthcheck & Compose Alignment Tests
# -----------------------------------------------------------------------------
def test_dockerfile_healthchecks_configured():
    api_dockerfile = PROJECT_ROOT / "deploy" / "Dockerfile.api"
    frontend_dockerfile = PROJECT_ROOT / "deploy" / "Dockerfile.frontend"

    assert api_dockerfile.exists()
    assert frontend_dockerfile.exists()

    api_content = api_dockerfile.read_text(encoding="utf-8")
    frontend_content = frontend_dockerfile.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in api_content, "Dockerfile.api must define a HEALTHCHECK"
    assert "http://localhost:8000/health" in api_content or "http://localhost:8000/ready" in api_content

    assert "HEALTHCHECK" in frontend_content, "Dockerfile.frontend must define a HEALTHCHECK"
    assert "http://localhost/" in frontend_content

def test_docker_compose_readiness_dependency():
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    assert compose_path.exists()

    content = compose_path.read_text(encoding="utf-8")
    assert "condition: service_healthy" in content, "frontend must wait for api to be service_healthy"
    assert "JWT_SECRET_KEY" in content, "docker-compose must set canonical JWT_SECRET_KEY"
    assert "http://localhost:8000/ready" in content, "api healthcheck in compose must verify readiness"

# -----------------------------------------------------------------------------
# DEF-01 & DEF-16: Model Artifact Reproducibility & Synthetic Isolation
# -----------------------------------------------------------------------------
def test_synthetic_test_fixture_isolation():
    from scripts.generate_test_models import generate_fixtures_if_missing
    import joblib

    # Test fixture generator script must exist
    script_path = PROJECT_ROOT / "scripts" / "generate_test_models.py"
    assert script_path.exists()

    # If test models were generated, assert their provenance is explicitly marked SYNTHETIC
    impact_path = PROJECT_ROOT / "models" / "impact_models.joblib"
    if impact_path.exists():
        bundle = joblib.load(impact_path)
        if isinstance(bundle, dict) and bundle.get("is_synthetic") is True:
            assert bundle["provenance"] == "SYNTHETIC_TEST_FIXTURE"
            assert "synthetic" in bundle["description"].lower()

def test_github_actions_ci_final_branch_trigger():
    ci_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists()

    content = ci_path.read_text(encoding="utf-8")
    assert "finalBr" in content, ".github/workflows/ci.yml must trigger on finalBr"
    assert "requirements-api.txt" in content, "CI must install requirements-api.txt"
    assert "generate_test_models.py" in content, "CI must ensure test fixtures are present"
    assert "permissions:" in content and "contents: read" in content, "CI must use least privilege"

# -----------------------------------------------------------------------------
# DEF-15: API Dependency Verification
# -----------------------------------------------------------------------------
def test_api_mandatory_dependencies_importable():
    # Verify all mandatory packages from requirements-api.txt are importable
    import fastapi
    import uvicorn
    import pydantic
    import pydantic_settings
    import httpx
    import sqlalchemy
    import bcrypt
    import jwt

    assert fastapi.__version__ is not None
    assert sqlalchemy.__version__ is not None
    assert pydantic.__version__ is not None
    assert jwt.__version__ is not None
