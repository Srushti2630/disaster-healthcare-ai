"""
Tamper-Evident Audit Log Module with SHA-256 Hash Chaining.
Logs human-in-the-loop decisions (approval/rejection) with cryptographic verification.
"""
from pathlib import Path
import hashlib
from datetime import datetime
import pandas as pd

REPORTS_DIR = Path("reports")
AUDIT_LOG_PATH = REPORTS_DIR / "audit_log.csv"

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

def init_audit_log(audit_path: Path = AUDIT_LOG_PATH) -> pd.DataFrame:
    """Initialize audit log CSV with hash chain headers if absent. Renames legacy log files lacking current_hash column."""
    audit_path = Path(audit_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    
    if audit_path.exists():
        try:
            df = pd.read_csv(audit_path, dtype=str)
            if "current_hash" not in df.columns:
                legacy_path = audit_path.parent / f"{audit_path.stem}_legacy.csv"
                audit_path.rename(legacy_path)
        except Exception:
            pass

    if not audit_path.exists():
        df = pd.DataFrame(columns=[
            "timestamp", "user_name", "user_role", "action",
            "reason_code", "confidence", "assumed_pct", "scenario_summary",
            "previous_hash", "current_hash"
        ])
        df.to_csv(audit_path, index=False)
        return df
    return pd.read_csv(audit_path, dtype=str)

def get_latest_hash(audit_path: Path = AUDIT_LOG_PATH) -> str:
    """Retrieve the current_hash of the most recent audit log entry."""
    df = init_audit_log(audit_path)
    if len(df) == 0:
        return GENESIS_HASH
    return str(df.iloc[-1]["current_hash"])

def log_decision(
    user_name: str,
    user_role: str,
    action: str,
    reason_code: str,
    confidence: float,
    assumed_pct: float,
    scenario_summary: str,
    audit_path: Path = AUDIT_LOG_PATH
) -> dict:
    """Append a cryptographically hash-chained entry to the audit log."""
    audit_path = Path(audit_path)
    prev_hash = get_latest_hash(audit_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    clean_user = user_name.strip() if user_name else "Anonymous Officer"
    clean_role = user_role.strip() if user_role else "Health Logistics Specialist"

    payload = f"{prev_hash}|{timestamp}|{clean_user}|{clean_role}|{action}|{reason_code}|{confidence:.3f}|{assumed_pct:.1f}|{scenario_summary}"
    current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    entry = {
        "timestamp": timestamp,
        "user_name": clean_user,
        "user_role": clean_role,
        "action": action,
        "reason_code": reason_code,
        "confidence": round(float(confidence), 3),
        "assumed_pct": round(float(assumed_pct), 1),
        "scenario_summary": scenario_summary,
        "previous_hash": prev_hash,
        "current_hash": current_hash
    }

    df_entry = pd.DataFrame([entry])
    df_entry.to_csv(audit_path, mode="a", header=not audit_path.exists(), index=False)
    return entry

def verify_audit_log_integrity(audit_path: Path = AUDIT_LOG_PATH) -> tuple[bool, int, list]:
    """Verify cryptographic integrity of the entire audit log hash chain."""
    audit_path = Path(audit_path)
    if not audit_path.exists():
        return True, 0, []

    df = pd.read_csv(audit_path, dtype=str)
    if len(df) == 0 or "current_hash" not in df.columns:
        return True, 0, []

    violations = []
    expected_prev = GENESIS_HASH

    for idx, row in df.iterrows():
        if str(row["previous_hash"]) != expected_prev:
            violations.append(f"Row {idx+1}: Prev hash mismatch (found {row['previous_hash']}, expected {expected_prev})")

        payload = f"{row['previous_hash']}|{row['timestamp']}|{row['user_name']}|{row['user_role']}|{row['action']}|{row['reason_code']}|{float(row['confidence']):.3f}|{float(row['assumed_pct']):.1f}|{row['scenario_summary']}"
        recalculated_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        if recalculated_hash != str(row["current_hash"]):
            violations.append(f"Row {idx+1}: Content tampering detected (hash {row['current_hash']} != {recalculated_hash})")

        expected_prev = str(row["current_hash"])

    is_valid = len(violations) == 0
    return is_valid, len(df), violations

if __name__ == "__main__":
    init_audit_log()
    log_decision("Dr. A. Sharma", "District Health Officer", "APPROVE", "ROUTINE_ACCEPTANCE", 0.92, 15.0, "Scenario MH-Flood-2026")
    valid, n_entries, errs = verify_audit_log_integrity()
    print(f"Audit log integrity check: {valid} ({n_entries} entries verified, {len(errs)} errors)")
