"""Authentication and User Management API router."""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.entities import User
from app.modules.auth.service import (
    authenticate_user,
    build_user_response,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.schemas.api_schemas import (
    AuthTokenResponse,
    TokenRefreshRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(tags=["Authentication & Users"])


@router.post("/auth/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register_endpoint(req: UserRegisterRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    return register_user(db, req)


@router.post("/auth/login", response_model=AuthTokenResponse)
def login_endpoint(req: UserLoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    return authenticate_user(db, req)


@router.post("/auth/refresh", response_model=AuthTokenResponse)
def refresh_endpoint(req: TokenRefreshRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    return rotate_refresh_token(db, req)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_endpoint(
    req: TokenRefreshRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    revoke_refresh_token(db, req.refresh_token, current_user)


@router.get("/auth/me", response_model=UserResponse)
def current_user_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    return build_user_response(db, current_user)


@router.get("/users", response_model=List[UserResponse])
def list_users_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[UserResponse]:
    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.created_at.asc()).all()
    return [build_user_response(db, u) for u in users]
