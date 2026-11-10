"""Tamper-evident SHA-256 hash-chained audit ledger for human decision governance."""
import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Tuple, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from fastapi import HTTPException, status
import yaml

from api.models import AuditEvent, User, AllocationRecord
from api.config import settings

logger = logging.getLogger(__name__)

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
_ledger_lock = threading.Lock()

def compute_canonical_simulation_hash(inputs: Dict[str, Any], results: List[Any]) -> Tuple[str, str]:
    """
    Compute canonical JSON representation of simulation inputs and deterministic SHA-256 hash of inputs + results.
    Returns (inputs_json, results_hash).
    """
    canonical_inputs_json = json.dumps(inputs, sort_keys=True, separators=(",", ":"))

    simplified_results = []
    for r in results:
        if hasattr(r, "model_dump"):
            d = r.model_dump()
        elif hasattr(r, "dict"):
            d = r.dict()
        elif isinstance(r, dict):
            d = r
        else:
            d = r.__dict__
        simplified_results.append({
            "district": str(d.get("district")),
            "medicine": str(d.get("medicine")),
            "demand_p10": round(float(d.get("demand_p10", 0.0)), 2),
            "demand_p50": round(float(d.get("demand_p50", 0.0)), 2),
            "demand_p75": round(float(d.get("demand_p75", 0.0)), 2),
            "demand_p90": round(float(d.get("demand_p90", 0.0)), 2),
            "selected_planning_demand": round(float(d.get("selected_planning_demand", 0.0)), 2),
            "available_stock": round(float(d.get("available_stock", 0.0)), 2),
            "shortage_probability": round(float(d.get("shortage_probability", 0.0)), 4),
            "risk_level": str(d.get("risk_level", "Low"))
        })
    simplified_results.sort(key=lambda x: (x["district"], x["medicine"]))
    canonical_results_json = json.dumps(simplified_results, sort_keys=True, separators=(",", ":"))

    combined = f"{canonical_inputs_json}|{canonical_results_json}".encode("utf-8")
    results_hash = hashlib.sha256(combined).hexdigest()
    return canonical_inputs_json, results_hash

