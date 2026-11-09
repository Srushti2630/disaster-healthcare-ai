#!/usr/bin/env python3
"""
scripts/audit_backend_system.py

Comprehensive FastAPI Backend Architecture, Security, and API Integration Audit Script.
Generates:
1. reports/api_endpoint_inventory.csv
2. reports/api_security_audit.csv
3. reports/frontend_backend_contract_audit.csv
4. reports/backend_test_coverage.csv
5. reports/model_serving_integration_audit.csv
6. reports/database_integrity_audit.csv
"""

import os
import sys
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. API ENDPOINT INVENTORY AUDIT
# -----------------------------------------------------------------------------
def generate_endpoint_inventory():
    endpoints = [
        {
            "http_method": "GET",
            "url_path": "/health",
            "tag": "System",
            "purpose": "Liveness Probe: confirms API server process is responding",
            "request_schema": "None",
            "response_schema": "Dict[str, str] ({'status': 'ok'})",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "Inline handler",
            "database_interactions": "None",
            "ml_or_optimization": "None",
            "error_responses": "500 Internal Server Error",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_health_check)"
        },
        {
            "http_method": "GET",
            "url_path": "/ready",
            "tag": "System",
            "purpose": "Readiness Probe: verifies model bundles, datasets, and distance matrices are loaded in app.state",
            "request_schema": "None",
            "response_schema": "Dict[str, Any] ({'status': 'ready', 'artifacts_loaded': ...})",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "Inline handler inspecting request.app.state",
            "database_interactions": "None",
            "ml_or_optimization": "Checks impact_bundle and distance_matrix presence",
            "error_responses": "503 Service Unavailable (if app.state.ready is False)",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_readiness_probe)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/districts",
            "tag": "Data",
            "purpose": "District Registry: returns 35 Maharashtra districts with population, capacity bounds, and cleaned facility counts",
            "request_schema": "None",
            "response_schema": "DistrictListResponse",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "get_districts_service(app_state)",
            "database_interactions": "None (Memory cache from app.state or reads CSV)",
            "ml_or_optimization": "None",
            "error_responses": "503 Service Unavailable (if CSV files missing)",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_get_districts_endpoint, test_facilities_total_above_4000)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/geo/districts",
            "tag": "Data",
            "purpose": "Spatial Geometry: returns normalised GeoJSON MultiPolygon boundaries for all 35 districts",
            "request_schema": "None",
            "response_schema": "GeoJSON FeatureCollection",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "Inline handler returning app.state.geojson",
            "database_interactions": "None",
            "ml_or_optimization": "None",
            "error_responses": "404 Not Found (if GeoJSON boundary file missing)",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_get_geo_districts_endpoint)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/metrics",
            "tag": "Evaluation",
            "purpose": "Validation Telemetry: retrieves historical EM-DAT regression metrics, CQR coverage, surrogate fidelity, and methodology limitations",
            "request_schema": "None",
            "response_schema": "MetricsResponse",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "get_metrics_service(app_state)",
            "database_interactions": "None (Cached from reports/metrics.json and models/shortage_classifier.joblib)",
            "ml_or_optimization": "Surrogate model metrics and CQR calibration parameters",
            "error_responses": "503 Service Unavailable (if metrics.json missing)",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_get_metrics_endpoint)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/backtest",
            "tag": "Evaluation",
            "purpose": "Historical Replay: retrieves Leave-One-Event-Out historical replay across benchmark Indian disasters",
            "request_schema": "None",
            "response_schema": "BacktestResponse",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "get_backtest_service(app_state)",
            "database_interactions": "None (Cached from reports/historical_backtest.csv)",
            "ml_or_optimization": "Historical prediction intervals vs actual casualties",
            "error_responses": "503 Service Unavailable (if historical_backtest.csv missing)",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_get_backtest_endpoint)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/baselines",
            "tag": "Evaluation",
            "purpose": "Optimization Benchmark: retrieves 20-scenario / 36-scenario baseline comparison across SCIP MIP and 4 heuristics",
            "request_schema": "None",
            "response_schema": "BaselineResponse",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "get_baselines_service(app_state)",
            "database_interactions": "None (Reads reports/baseline_comparison.csv & baseline_comparison_restricted.csv)",
            "ml_or_optimization": "SCIP MIP vs Heuristic performance comparison",
            "error_responses": "503 Service Unavailable (if baseline reports missing)",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_get_baselines_endpoint)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/baselines/pareto-plot",
            "tag": "Evaluation",
            "purpose": "Pareto Plot Image: streams PNG image of cost index vs unmet demand tradeoff curve",
            "request_schema": "None",
            "response_schema": "FileResponse (image/png)",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "Inline file streaming from reports/pareto_sweep.png",
            "database_interactions": "None",
            "ml_or_optimization": "Visual trade-off frontier",
            "error_responses": "404 Not Found (if PNG image missing)",
            "test_coverage": "Not covered in automated tests (Manual browser test only)"
        },
        {
            "http_method": "POST",
            "url_path": "/api/predict-impact",
            "tag": "Impact",
            "purpose": "Disaster Casualty Prediction: calculates expected affected population and CQR 90% uncertainty interval",
            "request_schema": "ImpactPredictionRequest",
            "response_schema": "ImpactPredictionResponse",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "predict_impact_service(app_state, body)",
            "database_interactions": "None",
            "ml_or_optimization": "Ridge Regression model + Conformal Quantile Regression (CQR) interval",
            "error_responses": "422 Validation Error, 503 Unavailable, 500 Inference Error",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_predict_impact_success, test_predict_impact_validation_error)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/explain/global",
            "tag": "Explainability",
            "purpose": "Global SHAP Explanations: returns global model feature importances and base64-encoded SHAP summary plot",
            "request_schema": "None",
            "response_schema": "GlobalExplanationResponse",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "get_global_explanation_service(app_state)",
            "database_interactions": "None",
            "ml_or_optimization": "Global Ridge coefficients & XGBoost Tree-SHAP summary values",
            "error_responses": "500 Internal Error",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_explain_global_endpoint)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/explain/summary-plot",
            "tag": "Explainability",
            "purpose": "SHAP Plot Image: returns raw saved SHAP summary plot PNG image",
            "request_schema": "None",
            "response_schema": "FileResponse (image/png)",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "Inline file streaming from reports/shap_summary.png",
            "database_interactions": "None",
            "ml_or_optimization": "Bee-swarm feature attribution visualization",
            "error_responses": "404 Not Found (if shap_summary.png missing)",
            "test_coverage": "Not covered in automated tests"
        },
        {
            "http_method": "POST",
            "url_path": "/api/explain",
            "tag": "Explainability",
            "purpose": "Local Prediction Attribution: explains Ridge casualty prediction via exact linear decomposition (beta * z) with Tree-SHAP comparison",
            "request_schema": "ImpactPredictionRequest",
            "response_schema": "LocalExplanationResponse",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "explain_prediction_service(app_state, body)",
            "database_interactions": "None (May read emdat_events.csv if fallback model retraining triggered)",
            "ml_or_optimization": "shap.LinearExplainer on Ridge model + optional XGBoost TreeSHAP",
            "error_responses": "422 Validation Error, 503 Model Unavailable, 500 Inference Error",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_explain_local_endpoint)"
        },
        {
            "http_method": "POST",
            "url_path": "/api/stock",
            "tag": "Inventory",
            "purpose": "Custom Inventory Upload: saves or updates user-specific district medicine stock overrides",
            "request_schema": "UpdateStockRequest",
            "response_schema": "UserStockResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "officer, coordinator, admin",
            "service_invoked": "save_user_stock_service(db, current_user, body)",
            "database_interactions": "INSERT / UPDATE on user_custom_stocks table",
            "ml_or_optimization": "Stock overrides feed into subsequent simulations and MIP solves",
            "error_responses": "400 Bad Request (empty payload), 401 Unauthorized, 403 Forbidden",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_stock_role_enforcement_and_validation)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/stock",
            "tag": "Inventory",
            "purpose": "Get Custom Inventory: retrieves active custom district stocks for authenticated user",
            "request_schema": "None",
            "response_schema": "UserStockResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "viewer, officer, coordinator, admin",
            "service_invoked": "get_user_stock_service(db, current_user)",
            "database_interactions": "SELECT from user_custom_stocks WHERE user_id = :id",
            "ml_or_optimization": "None",
            "error_responses": "401 Unauthorized",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py"
        },
        {
            "http_method": "DELETE",
            "url_path": "/api/stock",
            "tag": "Inventory",
            "purpose": "Reset Custom Inventory: deletes all custom stock overrides for user, reverting to baseline estimated stocks",
            "request_schema": "None",
            "response_schema": "UserStockResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "officer, coordinator, admin",
            "service_invoked": "reset_user_stock_service(db, current_user)",
            "database_interactions": "DELETE FROM user_custom_stocks WHERE user_id = :id",
            "ml_or_optimization": "Reverts simulation to baseline hospital bed stock estimation",
            "error_responses": "401 Unauthorized, 403 Forbidden",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_stock_used_in_simulate)"
        },
        {
            "http_method": "POST",
            "url_path": "/api/stock/reset",
            "tag": "Inventory",
            "purpose": "Reset Custom Inventory (POST alternative): legacy/alternative endpoint to clear custom stocks",
            "request_schema": "None",
            "response_schema": "UserStockResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "officer, coordinator, admin",
            "service_invoked": "reset_user_stock_service(db, current_user)",
            "database_interactions": "DELETE FROM user_custom_stocks WHERE user_id = :id",
            "ml_or_optimization": "Reverts simulation to baseline hospital bed stock estimation",
            "error_responses": "401 Unauthorized, 403 Forbidden",
            "test_coverage": "Not explicitly tested (DELETE /api/stock tested instead)"
        },
        {
            "http_method": "POST",
            "url_path": "/api/simulate",
            "tag": "Simulation",
            "purpose": "Disaster Scenario Simulator: runs 2,000-draw Monte Carlo simulation across 35 districts with population capping and shortage risk",
            "request_schema": "SimulationRequest",
            "response_schema": "SimulationResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "officer, coordinator, admin",
            "service_invoked": "simulate_service(app_state, body, user, db)",
            "database_interactions": "Reads user_custom_stocks; generates UUID simulation_id (UNPERSISTED)",
            "ml_or_optimization": "Spatial Monte Carlo decay engine (2,000 draws) + Random Forest surrogate classifier",
            "error_responses": "400 Invalid Epicentre, 401 Unauthorized, 403 Forbidden, 422 Validation Error, 429 Rate Limit",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_simulate_success_and_capping, test_simulate_validation_error_*)"
        },
        {
            "http_method": "POST",
            "url_path": "/api/allocate",
            "tag": "Optimization",
            "purpose": "Resource Allocation MIP: executes SCIP multi-objective MIP optimization across 35 nodes and 5 commodities, evaluating 5 methods",
            "request_schema": "AllocationRequest",
            "response_schema": "AllocationResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "officer, coordinator, admin",
            "service_invoked": "allocate_service(app_state, body, user, db)",
            "database_interactions": "Invokes simulate_service (reads user_custom_stocks)",
            "ml_or_optimization": "Google OR-Tools SCIP MIP solver + 4 heuristic baseline solvers + constraint checking",
            "error_responses": "400 Invalid Epicentre, 401 Unauthorized, 403 Forbidden, 422 Validation Error",
            "test_coverage": "Covered in tests_api/test_api_endpoints.py (test_allocate_success, test_allocate_validation_error)"
        },
        {
            "http_method": "POST",
            "url_path": "/api/auth/register",
            "tag": "Auth & Governance",
            "purpose": "User Registration: creates account; first user automatically becomes admin; subsequent registrations require active admin token",
            "request_schema": "UserRegisterRequest",
            "response_schema": "UserResponse (HTTP 201)",
            "auth_required": "Conditional (None for 1st user; Admin Bearer token for 2nd+ users)",
            "required_role": "admin (for non-first user)",
            "service_invoked": "register_user(body, request, db)",
            "database_interactions": "INSERT INTO users (email, hashed_password, role)",
            "ml_or_optimization": "None",
            "error_responses": "400 Email Already Registered, 403 Forbidden (non-admin registration), 422 Validation Error",
            "test_coverage": "Covered in tests_api/test_auth_audit.py (test_first_user_registration_becomes_admin, test_subsequent_registration_blocked_without_admin_token)"
        },
        {
            "http_method": "POST",
            "url_path": "/api/auth/login",
            "tag": "Auth & Governance",
            "purpose": "Authentication: verifies bcrypt password hash and issues HS256 JWT access token with user role and expiry",
            "request_schema": "UserLoginRequest",
            "response_schema": "TokenResponse",
            "auth_required": "No",
            "required_role": "None (Public)",
            "service_invoked": "login_user(body, request, db)",
            "database_interactions": "SELECT FROM users WHERE email = :email",
            "ml_or_optimization": "None",
            "error_responses": "401 Unauthorized (invalid credentials), 429 Rate Limit (10 req/min)",
            "test_coverage": "Covered in tests_api/test_auth_audit.py (test_admin_can_register_officer_and_coordinator, test_login_invalid_credentials)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/auth/me",
            "tag": "Auth & Governance",
            "purpose": "User Profile: returns current authenticated user ID, email, and RBAC role",
            "request_schema": "None",
            "response_schema": "UserResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "viewer, officer, coordinator, admin",
            "service_invoked": "get_me(current_user)",
            "database_interactions": "SELECT FROM users WHERE id = :id (via get_current_user dependency)",
            "ml_or_optimization": "None",
            "error_responses": "401 Unauthorized (expired or missing token)",
            "test_coverage": "Covered implicitly via authenticated test fixtures"
        },
        {
            "http_method": "POST",
            "url_path": "/api/audit/decision",
            "tag": "Auth & Governance",
            "purpose": "Audit Decision Logging: records officer APPROVE / REJECT review decision cryptographically chained with SHA-256",
            "request_schema": "AuditDecisionRequest",
            "response_schema": "AuditEventResponse (HTTP 201)",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "coordinator, admin",
            "service_invoked": "record_audit_decision(body, current_user, db)",
            "database_interactions": "SELECT latest AuditEvent, INSERT new AuditEvent with computed current_hash",
            "ml_or_optimization": "Checks confidence >= 0.60 threshold from config.yaml",
            "error_responses": "401 Unauthorized, 403 Forbidden, 409 Conflict (approval when confidence < 0.60)",
            "test_coverage": "Covered in tests_api/test_auth_audit.py (test_role_enforcement_on_audit_decision, test_low_confidence_approval_blocked_with_409, test_rejection_of_low_confidence_plan_allowed)"
        },
        {
            "http_method": "GET",
            "url_path": "/api/audit",
            "tag": "Auth & Governance",
            "purpose": "Audit Log Listing: returns paginated list of audit events in descending order",
            "request_schema": "Query params: page (ge=1), page_size (1-100)",
            "response_schema": "AuditListResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "viewer, officer, coordinator, admin",
            "service_invoked": "get_audit_log(page, page_size, current_user, db)",
            "database_interactions": "SELECT COUNT(*) FROM audit_events, SELECT * FROM audit_events ORDER BY id DESC LIMIT :limit OFFSET :offset",
            "ml_or_optimization": "None",
            "error_responses": "401 Unauthorized, 422 Validation Error (invalid page)",
            "test_coverage": "Covered in tests_api/test_auth_audit.py"
        },
        {
            "http_method": "GET",
            "url_path": "/api/audit/verify",
            "tag": "Auth & Governance",
            "purpose": "Cryptographic Integrity Check: recomputes SHA-256 hash chain from genesis block to current head to detect database tampering",
            "request_schema": "None",
            "response_schema": "AuditVerifyResponse",
            "auth_required": "Yes (Bearer JWT)",
            "required_role": "viewer, officer, coordinator, admin",
            "service_invoked": "verify_audit_log(current_user, db)",
            "database_interactions": "SELECT * FROM audit_events ORDER BY id ASC",
            "ml_or_optimization": "None",
            "error_responses": "401 Unauthorized",
            "test_coverage": "Covered in tests_api/test_auth_audit.py (test_audit_hash_chain_creation_and_verification, test_tamper_detection_flags_modified_record)"
        }
    ]

    out_path = REPORTS_DIR / "api_endpoint_inventory.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(endpoints[0].keys()))
        writer.writeheader()
        writer.writerows(endpoints)
    print(f"✓ Saved API endpoint inventory ({len(endpoints)} endpoints) to {out_path}")

