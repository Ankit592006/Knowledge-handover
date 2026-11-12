"""Project Management & Member Role Assignment API router."""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.entities import User
from app.modules.projects.service import (
    assign_project_member,
    create_project,
    get_project_for_user,
    list_user_projects,
)
from app.schemas.api_schemas import (
    ProjectCreateRequest,
    ProjectMemberAssignRequest,
    ProjectResponse,
)

router = APIRouter(tags=["Projects & RBAC"])


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    req: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return create_project(db, req, current_user)


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ProjectResponse]:
    return list_user_projects(db, current_user)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project_endpoint(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return get_project_for_user(db, project_id, current_user)


@router.post("/projects/{project_id}/members", response_model=ProjectResponse)
def assign_member_endpoint(
    project_id: str,
    req: ProjectMemberAssignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return assign_project_member(db, project_id, req, current_user)
