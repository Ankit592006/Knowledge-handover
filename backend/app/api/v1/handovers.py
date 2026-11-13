"""Handovers, Claims, Review, Successor Continuation Plan & Audit Trail API router."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    ensure_guest_demo_user,
    get_current_user,
    get_current_user_or_guest_demo,
    get_project_membership,
    hash_password,
    require_platform_admin,
)
from app.models.entities import Handover, Project, ProjectMember, User
from app.models.enums import PlatformRole, ProjectRole
from app.modules.audit.service import list_audit_events, record_audit_event
from app.modules.handovers.service import (
    acknowledge_handover_receipt,
    answer_clarification_question,
    approve_handover_package,
    build_successor_continuation_plan,
    create_scoped_handover,
    format_handover_draft,
    get_handover_by_id_or_code,
    get_handover_draft_for_user,
    import_sources_into_handover,
    reconstruct_handover_with_agents,
    update_claim_by_reviewer,
)
from app.modules.ingestion.service import seed_payflow_sources_for_project
from app.modules.projects.service import create_project
from app.schemas.api_schemas import (
    AccessClassification,
    AuditLogResponse,
    ClaimOutputSchema,
    ClaimPatchRequest,
    ClarificationAnswerRequest,
    HandoverApproveRequest,
    HandoverCreateRequest,
    HandoverDraftResponse,
    HandoverSourceImportRequest,
    OpenQuestionOutputSchema,
    ProjectCreateRequest,
    SuccessorAcknowledgeRequest,
    SuccessorContinuationPlanResponse,
)

router = APIRouter(tags=["Handovers, AI Reconstruction, Review & Successor"])

PAYFLOW_SYSTEM_OWNER_EMAIL = "demo.system@payflow.demo"


def _ensure_payflow_system_owner(db: Session) -> User:
    """Internal system owner for bootstrapping synthetic PayFlow demo data when invoked by a read-only Guest Demo user."""
    owner = db.query(User).filter(User.email == PAYFLOW_SYSTEM_OWNER_EMAIL).first()
    if not owner:
        owner = User(
            email=PAYFLOW_SYSTEM_OWNER_EMAIL,
            password_hash=hash_password("PayFlow_Internal_System_Owner_#2026!"),
            full_name="PayFlow Demo System Lead",
            platform_role=PlatformRole.STANDARD.value,
            is_active=True,
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)
    return owner


@router.get("/handovers", response_model=List[HandoverDraftResponse])
def list_handovers_endpoint(
    project_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> List[HandoverDraftResponse]:
    query = db.query(Handover)
    if project_id:
        get_project_membership(db, project_id, current_user)
        query = query.filter(Handover.project_id == project_id)
    else:
        member_proj_ids = [
            pm.project_id
            for pm in db.query(ProjectMember).filter(ProjectMember.user_id == current_user.id).all()
        ]
        if not member_proj_ids:
            return []
        query = query.filter(Handover.project_id.in_(member_proj_ids))

    rows = query.order_by(Handover.updated_at.desc()).all()
    results: List[HandoverDraftResponse] = []
    for h in rows:
        membership = get_project_membership(db, h.project_id, current_user)
        if (
            membership.project_role == ProjectRole.SUCCESSOR.value
            and h.status not in ("approved", "acknowledged")
        ):
            continue
        results.append(format_handover_draft(db, h, allowed_classifications=membership.allowed_classifications))
    return results


@router.post("/handovers", response_model=HandoverDraftResponse, status_code=status.HTTP_201_CREATED)
def create_handover_endpoint(
    req: HandoverCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HandoverDraftResponse:
    return create_scoped_handover(db, req, current_user)


@router.post("/handovers/{handover_id}/sources/import", response_model=HandoverDraftResponse)
def import_handover_sources_endpoint(
    handover_id: str,
    req: HandoverSourceImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HandoverDraftResponse:
    return import_sources_into_handover(db, handover_id, req, current_user)


@router.post("/handovers/{handover_id}/reconstruct", response_model=HandoverDraftResponse)
def reconstruct_handover_endpoint(
    handover_id: str,
    force_failure_agent: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HandoverDraftResponse:
    return reconstruct_handover_with_agents(
        db,
        handover_id,
        current_user,
        force_failure_agent=force_failure_agent,
    )


@router.get("/handovers/{handover_id}/status")
def handover_processing_status_endpoint(
    handover_id: str,
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    handover = get_handover_by_id_or_code(db, handover_id)
    get_project_membership(db, handover.project_id, current_user)
    return {
        "handoverId": handover.handover_code,
        "status": handover.status,
        "currentVersion": handover.current_version,
        "agentTelemetry": handover.agent_telemetry or {},
        "updatedAt": handover.updated_at.isoformat(),
    }


@router.get("/handovers/{handover_id}/draft", response_model=HandoverDraftResponse)
def get_handover_draft_endpoint(
    handover_id: str,
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> HandoverDraftResponse:
    return get_handover_draft_for_user(db, handover_id, current_user)


@router.patch("/claims/{claim_id}", response_model=ClaimOutputSchema)
def patch_claim_endpoint(
    claim_id: str,
    req: ClaimPatchRequest,
    handover_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClaimOutputSchema:
    return update_claim_by_reviewer(db, claim_id, req, current_user, handover_id=handover_id)


@router.post(
    "/handovers/{handover_id}/clarifications/{question_id}",
    response_model=OpenQuestionOutputSchema,
)
def answer_clarification_endpoint(
    handover_id: str,
    question_id: str,
    req: ClarificationAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OpenQuestionOutputSchema:
    return answer_clarification_question(db, handover_id, question_id, req, current_user)


@router.post("/handovers/{handover_id}/approve", response_model=HandoverDraftResponse)
def approve_handover_endpoint(
    handover_id: str,
    req: HandoverApproveRequest = HandoverApproveRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HandoverDraftResponse:
    return approve_handover_package(db, handover_id, req, current_user)


@router.get(
    "/handovers/{handover_id}/successor-view",
    response_model=SuccessorContinuationPlanResponse,
)
def get_successor_view_endpoint(
    handover_id: str,
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> SuccessorContinuationPlanResponse:
    return build_successor_continuation_plan(db, handover_id, current_user)


@router.post("/handovers/{handover_id}/acknowledge", response_model=HandoverDraftResponse)
def acknowledge_handover_endpoint(
    handover_id: str,
    req: SuccessorAcknowledgeRequest = SuccessorAcknowledgeRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HandoverDraftResponse:
    return acknowledge_handover_receipt(db, handover_id, req, current_user)


@router.get("/handovers/{handover_id}/audit-logs", response_model=List[AuditLogResponse])
def get_handover_audit_logs_endpoint(
    handover_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AuditLogResponse]:
    handover = get_handover_by_id_or_code(db, handover_id)
    get_project_membership(
        db,
        handover.project_id,
        current_user,
        allowed_roles=[ProjectRole.PROJECT_LEAD.value, ProjectRole.REVIEWER_SME.value],
    )
    events = list_audit_events(db, handover_id=handover.id)
    return [AuditLogResponse.model_validate(e) for e in events]


@router.get("/audit-logs", response_model=List[AuditLogResponse])
def list_project_audit_logs_endpoint(
    project_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AuditLogResponse]:
    if project_id:
        get_project_membership(
            db,
            project_id,
            current_user,
            allowed_roles=[ProjectRole.PROJECT_LEAD.value, ProjectRole.REVIEWER_SME.value],
        )
    else:
        require_platform_admin(current_user, db)
        record_audit_event(
            db=db,
            action="ADMIN_GLOBAL_AUDIT_LOGS_VIEWED",
            target_type="audit_log",
            target_id="all",
            actor=current_user,
            actor_role=PlatformRole.ADMIN.value,
        )
        db.commit()
    events = list_audit_events(db, project_id=project_id)
    return [AuditLogResponse.model_validate(e) for e in events]


@router.get("/handovers/{handover_id}/export")
def export_handover_package_endpoint(
    handover_id: str,
    format_type: str = Query(default="json", pattern="^(json|markdown)$"),
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    plan = build_successor_continuation_plan(db, handover_id, current_user)
    if format_type == "markdown":
        lines = [
            f"# {plan.title} ({plan.handoverId} — v{plan.version})",
            f"**Access Scope Applied:** `{', '.join(plan.accessScopeApplied)}` | **Restricted Sources Filtered:** {plan.restrictedSourcesFilteredOut}",
            f"**Approval Status:** `{plan.approval.status}` by `{plan.approval.reviewer}` at `{plan.approval.approvedAt}`",
            "",
            "## 1. Evidence-Linked Claims",
        ]
        for c in plan.claims:
            ev_ids = ", ".join(e.sourceId for e in c.evidence)
            lines.append(
                f"- **[{c.claimId}] ({c.type} | Status: `{c.status}` | Owner: `{c.owner or 'UNKNOWN'}`):** {c.text} *(Sources: {ev_ids})*"
            )
        lines.append("\n## 2. Prioritised Next Actions")
        for a in plan.nextActions:
            lines.append(
                f"{a.priorityRank}. **[{a.priority.upper()}]** {a.action} *(Owner: {a.owner or 'Unassigned'}, Claims: {', '.join(a.evidenceClaimIds)})*"
            )
        lines.append("\n## 3. Open Questions")
        for q in plan.openQuestions:
            lines.append(
                f"- **{q.question}** — Status: `{q.status}` | Answer: {q.answerText or 'Pending human clarification'}"
            )
        return {
            "handoverId": plan.handoverId,
            "format": "markdown",
            "content": "\n".join(lines),
        }
    return {
        "handoverId": plan.handoverId,
        "format": "json",
        "payload": plan.model_dump(mode="json"),
    }


@router.post("/demo/bootstrap-payflow", response_model=HandoverDraftResponse)
def bootstrap_payflow_demo_endpoint(
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> HandoverDraftResponse:
    """One-click idempotent PayFlow demo workspace initializer for judges and testers."""
    is_guest = current_user.platform_role == PlatformRole.GUEST_DEMO.value
    system_lead = _ensure_payflow_system_owner(db)

    project = db.query(Project).filter(Project.slug == "payflow").first()
    if not project:
        proj_resp = create_project(
            db,
            ProjectCreateRequest(
                slug="payflow",
                name="PayFlow Payment Gateway & Settlement Service",
                description="Synthetic microservice project with intentional conflicting statuses, stale docs, unknown owners, and restricted records.",
                data_classification="synthetic_demo",
            ),
            system_lead,
        )
        project_id = proj_resp.id
    else:
        project_id = project.id
        existing_sys_mem = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == system_lead.id)
            .first()
        )
        if not existing_sys_mem:
            db.add(
                ProjectMember(
                    project_id=project_id,
                    user_id=system_lead.id,
                    project_role=ProjectRole.PROJECT_LEAD.value,
                    allowed_classifications=[
                        AccessClassification.PUBLIC.value,
                        AccessClassification.INTERNAL.value,
                        AccessClassification.RESTRICTED.value,
                    ],
                )
            )
            db.commit()

    if is_guest:
        ensure_guest_demo_user(db)
    else:
        existing_user_mem = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == current_user.id)
            .first()
        )
        if not existing_user_mem:
            db.add(
                ProjectMember(
                    project_id=project_id,
                    user_id=current_user.id,
                    project_role=ProjectRole.PROJECT_LEAD.value,
                    allowed_classifications=[
                        AccessClassification.PUBLIC.value,
                        AccessClassification.INTERNAL.value,
                    ],
                )
            )
            db.commit()

    seed_payflow_sources_for_project(db, project_id, system_lead)

    existing_handover = (
        db.query(Handover)
        .filter(Handover.handover_code == "payflow-handover-001")
        .first()
    )
    if not existing_handover:
        draft = create_scoped_handover(
            db,
            HandoverCreateRequest(
                project_id=project_id,
                handover_code="payflow-handover-001",
                title="PayFlow v2.1 Payment Integration Handover",
                scope_description="Transition package for payment orchestration, 3DS2 timeout handling, and settlement ledger migrations.",
                departing_role="Senior Payment Integration Engineer (Arjun Mehta)",
                allowed_classifications=[
                    AccessClassification.PUBLIC,
                    AccessClassification.INTERNAL,
                ],
            ),
            system_lead,
        )
        handover_code = draft.handoverId
    else:
        handover_code = existing_handover.handover_code

    import_sources_into_handover(
        db,
        handover_code,
        HandoverSourceImportRequest(source_ids=[], seed_payflow_if_empty=True),
        system_lead,
    )
    reconstruct_handover_with_agents(db, handover_code, system_lead)
    return get_handover_draft_for_user(db, handover_code, current_user)
