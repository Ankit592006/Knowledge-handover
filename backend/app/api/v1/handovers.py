"""Handovers, Claims, Review, Successor Continuation Plan & Audit Trail API router."""

from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_and_store_refresh_token,
    ensure_guest_demo_user,
    get_current_user,
    get_current_user_or_guest_demo,
    get_project_membership,
    hash_password,
    require_platform_admin,
)
from app.models.entities import (
    AuditLog,
    Handover,
    HandoverSource,
    HandoverVersion,
    Project,
    ProjectMember,
    SourceDocument,
    User,
)
from app.models.enums import PlatformRole, ProjectRole
from app.modules.audit.service import list_audit_events, record_audit_event
from app.modules.auth.service import build_user_response
from app.modules.evaluation.harness import run_payflow_evaluation_harness
from app.modules.handovers.service import (
    acknowledge_handover_receipt,
    answer_clarification_question,
    approve_handover_package,
    build_evidence_backed_dependency_map,
    build_successor_continuation_plan,
    compare_handover_versions,
    create_scoped_handover,
    format_handover_draft,
    get_handover_by_id_or_code,
    get_handover_draft_for_user,
    import_sources_into_handover,
    reconstruct_handover_with_agents,
    update_claim_by_reviewer,
)
from app.modules.ingestion.service import (
    PAYFLOW_SYNTHETIC_SOURCES,
    seed_payflow_sources_for_project,
)
from app.modules.projects.service import create_project
from app.schemas.api_schemas import (
    AccessClassification,
    AuditLogResponse,
    AuthTokenResponse,
    ClaimOutputSchema,
    ClaimPatchRequest,
    ClarificationAnswerRequest,
    DemoRoleSwitchRequest,
    DependencyMapResponse,
    EvaluationHarnessResponse,
    HandoverApproveRequest,
    HandoverCreateRequest,
    HandoverDraftResponse,
    HandoverSourceImportRequest,
    HandoverVersionDiffResponse,
    OpenQuestionOutputSchema,
    ProjectCreateRequest,
    SuccessorAcknowledgeRequest,
    SuccessorContinuationPlanResponse,
)

router = APIRouter(tags=["Handovers, AI Reconstruction, Review & Successor"])

PAYFLOW_SYSTEM_OWNER_EMAIL = "demo.system@payflow.demo"
PAYFLOW_DEMO_PASSWORD = "PayFlow_Demo_Role_Password_#2026!"

PAYFLOW_DEMO_PERSONAS: Dict[str, Dict[str, Any]] = {
    ProjectRole.PROJECT_LEAD.value: {
        "email": "preeti.lead@payflow.demo",
        "full_name": "Preeti Satish Mittal (Project Lead)",
        "project_role": ProjectRole.PROJECT_LEAD.value,
        "allowed_classifications": [
            AccessClassification.PUBLIC.value,
            AccessClassification.INTERNAL.value,
            AccessClassification.RESTRICTED.value,
        ],
    },
    ProjectRole.OUTGOING_DEV.value: {
        "email": "arjun.outgoing@payflow.demo",
        "full_name": "Arjun Mehta (Outgoing Engineer)",
        "project_role": ProjectRole.OUTGOING_DEV.value,
        "allowed_classifications": [
            AccessClassification.PUBLIC.value,
            AccessClassification.INTERNAL.value,
        ],
    },
    ProjectRole.REVIEWER_SME.value: {
        "email": "kavita.reviewer@payflow.demo",
        "full_name": "Kavita Rao (Reviewer / SME)",
        "project_role": ProjectRole.REVIEWER_SME.value,
        "allowed_classifications": [
            AccessClassification.PUBLIC.value,
            AccessClassification.INTERNAL.value,
        ],
    },
    ProjectRole.SUCCESSOR.value: {
        "email": "ankit.successor@payflow.demo",
        "full_name": "Ankit Chaudhari (Incoming Successor)",
        "project_role": ProjectRole.SUCCESSOR.value,
        "allowed_classifications": [
            AccessClassification.PUBLIC.value,
            AccessClassification.INTERNAL.value,
        ],
    },
}


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


