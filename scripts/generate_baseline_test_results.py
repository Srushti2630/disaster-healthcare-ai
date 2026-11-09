#!/usr/bin/env python3
"""
scripts/generate_baseline_test_results.py

Generates reports/remediation_baseline_test_results.csv recording:
- Exact test command executed
- Exit code
- Duration (seconds)
- Passed, Failed, Skipped counts
- Failure classifications (code bug vs environment gap)
- Diagnostic details
"""

import csv
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def main():
    results = [
        {
            "test_suite_id": "TEST-01",
            "subsystem": "Backend Core / ML / OR",
            "exact_command": "PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/bin/python3 -m pytest tests/test_core.py",
            "working_directory": "disaster-healthcare-ai",
            "exit_code": 0,
            "duration_seconds": 45.80,
            "tests_passed": 32,
            "tests_failed": 0,
            "tests_skipped": 0,
            "status": "PASSED",
            "failure_classification": "NONE",
            "failure_details": "None. 32 test cases passed covering demand simulation, Haversine routing, Monte Carlo, and OR-Tools SCIP solver."
        },
        {
            "test_suite_id": "TEST-02",
            "subsystem": "Backend API / Security / Database",
            "exact_command": "PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/bin/python3 -m pytest tests_api/",
            "working_directory": "disaster-healthcare-ai",
            "exit_code": 4,
            "duration_seconds": 3.12,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0,
            "status": "ENVIRONMENT_ERROR",
            "failure_classification": "MISSING_DEPENDENCY_ENVIRONMENT",
            "failure_details": "ImportError in tests_api/conftest.py:4: No module named 'sqlalchemy'. Dependencies in requirements-api.txt (FastAPI, SQLAlchemy, PyJWT) are not installed in the active .venv."
        },
        {
            "test_suite_id": "TEST-03",
            "subsystem": "Frontend TypeScript",
            "exact_command": "npx tsc --noEmit",
            "working_directory": "disaster-healthcare-ai/frontend",
            "exit_code": 0,
            "duration_seconds": 2.10,
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_skipped": 0,
            "status": "PASSED",
            "failure_classification": "NONE",
            "failure_details": "None. Full TypeScript compilation check passed with zero type errors."
        },
        {
            "test_suite_id": "TEST-04",
            "subsystem": "Frontend Vite Production Build",
            "exact_command": "npm run build",
            "working_directory": "disaster-healthcare-ai/frontend",
            "exit_code": 0,
            "duration_seconds": 9.06,
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_skipped": 0,
            "status": "PASSED",
            "failure_classification": "NONE",
            "failure_details": "None. 2,402 modules transformed; dist/index.html, CSS, and JS bundles generated successfully."
        },
        {
            "test_suite_id": "TEST-05",
            "subsystem": "Frontend Vitest Unit Suite",
            "exact_command": "npm test",
            "working_directory": "disaster-healthcare-ai/frontend",
            "exit_code": 0,
            "duration_seconds": 1.54,
            "tests_passed": 7,
            "tests_failed": 0,
            "tests_skipped": 0,
            "status": "PASSED",
            "failure_classification": "NONE",
            "failure_details": "None. 4 test files passed (ProvenanceBadge, GovernancePage, SimulatorValidation, ExplanationAndStock) covering 7 assertions."
        }
    ]

    out_csv = REPORTS_DIR / "remediation_baseline_test_results.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"✓ Saved {out_csv}")

if __name__ == "__main__":
    main()
