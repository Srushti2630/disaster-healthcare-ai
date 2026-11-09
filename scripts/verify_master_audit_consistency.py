#!/usr/bin/env python3
"""
Master Cross-Audit Reconciliation, Technical Defect Verification & Phased Roadmap Script.
Compiles and generates all 5 master audit CSV datasets for DisasterMed.
"""

import os
import csv
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("EXECUTING MASTER CROSS-AUDIT CONSISTENCY & ROADMAP SCRIPT")
print("=" * 80)

# ---------------------------------------------------------------------------
# 1. CROSS-AUDIT CONTRADICTION REGISTER CSV
# ---------------------------------------------------------------------------
contradictions = [
    {
        "contradiction_id": "CONTRA-01",
        "topic_name": "Healthcare Facility Counts (4,458 vs 4,767)",
        "claim_audit_a": "Initial technical audit & early docs report 4,458 healthcare facilities in Maharashtra.",
        "claim_audit_b": "Data quality audit and API backend report 4,767 cleaned facilities (cleaned_facilities.csv).",
        "source_files_inspected": "data/processed/cleaned_facilities.csv, data_quality_audit.md:42, 81, api/services.py:64",
        "empirical_truth": "Both numbers derive from the same National Health Portal directory. The raw cleaned Maharashtra extract contains exactly 4,767 facilities (4,677 Public, 90 Private; 2,952 exact coordinates, 1,815 pincode-geocoded). In an early data filtering pass, 4,458 represented the subset of active clinics with confirmed bed counts.",
        "resolution_status": "CONFIRMED & RECONCILED",
        "technical_rationale": "Authoritative system count is 4,767 facilities. Backend GET /api/districts provides both total_facilities: 4767 and total_cleaned_facilities: 4767 for backward compatibility."
    },
    {
        "contradiction_id": "CONTRA-02",
        "topic_name": "Perishables Transit Limit for Blood Units (100 km vs 150 km)",
        "claim_audit_a": "Initial system architecture documentation states blood units are restricted to <= 100 km transit.",
        "claim_audit_b": "Operations research audit and codebase state blood units transit is constrained to <= 150 km.",
        "source_files_inspected": "src/optimise.py:38, 264, api/services.py:844, frontend/src/pages/AllocationPage.tsx:225",
        "empirical_truth": "The implemented codebase strictly enforces 150.0 km (src/optimise.py: PERISHABLE_MAX_DISTANCE = {'blood_units': 150.0}). The 100 km threshold was an initial concept note that was calibrated to 150 km to accommodate Maharashtra district centroid spacing (neighboring centroids span 110-140 km).",
        "resolution_status": "CONFIRMED & RECONCILED",
        "technical_rationale": "Code implementation is authoritative: 150.0 km. Documentation references to 100 km are legacy design notes."
    },
    {
        "contradiction_id": "CONTRA-03",
        "topic_name": "Donor Reserve Formula & Zero-Demand Behavior",
        "claim_audit_a": "System documentation claims donor districts always retain 60% of their local inventory.",
        "claim_audit_b": "OR audit reveals that when local disaster surge demand is zero (dem=0), reserve is zero, permitting 100% stock export.",
        "source_files_inspected": "src/optimise.py:119-120, src/optimise.py:280, api/services.py:800",
        "empirical_truth": "Verified in src/optimise.py:119: 'reserve = safety_reserve_ratio * dem'. When dem = 0.0, reserve = 0.0, and 'exportable = max(0, int(np.floor(stk - 0))) = stk'. The solver drains 100% of a district's baseline routine stock if no disaster casualties occur locally.",
        "resolution_status": "CONFIRMED DEFECT",
        "technical_rationale": "Safety reserve was formulated relative to disaster surge demand rather than baseline inventory. Formula must be updated to max(alpha * dem, beta * stk) to protect routine hospital operations."
    },
    {
        "contradiction_id": "CONTRA-04",
        "topic_name": "OR-Tools Solver Objective vs Benchmark Cost Index Mismatch",
        "claim_audit_a": "Benchmarking reports that OR-Tools SCIP minimizes Cost Index = unit_km * 15.0 + active_routes * 500.0.",
        "claim_audit_b": "OR audit reveals the SCIP solver objective minimizes normalized distance without fixed route activation costs.",
        "source_files_inspected": "src/optimise.py:155-165 vs src/optimise.py:287",
        "empirical_truth": "Verified in src/optimise.py: The solver objective minimizes unmet demand + w_cost * (d_ij / max_dist) * 0.05 * x_ijm - w_fairness * theta. It has NO binary route activation variable y_ij and NO 500.0 fixed charge! The evaluator in evaluate_allocation_plan() computes transport_cost = unit_km * 15.0 + active_routes * 500.0.",
        "resolution_status": "CONFIRMED DEFECT",
        "technical_rationale": "Mathematical misalignment between solver objective and evaluation metric. Solver produces fragmented multi-route solutions that are penalized ex-post by the evaluator."
    },
    {
        "contradiction_id": "CONTRA-05",
        "topic_name": "Optimization Statistical Superiority & P-Values",
        "claim_audit_a": "Legacy documentation reported identical Wilcoxon p-value = 0.043 across all 4 baselines.",
        "claim_audit_b": "OR audit reports Wilcoxon p-value = 0.00049 against No-Redistribution, but p = 0.8286 against greedy baselines on unmet demand.",
        "source_files_inspected": "OR_OPTIMIZATION_TECHNICAL_AUDIT.md:32, reports/optimization_benchmark_reproduction.csv",
        "empirical_truth": "In the legacy 20-scenario benchmark, only 5 scenarios had shortages; 5 non-zero pairs in a two-sided Wilcoxon test mathematically yields exactly p = 0.0431. In the expanded 36-scenario benchmark (13 shortage scenarios), OR-Tools is significantly superior to No-Redistribution (p = 0.00049), but statistically equivalent on unmet demand to Nearest-Neighbor (p = 0.8286). Its superiority is on cost and minimum coverage equity.",
        "resolution_status": "CONFIRMED & RECONCILED",
        "technical_rationale": "Legacy p=0.043 was an artifact of low non-zero sample size (n=5). Under n=36, OR-Tools dominates on multi-objective trade-offs (cost + equity), not raw demand elimination."
    },
    {
        "contradiction_id": "CONTRA-06",
        "topic_name": "Clinical Demand Forecasting Champion Model Selection",
        "claim_audit_a": "ML audit identified PureHybridForecaster (Seasonal + Ridge Residuals) as champion (MAE=43.14) in final_model.joblib.",
        "claim_audit_b": "Backend audit revealed final_model.joblib is never loaded in api/lifespan.py, and no API route serves it.",
        "source_files_inspected": "final_model.joblib, final_model_metadata.json, api/lifespan.py:50-70, deploy/Dockerfile.api:44",
        "empirical_truth": "Verified. final_model.joblib exists on disk in git root, with valid metadata and holdout evaluation. However, it was never integrated into api/lifespan.py, no route exists in api/routes.py, and Dockerfile.api omits it from container builds (only copies models/).",
        "resolution_status": "CONFIRMED ARCHITECTURAL GAP",
        "technical_rationale": "PureHybridForecaster is an offline research artifact, not an operational API capability. Needs dedicated endpoint POST /api/forecast/clinical."
    },
    {
        "contradiction_id": "CONTRA-07",
        "topic_name": "CQR Uncertainty Bounds Multiplicative Factor vs Margin",
        "claim_audit_a": "Legacy audit text claimed CQR intervals imply an uncertainty multiplicative factor of x518.4.",
        "claim_audit_b": "Explainability verification established conformal margin is +/- 0.9314 in log-space, giving an upper/lower ratio of ~6.44x.",
        "source_files_inspected": "EXPLAINABILITY_UNCERTAINTY_VERIFICATION.md:15-35, models/impact_models.joblib",
        "empirical_truth": "Verified mathematically: In log10/ln space, non-conformity margin E = 0.9314 gives upper/lower ratio exp(2 * 0.9314) = 6.44x. The x518.4 number in legacy drafts was the ratio of maximum to minimum raw casualties across extreme events, erroneously conflated with the CQR margin.",
        "resolution_status": "CONFIRMED & RECONCILED",
        "technical_rationale": "Conformal margin is strictly +/- 0.9314 log units (~6.44x multiplicative ratio). Terminology corrected."
    },
    {
        "contradiction_id": "CONTRA-08",
        "topic_name": "Simulation ID Persistence & PostgreSQL Foreign Key Validity",
        "claim_audit_a": "Backend audit claimed unpersisted SimulationRecord necessarily breaks PostgreSQL migration.",
        "claim_audit_b": "Inspection of database schema reveals simulation_id in audit_events is nullable (nullable=True).",
        "source_files_inspected": "api/models.py:61, disaster_healthcare.db (audit_events table)",
        "empirical_truth": "In disaster_healthcare.db, audit_events row 1 has simulation_id = NULL. In SQL/PostgreSQL, a foreign key column with NULL is legally valid. PostgreSQL migration only fails if a non-null, non-existent simulation_id string is passed. Currently, GovernancePage omits simulation_id, resulting in NULL. If simulation_id is passed, it triggers ForeignKeyViolation because simulations table has 0 rows.",
        "resolution_status": "CONFIRMED DEFECT WITH NUANCE",
        "technical_rationale": "Nullable foreign keys accept NULL. However, leaving simulation_id as NULL breaks audit traceability (orphans the decision from the simulation scenario it approved)."
    },
    {
        "contradiction_id": "CONTRA-09",
        "topic_name": "JWT Secret Key Environment Variable Mapping",
        "claim_audit_a": "docker-compose.yml sets JWT_SECRET_KEY=dev-secret-key-change-in-production-disaster-ai-2025.",
        "claim_audit_b": "Backend audit reveals api/config.py Settings only reads JWT_SECRET or SECRET_KEY.",
        "source_files_inspected": "docker-compose.yml:14, api/config.py:27-35",
        "empirical_truth": "Verified in api/config.py: Settings class defines SECRET_KEY and JWT_SECRET, but has no field named JWT_SECRET_KEY. Because extra='ignore', Pydantic drops JWT_SECRET_KEY, reverting to default SECRET_KEY.",
        "resolution_status": "CONFIRMED CONFIGURATION DEFECT",
        "technical_rationale": "Variable name mismatch in Docker Compose causes silent fallback to insecure hardcoded default secret."
    },
    {
        "contradiction_id": "CONTRA-10",
        "topic_name": "Frontend API Base URL Compilation in Docker",
        "claim_audit_a": "docker-compose.yml and nginx.conf configure reverse proxying /api/ to http://api:8000/api/.",
        "claim_audit_b": "Frontend audit reveals Vite bakes VITE_API_URL=http://localhost:8000 into static JS at build time.",
        "source_files_inspected": "frontend/.env:1, deploy/Dockerfile.frontend:17, deploy/nginx.conf:23-33",
        "empirical_truth": "Verified in deploy/Dockerfile.frontend: RUN npm run build compiles assets with VITE_API_URL=http://localhost:8000. In remote deployments, client browsers make fetch calls to localhost:8000 on their local machine, completely bypassing the Nginx reverse proxy.",
        "resolution_status": "CONFIRMED DEPLOYMENT DEFECT",
        "technical_rationale": "Hardcoded localhost:8000 breaks remote deployment. Must be set to empty string for origin-relative API calls."
    },
    {
        "contradiction_id": "CONTRA-11",
        "topic_name": "Model Artifact Git Tracking vs Runtime Availability",
        "claim_audit_a": "System documentation claims pre-trained models are included in repository.",
        "claim_audit_b": "Deployment audit shows .gitignore excludes models/*.joblib.",
        "source_files_inspected": ".gitignore:39-41, git ls-files models/",
        "empirical_truth": "Verified: git ls-files models/ returns 0 files. models/*.joblib is ignored. A fresh clone has an empty models/ directory, causing cold-start Docker containers to fail with HTTP 503 until models are trained on host.",
        "resolution_status": "CONFIRMED PACKAGING DEFECT",
        "technical_rationale": "Model binaries excluded from git. Must be versioned via Git LFS or generated via container entrypoint."
    }
]