def _ensure_payflow_demo_workspace(
    db: Session,
    reset_reconstruction: bool = False,
    actor: Optional[User] = None,
) -> Tuple[str, str, Dict[str, User]]:
    """Provision the synthetic PayFlow project, 4 canonical role personas, seeded sources, and handover draft."""
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

    persona_users: Dict[str, User] = {}
    for role_key, cfg in PAYFLOW_DEMO_PERSONAS.items():
        u = db.query(User).filter(User.email == cfg["email"]).first()
        if not u:
            u = User(
                email=cfg["email"],
                password_hash=hash_password(PAYFLOW_DEMO_PASSWORD),
                full_name=cfg["full_name"],
                platform_role=PlatformRole.STANDARD.value,
                is_active=True,
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        pm = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == u.id)
            .first()
        )
        if not pm:
            pm = ProjectMember(
                project_id=project_id,
                user_id=u.id,
                project_role=cfg["project_role"],
                allowed_classifications=list(cfg["allowed_classifications"]),
            )
            db.add(pm)
            db.commit()
        elif pm.project_role != cfg["project_role"] or pm.allowed_classifications != list(cfg["allowed_classifications"]):
            pm.project_role = cfg["project_role"]
            pm.allowed_classifications = list(cfg["allowed_classifications"])
            db.commit()
        persona_users[role_key] = u

    if actor is not None and actor.platform_role != PlatformRole.GUEST_DEMO.value:
        existing_actor_mem = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == actor.id)
            .first()
        )
        if not existing_actor_mem:
            db.add(
                ProjectMember(
                    project_id=project_id,
                    user_id=actor.id,
                    project_role=ProjectRole.PROJECT_LEAD.value,
                    allowed_classifications=[
                        AccessClassification.PUBLIC.value,
                        AccessClassification.INTERNAL.value,
                    ],
                )
            )
            db.commit()

    canonical_ids = {item["stable_source_id"] for item in PAYFLOW_SYNTHETIC_SOURCES}
    existing_sources = (
        db.query(SourceDocument).filter(SourceDocument.project_id == project_id).all()
    )
    existing_canonical_ids = {
        s.stable_source_id for s in existing_sources if s.stable_source_id in canonical_ids
    }
    if reset_reconstruction:
        extra_sources = [s for s in existing_sources if s.stable_source_id not in canonical_ids]
        for extra_src in extra_sources:
            db.query(HandoverSource).filter(HandoverSource.source_document_id == extra_src.id).delete()
            db.delete(extra_src)
        db.flush()

    if reset_reconstruction or len(existing_canonical_ids) < len(canonical_ids):
        seed_payflow_sources_for_project(db, project_id, system_lead)

    existing_handover = (
        db.query(Handover)
        .filter(Handover.handover_code == "payflow-handover-001")
        .first()
    )
    created_new = False
    if not existing_handover:
        draft = create_scoped_handover(
            db,
            HandoverCreateRequest(
                project_id=project_id,
                handover_code="payflow-handover-001",
                title="PayFlow v2.1 Payment Integration Handover",
                scope_description="Transition package for payment orchestration, 3DS2 timeout handling, and settlement ledger migrations.",
                departing_role="Senior Payment Integration Engineer (Arjun Mehta)",
                outgoing_user_id=persona_users[ProjectRole.OUTGOING_DEV.value].id,
                successor_user_id=persona_users[ProjectRole.SUCCESSOR.value].id,
                allowed_classifications=[
                    AccessClassification.PUBLIC,
                    AccessClassification.INTERNAL,
                ],
            ),
            system_lead,
        )
        handover_code = draft.handoverId
        created_new = True
    else:
        handover_code = existing_handover.handover_code

    handover_obj = get_handover_by_id_or_code(db, handover_code)
    needs_reconstruction = created_new or reset_reconstruction or len(handover_obj.claims) == 0
    if needs_reconstruction:
        previous_handover_state = {
            "status": handover_obj.status,
            "current_version": handover_obj.current_version,
            "approved_by": handover_obj.approved_by,
            "approved_at": handover_obj.approved_at.isoformat() if handover_obj.approved_at else None,
            "acknowledged_by": handover_obj.acknowledged_by,
            "acknowledged_at": handover_obj.acknowledged_at.isoformat() if handover_obj.acknowledged_at else None,
        }
        if reset_reconstruction:
            # Reset workflow version snapshots to v1 while strictly preserving all immutable AuditLog records
            db.query(HandoverVersion).filter(HandoverVersion.handover_id == handover_obj.id).delete()
            db.flush()
        import_sources_into_handover(
            db,
            handover_code,
            HandoverSourceImportRequest(source_ids=[], seed_payflow_if_empty=True),
            system_lead,
        )
        reconstruct_handover_with_agents(db, handover_code, system_lead)
        if reset_reconstruction:
            reset_actor = actor or system_lead
            record_audit_event(
                db=db,
                action="DEMO_HANDOVER_RESET_TO_V1",
                target_type="handover",
                target_id=handover_obj.handover_code,
                actor=reset_actor,
                project_id=project_id,
                handover_id=handover_obj.id,
                previous_state=previous_handover_state,
                new_state={
                    "status": handover_obj.status,
                    "current_version": handover_obj.current_version,
                    "approval_status": "not_approved",
                    "reset_by_email": reset_actor.email,
                },
            )
            db.commit()

    return project_id, handover_code, persona_users


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
    events = (
        db.query(AuditLog)
        .filter(
            (AuditLog.handover_id == handover.id)
            | (AuditLog.project_id == handover.project_id)
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(500)
        .all()
    )
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
    reset: bool = Query(default=False, description="Force fresh 3-agent reconstruction of PayFlow handover draft"),
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> HandoverDraftResponse:
    """One-click idempotent PayFlow demo workspace initializer for judges and testers."""
    is_guest = current_user.platform_role == PlatformRole.GUEST_DEMO.value
    project_id, handover_code, _ = _ensure_payflow_demo_workspace(
        db, reset_reconstruction=reset, actor=current_user
    )

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

    return get_handover_draft_for_user(db, handover_code, current_user)


@router.post("/demo/switch-role", response_model=AuthTokenResponse)
def switch_payflow_demo_role_endpoint(
    req: DemoRoleSwitchRequest,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    """Authenticate as one of the four canonical PayFlow demo role personas with genuine JWT and DB permissions."""
    project_id, handover_code, persona_users = _ensure_payflow_demo_workspace(
        db, reset_reconstruction=False
    )
    target_role = req.project_role.value
    persona_user = persona_users[target_role]
    settings = get_settings()
    access_token = create_access_token(persona_user)
    refresh_token = create_and_store_refresh_token(db, persona_user)
    record_audit_event(
        db=db,
        action="DEMO_ROLE_SESSION_SWITCHED",
        target_type="user",
        target_id=persona_user.id,
        actor=persona_user,
        actor_role=target_role,
        project_id=project_id,
        new_state={
            "email": persona_user.email,
            "project_role": target_role,
            "handover_code": handover_code,
        },
    )
    db.commit()
    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=build_user_response(db, persona_user),
    )


# -----------------------------------------------------------------------------
# Round 3 Improvement 2 & 3 Endpoints: Evaluation Harness, Dependency Map, Version Diff
# -----------------------------------------------------------------------------
@router.get("/evaluation/payflow-benchmark", response_model=EvaluationHarnessResponse)
def get_payflow_evaluation_benchmark_endpoint() -> EvaluationHarnessResponse:
    """Run the repeatable Ground-Truth Evaluation Harness comparing Baseline (L6.1) vs Post-Improvement (L6.2)."""
    return run_payflow_evaluation_harness()


@router.get(
    "/handovers/{handover_id}/dependency-map",
    response_model=DependencyMapResponse,
)
def get_handover_dependency_map_endpoint(
    handover_id: str,
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> DependencyMapResponse:
    """Return the Evidence-Backed Dependency Map of people, components, teams, tasks, and unknown owner gaps."""
    return build_evidence_backed_dependency_map(db, handover_id, current_user)


@router.get(
    "/handovers/{handover_id}/versions/compare",
    response_model=HandoverVersionDiffResponse,
)
def compare_handover_versions_endpoint(
    handover_id: str,
    base_version: int = Query(default=1, ge=1),
    target_version: Optional[int] = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user_or_guest_demo),
    db: Session = Depends(get_db),
) -> HandoverVersionDiffResponse:
    """Side-by-side comparison of two handover versions (e.g., v1 Initial Draft vs. v2 Approved Package)."""
    return compare_handover_versions(
        db=db,
        handover_id_or_code=handover_id,
        user=current_user,
        base_version=base_version,
        target_version=target_version,
    )
