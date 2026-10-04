"""Tamper-evident SHA-256 hash-chained audit ledger for human decision governance."""
import hashlib
from datetime import datetime, timezone
from typing import Tuple, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
import yaml

from api.models import AuditEvent, User
from api.config import settings

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

def get_min_confidence_threshold() -> float:
    """Read minimum confidence threshold for plan approval from config.yaml."""
    if settings.CONFIG_YAML.exists():
        try:
            with open(settings.CONFIG_YAML, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                return float(cfg.get("thresholds", {}).get("confidence_min", 0.60))
        except Exception:
            pass
    return 0.60

def compute_block_hash(
    prev_hash: str,
    timestamp_str: str,
    user_id: int,
    simulation_id: Optional[str],
    action: str,
    reason_code: str,
    plan_hash: str,
    confidence: float
) -> str:
    """Calculate cryptographic SHA-256 block hash linking to previous block."""
    sim_str = str(simulation_id or "NONE")
    payload = f"{prev_hash}|{timestamp_str}|{user_id}|{sim_str}|{action.upper()}|{reason_code.strip()}|{plan_hash}|{confidence:.3f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def record_decision(
    db: Session,
    user: User,
    action: str,
    reason_code: str,
    plan_hash: str,
    confidence: float,
    simulation_id: Optional[str] = None
) -> AuditEvent:
    """Record a cryptographically hash-chained officer review decision."""
    action = action.upper()
    min_confidence = get_min_confidence_threshold()

    # Rule: Block APPROVE if confidence is below threshold in config.yaml
    if action == "APPROVE" and confidence < min_confidence:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Governance Policy Violation: Cannot APPROVE allocation plan with confidence ({confidence:.3f}) "
                f"below required safety threshold ({min_confidence:.3f}) in config.yaml. "
                "Action must be REJECT or requested for revision."
            )
        )

    # 1. Fetch the latest block in the chain to get prev_hash
    latest_event = db.query(AuditEvent).order_by(desc(AuditEvent.id)).first()
    prev_hash = latest_event.current_hash if latest_event else GENESIS_HASH

    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")

    # 2. Compute current block hash
    current_hash = compute_block_hash(
        prev_hash=prev_hash,
        timestamp_str=timestamp_str,
        user_id=user.id,
        simulation_id=simulation_id,
        action=action,
        reason_code=reason_code,
        plan_hash=plan_hash,
        confidence=confidence
    )

    # 3. Create persistent audit record
    event = AuditEvent(
        user_id=user.id,
        simulation_id=simulation_id,
        action=action,
        reason_code=reason_code,
        plan_hash=plan_hash,
        confidence=round(float(confidence), 3),
        prev_hash=prev_hash,
        current_hash=current_hash,
        created_at=now_utc
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def verify_chain(db: Session) -> Tuple[bool, int, Optional[Dict[str, Any]]]:
    """
    Verify complete cryptographic integrity of the audit ledger.
    Recomputes SHA-256 chain from genesis to head; reports first broken block if tampered.
    """
    events: List[AuditEvent] = db.query(AuditEvent).order_by(AuditEvent.id.asc()).all()
    if not events:
        return True, 0, None

    expected_prev = GENESIS_HASH

    for idx, event in enumerate(events):
        # 1. Check link to previous block
        if event.prev_hash != expected_prev:
            return False, len(events), {
                "broken_row_id": event.id,
                "row_index": idx + 1,
                "error_type": "PREV_HASH_MISMATCH",
                "expected_prev_hash": expected_prev,
                "found_prev_hash": event.prev_hash
            }

        # 2. Recompute hash
        timestamp_str = event.created_at.strftime("%Y-%m-%d %H:%M:%S")
        recomputed = compute_block_hash(
            prev_hash=event.prev_hash,
            timestamp_str=timestamp_str,
            user_id=event.user_id,
            simulation_id=event.simulation_id,
            action=event.action,
            reason_code=event.reason_code,
            plan_hash=event.plan_hash,
            confidence=event.confidence
        )

        if event.current_hash != recomputed:
            return False, len(events), {
                "broken_row_id": event.id,
                "row_index": idx + 1,
                "error_type": "BLOCK_TAMPERING_DETECTED",
                "expected_hash": recomputed,
                "found_hash": event.current_hash
            }

        expected_prev = event.current_hash

    return True, len(events), None
