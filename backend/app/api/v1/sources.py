"""Source Ingestion & Inspection API router."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_or_guest_demo
from app.models.entities import User
from app.modules.ingestion.github_connector import (
    import_github_repository_sources,
    update_source_access_permission,
)
from app.modules.ingestion.service import (
    get_source_detail_for_user,
    list_project_sources_for_user,
    seed_payflow_sources_for_project,
    upload_custom_source,
)
from app.schemas.api_schemas import (
    GitHubImportRequest,
    GitHubImportResponse,
    SourceAccessUpdateRequest,
    SourceDocumentResponse,
    SourceUploadRequest,
)

router = APIRouter(tags=["Sources & RAG Ingestion"])


@router.post(
    "/projects/{project_id}/sources/seed-payflow",
    response_model=List[SourceDocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
def seed_payflow_endpoint(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[SourceDocumentResponse]:
    return seed_payflow_sources_for_project(db, project_id, current_user)


@router.post(
    "/projects/{project_id}/sources/upload",
    response_model=SourceDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_source_endpoint(
    project_id: str,
    req: SourceUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceDocumentResponse:
    return upload_custom_source(db, project_id, req, current_user)


@router.get(
    "/projects/{project_id}/sources",
    response_model=List[SourceDocumentResponse],
)
def list_project_sources_endpoint(
    project_id: str,
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> List[SourceDocumentResponse]:
    return list_project_sources_for_user(db, project_id, current_user)


@router.get(
    "/sources/{source_id}",
    response_model=SourceDocumentResponse,
)
def get_source_detail_endpoint(
    source_id: str,
    project_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> SourceDocumentResponse:
    return get_source_detail_for_user(db, source_id, current_user, project_id=project_id)


@router.post(
    "/projects/{project_id}/sources/github-import",
    response_model=GitHubImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_github_sources_endpoint(
    project_id: str,
    req: GitHubImportRequest = GitHubImportRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GitHubImportResponse:
    return import_github_repository_sources(db, project_id, req, current_user)


@router.patch(
    "/projects/{project_id}/sources/{source_id}/access",
    response_model=SourceDocumentResponse,
)
def update_source_access_endpoint(
    project_id: str,
    source_id: str,
    req: SourceAccessUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceDocumentResponse:
    return update_source_access_permission(db, project_id, source_id, req, current_user)
