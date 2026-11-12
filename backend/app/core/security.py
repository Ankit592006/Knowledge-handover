"""Password hashing (Argon2id), JWT token signing, refresh token rotation, and RBAC dependencies."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Dict, List, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import ProjectMember, RefreshToken, User

settings = get_settings()
ph = PasswordHasher(time_cost=2, memory_cost=32768, parallelism=2)
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return ph.verify(password_hash, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def hash_refresh_token(raw_token: str) -> str:
    """Store only the SHA-256 digest of refresh tokens in the database."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": user.id,
        "email": user.email,
        "platform_role": user.platform_role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_and_store_refresh_token(db: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(48)
    token_digest = hash_refresh_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=token_digest,
        expires_at=expires_at,
    )
    db.add(db_token)
    db.flush()
    return raw_token


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )
    return user


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.platform_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Administrator role required.",
        )
    return current_user


def get_project_membership(
    db: Session,
    project_id: str,
    user: User,
    allowed_roles: Optional[List[str]] = None,
) -> ProjectMember:
    """Enforce project membership and optional role check on the backend (prevents IDOR & privilege escalation)."""
    membership = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        if user.platform_role == "ADMIN":
            # Platform Admin receives synthetic virtual membership with full classification for administration
            return ProjectMember(
                id="admin-virtual",
                project_id=project_id,
                user_id=user.id,
                project_role="PROJECT_LEAD",
                allowed_classifications=["PUBLIC", "INTERNAL", "RESTRICTED"],
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not an authorised member of this project.",
        )

    if allowed_roles and membership.project_role not in allowed_roles and user.platform_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient project permissions. Required one of: {', '.join(allowed_roles)}.",
        )
    return membership