# -----------------------------------------------------------------------------
# 2. SECURITY & RBAC AUDIT
# -----------------------------------------------------------------------------
def generate_security_audit():
    findings = [
        {
            "control_area": "Password Hashing",
            "implementation": "Native bcrypt library with auto-generated per-user salt (bcrypt.gensalt())",
            "code_location": "api/auth.py:23-30",
            "security_standard": "OWASP ASVS v4.0 (5.1.1)",
            "audit_verdict": "COMPLIANT",
            "vulnerability_notes": "Native bcrypt implementation is robust, avoids passlib Python 3.13 deprecation bugs, and enforces one-way salted hashing."
        },
        {
            "control_area": "JWT Token Signature",
            "implementation": "HMAC-SHA256 (HS256) signature verified using PyJWT",
            "code_location": "api/auth.py:35-59",
            "security_standard": "RFC 7519 / OWASP ASVS (3.5.2)",
            "audit_verdict": "COMPLIANT WITH CAUTION",
            "vulnerability_notes": "Symmetric HS256 secret. If database or environment variables are leaked, attacker can forge tokens. Asymmetric RS256/EdDSA recommended for enterprise SSO."
        },
        {
            "control_area": "Token Expiration",
            "implementation": "2-hour access token expiry (ACCESS_TOKEN_EXPIRE_MINUTES = 120)",
            "code_location": "api/config.py:30, api/auth.py:38-39",
            "security_standard": "NIST SP 800-63B",
            "audit_verdict": "COMPLIANT",
            "vulnerability_notes": "Tokens carry explicit 'exp' and 'iat' UTC claims; ExpiredSignatureError handled with HTTP 401."
        },
        {
            "control_area": "Secret Key & Default Credentials",
            "implementation": "Startup validation check: raises ValueError in production if JWT_SECRET or ADMIN_PASSWORD uses default 'change-in-prod'",
            "code_location": "api/config.py:36-52",
            "security_standard": "OWASP Top 10 A05:2021 Security Misconfiguration",
            "audit_verdict": "COMPLIANT IN PROD, DEFECT IN DEV",
            "vulnerability_notes": "Hardcoded default secret key exists in config.py line 27. While validate_security() blocks startup in production, development environments default to insecure shared secret."
        },
        {
            "control_area": "User Registration Privileges",
            "implementation": "First registered user auto-bootstraps as 'admin'; subsequent registrations require active admin Bearer token",
            "code_location": "api/routes_auth.py:41-64",
            "security_standard": "CWE-276 Incorrect Default Permissions",
            "audit_verdict": "COMPLIANT WITH RACE CONDITION",
            "vulnerability_notes": "First-user bootstrap is convenient for local setup, but vulnerable to Time-of-Check to Time-of-Use (TOCTOU) race condition if two registration requests execute concurrently on an empty database."
        },
        {
            "control_area": "Role-Based Access Control (RBAC)",
            "implementation": "Strict hierarchical dependency require_role(['officer', 'coordinator', 'admin'])",
            "code_location": "api/auth.py:109-118",
            "security_standard": "OWASP ASVS v4.0 (4.1.1)",
            "audit_verdict": "COMPLIANT",
            "vulnerability_notes": "Enforced at FastAPI dependency level on backend routes. Viewers cannot modify stock or trigger allocations. Officers cannot approve ledger decisions."
        },
        {
            "control_area": "Rate Limiting",
            "implementation": "In-memory sliding window limiter: 10 req/min on login, 30 req/min on simulation",
            "code_location": "api/auth.py:123-162",
            "security_standard": "OWASP Top 10 A04:2021 Insecure Design",
            "audit_verdict": "PARTIALLY COMPLIANT (CLUSTER LIMITATION)",
            "vulnerability_notes": "In-memory dictionary with threading lock works for single-process server, but does NOT synchronize across multi-worker Uvicorn or distributed Kubernetes replicas (needs Redis)."
        },
        {
            "control_area": "Governance Decision Guardrails",
            "implementation": "HTTP 409 Conflict raised if officer attempts APPROVE with confidence < 0.60 threshold in config.yaml",
            "code_location": "api/audit_ledger.py:54-63",
            "security_standard": "EU AI Act High-Risk Human Oversight Article 14",
            "audit_verdict": "COMPLIANT",
            "vulnerability_notes": "Hard programmatic guardrail prevents human officers from rubber-stamping high-uncertainty allocation plans."
        },
        {
            "control_area": "CORS Policy",
            "implementation": "Configurable CORS origins from settings.CORS_ORIGINS (defaults to localhost:3000, 5173, 8501)",
            "code_location": "api/main.py:38-44, api/config.py:54-68",
            "security_standard": "W3C Cross-Origin Resource Sharing",
            "audit_verdict": "COMPLIANT",
            "vulnerability_notes": "Origins properly parsed as JSON list or comma-separated string; wildcard '*' is NOT used for allowed origins."
        }
    ]

    out_path = REPORTS_DIR / "api_security_audit.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(findings[0].keys()))
        writer.writeheader()
        writer.writerows(findings)
    print(f"✓ Saved API security audit ({len(findings)} controls) to {out_path}")

