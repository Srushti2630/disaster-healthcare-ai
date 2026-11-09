#!/usr/bin/env python3
"""
scripts/execute_phase0_backup.py

Executes Step 2 of Phase 0:
1. Creates a timestamped backup directory outside tracked git directories.
2. Backs up database, models, metadata, and all existing audit reports.
3. Computes SHA-256 checksums and exact byte sizes.
4. Verifies backup checksums match original files.
5. Generates reports/remediation_artifact_manifest.csv.
"""

import hashlib
import os
import shutil
import csv
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = REPO_DIR.parent / f"backups_phase0_{TIMESTAMP}"
REPORTS_DIR = REPO_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    print(f"Creating backup directory outside tracked repo at: {BACKUP_DIR}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    artifacts_to_backup = [
        # Database
        ("Database", REPO_DIR / "disaster_healthcare.db"),
        # Models & Metadata
        ("Model Artifact", REPO_DIR / "final_model.joblib"),
        ("Model Metadata", REPO_DIR / "final_model_metadata.json"),
        ("Model Artifact", REPO_DIR / "models" / "conformal_quantiles.joblib"),
        ("Model Artifact", REPO_DIR / "models" / "demand_model.joblib"),
        ("Model Artifact", REPO_DIR / "models" / "impact_models.joblib"),
        ("Model Artifact", REPO_DIR / "models" / "pipeline_bundle.joblib"),
        ("Model Artifact", REPO_DIR / "models" / "shap_explainer.joblib"),
        ("Model Artifact", REPO_DIR / "models" / "shortage_classifier.joblib"),
        # Root Markdown Audit Reports
        ("Audit Report MD", REPO_DIR / "DISASTERMED_TECHNICAL_AUDIT.md"),
        ("Audit Report MD", REPO_DIR / "data_quality_audit.md"),
        ("Audit Report MD", REPO_DIR / "ml_research_report.md"),
        ("Audit Report MD", REPO_DIR / "ML_RESEARCH_AND_OPTIMIZATION_AUDIT.md"),
        ("Audit Report MD", REPO_DIR / "EXPLAINABILITY_AND_UNCERTAINTY_AUDIT.md"),
        ("Audit Report MD", REPO_DIR / "EXPLAINABILITY_UNCERTAINTY_VERIFICATION.md"),
        ("Audit Report MD", REPO_DIR / "OR_OPTIMIZATION_TECHNICAL_AUDIT.md"),
        ("Audit Report MD", REPO_DIR / "FASTAPI_BACKEND_TECHNICAL_AUDIT.md"),
        ("Audit Report MD", REPO_DIR / "FRONTEND_ARCHITECTURE_SECURITY_UX_AUDIT.md"),
        ("Audit Report MD", REPO_DIR / "DEPLOYMENT_INFRASTRUCTURE_AUDIT.md"),
        ("Audit Report MD", REPO_DIR / "MASTER_TECHNICAL_AUDIT_AND_REMEDIATION_ROADMAP.md"),
        ("Audit Report MD", REPO_DIR / "MASTER_AUDIT_CLAIMS_VERIFICATION.md")
    ]

    # Add all reports in reports/
    for r_file in sorted(REPORTS_DIR.glob("*.csv")):
        artifacts_to_backup.append(("Audit Report CSV", r_file))

    manifest_rows = []
    verified_count = 0
    missing_count = 0

    for category, orig_path in artifacts_to_backup:
        rel_path = orig_path.relative_to(REPO_DIR)
        dest_path = BACKUP_DIR / rel_path

        if not orig_path.exists():
            print(f"[MISSING] {rel_path}")
            manifest_rows.append({
                "category": category,
                "relative_path": str(rel_path),
                "status": "MISSING",
                "original_size_bytes": 0,
                "original_sha256": "N/A",
                "backup_destination": "N/A",
                "backup_sha256": "N/A",
                "checksum_verified": "FALSE"
            })
            missing_count += 1
            continue

        # Copy file
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(orig_path, dest_path)

        orig_size = orig_path.stat().st_size
        orig_sha = compute_sha256(orig_path)
        dest_sha = compute_sha256(dest_path)

        is_match = (orig_sha == dest_sha)
        if is_match:
            verified_count += 1
            status_label = "VERIFIED_BACKED_UP"
        else:
            status_label = "CHECKSUM_MISMATCH"

        manifest_rows.append({
            "category": category,
            "relative_path": str(rel_path),
            "status": status_label,
            "original_size_bytes": orig_size,
            "original_sha256": orig_sha,
            "backup_destination": str(dest_path),
            "backup_sha256": dest_sha,
            "checksum_verified": "TRUE" if is_match else "FALSE"
        })

    # Save manifest CSV
    manifest_csv_path = REPORTS_DIR / "remediation_artifact_manifest.csv"
    with open(manifest_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        w.writeheader()
        w.writerows(manifest_rows)

    print(f"\n✓ Successfully backed up {verified_count} artifacts to {BACKUP_DIR}")
    print(f"✓ Missing artifacts: {missing_count}")
    print(f"✓ Manifest generated at {manifest_csv_path}")

if __name__ == "__main__":
    main()