with open(REPORTS_DIR / "cross_audit_contradiction_register.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(contradictions[0].keys()))
    writer.writeheader()
    writer.writerows(contradictions)
print(f"✓ Saved contradiction register ({len(contradictions)} items) to {REPORTS_DIR / 'cross_audit_contradiction_register.csv'}")

# ---------------------------------------------------------------------------
# 2. MASTER DEFECT REGISTER CSV
# ---------------------------------------------------------------------------
master_defects = [
    {
        "defect_id": "DEF-P0-01",
        "original_audit_source": "DEPLOYMENT_INFRASTRUCTURE_AUDIT (INFRA-P0-01) & FRONTEND_AUDIT",
        "subsystem": "Frontend & Reverse Proxy Networking",
        "file_path": "frontend/.env:1, deploy/Dockerfile.frontend:17",
        "line_numbers": "frontend/.env:1",
        "technical_description": "Vite compiles hardcoded VITE_API_URL=http://localhost:8000 into JS bundle, causing remote browsers to bypass Nginx proxy and connect to client localhost.",
        "reproduction_evidence": "Deploy container to remote VM; browser network tab shows failed API requests targeting http://localhost:8000.",
        "root_cause": "Hardcoded VITE_API_URL in frontend/.env instead of using empty string for origin-relative paths.",
        "operational_impact": "Total failure of web application on any remote host, staging VM, or cloud deployment.",
        "data_integrity_or_scientific_impact": "None directly, but blocks access to all predictions and allocations.",
        "security_impact": "CORS preflight failures and potential mixed-content security blocks.",
        "severity": "P0 CRITICAL",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Set VITE_API_URL='' in frontend/.env so fetch requests use origin-relative paths (/api/*).",
        "required_regression_test": "Build frontend Docker container; assert generated bundle makes relative requests to /api/districts.",
        "acceptance_criteria": "Web application functions cleanly over remote IP/domain without connecting to localhost.",
        "blocks_deployment": "YES",
        "blocks_academic_demo": "YES (Blocks remote/live presentation)"
    },
    {
        "defect_id": "DEF-P0-02",
        "original_audit_source": "FASTAPI_BACKEND_TECHNICAL_AUDIT (P0-1) & DEPLOYMENT_AUDIT",
        "subsystem": "Database Persistence & Schema Integrity",
        "file_path": "api/services.py:265-279, api/models.py:42-55",
        "line_numbers": "api/services.py:265-279",
        "technical_description": "simulate_service() generates random UUID but never inserts SimulationRecord into simulations table. Table has 0 rows.",
        "reproduction_evidence": "Inspect disaster_healthcare.db: SELECT COUNT(*) FROM simulations returns 0 despite simulated scenarios.",
        "root_cause": "Omission of db.add(SimulationRecord) and db.commit() in simulate_service().",
        "operational_impact": "Scenarios are ephemeral and unpersisted. Governance decisions referencing simulation_id fail FK validation in strict databases.",
        "data_integrity_or_scientific_impact": "Loss of provenance between simulated stochastic scenarios and human approval decisions.",
        "security_impact": "Orphaned audit ledger entries violate EU AI Act Article 14 record-keeping requirements.",
        "severity": "P0 CRITICAL",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Instantiate SimulationRecord with inputs_json and results_hash and commit to db in simulate_service().",
        "required_regression_test": "Execute POST /api/simulate; assert row exists in simulations table with matching UUID.",
        "acceptance_criteria": "simulations table contains valid record for every executed scenario.",
        "blocks_deployment": "YES",
        "blocks_academic_demo": "YES (Governance audit trail cannot link scenarios)"
    },
    {
        "defect_id": "DEF-P0-03",
        "original_audit_source": "FASTAPI_BACKEND_TECHNICAL_AUDIT (P0-2) & DEPLOYMENT_AUDIT",
        "subsystem": "API Concurrency & Event Loop",
        "file_path": "api/routes.py:87-115, api/services.py:162, 770",
        "line_numbers": "api/routes.py:87-115",
        "technical_description": "CPU-bound Monte Carlo simulation (2,000 draws) and SCIP solver optimization run synchronously inside async def handlers, freezing asyncio event loop for 1.5-3.5s.",
        "reproduction_evidence": "Send GET /health while POST /api/simulate runs; observe /health stalls for >2 seconds.",
        "root_cause": "Synchronous CPU workloads declared in async def instead of standard def or run_in_threadpool().",
        "operational_impact": "Single Uvicorn worker becomes completely unresponsive to concurrent requests during simulations.",
        "data_integrity_or_scientific_impact": "None",
        "security_impact": "Denial of Service (DoS) vulnerability under light concurrent load.",
        "severity": "P0 CRITICAL",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Remove async keyword from simulate_scenario and allocate_resources route definitions.",
        "required_regression_test": "Fire concurrent requests to /health during /api/simulate; assert /health latency < 20 ms.",
        "acceptance_criteria": "Event loop remains responsive (<50ms) during heavy CPU simulation and optimization.",
        "blocks_deployment": "YES",
        "blocks_academic_demo": "NO (Single user demo unaffected)"
    },
    {
        "defect_id": "DEF-P0-04",
        "original_audit_source": "DEPLOYMENT_INFRASTRUCTURE_AUDIT (INFRA-P0-02)",
        "subsystem": "Configuration & Secret Management",
        "file_path": "docker-compose.yml:14, api/config.py:27-35",
        "line_numbers": "docker-compose.yml:14, api/config.py:27-35",
        "technical_description": "docker-compose.yml passes JWT_SECRET_KEY, but api/config.py Settings only reads JWT_SECRET or SECRET_KEY. Variable is ignored, falling back to hardcoded default secret.",
        "reproduction_evidence": "Print settings.get_jwt_secret inside Docker container; observe it does not match docker-compose.yml value.",
        "root_cause": "Field name mismatch between docker-compose.yml (JWT_SECRET_KEY) and api/config.py (JWT_SECRET).",
        "operational_impact": "Secret rotation in Docker Compose fails silently; production containers run on insecure default secret.",
        "data_integrity_or_scientific_impact": "None",
        "security_impact": "High: Insecure default JWT secret allows token forgery if network is exposed.",
        "severity": "P0 CRITICAL",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Update docker-compose.yml to pass JWT_SECRET=... and SECRET_KEY=....",
        "required_regression_test": "Start container with custom JWT_SECRET; assert settings.get_jwt_secret matches environment.",
        "acceptance_criteria": "Custom JWT secret from Docker environment is actively enforced.",
        "blocks_deployment": "YES",
        "blocks_academic_demo": "NO"
    },
    {
        "defect_id": "DEF-P0-05",
        "original_audit_source": "DEPLOYMENT_INFRASTRUCTURE_AUDIT (INFRA-P0-03)",
        "subsystem": "Database Persistence & Host Mount",
        "file_path": "docker-compose.yml:21",
        "line_numbers": "docker-compose.yml:21",
        "technical_description": "Host SQLite bind mount (./disaster_healthcare.db:/app/disaster_healthcare.db) creates a host directory if absent, crashing SQLite. Permission conflicts occur under non-root appuser.",
        "reproduction_evidence": "Run docker compose up without pre-existing disaster_healthcare.db file on host; observe directory created and SQLite startup crash.",
        "root_cause": "Binding a single file rather than a directory or named volume.",
        "operational_impact": "Container fails to boot on clean server checkouts.",
        "data_integrity_or_scientific_impact": "Database corruption risk under host crash.",
        "security_impact": "Host file permission errors under non-root container user.",
        "severity": "P0 CRITICAL",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Migrate database storage to a Docker named volume (e.g. db_data:/app/data) or deploy PostgreSQL service.",
        "required_regression_test": "Run docker compose up on fresh checkout; assert database boots cleanly.",
        "acceptance_criteria": "Clean startup without requiring manual host file pre-creation.",
        "blocks_deployment": "YES",
        "blocks_academic_demo": "YES (Docker setup fails on clean checkout)"
    },
    {
        "defect_id": "DEF-P1-01",
        "original_audit_source": "FRONTEND_AUDIT (FE-P1-01) & FASTAPI_BACKEND_AUDIT",
        "subsystem": "Frontend-Backend Contract & Spatial Geometry",
        "file_path": "frontend/src/pages/SimulatorPage.tsx:26, api/services.py:169",
        "line_numbers": "frontend/src/pages/SimulatorPage.tsx:26",
        "technical_description": "Dropdown includes 'Mumbai Suburban'. Backend validates strictly against 35 keys where only 'Mumbai' exists, crashing request with HTTP 400 Bad Request.",
        "reproduction_evidence": "Select 'Mumbai Suburban' in simulator dropdown; observe HTTP 400 error banner.",
        "root_cause": "Frontend list contains 36 administrative names; backend uses 35-district consolidated spatial framework without normalization.",
        "operational_impact": "Users selecting Mumbai Suburban cannot run simulations.",
        "data_integrity_or_scientific_impact": "Breaks 35-district framework consistency.",
        "security_impact": "None",
        "severity": "P1 HIGH",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Remove 'Mumbai Suburban' from frontend dropdown, or call normalize_district_name() in backend simulate_service().",
        "required_regression_test": "Simulate with 'Mumbai' and 'Mumbai Suburban'; assert both succeed with HTTP 200.",
        "acceptance_criteria": "Simulator executes successfully for all selectable districts.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "YES (Selecting Mumbai Suburban crashes live demo)"
    },
    {
        "defect_id": "DEF-P1-02",
        "original_audit_source": "FRONTEND_AUDIT (FE-P1-02, FE-P1-03) & GOVERNANCE_WORKFLOW",
        "subsystem": "Governance & Human Oversight Workflow",
        "file_path": "frontend/src/pages/GovernancePage.tsx:23, 67-76, frontend/src/pages/AllocationPage.tsx",
        "line_numbers": "GovernancePage.tsx:23, 67-76",
        "technical_description": "Governance form omits simulation_id and defaults to empty-string plan hash. AllocationPage has no button to forward plan to Governance. No confirmation modal on approve.",
        "reproduction_evidence": "Run allocation; navigate to /governance; observe hardcoded empty-string hash and absent simulation_id.",
        "root_cause": "Missing state bridge between AllocationPage and GovernancePage.",
        "operational_impact": "Officers cannot formally approve optimized plans without manual copy-paste of 64-char hashes.",
        "data_integrity_or_scientific_impact": "Appends dummy plan hashes to cryptographic ledger.",
        "security_impact": "Violates human oversight workflow requirements under EU AI Act Article 14.",
        "severity": "P1 HIGH",
        "confidence_score": 1.0,
        "dependency_defect_ids": "DEF-P0-02",
        "proposed_remediation": "Add 'Forward Plan to Governance' button on AllocationPage; read plan_hash and simulation_id via location state in GovernancePage.",
        "required_regression_test": "Solve allocation, click forward button, submit approval; assert ledger record contains matching plan_hash and simulation_id.",
        "acceptance_criteria": "End-to-end allocation-to-governance workflow operates seamlessly with confirmation modal.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "YES (Breaks the human-in-the-loop narrative)"
    },
    {
        "defect_id": "DEF-P1-03",
        "original_audit_source": "ML_RESEARCH_AUDIT, FASTAPI_BACKEND_AUDIT & DEPLOYMENT_AUDIT",
        "subsystem": "Machine Learning Serving Pipeline",
        "file_path": "final_model.joblib, api/lifespan.py:50-70, deploy/Dockerfile.api:44",
        "line_numbers": "api/lifespan.py:50-70",
        "technical_description": "Clinical forecasting champion PureHybridForecaster (final_model.joblib) is omitted from api/lifespan.py, has no API route, and is excluded from Docker container.",
        "reproduction_evidence": "Inspect api/lifespan.py and api/routes.py; observe zero code loading or serving final_model.joblib.",
        "root_cause": "Model was generated as an offline research artifact but never connected to FastAPI serving layer.",
        "operational_impact": "System cannot forecast routine clinical hospital attendance.",
        "data_integrity_or_scientific_impact": "Disconnect between academic ML research claims and operational API capabilities.",
        "security_impact": "None",
        "severity": "P1 HIGH",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Move final_model.joblib to models/, load in lifespan.py, and expose POST /api/forecast/clinical.",
        "required_regression_test": "Call POST /api/forecast/clinical; assert 4-service forecast returned with prediction intervals.",
        "acceptance_criteria": "Champion clinical model is loaded and served via API.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "YES (Claimed clinical forecaster cannot be demonstrated via API)"
    },
    {
        "defect_id": "DEF-P1-04",
        "original_audit_source": "FASTAPI_BACKEND_TECHNICAL_AUDIT (P1-2)",
        "subsystem": "ML Explainability & Performance",
        "file_path": "api/services.py:390-424",
        "line_numbers": "api/services.py:390-424",
        "technical_description": "explain_prediction_service() synchronously reads emdat_events.csv and retrains a scikit-learn Ridge model during active HTTP request if model is missing in memory.",
        "reproduction_evidence": "Delete impact model from memory; call POST /api/explain; observe 1,200ms latency spike and disk I/O.",
        "root_cause": "Fallback retraining logic embedded inside route service handler.",
        "operational_impact": "Severe request latency spike (~1.2s), memory bloat, and thread contention under concurrent requests.",
        "data_integrity_or_scientific_impact": "Mutates global model bundle state during runtime.",
        "security_impact": "DoS vulnerability via repeated requests triggering synchronous training.",
        "severity": "P1 HIGH",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Remove on-demand retraining code; return HTTP 503 if impact model artifact is missing.",
        "required_regression_test": "Invoke POST /api/explain with missing model; assert HTTP 503 returned cleanly without disk write.",
        "acceptance_criteria": "No training or disk fitting occurs during active HTTP request handling.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "NO"
    },
    {
        "defect_id": "DEF-P1-05",
        "original_audit_source": "DEPLOYMENT_INFRASTRUCTURE_AUDIT (INFRA-P1-01)",
        "subsystem": "Reverse Proxy & SRE Health Probes",
        "file_path": "deploy/nginx.conf:23-42",
        "line_numbers": "deploy/nginx.conf:23-42",
        "technical_description": "Nginx config omits proxy routes for /health and /ready. Requests to /health on port 80 return index.html (200 OK) with HTML content instead of backend health JSON.",
        "reproduction_evidence": "curl -i http://localhost/health through Nginx; observe Content-Type: text/html and index.html payload.",
        "root_cause": "Nginx configuration only defines location /api/ and location ~ ^/(docs|redoc|openapi.json).",
        "operational_impact": "External load balancers cannot evaluate backend health or model readiness.",
        "data_integrity_or_scientific_impact": "None",
        "security_impact": "False positive health checks in cloud orchestrators.",
        "severity": "P1 HIGH",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Add location ~ ^/(health|ready) { proxy_pass http://api:8000; } to deploy/nginx.conf.",
        "required_regression_test": "curl -f http://localhost/health through Nginx; assert JSON {'status': 'healthy'} returned.",
        "acceptance_criteria": "Health and readiness endpoints proxied cleanly through Nginx on port 80.",
        "blocks_deployment": "YES",
        "blocks_academic_demo": "NO"
    },
    {
        "defect_id": "DEF-P1-06",
        "original_audit_source": "DEPLOYMENT_INFRASTRUCTURE_AUDIT (INFRA-P1-03)",
        "subsystem": "Repository Packaging & Cold Start",
        "file_path": ".gitignore:39-41",
        "line_numbers": ".gitignore:39-41",
        "technical_description": ".gitignore excludes models/*.joblib. A fresh git clone has an empty models/ directory, causing cold-start Docker builds to fail with HTTP 503.",
        "reproduction_evidence": "git ls-files models/ returns 0 files. Fresh clone cannot serve /api/predict-impact.",
        "root_cause": ".gitignore ignores all joblib artifacts without providing an automated download or packaging strategy.",
        "operational_impact": "Cold-start deployments fail until someone manually trains models on host.",
        "data_integrity_or_scientific_impact": "Non-reproducible deployments across environments.",
        "security_impact": "None",
        "severity": "P1 HIGH",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Track baseline model weights via Git LFS or provide an automated seeding script in container entrypoint.",
        "required_regression_test": "Clone repo in clean directory; run container build; assert GET /ready returns healthy.",
        "acceptance_criteria": "Fresh clone boots into operational state with models available.",
        "blocks_deployment": "YES",
        "blocks_academic_demo": "YES (Evaluation reviewers cloning repo cannot run backend)"
    },
    {
        "defect_id": "DEF-P1-07",
        "original_audit_source": "FRONTEND_AUDIT (FE-P1-04)",
        "subsystem": "Frontend Mobile Responsiveness & UX",
        "file_path": "frontend/src/components/Navbar.tsx:45-64",
        "line_numbers": "frontend/src/components/Navbar.tsx:45-64",
        "technical_description": "Navigation links are wrapped in <nav className='hidden lg:flex'>. On mobile/tablet screens (<1024px), navigation disappears completely with no mobile drawer.",
        "reproduction_evidence": "Resize browser to 768px; observe navigation bar displays only title and login button. No menu exists.",
        "root_cause": "Desktop navigation hidden on mobile without implementing responsive hamburger menu drawer.",
        "operational_impact": "Mobile/tablet users cannot navigate between Simulator, Allocation, Backtest, or Governance.",
        "data_integrity_or_scientific_impact": "None",
        "security_impact": "None",
        "severity": "P1 HIGH",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Implement mobile hamburger menu toggle with responsive sliding drawer in Navbar.tsx.",
        "required_regression_test": "Test on viewport 375px; assert menu button opens navigation drawer with all 6 page links.",
        "acceptance_criteria": "Navigation functional across mobile, tablet, and desktop viewports.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "YES (Demonstration on tablet/mobile fails)"
    },
    {
        "defect_id": "DEF-P2-01",
        "original_audit_source": "OR_OPTIMIZATION_AUDIT (CONTRA-03, CONTRA-04)",
        "subsystem": "Operations Research & Solver Mathematical Formulation",
        "file_path": "src/optimise.py:119, 155-165, 287",
        "line_numbers": "src/optimise.py:119-120, 155-165",
        "technical_description": "1. Zero-demand donor districts have 0 reserve, allowing 100% routine stock drain. 2. Solver objective omits fixed route activation charges ($500*y_ij), causing misalignment with evaluator.",
        "reproduction_evidence": "Inspect src/optimise.py:119 and objective function; observe dem=0 gives reserve=0 and fixed charge is absent.",
        "root_cause": "Safety reserve formulated relative to disaster surge demand; fixed route charge omitted from MIP objective.",
        "operational_impact": "1. Drains routine hospital inventory in non-disaster districts. 2. Produces fragmented multi-route shipments.",
        "data_integrity_or_scientific_impact": "Mathematical misalignment between solver objective and reported Cost Index benchmark.",
        "security_impact": "None",
        "severity": "P2 MEDIUM",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "1. Set reserve = max(safety_reserve_ratio * dem, 0.30 * stk). 2. Add binary route variables y_ij with fixed cost to MIP objective.",
        "required_regression_test": "Run solve_resource_allocation on zero-demand district; assert >=30% baseline stock retained.",
        "acceptance_criteria": "Routine stock protected; solver objective aligns with benchmark Cost Index.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "NO (Operational in current state)"
    },
    {
        "defect_id": "DEF-P2-02",
        "original_audit_source": "FRONTEND_AUDIT (FE-P2-01)",
        "subsystem": "Frontend Security / Leaflet XSS Surface",
        "file_path": "frontend/src/components/DistrictMap.tsx:61-72",
        "line_numbers": "frontend/src/components/DistrictMap.tsx:61-72",
        "technical_description": "District names and risk levels are interpolated directly into unencoded HTML template string passed to Leaflet bindTooltip().",
        "reproduction_evidence": "Supply a district property containing HTML/script tags; observe unescaped markup rendered in tooltip DOM.",
        "root_cause": "Raw string interpolation into Leaflet layer.bindTooltip().",
        "operational_impact": "DOM XSS vulnerability if malicious district names or custom stock payloads are supplied via API.",
        "data_integrity_or_scientific_impact": "None",
        "security_impact": "CWE-79 Cross-Site Scripting (XSS) in map visualization.",
        "severity": "P2 MEDIUM",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Escape HTML entities in tooltipContent or construct tooltip DOM elements safely with textContent.",
        "required_regression_test": "Render map with district name '<script>alert(1)</script>'; assert tags rendered as escaped text.",
        "acceptance_criteria": "Zero raw HTML string interpolation in Leaflet tooltips.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "NO"
    },
    {
        "defect_id": "DEF-P2-03",
        "original_audit_source": "FRONTEND_AUDIT (FE-P2-02) & AUTH_AUDIT",
        "subsystem": "Frontend Session Management & Error Recovery",
        "file_path": "frontend/src/api/client.ts:37-46, frontend/src/context/AuthContext.tsx",
        "line_numbers": "frontend/src/api/client.ts:37-46",
        "technical_description": "HTTP 401 Unauthorized responses do not trigger session logout or redirect. User remains in broken visually authenticated state when 120-minute JWT expires.",
        "reproduction_evidence": "Expire token in localStorage; click any officer action; observe generic HTTP 401 error alert without redirect.",
        "root_cause": "client.ts request() function throws generic Error without intercepting status 401 to clear auth state.",
        "operational_impact": "Degraded user experience; officers cannot complete actions until manually refreshing or finding logout button.",
        "data_integrity_or_scientific_impact": "None",
        "security_impact": "Stale token retained in browser storage.",
        "severity": "P2 MEDIUM",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "In client.ts, intercept status 401 to remove token and dispatch auth-expired event to redirect to /login.",
        "required_regression_test": "Mock 401 response; assert localStorage token is removed and user redirected to /login.",
        "acceptance_criteria": "Automatic graceful logout and login redirect on session expiration.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "NO"
    },
    {
        "defect_id": "DEF-P2-04",
        "original_audit_source": "FRONTEND_AUDIT (FE-P2-03)",
        "subsystem": "Data Provenance & Scientific Rigor",
        "file_path": "frontend/src/components/StockEditingTable.tsx:36-46",
        "line_numbers": "frontend/src/components/StockEditingTable.tsx:36-46",
        "technical_description": "getEstimatedBaselineStock() calculates fallback inventory using client-side character-code hashing (district.charCodeAt(0) * 1000 + ...) rather than authoritative data.",
        "reproduction_evidence": "Inspect StockEditingTable with unpopulated custom stock; observe pseudo-random numbers generated in browser.",
        "root_cause": "Client-side fallback synthetic inventory function.",
        "operational_impact": "Displays fabricated baseline stocks if backend custom stock is uninitialized.",
        "data_integrity_or_scientific_impact": "Violates scientific data provenance; displays synthetic numbers without SYNTHETIC badge.",
        "security_impact": "None",
        "severity": "P2 MEDIUM",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Fetch baseline stock strictly from backend GET /api/stock, labeling it clearly with ProvenanceBadge ESTIMATED.",
        "required_regression_test": "Render StockEditingTable; assert displayed baseline values match GET /api/stock API response.",
        "acceptance_criteria": "Zero client-side character-code synthetic inventory generation.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "YES (Academic reviewer inspecting code will flag character-code math)"
    },
    {
        "defect_id": "DEF-P2-05",
        "original_audit_source": "DEPLOYMENT_INFRASTRUCTURE_AUDIT (INFRA-P2-01, INFRA-P2-02)",
        "subsystem": "Supply Chain & Build Reproducibility",
        "file_path": "requirements.txt, requirements-api.txt, .github/workflows/ci.yml:16-19",
        "line_numbers": "requirements.txt:1-24",
        "technical_description": "1. All Python dependencies use floating '>=' minimum specifications without a lockfile. 2. GitHub Actions pinned to mutable major tags (@v4, @v5).",
        "reproduction_evidence": "Inspect requirements.txt (pandas>=2.0.0) and ci.yml (actions/checkout@v4); observe missing lockfile and SHAs.",
        "root_cause": "Absence of pip-tools / poetry lockfile and SHA-pinned CI actions.",
        "operational_impact": "Non-reproducible builds; upstream library releases can break builds unpredictably.",
        "data_integrity_or_scientific_impact": "Model prediction drift if newer scikit-learn/numpy versions alter floating-point math.",
        "security_impact": "Supply chain poisoning vulnerability if upstream GitHub action tag is re-pointed.",
        "severity": "P2 MEDIUM",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Generate requirements.lock with exact pinned versions; pin GitHub Actions to full 40-character commit SHAs.",
        "required_regression_test": "Run pip install -r requirements.lock in clean virtualenv; assert deterministic package hashes.",
        "acceptance_criteria": "100% pinned, deterministic Python and CI dependency tree.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "NO"
    },
    {
        "defect_id": "DEF-P3-01",
        "original_audit_source": "DEPLOYMENT_INFRASTRUCTURE_AUDIT (INFRA-P3-01)",
        "subsystem": "Developer Tooling & Data Safety",
        "file_path": "Makefile:52-53",
        "line_numbers": "Makefile:52-53",
        "technical_description": "'make clean' command dangerously executes rm -rf data/processed/* models/*.joblib, wiping trained weights and processed datasets.",
        "reproduction_evidence": "Inspect Makefile line 53; observe destructive rm -rf commands targeting data/processed and models.",
        "root_cause": "Overly broad clean target including persistent data and model artifacts.",
        "operational_impact": "Accidental developer invocation wipes hours of pipeline data processing and model training.",
        "data_integrity_or_scientific_impact": "Irreversible loss of local datasets if uncommitted.",
        "security_impact": "None",
        "severity": "P3 MINOR",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Remove data/processed/* and models/*.joblib from standard clean target; introduce separate clean-all target.",
        "required_regression_test": "Run make clean; assert data/processed/cleaned_facilities.csv and models/*.joblib remain intact.",
        "acceptance_criteria": "make clean only purges temporary caches (__pycache__, .pytest_cache).",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "NO"
    },
    {
        "defect_id": "DEF-P3-02",
        "original_audit_source": "FRONTEND_AUDIT (FE-P3-01, FE-P3-02)",
        "subsystem": "Accessibility & UI Polish",
        "file_path": "frontend/src/pages/AllocationPage.tsx:127-135, frontend/src/components/ProvenanceBadge.tsx",
        "line_numbers": "AllocationPage.tsx:127-135",
        "technical_description": "Range sliders lack aria-label / aria-valuetext for screen readers. ProvenanceBadge lacks dedicated styling for SYNTHETIC tag.",
        "reproduction_evidence": "Inspect range sliders in accessibility tree; observe missing accessible names.",
        "root_cause": "Omission of accessibility ARIA attributes on native input sliders.",
        "operational_impact": "Impaired accessibility for assistive technology users.",
        "data_integrity_or_scientific_impact": "None",
        "security_impact": "None",
        "severity": "P3 MINOR",
        "confidence_score": 1.0,
        "dependency_defect_ids": "None",
        "proposed_remediation": "Add aria-label and aria-valuetext to sliders; add purple styling branch for SYNTHETIC tag in ProvenanceBadge.",
        "required_regression_test": "Audit with axe-core / Lighthouse; assert zero form control accessibility violations.",
        "acceptance_criteria": "WCAG 2.1 AA compliant slider controls and complete provenance badge styling.",
        "blocks_deployment": "NO",
        "blocks_academic_demo": "NO"
    }
]

with open(REPORTS_DIR / "master_defect_register.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(master_defects[0].keys()))
    writer.writeheader()
    writer.writerows(master_defects)
print(f"✓ Saved master defect register ({len(master_defects)} unified defects) to {REPORTS_DIR / 'master_defect_register.csv'}")

# ---------------------------------------------------------------------------
# 3. REMEDIATION DEPENDENCY MATRIX CSV
# ---------------------------------------------------------------------------
remediation_phases = [
    {
        "phase_id": "Phase 0",
        "phase_name": "Reproducible Baseline, Safety & Branch Verification",
        "defect_id": "BASELINE-CHECK",
        "task_summary": "Verify testing branch, confirm clean working tree, lock database file, and establish baseline test pass status.",
        "prerequisite_tasks": "None",
        "blocks_tasks": "All subsequent phases",
        "estimated_effort": "0.5 days",
        "verification_gate": "git status clean on branch testing; pytest tests/ and npm test pass."
    },
    {
        "phase_id": "Phase 1",
        "phase_name": "Deployment, Networking & Secret Foundations",
        "defect_id": "DEF-P0-01",
        "task_summary": "Set VITE_API_URL='' in frontend/.env to enable origin-relative routing through Nginx.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 6, Phase 7",
        "estimated_effort": "0.5 days",
        "verification_gate": "Built frontend issues relative requests to /api/districts over remote IP."
    },
    {
        "phase_id": "Phase 1",
        "phase_name": "Deployment, Networking & Secret Foundations",
        "defect_id": "DEF-P0-04",
        "task_summary": "Align JWT secret environment variable mapping in docker-compose.yml (pass JWT_SECRET and SECRET_KEY).",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 7",
        "estimated_effort": "0.5 days",
        "verification_gate": "Backend container settings.get_jwt_secret matches environment variable."
    },
    {
        "phase_id": "Phase 1",
        "phase_name": "Deployment, Networking & Secret Foundations",
        "defect_id": "DEF-P0-05",
        "task_summary": "Establish reliable database persistence (named Docker volume or PostgreSQL container service).",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 2, Phase 7",
        "estimated_effort": "1.0 days",
        "verification_gate": "docker compose up boots on clean checkout without pre-existing host file."
    },
    {
        "phase_id": "Phase 1",
        "phase_name": "Deployment, Networking & Secret Foundations",
        "defect_id": "DEF-P1-05",
        "task_summary": "Add reverse proxy routes for /health and /ready in deploy/nginx.conf.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 7",
        "estimated_effort": "0.5 days",
        "verification_gate": "curl -f http://localhost/health through Nginx returns JSON status: healthy."
    },
    {
        "phase_id": "Phase 1",
        "phase_name": "Deployment, Networking & Secret Foundations",
        "defect_id": "DEF-P1-06",
        "task_summary": "Track core model weights via Git LFS or implement automated container seeding script.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 5, Phase 7",
        "estimated_effort": "1.0 days",
        "verification_gate": "Fresh git clone boots into operational state with impact models loaded."
    },
    {
        "phase_id": "Phase 2",
        "phase_name": "Backend Integrity, Persistence & Concurrency",
        "defect_id": "DEF-P0-02",
        "task_summary": "Persist SimulationRecord in simulate_service() with inputs_json and results_hash.",
        "prerequisite_tasks": "Phase 1 (DEF-P0-05)",
        "blocks_tasks": "Phase 3 (DEF-P1-02)",
        "estimated_effort": "1.0 days",
        "verification_gate": "simulations table populated with UUID on every POST /api/simulate call."
    },
    {
        "phase_id": "Phase 2",
        "phase_name": "Backend Integrity, Persistence & Concurrency",
        "defect_id": "DEF-P0-03",
        "task_summary": "Remove async keyword from simulate_scenario and allocate_resources route definitions to offload CPU work to threadpool.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 7",
        "estimated_effort": "0.5 days",
        "verification_gate": "/health responds in <20ms while /api/simulate runs concurrently."
    },
    {
        "phase_id": "Phase 2",
        "phase_name": "Backend Integrity, Persistence & Concurrency",
        "defect_id": "DEF-P1-04",
        "task_summary": "Remove on-demand Ridge model retraining from explain_prediction_service(); return HTTP 503 if missing.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 5",
        "estimated_effort": "0.5 days",
        "verification_gate": "POST /api/explain returns HTTP 503 if model missing without disk write."
    },
    {
        "phase_id": "Phase 3",
        "phase_name": "End-to-End Governance & Human Oversight",
        "defect_id": "DEF-P1-02",
        "task_summary": "Bridge AllocationPage to GovernancePage; pass plan_hash and simulation_id; add confirmation modal on approve.",
        "prerequisite_tasks": "Phase 2 (DEF-P0-02)",
        "blocks_tasks": "Phase 6, Phase 7",
        "estimated_effort": "1.5 days",
        "verification_gate": "Approved audit ledger record links valid simulation_id and actual plan hash."
    },
    {
        "phase_id": "Phase 4",
        "phase_name": "Data Consistency & Optimization Correctness",
        "defect_id": "DEF-P1-01",
        "task_summary": "Remove 'Mumbai Suburban' from SimulatorPage dropdown and enforce 35-district normalization in backend.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 6",
        "estimated_effort": "0.5 days",
        "verification_gate": "Simulations run cleanly for all 35 selectable districts."
    },
    {
        "phase_id": "Phase 4",
        "phase_name": "Data Consistency & Optimization Correctness",
        "defect_id": "DEF-P2-01",
        "task_summary": "Update donor safety reserve formula to max(safety_reserve_ratio * dem, 0.30 * stk); align solver objective with fixed route charges.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 7",
        "estimated_effort": "1.5 days",
        "verification_gate": "Zero-demand districts retain >=30% routine stock; solver objective includes route activation penalties."
    },
    {
        "phase_id": "Phase 5",
        "phase_name": "Machine Learning Integration & Serving",
        "defect_id": "DEF-P1-03",
        "task_summary": "Integrate champion PureHybridForecaster (final_model.joblib); load in lifespan.py; expose POST /api/forecast/clinical.",
        "prerequisite_tasks": "Phase 1 (DEF-P1-06)",
        "blocks_tasks": "Phase 6, Phase 7",
        "estimated_effort": "1.5 days",
        "verification_gate": "POST /api/forecast/clinical serves 4-service demand forecasts with prediction intervals."
    },
    {
        "phase_id": "Phase 6",
        "phase_name": "Frontend Security, UX & Accessibility",
        "defect_id": "DEF-P1-07",
        "task_summary": "Implement mobile hamburger navigation drawer in Navbar.tsx.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 7",
        "estimated_effort": "1.0 days",
        "verification_gate": "Navigation fully functional on mobile viewports (<1024px)."
    },
    {
        "phase_id": "Phase 6",
        "phase_name": "Frontend Security, UX & Accessibility",
        "defect_id": "DEF-P2-02",
        "task_summary": "Sanitize Leaflet tooltip HTML interpolation to prevent DOM XSS.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 7",
        "estimated_effort": "0.5 days",
        "verification_gate": "District names containing HTML entities render safely as escaped text."
    },
    {
        "phase_id": "Phase 6",
        "phase_name": "Frontend Security, UX & Accessibility",
        "defect_id": "DEF-P2-03",
        "task_summary": "Intercept HTTP 401 in api/client.ts to clear token and redirect to /login.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 7",
        "estimated_effort": "0.5 days",
        "verification_gate": "Expired JWT triggers automatic logout and login redirect."
    },
    {
        "phase_id": "Phase 6",
        "phase_name": "Frontend Security, UX & Accessibility",
        "defect_id": "DEF-P2-04",
        "task_summary": "Replace client-side character-code stock calculation with backend GET /api/stock values.",
        "prerequisite_tasks": "Phase 0",
        "blocks_tasks": "Phase 7",
        "estimated_effort": "0.5 days",
        "verification_gate": "StockEditingTable renders authoritative baseline stock with ESTIMATED badge."
    },
    {
        "phase_id": "Phase 7",
        "phase_name": "Production Hardening, CI/CD & Verification",
        "defect_id": "DEF-P2-05",
        "task_summary": "Pin Python dependencies with requirements.lock; pin CI actions to commit SHAs; add testing branch to CI triggers.",
        "prerequisite_tasks": "Phase 1 - Phase 6",
        "blocks_tasks": "Release Readiness",
        "estimated_effort": "1.0 days",
        "verification_gate": "CI triggers and passes cleanly on testing branch with pinned dependencies."
    }
]

with open(REPORTS_DIR / "remediation_dependency_matrix.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(remediation_phases[0].keys()))
    writer.writeheader()
    writer.writerows(remediation_phases)
print(f"✓ Saved remediation dependency matrix ({len(remediation_phases)} phase tasks) to {REPORTS_DIR / 'remediation_dependency_matrix.csv'}")

# ---------------------------------------------------------------------------
# 4. REGRESSION TEST VERIFICATION MATRIX CSV
# ---------------------------------------------------------------------------
regression_tests = [
    {
        "defect_id": "DEF-P0-01",
        "test_type": "Docker / End-to-End Contract",
        "test_file": "tests_api/test_deployment_contract.py",
        "test_signature": "test_frontend_docker_bundle_relative_api_calls()",
        "test_description": "Inspect compiled dist/assets/index-*.js; verify no literal 'http://localhost:8000' string exists in fetch calls.",
        "expected_outcome": "Bundle uses relative path /api/* without hardcoded localhost.",
        "pass_condition": "'http://localhost:8000' not in compiled_js_bundle"
    },
    {
        "defect_id": "DEF-P0-02",
        "test_type": "Backend Integration / Database",
        "test_file": "tests_api/test_simulation_persistence.py",
        "test_signature": "test_simulate_scenario_persists_simulation_record()",
        "test_description": "Call POST /api/simulate; query database table simulations; assert record with matching UUID exists with inputs_json and results_hash.",
        "expected_outcome": "Record successfully retrieved from database.",
        "pass_condition": "db.query(SimulationRecord).filter_by(id=resp.json()['sim_id']).count() == 1"
    },
    {
        "defect_id": "DEF-P0-03",
        "test_type": "Backend Concurrency / Asynchronous",
        "test_file": "tests_api/test_concurrency.py",
        "test_signature": "test_event_loop_unblocked_during_heavy_simulation()",
        "test_description": "Send GET /health concurrently while POST /api/simulate executes 2,000 draws. Measure /health response latency.",
        "expected_outcome": "Health probe returns in < 30 ms without stalling behind simulation.",
        "pass_condition": "health_response_latency_ms < 50.0"
    },
    {
        "defect_id": "DEF-P0-04",
        "test_type": "Configuration / Unit",
        "test_file": "tests_api/test_config.py",
        "test_signature": "test_jwt_secret_mapping_from_environment()",
        "test_description": "Initialize Settings with JWT_SECRET set; assert settings.get_jwt_secret returns expected secret string.",
        "expected_outcome": "Settings extracts secret correctly.",
        "pass_condition": "settings.get_jwt_secret == os.environ['JWT_SECRET']"
    },
    {
        "defect_id": "DEF-P0-05",
        "test_type": "Docker Build / Startup",
        "test_file": "tests_api/test_docker_startup.py",
        "test_signature": "test_clean_checkout_database_initialization()",
        "test_description": "Verify database file or volume initializes automatically without pre-existing host file.",
        "expected_outcome": "Database tables created without permission denial.",
        "pass_condition": "engine.connect() succeeds and Base.metadata tables exist."
    },
    {
        "defect_id": "DEF-P1-01",
        "test_type": "API Contract / Spatial Validation",
        "test_file": "tests_api/test_district_normalization.py",
        "test_signature": "test_mumbai_suburban_normalization()",
        "test_description": "Submit simulation request with epicentre='Mumbai Suburban'; assert status 200 and epicentre normalized to 'Mumbai'.",
        "expected_outcome": "Simulation completes successfully with status 200.",
        "pass_condition": "response.status_code == 200 and response.json()['epicentre'] in ['Mumbai', 'Mumbai Suburban']"
    },
    {
        "defect_id": "DEF-P1-02",
        "test_type": "End-to-End Governance Workflow",
        "test_file": "tests_api/test_governance_workflow.py",
        "test_signature": "test_allocation_to_governance_chain()",
        "test_description": "Execute allocation; record decision using returned plan_hash and simulation_id; verify audit_events row references both.",
        "expected_outcome": "Audit event committed with non-null simulation_id and matching plan_hash.",
        "pass_condition": "audit_event.plan_hash == allocation.plan_hash and audit_event.simulation_id == simulation.id"
    },
    {
        "defect_id": "DEF-P1-03",
        "test_type": "ML Model Serving / API Integration",
        "test_file": "tests_api/test_clinical_forecaster.py",
        "test_signature": "test_clinical_service_demand_forecast_endpoint()",
        "test_description": "Call POST /api/forecast/clinical with 4-week horizon; assert predictions returned for General Medicine, Emergency, Surgery, Pediatrics.",
        "expected_outcome": "Status 200 with forecast arrays and prediction intervals.",
        "pass_condition": "set(response.json()['services'].keys()) == {'General Medicine', 'Emergency', 'Surgery', 'Pediatrics'}"
    },
    {
        "defect_id": "DEF-P1-04",
        "test_type": "Backend Unit / Exception Handling",
        "test_file": "tests_api/test_explain_missing_model.py",
        "test_signature": "test_explain_endpoint_returns_503_when_model_missing()",
        "test_description": "Set app.state.impact_bundle = None; call POST /api/explain; assert HTTP 503 Service Unavailable returned without disk write.",
        "expected_outcome": "Status 503 returned gracefully.",
        "pass_condition": "response.status_code == 503 and 'model not loaded' in response.json()['message'].lower()"
    },
    {
        "defect_id": "DEF-P1-05",
        "test_type": "Reverse Proxy / Nginx Routing",
        "test_file": "tests_api/test_nginx_proxy.py",
        "test_signature": "test_nginx_health_and_ready_proxy_routes()",
        "test_description": "Send GET /health and GET /ready through Nginx proxy port 80; assert Content-Type is application/json and status is healthy.",
        "expected_outcome": "Backend JSON health response returned via port 80.",
        "pass_condition": "response.headers['content-type'].startswith('application/json') and response.json()['status'] == 'healthy'"
    },
    {
        "defect_id": "DEF-P1-07",
        "test_type": "Frontend Component / Vitest",
        "test_file": "frontend/src/test/NavbarMobile.test.tsx",
        "test_signature": "test_navbar_mobile_menu_drawer_toggles()",
        "test_description": "Render Navbar with viewport 375px; click mobile menu button; assert navigation links appear in DOM.",
        "expected_outcome": "Mobile drawer opens and displays page navigation links.",
        "pass_condition": "screen.getByRole('dialog').textContent.includes('Simulator')"
    },
    {
        "defect_id": "DEF-P2-01",
        "test_type": "Operations Research / Solver Unit",
        "test_file": "tests/test_optimisation_safety.py",
        "test_signature": "test_zero_demand_district_retains_routine_stock()",
        "test_description": "Run solver with district demand = 0.0 and stock = 10,000. Assert total exported stock <= 7,000 (retains >=30%).",
        "expected_outcome": "Remaining stock in zero-demand district >= 3,000 units.",
        "pass_condition": "transferred_out <= 7000 and remaining_stock >= 3000"
    },
    {
        "defect_id": "DEF-P2-02",
        "test_type": "Frontend Security / DOM XSS",
        "test_file": "frontend/src/test/DistrictMapSecurity.test.tsx",
        "test_signature": "test_leaflet_tooltip_escapes_html_entities()",
        "test_description": "Pass feature properties with district = '<img src=x onerror=alert(1)>'; assert rendered tooltip does not create executable element.",
        "expected_outcome": "HTML characters rendered as text entities.",
        "pass_condition": "tooltip_html.includes('&lt;img') or '<img' not in tooltip_html"
    },
    {
        "defect_id": "DEF-P2-03",
        "test_type": "Frontend Authentication / Session",
        "test_file": "frontend/src/test/AuthExpiry.test.tsx",
        "test_signature": "test_401_response_clears_token_and_redirects()",
        "test_description": "Simulate 401 response from api.request(); assert localStorage.getItem('token') is null and navigate('/login') triggered.",
        "expected_outcome": "Token purged and user redirected.",
        "pass_condition": "localStorage.getItem('token') is None"
    },
    {
        "defect_id": "DEF-P2-04",
        "test_type": "Frontend Data Integrity / Vitest",
        "test_file": "frontend/src/test/StockTableData.test.tsx",
        "test_signature": "test_stock_table_renders_authoritative_baseline()",
        "test_description": "Render StockEditingTable; assert initial cell values equal mock GET /api/stock response, not character-code hash.",
        "expected_outcome": "Table populated with authoritative values.",
        "pass_condition": "displayed_val == mock_stock_val and displayed_val != character_code_hash_val"
    }
]

with open(REPORTS_DIR / "regression_test_verification_matrix.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(regression_tests[0].keys()))
    writer.writeheader()
    writer.writerows(regression_tests)
print(f"✓ Saved regression test verification matrix ({len(regression_tests)} tests) to {REPORTS_DIR / 'regression_test_verification_matrix.csv'}")

# ---------------------------------------------------------------------------
# 5. RELEASE READINESS ASSESSMENT CSV
# ---------------------------------------------------------------------------
readiness_assessment = [
    {
        "readiness_dimension": "Academic Demonstration Readiness",
        "current_status": "CONDITIONAL (READY WITH CONSTRAINTS)",
        "score_out_of_100": 85,
        "blocking_issues": "1. Selecting 'Mumbai Suburban' crashes demo (DEF-P1-01). 2. Governance review cannot link allocation plan directly (DEF-P1-02). 3. Mobile screen display lacks navigation drawer (DEF-P1-07).",
        "prerequisite_phases": "Phase 2 (DEF-P0-02), Phase 3 (DEF-P1-02), Phase 4 (DEF-P1-01)",
        "risk_summary": "Highly credible for desktop viva demonstration if presenter avoids 'Mumbai Suburban' and demonstrates the precomputed baseline comparison benchmark."
    },
    {
        "readiness_dimension": "Local Development Readiness",
        "current_status": "READY",
        "score_out_of_100": 90,
        "blocking_issues": "Parent .venv has Windows AMD64 .pyd binaries, requiring local developer to create clean macOS/Linux virtualenv.",
        "prerequisite_phases": "Phase 0 (Virtualenv setup)",
        "risk_summary": "Core pytest (25 tests) and Vitest (7 tests) pass cleanly when run in appropriate host environment."
    },
    {
        "readiness_dimension": "Reproducible Fresh-Clone Readiness",
        "current_status": "BLOCKED",
        "score_out_of_100": 45,
        "blocking_issues": "1. Git ignores models/*.joblib (DEF-P1-06); fresh clone starts with missing models. 2. requirements.txt unpinned (DEF-P2-05).",
        "prerequisite_phases": "Phase 1 (DEF-P1-06), Phase 7 (DEF-P2-05)",
        "risk_summary": "A reviewer or examiner cloning the repo from scratch cannot immediately boot backend API without running python run_all.py first."
    },
    {
        "readiness_dimension": "Docker Deployment Readiness (Local Host)",
        "current_status": "BLOCKED",
        "score_out_of_100": 50,
        "blocking_issues": "1. Host bind mount SQLite file hazard (DEF-P0-05). 2. JWT_SECRET_KEY ignored in compose (DEF-P0-04). 3. Models missing if not pre-trained on host.",
        "prerequisite_phases": "Phase 1 (DEF-P0-04, DEF-P0-05, DEF-P1-06)",
        "risk_summary": "Docker Compose builds, but risks startup failure on clean machines due to missing SQLite file or missing models."
    },
    {
        "readiness_dimension": "Remote Server Deployment Readiness",
        "current_status": "CRITICALLY BLOCKED",
        "score_out_of_100": 20,
        "blocking_issues": "1. Frontend hardcodes http://localhost:8000 (DEF-P0-01), causing all remote API calls to fail. 2. Nginx omits /health and /ready routes (DEF-P1-05).",
        "prerequisite_phases": "Phase 1 (DEF-P0-01, DEF-P1-05)",
        "risk_summary": "Cannot be deployed to staging server, cloud VM, or public IP in current state. Remote browsers cannot communicate with backend."
    },
    {
        "readiness_dimension": "Production Operational Readiness",
        "current_status": "CRITICALLY BLOCKED",
        "score_out_of_100": 15,
        "blocking_issues": "1. Event loop freezing under CPU simulation (DEF-P0-03). 2. SQLite single-writer lock contention. 3. Missing PostgreSQL persistence & Alembic migrations. 4. Unpersisted simulation records (DEF-P0-02).",
        "prerequisite_phases": "All Phases (Phase 1 through Phase 7)",
        "risk_summary": "Unsuitable for production healthcare dispatch. Concurrency bottlenecks and data persistence flaws preclude mission-critical deployment."
    }
]

with open(REPORTS_DIR / "release_readiness_assessment.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(readiness_assessment[0].keys()))
    writer.writeheader()
    writer.writerows(readiness_assessment)
print(f"✓ Saved release readiness assessment ({len(readiness_assessment)} dimensions) to {REPORTS_DIR / 'release_readiness_assessment.csv'}")

print("=" * 80)
print("ALL 5 MASTER AUDIT DATASETS COMPILED & EXPORTED SUCCESSFULLY")
print("=" * 80)