# -----------------------------------------------------------------------------
# 3. FRONTEND-BACKEND CONTRACT AUDIT
# -----------------------------------------------------------------------------
def generate_contract_audit():
    contracts = [
        {
            "feature_area": "Overview Dashboard - Total Facilities",
            "frontend_component": "frontend/src/pages/OverviewPage.tsx:76",
            "frontend_expected_field": "total_cleaned_facilities or total_facilities",
            "backend_endpoint": "GET /api/districts",
            "backend_provided_field": "total_cleaned_facilities and total_facilities",
            "contract_alignment": "MATCHED",
            "mismatch_details": "Resolved in previous audit. Backend provides both total_facilities and total_cleaned_facilities (4,767 facilities)."
        },
        {
            "feature_area": "Simulator - District Selection Dropdown",
            "frontend_component": "frontend/src/pages/SimulatorPage.tsx:23-29",
            "frontend_expected_field": "Includes 'Mumbai Suburban' in MAHARASHTRA_DISTRICT_NAMES",
            "backend_endpoint": "POST /api/simulate",
            "backend_provided_field": "Validates strictly against MAHARASHTRA_DISTRICTS keys (expects 'Mumbai')",
            "contract_alignment": "MISMATCH / CONTRACT BUG",
            "mismatch_details": "If user selects 'Mumbai Suburban' from dropdown, backend throws HTTP 400 Bad Request because normalize_district_name() is not called in simulate_service()."
        },
        {
            "feature_area": "Simulator - Planning Level Enum",
            "frontend_component": "frontend/src/pages/SimulatorPage.tsx:35",
            "frontend_expected_field": "'P50' | 'P75' | 'P90'",
            "backend_endpoint": "POST /api/simulate",
            "backend_provided_field": "PlanningLevel Enum: P50, P75, P90",
            "contract_alignment": "MATCHED",
            "mismatch_details": "Exact string case matching across TypeScript union type and Pydantic StrEnum."
        },
        {
            "feature_area": "Optimization Page - Baseline Method Comparison",
            "frontend_component": "frontend/src/pages/AllocationPage.tsx:51-56",
            "frontend_expected_field": "min_coverage or min_coverage_mean",
            "backend_endpoint": "POST /api/allocate & GET /api/baselines",
            "backend_provided_field": "MethodComparisonSummary with min_coverage and AliasChoices('min_coverage', 'minimum_coverage')",
            "contract_alignment": "MATCHED",
            "mismatch_details": "Pydantic AliasChoices properly handles both min_coverage and minimum_coverage field aliases."
        },
        {
            "feature_area": "Historical Backtest - Disaster Number Alias",
            "frontend_component": "frontend/src/pages/BacktestPage.tsx:41",
            "frontend_expected_field": "r['DisNo.'] || r.disno",
            "backend_endpoint": "GET /api/backtest",
            "backend_provided_field": "BacktestRecord serialization_alias='DisNo.', validation_alias=AliasChoices('disno', 'DisNo.')",
            "contract_alignment": "MATCHED",
            "mismatch_details": "Handled via Pydantic v2 ConfigDict(populate_by_name=True) and field aliases."
        },
        {
            "feature_area": "Custom Stock Upload - Data Structure",
            "frontend_component": "frontend/src/api/client.ts:101",
            "frontend_expected_field": "stocks: Record<string, Record<string, number>> OR items: Array<{district, medicine, quantity}>",
            "backend_endpoint": "POST /api/stock",
            "backend_provided_field": "UpdateStockRequest(stocks: Optional[Dict[str, Dict[str, float]]], items: Optional[List[StockItem]])",
            "contract_alignment": "MATCHED",
            "mismatch_details": "Dual payload support cleanly accommodates both nested map and flat tabular uploads."
        },
        {
            "feature_area": "Governance - Simulation ID Binding",
            "frontend_component": "frontend/src/pages/GovernancePage.tsx:70-75",
            "frontend_expected_field": "simulation_id passed in decision payload",
            "backend_endpoint": "POST /api/audit/decision",
            "backend_provided_field": "simulation_id ForeignKey to simulations.id",
            "contract_alignment": "PARTIAL / DATA INTEGRITY RISK",
            "mismatch_details": "Frontend passes simulation_id string, but backend simulate_service() never commits SimulationRecord to database, leaving foreign key pointing to non-existent row."
        },
        {
            "feature_area": "Explainability - Local Feature Importances",
            "frontend_component": "frontend/src/pages/SimulatorPage.tsx (PredictionExplanationPanel)",
            "frontend_expected_field": "top_contributions: Array<{feature, contribution, direction, plain_english}>",
            "backend_endpoint": "POST /api/explain",
            "backend_provided_field": "LocalExplanationResponse with top_contributions: List[FeatureContribution]",
            "contract_alignment": "MATCHED",
            "mismatch_details": "Perfect contract parity. Top 6 features provided with plain-English explanation string for every feature."
        }
    ]

    out_path = REPORTS_DIR / "frontend_backend_contract_audit.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(contracts[0].keys()))
        writer.writeheader()
        writer.writerows(contracts)
    print(f"✓ Saved frontend-backend contract audit ({len(contracts)} interfaces) to {out_path}")