def compute_canonical_plan_hash(transfers: List[Any]) -> Tuple[str, str]:
    """
    Compute canonical JSON representation of transfer plan and deterministic SHA-256 hash.
    Stably sorted by (source_region, dest_region, medicine).
    Returns (transfers_json, plan_hash).
    """
    simplified = []
    for t in transfers:
        if hasattr(t, "model_dump"):
            d = t.model_dump()
        elif hasattr(t, "dict"):
            d = t.dict()
        elif isinstance(t, dict):
            d = t
        else:
            d = t.__dict__
        simplified.append({
            "source_region": str(d.get("source_region")),
            "dest_region": str(d.get("dest_region")),
            "medicine": str(d.get("medicine")),
            "quantity": int(d.get("quantity", 0)),
            "distance_km": round(float(d.get("distance_km", 0.0)), 2),
            "cost_index": round(float(d.get("cost_index", 0.0)), 2),
            "priority": str(d.get("priority", "STANDARD")),
            "confidence": round(float(d.get("confidence", 0.85)), 3)
        })
    simplified.sort(key=lambda x: (x["source_region"], x["dest_region"], x["medicine"]))
    transfers_json = json.dumps(simplified, sort_keys=True, separators=(",", ":"))
    plan_hash = hashlib.sha256(transfers_json.encode("utf-8")).hexdigest()
    return transfers_json, plan_hash

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
    confidence: float,
    allocation_id: Optional[str] = None,
    version: int = 2
) -> str:
    """
    Calculate cryptographic SHA-256 block hash linking to previous block.
    Supports version 1 (legacy: 8 fields) and version 2 (current: 10 fields binding allocation_id).
    """
    sim_str = str(simulation_id or "NONE")
    action_str = action.upper()
    reason_str = reason_code.strip()
    conf_str = f"{confidence:.3f}"

    if version == 1:
        payload = f"{prev_hash}|{timestamp_str}|{user_id}|{sim_str}|{action_str}|{reason_str}|{plan_hash}|{conf_str}"
    elif version == 2:
        alloc_str = str(allocation_id or "NONE")
        payload = f"v2|{prev_hash}|{timestamp_str}|{user_id}|{sim_str}|{alloc_str}|{action_str}|{reason_str}|{plan_hash}|{conf_str}"
    else:
        raise ValueError(f"Unsupported block version: {version}")

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def record_decision(
    db: Session,
    user: User,
    action: str,
    reason_code: str,
    plan_hash: str,
    confidence: float,
    simulation_id: Optional[str] = None,
    allocation_id: Optional[str] = None
) -> AuditEvent:
    """
    Record a cryptographically hash-chained officer review decision.
    Executes atomically with allocation status update in a single database transaction with a single commit.
    Enforces terminal-state protection: allocations in APPROVED or REJECTED state cannot be re-decided (409 Conflict).
    """
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

    with _ledger_lock:
        try:
            # SQLite serialization: acquire exclusive reserved write lock to serialize read-latest, check terminal state, and insert
            if db.bind and db.bind.dialect.name == "sqlite":
                try:
                    db.execute(text("BEGIN IMMEDIATE"))
                except Exception as exc:
                    err_msg = str(exc).lower()
                    if "database is locked" in err_msg or "busy" in err_msg:
                        logger.warning("Database write lock acquisition timed out: %s", exc)
                        db.rollback()
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database write lock acquisition timed out. Please retry the decision submission."
                        ) from exc
                    logger.error("Failed to acquire SQLite write lock via BEGIN IMMEDIATE: %s", exc, exc_info=True)
                    db.rollback()
                    raise

            alloc = None
            if allocation_id:
                alloc = db.query(AllocationRecord).filter(AllocationRecord.id == allocation_id).first()
                if alloc:
                    if alloc.status in ["APPROVED", "REJECTED"]:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                f"Allocation '{alloc.id}' has already been finalized with status '{alloc.status}'. "
                                "Cannot submit duplicate or conflicting decision."
                            )
                        )
                    if alloc.status == "UNLINKED_LEGACY":
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot approve an unlinked legacy allocation lacking a verified simulation record."
                        )
                    if alloc.status != "PENDING_REVIEW":
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Allocation '{alloc.id}' is in status '{alloc.status}' and cannot be reviewed."
                        )

            # 1. Fetch the latest block in the chain inside the serialized transaction
            latest_event = db.query(AuditEvent).order_by(desc(AuditEvent.id)).first()
            prev_hash = latest_event.current_hash if latest_event else GENESIS_HASH

            now_utc = datetime.now(timezone.utc)
            timestamp_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")

            # 2. Compute current block hash (v2)
            current_hash = compute_block_hash(
                prev_hash=prev_hash,
                timestamp_str=timestamp_str,
                user_id=user.id,
                simulation_id=simulation_id,
                action=action,
                reason_code=reason_code,
                plan_hash=plan_hash,
                confidence=confidence,
                allocation_id=allocation_id,
                version=2
            )

            # 3. Create persistent audit record
            event = AuditEvent(
                user_id=user.id,
                simulation_id=simulation_id,
                allocation_id=allocation_id,
                action=action,
                reason_code=reason_code,
                plan_hash=plan_hash,
                confidence=round(float(confidence), 3),
                prev_hash=prev_hash,
                current_hash=current_hash,
                block_version=2,
                created_at=now_utc
            )
            db.add(event)

            # 4. Atomically update allocation status within the same transaction
            if alloc:
                alloc.status = "APPROVED" if action == "APPROVE" else "REJECTED"
                alloc.updated_at = now_utc

            # 5. Single atomic commit for both audit event and allocation record
            db.commit()
            db.refresh(event)
            if alloc:
                db.refresh(alloc)
            return event
        except Exception:
            db.rollback()
            raise

def verify_chain(db: Session) -> Tuple[bool, int, Optional[Dict[str, Any]]]:
    """
    Verify complete cryptographic integrity of the audit ledger.
    Recomputes SHA-256 chain from genesis to head; reports first broken block if tampered.
    Supports both version 1 (legacy: 8 fields) and version 2 (current: 10 fields binding allocation_id).
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

        # 2. Check block version
        version = getattr(event, "block_version", 1) or 1
        if version not in (1, 2):
            return False, len(events), {
                "broken_row_id": event.id,
                "row_index": idx + 1,
                "error_type": "UNSUPPORTED_BLOCK_VERSION",
                "unsupported_version": version
            }

        # 3. Recompute hash according to block version
        timestamp_str = event.created_at.strftime("%Y-%m-%d %H:%M:%S")
        recomputed = compute_block_hash(
            prev_hash=event.prev_hash,
            timestamp_str=timestamp_str,
            user_id=event.user_id,
            simulation_id=event.simulation_id,
            action=event.action,
            reason_code=event.reason_code,
            plan_hash=event.plan_hash,
            confidence=event.confidence,
            allocation_id=event.allocation_id,
            version=version
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
