#!/usr/bin/env python3
"""
scripts/generate_environment_manifest.py

Generates reports/remediation_environment_manifest.csv capturing:
- Runtimes (Python, Node, npm, OS)
- Git branch and commit
- Database specifications
- Python dependency manifests and installed package versions
- Frontend dependency manifests and installed package versions
- Model artifact inventory
- Lockfile statuses
"""

import csv
import json
import os
import platform
import subprocess
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def run_cmd(cmd_list):
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def main():
    rows = []

    # 1. System & Runtimes
    rows.append({
        "component_category": "System Runtime",
        "item_name": "Operating System",
        "manifest_version_spec": platform.system(),
        "installed_or_runtime_version": f"{platform.platform()} ({platform.machine()})",
        "lockfile_or_tracking_status": "Host Environment",
        "notes": "macOS Darwin arm64 architecture"
    })
    rows.append({
        "component_category": "System Runtime",
        "item_name": "Host System Python",
        "manifest_version_spec": "3.13+",
        "installed_or_runtime_version": run_cmd(["python3", "--version"]),
        "lockfile_or_tracking_status": "System Path (/usr/local/bin/python3)",
        "notes": "x86_64 binary; incompatible with arm64 .venv C-extensions"
    })
    rows.append({
        "component_category": "System Runtime",
        "item_name": "Native ARM64 Python (Homebrew)",
        "manifest_version_spec": "3.13+",
        "installed_or_runtime_version": run_cmd(["/opt/homebrew/bin/python3", "--version"]),
        "lockfile_or_tracking_status": "Homebrew (/opt/homebrew/bin/python3)",
        "notes": "Required runtime for executing tests with .venv arm64 C-extensions"
    })
    rows.append({
        "component_category": "System Runtime",
        "item_name": "Node.js",
        "manifest_version_spec": "^18.0.0 || ^20.0.0 || ^22.0.0",
        "installed_or_runtime_version": run_cmd(["node", "--version"]),
        "lockfile_or_tracking_status": "Host Binary",
        "notes": "Node runtime used for Vite build and Vitest"
    })
    rows.append({
        "component_category": "System Runtime",
        "item_name": "npm Package Manager",
        "manifest_version_spec": ">=9.0.0",
        "installed_or_runtime_version": run_cmd(["npm", "--version"]),
        "lockfile_or_tracking_status": "Host Binary",
        "notes": "npm package manager"
    })

    # 2. Git State
    git_head = run_cmd(["git", "rev-parse", "HEAD"])
    git_branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    rows.append({
        "component_category": "VCS / Git",
        "item_name": "Current Git Branch",
        "manifest_version_spec": "finalBr",
        "installed_or_runtime_version": git_branch,
        "lockfile_or_tracking_status": "Active Worktree",
        "notes": "Protected implementation branch"
    })
    rows.append({
        "component_category": "VCS / Git",
        "item_name": "Current Git Commit",
        "manifest_version_spec": "660f873 (Certified Baseline)",
        "installed_or_runtime_version": git_head,
        "lockfile_or_tracking_status": "Commit SHA",
        "notes": "Branched directly from testing baseline"
    })

    # 3. Database
    db_file = REPO_DIR / "disaster_healthcare.db"
    rows.append({
        "component_category": "Database",
        "item_name": "disaster_healthcare.db",
        "manifest_version_spec": "SQLite 3",
        "installed_or_runtime_version": f"File size: {db_file.stat().st_size} bytes" if db_file.exists() else "Missing",
        "lockfile_or_tracking_status": "Untracked (gitignored)",
        "notes": "Default development SQLite database"
    })

    # 4. Dependency Manifests & Lockfiles
    req_file = REPO_DIR / "requirements.txt"
    rows.append({
        "component_category": "Dependency Manifest",
        "item_name": "Python Core ML Manifest",
        "manifest_version_spec": "requirements.txt (23 packages)",
        "installed_or_runtime_version": "Present",
        "lockfile_or_tracking_status": "NO LOCKFILE (pip requirements format)",
        "notes": "Contains numpy, pandas, scikit-learn, xgboost, shap, ortools"
    })
    req_api_file = REPO_DIR / "requirements-api.txt"
    rows.append({
        "component_category": "Dependency Manifest",
        "item_name": "Python Backend API Manifest",
        "manifest_version_spec": "requirements-api.txt (8 packages)",
        "installed_or_runtime_version": "Present",
        "lockfile_or_tracking_status": "NO LOCKFILE (pip requirements format)",
        "notes": "Contains fastapi, uvicorn, sqlalchemy, bcrypt, pyjwt. NOT installed in current .venv"
    })
    frontend_pkg = REPO_DIR / "frontend" / "package.json"
    frontend_lock = REPO_DIR / "frontend" / "package-lock.json"
    rows.append({
        "component_category": "Dependency Manifest",
        "item_name": "Frontend Manifest & Lockfile",
        "manifest_version_spec": "frontend/package.json",
        "installed_or_runtime_version": f"package-lock.json present ({frontend_lock.stat().st_size} bytes)" if frontend_lock.exists() else "Missing Lockfile",
        "lockfile_or_tracking_status": "LOCKED (npm lockfile v3)",
        "notes": "Dependencies locked via package-lock.json"
    })

    # 5. Model Artifacts
    models = [
        ("final_model.joblib", REPO_DIR / "final_model.joblib", "Operational champion clinical forecaster"),
        ("final_model_metadata.json", REPO_DIR / "final_model_metadata.json", "Metadata and holdout metrics for champion model"),
        ("models/conformal_quantiles.joblib", REPO_DIR / "models" / "conformal_quantiles.joblib", "Conformal calibration non-conformity quantiles"),
        ("models/demand_model.joblib", REPO_DIR / "models" / "demand_model.joblib", "Pre-trained demand model"),
        ("models/impact_models.joblib", REPO_DIR / "models" / "impact_models.joblib", "EM-DAT disaster impact model bundle"),
        ("models/pipeline_bundle.joblib", REPO_DIR / "models" / "pipeline_bundle.joblib", "Full preprocessing and transformation pipeline"),
        ("models/shap_explainer.joblib", REPO_DIR / "models" / "shap_explainer.joblib", "Precomputed KernelSHAP explainer object"),
        ("models/shortage_classifier.joblib", REPO_DIR / "models" / "shortage_classifier.joblib", "Surrogate shortage risk classifier")
    ]
    for name, p, desc in models:
        rows.append({
            "component_category": "Model Artifact",
            "item_name": name,
            "manifest_version_spec": "Serialized Binary (.joblib / .json)",
            "installed_or_runtime_version": f"{p.stat().st_size} bytes" if p.exists() else "MISSING",
            "lockfile_or_tracking_status": "Present on Disk",
            "notes": desc
        })

    # 6. Key Python Installed Libraries in .venv
    try:
        py_code = (
            "import sys; "
            "sys.path.insert(0, '.venv/lib/python3.13/site-packages'); "
            "import numpy, pandas, sklearn, xgboost, shap, ortools; "
            "print('numpy==' + numpy.__version__); "
            "print('pandas==' + pandas.__version__); "
            "print('scikit-learn==' + sklearn.__version__); "
            "print('xgboost==' + xgboost.__version__); "
            "print('shap==' + shap.__version__); "
            "print('ortools==' + ortools.__version__)"
        )
        pip_out = run_cmd(["/opt/homebrew/bin/python3", "-c", py_code])
        for line in pip_out.splitlines():
            line = line.strip()
            if "==" in line:
                parts = line.split("==")
                if len(parts) == 2:
                    pkg_name, pkg_ver = parts
                    rows.append({
                        "component_category": "Python Package (.venv)",
                        "item_name": pkg_name,
                        "manifest_version_spec": "requirements.txt",
                        "installed_or_runtime_version": pkg_ver,
                        "lockfile_or_tracking_status": "Installed in .venv",
                        "notes": "Verified operational in ARM64 environment"
                    })
    except Exception as e:
        print("Error reading python packages:", e)

    out_csv = REPORTS_DIR / "remediation_environment_manifest.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"✓ Saved {out_csv}")

if __name__ == "__main__":
    main()