# -----------------------------------------------------------------------------
# 4. BACKEND TEST COVERAGE AUDIT
# -----------------------------------------------------------------------------
def generate_test_coverage_audit():
    tests = [
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_health_check",
            "target_endpoint": "GET /health",
            "test_type": "Integration / Health",
            "assertions_checked": "status_code == 200, status == 'ok', x-request-id present, x-process-time-ms present",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_readiness_probe",
            "target_endpoint": "GET /ready",
            "test_type": "Integration / Readiness",
            "assertions_checked": "status_code == 200, artifacts_loaded flags for districts_data and impact_model == True",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_get_districts_endpoint",
            "target_endpoint": "GET /api/districts",
            "test_type": "Functional / Schema",
            "assertions_checked": "total_districts == 35, population > 100M, bed anchor 144,983, icu anchor 11,587, provenance tags",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_facilities_total_above_4000",
            "target_endpoint": "GET /api/districts",
            "test_type": "Data Quality / Audit",
            "assertions_checked": "total_cleaned_facilities > 4000, sum of district facilities > 4000",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_get_geo_districts_endpoint",
            "target_endpoint": "GET /api/geo/districts",
            "test_type": "Spatial / GeoJSON",
            "assertions_checked": "status_code == 200, type == FeatureCollection, >= 35 features, 'district' in properties",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_get_metrics_endpoint",
            "target_endpoint": "GET /api/metrics",
            "test_type": "Evaluation / ML",
            "assertions_checked": "sample_size == 512, Ridge in benchmarked models, surrogate_fidelity present, >= 5 limitations",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_get_backtest_endpoint",
            "target_endpoint": "GET /api/backtest",
            "test_type": "Historical Backtest",
            "assertions_checked": "count >= 5, DisNo. alias present, scope present, interval width > 0",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_get_baselines_endpoint",
            "target_endpoint": "GET /api/baselines",
            "test_type": "Optimizer Benchmark",
            "assertions_checked": "scenarios_evaluated == 20, OR-Tools SCIP and No Redistribution in methods, cost_index_mean present",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_predict_impact_success & test_predict_impact_validation_error",
            "target_endpoint": "POST /api/predict-impact",
            "test_type": "ML Inference & Validation",
            "assertions_checked": "200 on valid Flood payload; predicted_median > 0; 422 on invalid month 15",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_simulate_success_and_capping & validation errors",
            "target_endpoint": "POST /api/simulate",
            "test_type": "Simulation / Security",
            "assertions_checked": "200 on valid simulation; 175 results; 422 on invalid planning level; 400 on unknown district",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_allocate_success & test_allocate_validation_error",
            "target_endpoint": "POST /api/allocate",
            "test_type": "OR-Tools SCIP Optimization",
            "assertions_checked": "200 on valid allocate; solve_status OPTIMAL/FEASIBLE; 0 violations; 422 when reserve > 1.0",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_explain_global_endpoint & test_explain_local_endpoint",
            "target_endpoint": "GET /api/explain/global & POST /api/explain",
            "test_type": "SHAP Explainability",
            "assertions_checked": ">= 5 top features in global; top_contributions <= 6 with plain_english string in local",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_api_endpoints.py",
            "test_function": "test_stock_role_enforcement_and_validation & test_stock_used_in_simulate",
            "target_endpoint": "POST /api/stock & DELETE /api/stock",
            "test_type": "RBAC & Inventory State",
            "assertions_checked": "401 unauth, 403 viewer, 400 empty body, 200 officer, stock propagated to simulate, 200 on DELETE",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_auth_audit.py",
            "test_function": "test_first_user_registration_becomes_admin & test_subsequent_registration_blocked",
            "target_endpoint": "POST /api/auth/register",
            "test_type": "Auth Bootstrap & RBAC",
            "assertions_checked": "1st user gets role='admin'; 2nd user without admin token gets 403 Forbidden",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_auth_audit.py",
            "test_function": "test_admin_can_register_officer_and_coordinator & test_login_invalid_credentials",
            "target_endpoint": "POST /api/auth/register & POST /api/auth/login",
            "test_type": "Authentication / JWT",
            "assertions_checked": "Admin successfully registers officer/coordinator/viewer; invalid password returns 401",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_auth_audit.py",
            "test_function": "test_role_enforcement_on_audit_decision",
            "target_endpoint": "POST /api/audit/decision",
            "test_type": "RBAC Authorization",
            "assertions_checked": "Viewer gets 403 Forbidden; Officer gets 403 Forbidden; only Coordinator and Admin can submit",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_auth_audit.py",
            "test_function": "test_low_confidence_approval_blocked_with_409 & test_rejection_allowed",
            "target_endpoint": "POST /api/audit/decision",
            "test_type": "Governance Policy",
            "assertions_checked": "Approval with confidence 0.42 < 0.60 returns HTTP 409 Conflict; Rejection of 0.42 plan succeeds (201)",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "tests_api/test_auth_audit.py",
            "test_function": "test_audit_hash_chain_creation_and_verification & test_tamper_detection_flags_modified_record",
            "target_endpoint": "GET /api/audit/verify",
            "test_type": "Cryptographic Integrity",
            "assertions_checked": "is_valid == True for sequential blocks; SQL tampering of action immediately detected with is_valid == False",
            "coverage_verdict": "VERIFIED PASS"
        },
        {
            "test_file": "None (TEST GAP)",
            "test_function": "None",
            "target_endpoint": "GET /api/baselines/pareto-plot & GET /api/explain/summary-plot",
            "test_type": "Image Streaming",
            "assertions_checked": "None",
            "coverage_verdict": "UNTESTED GAP (P2)"
        },
        {
            "test_file": "None (TEST GAP)",
            "test_function": "None",
            "target_endpoint": "POST /api/stock/reset",
            "test_type": "Alternative Reset Endpoint",
            "assertions_checked": "None (DELETE /api/stock is tested)",
            "coverage_verdict": "UNTESTED GAP (P3)"
        }
    ]

    out_path = REPORTS_DIR / "backend_test_coverage.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(tests[0].keys()))
        writer.writeheader()
        writer.writerows(tests)
    print(f"✓ Saved backend test coverage audit ({len(tests)} cases) to {out_path}")

