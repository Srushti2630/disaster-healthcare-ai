"""Authentication and Audit Ledger route handlers."""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from api.database import get_db
from api.models import User, UserRole, AuditEvent, SimulationRecord
from api.schemas import (
    UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse,
    AuditDecisionRequest, AuditEventResponse, AuditListResponse, AuditVerifyResponse
)
from api.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_role, rate_limit_login
)
from api.audit_ledger import record_decision, verify_chain

auth_router = APIRouter(prefix="/api", tags=["Auth & Governance"])

# -------------------------------------------------------------
# AUTHENTICATION ENDPOINTS
# -------------------------------------------------------------
@auth_router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register User Account"
)
async def register_user(
    body: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    Rule: The very first user to register automatically becomes an 'admin'.
    Subsequent user registrations require an active 'admin' token.
    """
    total_users = db.query(User).count()

    if total_users == 0:
        assigned_role = UserRole.ADMIN.value
    else:
        # Require admin authorization for subsequent registrations
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration requires administrator privileges. Please log in as an administrator."
            )
        token = auth_header.split(" ")[1]
        from api.auth import decode_access_token
        payload = decode_access_token(token)
        req_user_id = payload.get("sub")
        admin_user = db.query(User).filter(User.id == int(req_user_id)).first() if req_user_id else None
        if not admin_user or admin_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators are authorized to register new user accounts."
            )
        assigned_role = body.role or UserRole.VIEWER.value

    # Check for existing email
    existing = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{body.email}' is already registered."
        )

    new_user = User(
        email=body.email.strip().lower(),
        hashed_password=hash_password(body.password),
        role=assigned_role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@auth_router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="User Login & JWT Issue"
)
async def login_user(
    body: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate user credentials and return a signed JWT Bearer access token."""
    rate_limit_login(request)

    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        email=user.email
    )

@auth_router.get(
    "/auth/me",
    response_model=UserResponse,
    summary="Get Current User Profile"
)
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve profile and role information for currently authenticated user."""
    return current_user

# -------------------------------------------------------------
# AUDIT LEDGER ENDPOINTS
# -------------------------------------------------------------
@auth_router.post(
    "/audit/decision",
    response_model=AuditEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Officer Decision (SHA-256 Hash Chained)"
)
async def record_audit_decision(
    body: AuditDecisionRequest,
    current_user: User = Depends(require_role(["coordinator", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Log an officer allocation review decision (APPROVE or REJECT).
    - Requires 'coordinator' or 'admin' role.
    - Cryptographically hash-chained with SHA-256 to prior blocks.
    - Blocks APPROVE with HTTP 409 if confidence is below safety threshold in config.yaml.
    """
    event = record_decision(
        db=db,
        user=current_user,
        action=body.action,
        reason_code=body.reason_code,
        plan_hash=body.plan_hash,
        confidence=body.confidence,
        simulation_id=body.simulation_id
    )

    return AuditEventResponse(
        id=event.id,
        user_id=event.user_id,
        simulation_id=event.simulation_id,
        action=event.action,
        reason_code=event.reason_code,
        plan_hash=event.plan_hash,
        confidence=event.confidence,
        prev_hash=event.prev_hash,
        current_hash=event.current_hash,
        created_at=event.created_at.isoformat()
    )

@auth_router.get(
    "/audit",
    response_model=AuditListResponse,
    summary="Get Paginated Audit Log"
)
async def get_audit_log(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve paginated tamper-evident audit log records."""
    total = db.query(AuditEvent).count()
    offset = (page - 1) * page_size
    events = db.query(AuditEvent).order_by(desc(AuditEvent.id)).offset(offset).limit(page_size).all()

    items = [
        AuditEventResponse(
            id=e.id,
            user_id=e.user_id,
            simulation_id=e.simulation_id,
            action=e.action,
            reason_code=e.reason_code,
            plan_hash=e.plan_hash,
            confidence=e.confidence,
            prev_hash=e.prev_hash,
            current_hash=e.current_hash,
            created_at=e.created_at.isoformat()
        )
        for e in events
    ]

    return AuditListResponse(
        total_count=total,
        page=page,
        page_size=page_size,
        items=items
    )

@auth_router.get(
    "/audit/verify",
    response_model=AuditVerifyResponse,
    summary="Verify Complete Audit Log Cryptographic Integrity"
)
async def verify_audit_log(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Recompute SHA-256 hash chain from genesis block to current head.
    Detects any database tampering, out-of-order records, or altered data fields.
    """
    is_valid, total_verified, broken_info = verify_chain(db)
    if is_valid:
        msg = f"Cryptographic integrity verified intact. All {total_verified} blocks validly chained."
    else:
        msg = f"TAMPERING DETECTED at block {broken_info.get('row_index')}. Hash chain broken."

    return AuditVerifyResponse(
        is_valid=is_valid,
        total_blocks_verified=total_verified,
        broken_block=broken_info,
        message=msg
    )
