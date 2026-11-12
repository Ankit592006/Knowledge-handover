"""Authentication and User Management Service (Modules 1 & 2)."""

from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_and_store_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.entities import Project, ProjectMember, RefreshToken, User
from app.modules.audit.service import record_audit_event
from app.schemas.api_schemas import (
    AuthTokenResponse,
    ProjectMembershipBrief,
    TokenRefreshRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

settings = get_settings()


def build_user_response(db: Session, user: User) -> UserResponse:
    rows = (
        db.query(ProjectMember, Project)
        .join(Project, Project.id == ProjectMember.project_id)
        .filter(ProjectMember.user_id == user.id)
        .all()
    )
    memberships: List[ProjectMembershipBrief] = [
        ProjectMembershipBrief(
            project_id=proj.id,
            project_slug=proj.slug,
            project_name=proj.name,
            project_role=member.project_role,
            allowed_classifications=member.allowed_classifications,
        )
        for member, proj in rows
    ]
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        platform_role=user.platform_role,
        is_active=user.is_active,
        created_at=user.created_at,
        memberships=memberships,
    )


def register_user(db: Session, req: UserRegisterRequest) -> AuthTokenResponse:
    normalized_email = req.email.strip().lower()
    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=normalized_email,
        password_hash=hash_password(req.password),
        full_name=req.full_name.strip(),
        platform_role=req.platform_role.value,
        is_active=True,
    )
    db.add(user)
    db.flush()

    access_token = create_access_token(user)
    refresh_token = create_and_store_refresh_token(db, user)

    record_audit_event(
        db=db,
        action="USER_REGISTERED",
        target_type="user",
        target_id=user.id,
        actor=user,
        new_state={"email": user.email, "platform_role": user.platform_role},
    )
    db.commit()
    db.refresh(user)

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=build_user_response(db, user),
    )


def authenticate_user(db: Session, req: UserLoginRequest) -> AuthTokenResponse:
    normalized_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled.",
        )

    access_token = create_access_token(user)
    refresh_token = create_and_store_refresh_token(db, user)

    record_audit_event(
        db=db,
        action="USER_LOGGED_IN",
        target_type="user",
        target_id=user.id,
        actor=user,
    )
    db.commit()

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=build_user_response(db, user),
    )


def rotate_refresh_token(db: Session, req: TokenRefreshRequest) -> AuthTokenResponse:
    digest = hash_refresh_token(req.refresh_token)
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == digest).first()
    now = datetime.now(timezone.utc)
    if not db_token or db_token.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token.",
        )

    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
        )

    user = db.query(User).filter(User.id == db_token.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )

    # Revoke old refresh token and issue a fresh pair
    db_token.revoked_at = now
    new_access = create_access_token(user)
    new_refresh = create_and_store_refresh_token(db, user)
    db.commit()

    return AuthTokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=build_user_response(db, user),
    )


def revoke_refresh_token(db: Session, raw_refresh_token: str, actor: User) -> None:
    digest = hash_refresh_token(raw_refresh_token)
    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == digest, RefreshToken.user_id == actor.id)
        .first()
    )
    if db_token and db_token.revoked_at is None:
        db_token.revoked_at = datetime.now(timezone.utc)
    record_audit_event(
        db=db,
        action="USER_LOGGED_OUT",
        target_type="user",
        target_id=actor.id,
        actor=actor,
    )
    db.commit()