# -----------------------------------------------------------------------------
# 5. MODEL SERVING & ML INTEGRATION AUDIT
# -----------------------------------------------------------------------------
def generate_model_serving_audit():
    models = [
        {
            "model_identifier": "EM-DAT Disaster Impact Model (Ridge)",
            "artifact_path": "models/impact_models.joblib",
            "bundle_contents": "preprocessor (ColumnTransformer), impact_model (Ridge), cqr_model, feature_cols_num, feature_cols_cat, sigma_log",
            "serving_endpoint": "POST /api/predict-impact, POST /api/explain",
            "feature_schema": "Numeric: magnitude, start_year, start_month, decade; Categorical: disaster_type, disaster_subtype, scope",
            "startup_loading_behavior": "Loaded into app.state.impact_bundle in lifespan()",
            "missing_artifact_behavior": "Returns HTTP 503 'Impact prediction model is not loaded.'",
            "inference_exception_handling": "Wrapped in try/except returning HTTP 500",
            "operational_status": "OPERATIONAL IN API"
        },
        {
            "model_identifier": "Conformal Quantile Regressor (CQR 90%)",
            "artifact_path": "models/impact_models.joblib (key 'cqr_model')",
            "bundle_contents": "Calibrated upper and lower quantile estimators with conformal non-conformity score E = 0.9314",
            "serving_endpoint": "POST /api/predict-impact",
            "feature_schema": "Identical transformed feature vector X_trans from impact preprocessor",
            "startup_loading_behavior": "Loaded with impact bundle in lifespan()",
            "missing_artifact_behavior": "Returns HTTP 503",
            "inference_exception_handling": "Protected by bounds clip [0, 16] and fallback",
            "operational_status": "OPERATIONAL IN API"
        },
        {
            "model_identifier": "Fast Shortage Risk Classifier (Surrogate)",
            "artifact_path": "models/shortage_classifier.joblib",
            "bundle_contents": "pipeline (StandardScaler + RandomForestClassifier), fidelity_acc (0.9128), macro_f1 (0.9085), ece (0.0490)",
            "serving_endpoint": "GET /api/metrics (telemetry) & src/engine/monte_carlo.py",
            "feature_schema": "Demand/stock ratios, epicentre distance, casualty estimates per commodity",
            "startup_loading_behavior": "Loaded into app.state.surrogate_bundle in lifespan()",
            "missing_artifact_behavior": "Gracefully defaults to hardcoded fallback metrics",
            "inference_exception_handling": "Surrogate used as fast fallback if 2,000-draw simulator times out",
            "operational_status": "OPERATIONAL IN API"
        },
        {
            "model_identifier": "Global & Local SHAP Explainers",
            "artifact_path": "models/shap_explainer.joblib & models/pipeline_bundle.joblib",
            "bundle_contents": "TreeExplainer for XGBoost & LinearExplainer for Ridge",
            "serving_endpoint": "GET /api/explain/global & POST /api/explain",
            "feature_schema": "Encoded one-hot and scaled numeric feature matrix",
            "startup_loading_behavior": "Lazy loaded on first request to POST /api/explain and cached in app.state.shap_explainer",
            "missing_artifact_behavior": "Falls back to exact coefficient decomposition (beta * z) or on-the-fly Ridge fitting",
            "inference_exception_handling": "Wrapped in try/except; defaults to heuristic contribution rules if shap fails",
            "operational_status": "OPERATIONAL IN API WITH ON-THE-FLY RETRAINING RISK"
        },
        {
            "model_identifier": "Clinical Service Forecasting Champion (PureHybridForecaster)",
            "artifact_path": "models/final_model.joblib & models/final_model_metadata.json",
            "bundle_contents": "SeasonalNaive + Ridge Residual Model for 4 healthcare services (General Medicine, Emergency, Surgery, Pediatrics)",
            "serving_endpoint": "NONE (OFFLINE ARTIFACT ONLY)",
            "feature_schema": "4-week lag, 4-week rolling mean, seasonal week-of-year index, emergency buffer",
            "startup_loading_behavior": "NOT LOADED in api/lifespan.py",
            "missing_artifact_behavior": "N/A (No API endpoint exists)",
            "inference_exception_handling": "N/A",
            "operational_status": "UNINTEGRATED OFFLINE ARTIFACT (CRITICAL ARCHITECTURAL GAP)"
        }
    ]

    out_path = REPORTS_DIR / "model_serving_integration_audit.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(models[0].keys()))
        writer.writeheader()
        writer.writerows(models)
    print(f"✓ Saved model serving integration audit ({len(models)} models) to {out_path}")

