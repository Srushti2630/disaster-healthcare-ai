"""Authentication, JWT tokens, password hashing, and role-based access control."""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
from collections import defaultdict
import threading

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.models import User, UserRole

security = HTTPBearer(auto_error=False)

# -------------------------------------------------------------
# PASSWORD HASHING (Native bcrypt - Python 3.13 safe)
# -------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash raw password with bcrypt and auto-generated salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify raw password against stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# -------------------------------------------------------------
# JWT TOKEN HANDLING
# -------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create signed HS256 JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def decode_access_token(token: str) -> dict:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

# -------------------------------------------------------------
# CURRENT USER & RBAC DEPENDENCIES
# -------------------------------------------------------------
def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate user from Bearer JWT token."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(auth.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

def get_optional_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Extract user if token provided, otherwise return None (for public read endpoints)."""
    if not auth or not auth.credentials:
        return None
    try:
        payload = decode_access_token(auth.credentials)
        user_id = payload.get("sub")
        if user_id:
            return db.query(User).filter(User.id == int(user_id)).first()
    except Exception:
        pass
    return None

def require_role(allowed_roles: List[str]):
    """Enforce role-based access control. Admin always has access."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == UserRole.ADMIN.value or current_user.role in allowed_roles:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not permitted. Required role: one of {allowed_roles}, your role: '{current_user.role}'."
        )
    return role_checker

# -------------------------------------------------------------
# THREAD-SAFE IN-MEMORY RATE LIMITER
# -------------------------------------------------------------
class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter per client IP."""
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.requests.clear()

    def check(self, key: str):
        now = time.time()
        with self.lock:
            # Purge timestamps older than window
            valid_timestamps = [t for t in self.requests[key] if now - t < self.window_seconds]
            if len(valid_timestamps) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window_seconds}s allowed."
                )
            valid_timestamps.append(now)
            self.requests[key] = valid_timestamps

login_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)
simulate_limiter = InMemoryRateLimiter(max_requests=30, window_seconds=60)

def reset_rate_limiters():
    login_limiter.reset()
    simulate_limiter.reset()

def rate_limit_login(request: Request):
    ip = request.client.host if request.client else "127.0.0.1"
    login_limiter.check(f"login:{ip}")

def rate_limit_simulate(request: Request):
    ip = request.client.host if request.client else "127.0.0.1"
    simulate_limiter.check(f"simulate:{ip}")

