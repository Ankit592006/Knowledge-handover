"""Project Management & Scoped Role Assignment Service (Module 3)."""

from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_project_membership
from app.models.entities import Handover, Project, ProjectMember, SourceDocument, User
from app.models.enums import PlatformRole, ProjectRole
from app.modules.audit.service import record_audit_event
from app.schemas.api_schemas import (
    ProjectCreateRequest,
    ProjectMemberAssignRequest,
    ProjectMemberResponse,
    ProjectResponse,
)


def format_project_response(
    db: Session,
    project: Project,
    current_user: Optional[User] = None,
) -> ProjectResponse:
    member_rows = (
        db.query(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .filter(ProjectMember.project_id == project.id)
        .all()
    )
    members: List[ProjectMemberResponse] = []
    current_user_role: Optional[str] = None
    for pm, u in member_rows:
        if current_user and u.id == current_user.id:
            current_user_role = pm.project_role
        members.append(
            ProjectMemberResponse(
                id=pm.id,
                user_id=u.id,
                email=u.email,
                full_name=u.full_name,
                project_role=pm.project_role,
                allowed_classifications=pm.allowed_classifications,
                assigned_at=pm.assigned_at,
            )
        )

    source_count = db.query(SourceDocument).filter(SourceDocument.project_id == project.id).count()
    handover_count = db.query(Handover).filter(Handover.project_id == project.id).count()

    return ProjectResponse(
        id=project.id,
        slug=project.slug,
        name=project.name,
        description=project.description,
        data_classification=project.data_classification,
        created_by=project.created_by,
        created_at=project.created_at,
        member_count=len(members),
        source_count=source_count,
        handover_count=handover_count,
        current_user_role=current_user_role,
        members=members,
    )


def create_project(db: Session, req: ProjectCreateRequest, creator: User) -> ProjectResponse:
    if creator.platform_role == PlatformRole.GUEST_DEMO.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest demo users have read-only access and cannot create projects.",
        )
    existing = db.query(Project).filter(Project.slug == req.slug.strip().lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with slug '{req.slug}' already exists.",
        )

    project = Project(
        slug=req.slug.strip().lower(),
        name=req.name.strip(),
        description=req.description.strip(),
        data_classification=req.data_classification,
        created_by=creator.id,
    )
    db.add(project)
    db.flush()

    # Creator is automatically assigned as PROJECT_LEAD with full classification access
    lead_membership = ProjectMember(
        project_id=project.id,
        user_id=creator.id,
        project_role=ProjectRole.PROJECT_LEAD.value,
        allowed_classifications=["PUBLIC", "INTERNAL", "RESTRICTED"],
    )
    db.add(lead_membership)

    record_audit_event(
        db=db,
        action="PROJECT_CREATED",
        target_type="project",
        target_id=project.id,
        actor=creator,
        actor_role=ProjectRole.PROJECT_LEAD.value,
        project_id=project.id,
        new_state={"slug": project.slug, "name": project.name},
    )
    db.commit()
    db.refresh(project)
    return format_project_response(db, project, creator)


def list_user_projects(db: Session, user: User) -> List[ProjectResponse]:
    projects = (
        db.query(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [format_project_response(db, p, user) for p in projects]


def get_project_for_user(db: Session, project_id: str, user: User) -> ProjectResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    # Verify explicit membership (raises 403 if user is not an explicit member of this project)
    get_project_membership(db, project.id, user)
    return format_project_response(db, project, user)


def assign_project_member(
    db: Session,
    project_id: str,
    req: ProjectMemberAssignRequest,
    actor: User,
) -> ProjectResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    actor_membership = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == actor.id)
        .first()
    )
    is_project_lead = (
        actor_membership is not None
        and actor_membership.project_role == ProjectRole.PROJECT_LEAD.value
    )
    is_platform_admin = actor.platform_role == PlatformRole.ADMIN.value

    if not is_project_lead and not is_platform_admin:
        # Delegate to get_project_membership so standard 403 + audit event are recorded
        get_project_membership(db, project_id, actor, allowed_roles=[ProjectRole.PROJECT_LEAD.value])

    target_user = db.query(User).filter(User.id == req.user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    existing = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == req.user_id)
        .first()
    )
    allowed_levels = [c.value for c in req.allowed_classifications]
    prev_state = None
    if existing:
        prev_state = {
            "project_role": existing.project_role,
            "allowed_classifications": existing.allowed_classifications,
        }
        existing.project_role = req.project_role.value
        existing.allowed_classifications = allowed_levels
    else:
        new_member = ProjectMember(
            project_id=project_id,
            user_id=req.user_id,
            project_role=req.project_role.value,
            allowed_classifications=allowed_levels,
        )
        db.add(new_member)

    audit_action = (
        "ADMIN_PROJECT_MEMBER_ASSIGNED"
        if (is_platform_admin and not is_project_lead)
        else "PROJECT_MEMBER_ASSIGNED"
    )
    audit_actor_role = (
        PlatformRole.ADMIN.value
        if (is_platform_admin and not is_project_lead)
        else ProjectRole.PROJECT_LEAD.value
    )

    record_audit_event(
        db=db,
        action=audit_action,
        target_type="project_member",
        target_id=req.user_id,
        actor=actor,
        actor_role=audit_actor_role,
        project_id=project_id,
        previous_state=prev_state,
        new_state={
            "user_email": target_user.email,
            "project_role": req.project_role.value,
            "allowed_classifications": allowed_levels,
        },
    )
    db.commit()
    return format_project_response(db, project, actor)