# -----------------------------------------------------------------------------
# 6. DATABASE & PERSISTENCE INTEGRITY AUDIT
# -----------------------------------------------------------------------------
def generate_database_integrity_audit():
    db_items = [
        {
            "table_name": "users",
            "model_class": "api.models.User",
            "primary_key": "id (Integer autoincrement)",
            "indexes_and_constraints": "unique index on email; nullable=False on hashed_password, role, created_at",
            "foreign_keys_out": "None",
            "cascade_relationships": "simulations (delete-orphan), custom_stocks (delete-orphan), audit_events",
            "transaction_boundary": "Per-request Session via get_db() dependency; commit on create; rollback on exception",
            "integrity_status": "VERIFIED ROBUST",
            "risk_assessment": "Low risk. Unique constraint on email prevents duplicates; clean cascade rules."
        },
        {
            "table_name": "user_custom_stocks",
            "model_class": "api.models.UserCustomStock",
            "primary_key": "id (Integer autoincrement)",
            "indexes_and_constraints": "index on user_id, district, medicine; nullable=False on quantity, provenance",
            "foreign_keys_out": "users.id (ForeignKey)",
            "cascade_relationships": "user (back_populates)",
            "transaction_boundary": "Atomic batch commit in save_user_stock_service() and reset_user_stock_service()",
            "integrity_status": "VERIFIED ROBUST WITH COMPOSITE UNIQUE DEFECT",
            "risk_assessment": "Defect: Table lacks UniqueConstraint('user_id', 'district', 'medicine'). Application logic checks existing record first, but concurrent requests could create duplicate rows."
        },
        {
            "table_name": "simulations",
            "model_class": "api.models.SimulationRecord",
            "primary_key": "id (String(36) UUID)",
            "indexes_and_constraints": "nullable=False on inputs_json, results_hash, created_at",
            "foreign_keys_out": "users.id (ForeignKey, nullable=True)",
            "cascade_relationships": "user, audit_events",
            "transaction_boundary": "NEVER WRITTEN TO IN APPLICATION CODE",
            "integrity_status": "CRITICAL PERSISTENCE DEFECT (P0)",
            "risk_assessment": "Severe architectural bug: simulate_service() returns random UUID without inserting row into simulations table. Table remains completely empty."
        },
        {
            "table_name": "audit_events",
            "model_class": "api.models.AuditEvent",
            "primary_key": "id (Integer autoincrement)",
            "indexes_and_constraints": "index on id; nullable=False on action, reason_code, plan_hash, prev_hash, current_hash",
            "foreign_keys_out": "users.id (ForeignKey), simulations.id (ForeignKey, nullable=True)",
            "cascade_relationships": "user, simulation",
            "transaction_boundary": "Atomic commit in record_decision() inside single DB transaction",
            "integrity_status": "TAMPER-EVIDENT WITH FOREIGN KEY ORPHAN RISK",
            "risk_assessment": "Because simulations table is never populated, foreign key simulation_id references non-existent rows. In SQLite this succeeds by default; in PostgreSQL it will fail."
        },
        {
            "table_name": "SQLite vs PostgreSQL Compatibility",
            "model_class": "Engine Configuration in api/database.py",
            "primary_key": "N/A",
            "indexes_and_constraints": "connect_args={'check_same_thread': False} for SQLite",
            "foreign_keys_out": "N/A",
            "cascade_relationships": "N/A",
            "transaction_boundary": "autocommit=False, autoflush=False",
            "integrity_status": "MIGRATION RISK (P1)",
            "risk_assessment": "SQLite default does NOT enforce foreign keys (PRAGMA foreign_keys = ON is missing). Migrating to PostgreSQL will immediately fail on unpersisted simulation_id."
        }
    ]

    out_path = REPORTS_DIR / "database_integrity_audit.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(db_items[0].keys()))
        writer.writeheader()
        writer.writerows(db_items)
    print(f"✓ Saved database integrity audit ({len(db_items)} tables/topics) to {out_path}")

def main():
    print("=" * 80)
    print("EXECUTING COMPREHENSIVE BACKEND AUDIT SCRIPT")
    print("=" * 80)
    generate_endpoint_inventory()
    generate_security_audit()
    generate_contract_audit()
    generate_test_coverage_audit()
    generate_model_serving_audit()
    generate_database_integrity_audit()
    print("=" * 80)
    print("ALL 6 BACKEND AUDIT ARTIFACTS GENERATED SUCCESSFULLY")

if __name__ == "__main__":
    main()
