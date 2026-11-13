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
from app.models.entities import Project, ProjectMember, RefreshToken, User
from app.models.enums import PlatformRole, ProjectRole
from app.modules.audit.service import record_audit_event

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


def ensure_guest_demo_user(db: Session) -> User:
    """Provision or retrieve the dedicated read-only Guest Demo account limited to synthetic PayFlow data."""
    guest_email = "guest.demo@payflow.demo"
    guest = db.query(User).filter(User.email == guest_email).first()
    if not guest:
        guest = User(
            email=guest_email,
            password_hash="!",
            full_name="Guest Demo Viewer (Read-Only)",
            platform_role=PlatformRole.GUEST_DEMO.value,
            is_active=True,
        )
        db.add(guest)
        db.flush()
    elif guest.platform_role != PlatformRole.GUEST_DEMO.value:
        guest.platform_role = PlatformRole.GUEST_DEMO.value
        db.flush()

    payflow_proj = (
        db.query(Project)
        .filter(Project.slug == "payflow", Project.data_classification == "synthetic_demo")
        .first()
    )
    if payflow_proj:
        mem = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == payflow_proj.id,
                ProjectMember.user_id == guest.id,
            )
            .first()
        )
        if not mem:
            db.add(
                ProjectMember(
                    project_id=payflow_proj.id,
                    user_id=guest.id,
                    project_role=ProjectRole.GUEST_DEMO.value,
                    allowed_classifications=["PUBLIC", "INTERNAL"],
                )
            )
            db.flush()
        elif mem.project_role != ProjectRole.GUEST_DEMO.value or mem.allowed_classifications != ["PUBLIC", "INTERNAL"]:
            mem.project_role = ProjectRole.GUEST_DEMO.value
            mem.allowed_classifications = ["PUBLIC", "INTERNAL"]
            db.flush()

    db.commit()
    return guest


def get_current_user_or_guest_demo(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return authenticated user if Bearer token is provided; otherwise return read-only Guest Demo user."""
    if credentials is not None and credentials.credentials:
        return get_current_user(credentials=credentials, db=db)
    return ensure_guest_demo_user(db)


def require_platform_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if current_user.platform_role != PlatformRole.ADMIN.value:
        record_audit_event(
            db=db,
            action="UNAUTHORIZED_ADMIN_OPERATION_BLOCKED",
            target_type="platform_admin",
            target_id=current_user.id,
            actor=current_user,
            actor_role=current_user.platform_role,
        )
        db.commit()
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
    """Enforce explicit project membership, role check, and guest demo isolation (prevents IDOR & privilege escalation)."""
    if user.platform_role == PlatformRole.GUEST_DEMO.value:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or project.slug != "payflow" or project.data_classification != "synthetic_demo":
            record_audit_event(
                db=db,
                action="GUEST_NON_DEMO_PROJECT_ACCESS_BLOCKED",
                target_type="project",
                target_id=project_id,
                actor=user,
                actor_role=PlatformRole.GUEST_DEMO.value,
                project_id=project_id,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Guest Demo role is strictly limited to the synthetic PayFlow demonstration project.",
            )

    membership = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        record_audit_event(
            db=db,
            action="UNAUTHORIZED_PROJECT_ACCESS_BLOCKED",
            target_type="project",
            target_id=project_id,
            actor=user,
            actor_role=user.platform_role,
            project_id=project_id,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not an authorised member of this project.",
        )

    if user.platform_role == PlatformRole.GUEST_DEMO.value:
        # Enforce strict read-only PUBLIC/INTERNAL clearance for Guest Demo regardless of DB state
        membership.project_role = ProjectRole.GUEST_DEMO.value
        membership.allowed_classifications = [
            c for c in (membership.allowed_classifications or ["PUBLIC", "INTERNAL"])
            if c in ("PUBLIC", "INTERNAL")
        ]

    if allowed_roles and membership.project_role not in allowed_roles:
        record_audit_event(
            db=db,
            action="INSUFFICIENT_PROJECT_ROLE_BLOCKED",
            target_type="project",
            target_id=project_id,
            actor=user,
            actor_role=membership.project_role,
            project_id=project_id,
            new_state={"required_roles": allowed_roles, "actual_role": membership.project_role},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient project permissions. Required one of: {', '.join(allowed_roles)}.",
        )
    return membership
