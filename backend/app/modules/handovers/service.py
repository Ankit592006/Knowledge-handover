"""Handover Lifecycle, AI Reconstruction, Human Review, Approval Gate & Successor Continuation Plan (Modules 12, 13, 14, 16)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agents.orchestrator.workflow import execute_handover_orchestration
from app.core.security import get_project_membership
from app.models.entities import (
    Claim,
    ClaimEvidenceLink,
    ClarificationQuestion,
    Handover,
    HandoverSource,
    HandoverVersion,
    NextAction,
    Project,
    RiskOrDependency,
    SourceDocument,
    User,
)
from app.models.enums import (
    ClaimReviewState,
    EvidenceStatus,
    HandoverStatus,
    ProjectRole,
)
from app.modules.audit.service import record_audit_event
from app.modules.ingestion.service import (
    format_source_document,
    retrieve_scoped_chunks,
    seed_payflow_sources_for_project,
)
from app.modules.validation.service import validate_claims_against_database
from app.schemas.api_schemas import (
    ApprovalBlockSchema,
    ClaimOutputSchema,
    ClaimPatchRequest,
    ClarificationAnswerRequest,
    ConflictPairSchema,
    EvidenceReferenceSchema,
    HandoverApproveRequest,
    HandoverCreateRequest,
    HandoverDraftResponse,
    HandoverSourceImportRequest,
    NextActionOutputSchema,
    OpenQuestionOutputSchema,
    RiskDependencyOutputSchema,
    SuccessorAcknowledgeRequest,
    SuccessorContinuationPlanResponse,
)


def _format_claim_output(claim: Claim) -> ClaimOutputSchema:
    ev_refs: List[EvidenceReferenceSchema] = [
        EvidenceReferenceSchema(
            sourceId=link.stable_source_id,
            sourceType=link.source_type,
            location=link.location,
            excerpt=link.excerpt,
            charStart=link.char_start,
            charEnd=link.char_end,
            versionTag=link.version_tag,
            sourceUpdatedAt=link.source_updated_at,
            deterministicVerified=link.deterministic_verified,
        )
        for link in claim.evidence_links
    ]
    conflicts: List[ConflictPairSchema] = []
    for c in claim.conflict_details or []:
        conflicts.append(
            ConflictPairSchema(
                conflictType=c.get("conflict_type", "STATUS_MISMATCH"),
                sourceAId=c.get("source_a_id", ""),
                sourceAExcerpt=c.get("source_a_excerpt", ""),
                sourceATimestamp=str(c.get("source_a_timestamp", "")),
                sourceBId=c.get("source_b_id", ""),
                sourceBExcerpt=c.get("source_b_excerpt", ""),
                sourceBTimestamp=str(c.get("source_b_timestamp", "")),
                explanation=c.get("explanation", ""),
            )
        )

    return ClaimOutputSchema(
        id=claim.id,
        claimId=claim.claim_code,
        type=claim.claim_type,
        text=claim.text,
        rationale=claim.rationale,
        owner=claim.owner_name,
        taskStatus=claim.task_status,
        dueDate=claim.due_date,
        status=claim.status,
        evidence=ev_refs,
        uncertainty=claim.uncertainty_flags or [],
        conflicts=conflicts,
        reviewState=claim.review_state,
        extractionConfidence=claim.extraction_confidence,
        isAiGenerated=claim.is_ai_generated,
        reviewerNotes=claim.reviewer_notes,
        reviewedBy=claim.reviewed_by,
        reviewedAt=claim.reviewed_at,
    )


def format_handover_draft(
    db: Session,
    handover: Handover,
    allowed_classifications: Optional[List[str]] = None,
) -> HandoverDraftResponse:
    project = db.query(Project).filter(Project.id == handover.project_id).first()
    effective_scope = set(allowed_classifications or handover.allowed_classifications)

    scoped_docs: List[SourceDocument] = [
        hs.source_document
        for hs in handover.scoped_sources
        if hs.source_document and hs.source_document.access_level in effective_scope
    ]

    claims_out: List[ClaimOutputSchema] = []
    for c in sorted(handover.claims, key=lambda x: x.claim_code):
        # Filter out claims that rely exclusively on restricted sources outside effective_scope
        visible_links = [
            lnk
            for lnk in c.evidence_links
            if any(sd.id == lnk.source_document_id for sd in scoped_docs)
        ]
        if c.evidence_links and not visible_links:
            continue
        claims_out.append(_format_claim_output(c))

    risks_out: List[RiskDependencyOutputSchema] = [
        RiskDependencyOutputSchema(
            id=r.id,
            recordType=r.record_type,
            title=r.title,
            description=r.description,
            severity=r.severity,
            sourceEntity=r.source_entity,
            targetEntity=r.target_entity,
            workaround=r.workaround,
            owner=r.owner_name,
            status=r.status,
            evidenceSourceIds=r.evidence_source_ids or [],
            evidenceClaimIds=r.evidence_claim_ids or [],
        )
        for r in handover.risks_and_dependencies
    ]

    questions_out: List[OpenQuestionOutputSchema] = [
        OpenQuestionOutputSchema(
            id=q.id,
            relatedClaimId=q.related_claim_code,
            question=q.question,
            reason=q.reason,
            status=q.status,
            answerText=q.answer_text,
            answeredBy=q.answered_by,
            answeredAt=q.answered_at,
        )
        for q in handover.open_questions
    ]

    actions_out: List[NextActionOutputSchema] = [
        NextActionOutputSchema(
            id=a.id,
            priorityRank=a.priority_rank,
            priority=a.priority,
            action=a.action,
            reason=a.reason,
            owner=a.owner,
            evidenceClaimIds=a.evidence_claim_ids or [],
        )
        for a in sorted(handover.next_actions, key=lambda x: x.priority_rank)
    ]

    reviewer_email = None
    if handover.approved_by:
        rev_user = db.query(User).filter(User.id == handover.approved_by).first()
        reviewer_email = rev_user.email if rev_user else handover.approved_by

    ack_email = None
    if handover.acknowledged_by:
        ack_user = db.query(User).filter(User.id == handover.acknowledged_by).first()
        ack_email = ack_user.email if ack_user else handover.acknowledged_by

    approval_status = "not_approved"
    if handover.status == HandoverStatus.ACKNOWLEDGED.value:
        approval_status = "acknowledged"
    elif handover.status == HandoverStatus.APPROVED.value or handover.approved_at is not None:
        approval_status = "approved"

    return HandoverDraftResponse(
        id=handover.id,
        handoverId=handover.handover_code,
        projectId=handover.project_id,
        title=handover.title,
        scopeDescription=handover.scope_description,
        departingRole=handover.departing_role,
        status=handover.status,
        currentVersion=handover.current_version,
        project={
            "name": project.name if project else "PayFlow",
            "dataClassification": project.data_classification if project else "synthetic_demo",
            "asOf": handover.updated_at.isoformat(),
        },
        summary={
            "text": handover.summary_text or f"Scoped handover workspace for {handover.title}",
            "reviewState": "approved" if approval_status in ("approved", "acknowledged") else "draft",
        },
        claims=claims_out,
        risksAndDependencies=risks_out,
        openQuestions=questions_out,
        nextActions=actions_out,
        approval=ApprovalBlockSchema(
            status=approval_status,
            reviewer=reviewer_email,
            approvedAt=handover.approved_at,
            acknowledgedBy=ack_email,
            acknowledgedAt=handover.acknowledged_at,
            acknowledgementNotes=handover.acknowledgement_notes,
        ),
        agentTelemetry=handover.agent_telemetry or {},
        scopedSources=[format_source_document(d, include_chunks=False) for d in scoped_docs],
    )


def create_scoped_handover(
    db: Session,
    req: HandoverCreateRequest,
    actor: User,
) -> HandoverDraftResponse:
    project = db.query(Project).filter(Project.id == req.project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    get_project_membership(
        db,
        project.id,
        actor,
        allowed_roles=[ProjectRole.PROJECT_LEAD.value, ProjectRole.OUTGOING_DEV.value],
    )

    existing_count = db.query(Handover).filter(Handover.project_id == project.id).count()
    handover_code = req.handover_code or f"{project.slug}-handover-{existing_count + 1:03d}"
    if db.query(Handover).filter(Handover.handover_code == handover_code).first():
        handover_code = f"{handover_code}-{existing_count + 1}"

    allowed_levels = [c.value for c in req.allowed_classifications]
    handover = Handover(
        handover_code=handover_code,
        project_id=project.id,
        title=req.title.strip(),
        scope_description=req.scope_description.strip(),
        departing_role=req.departing_role.strip(),
        outgoing_user_id=req.outgoing_user_id or actor.id,
        successor_user_id=req.successor_user_id,
        allowed_classifications=allowed_levels,
        status=HandoverStatus.INITIATED.value,
        summary_text="Scoped handover workspace created. Connect sources and run AI reconstruction.",
        created_by=actor.id,
    )
    db.add(handover)
    db.flush()

    if req.source_ids:
        docs = (
            db.query(SourceDocument)
            .filter(
                SourceDocument.project_id == project.id,
                (SourceDocument.id.in_(req.source_ids))
                | (SourceDocument.stable_source_id.in_(req.source_ids)),
            )
            .all()
        )
        for doc in docs:
            db.add(HandoverSource(handover_id=handover.id, source_document_id=doc.id))
        if docs:
            handover.status = HandoverStatus.SOURCES_CONNECTED.value

    record_audit_event(
        db=db,
        action="HANDOVER_CREATED",
        target_type="handover",
        target_id=handover.handover_code,
        actor=actor,
        project_id=project.id,
        handover_id=handover.id,
        new_state={
            "handover_code": handover.handover_code,
            "allowed_classifications": allowed_levels,
            "initial_sources_count": len(req.source_ids),
        },
    )
    db.commit()
    db.refresh(handover)
    return format_handover_draft(db, handover)


def get_handover_by_id_or_code(db: Session, handover_id_or_code: str) -> Handover:
    handover = (
        db.query(Handover)
        .filter(
            (Handover.id == handover_id_or_code)
            | (Handover.handover_code == handover_id_or_code)
        )
        .first()
    )
    if not handover:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover not found.")
    return handover


def import_sources_into_handover(
    db: Session,
    handover_id_or_code: str,
    req: HandoverSourceImportRequest,
    actor: User,
) -> HandoverDraftResponse:
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    get_project_membership(
        db,
        handover.project_id,
        actor,
        allowed_roles=[ProjectRole.PROJECT_LEAD.value, ProjectRole.OUTGOING_DEV.value],
    )

    project_sources = (
        db.query(SourceDocument)
        .filter(SourceDocument.project_id == handover.project_id)
        .all()
    )
    if not project_sources and req.seed_payflow_if_empty:
        seed_payflow_sources_for_project(db, handover.project_id, actor)
        project_sources = (
            db.query(SourceDocument)
            .filter(SourceDocument.project_id == handover.project_id)
            .all()
        )

    if req.source_ids:
        selected_docs = [
            d
            for d in project_sources
            if d.id in req.source_ids or d.stable_source_id in req.source_ids
        ]
    else:
        # Select all project sources within the handover's allowed classification levels
        selected_docs = [
            d for d in project_sources if d.access_level in handover.allowed_classifications
        ]

    db.query(HandoverSource).filter(HandoverSource.handover_id == handover.id).delete()
    for doc in selected_docs:
        db.add(HandoverSource(handover_id=handover.id, source_document_id=doc.id))

    handover.status = HandoverStatus.SOURCES_CONNECTED.value
    record_audit_event(
        db=db,
        action="HANDOVER_SOURCES_IMPORTED",
        target_type="handover",
        target_id=handover.handover_code,
        actor=actor,
        project_id=handover.project_id,
        handover_id=handover.id,
        new_state={"imported_source_ids": [d.stable_source_id for d in selected_docs]},
    )
    db.commit()
    db.refresh(handover)
    return format_handover_draft(db, handover)


def reconstruct_handover_with_agents(
    db: Session,
    handover_id_or_code: str,
    actor: User,
    force_failure_agent: Optional[str] = None,
) -> HandoverDraftResponse:
    """Workflow C: Execute permission-filtered RAG retrieval, LangGraph 3-agent orchestration, and deterministic DB validation."""
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    get_project_membership(
        db,
        handover.project_id,
        actor,
        allowed_roles=[
            ProjectRole.PROJECT_LEAD.value,
            ProjectRole.OUTGOING_DEV.value,
            ProjectRole.REVIEWER_SME.value,
        ],
    )

    scoped_doc_ids = [hs.source_document_id for hs in handover.scoped_sources]
    if not scoped_doc_ids:
        # Auto-import authorised sources if none bound yet
        import_sources_into_handover(
            db,
            handover.id,
            HandoverSourceImportRequest(source_ids=[], seed_payflow_if_empty=True),
            actor,
        )
        db.refresh(handover)
        scoped_doc_ids = [hs.source_document_id for hs in handover.scoped_sources]

    handover.status = HandoverStatus.RECONSTRUCTING.value
    db.flush()

    # Step 1: Permission-filtered RAG retrieval (enforces allowed_classifications BEFORE passing to LLM)
    passages = retrieve_scoped_chunks(
        db=db,
        project_id=handover.project_id,
        scoped_source_doc_ids=scoped_doc_ids,
        allowed_classifications=handover.allowed_classifications,
        query_text=f"{handover.title} {handover.scope_description} decisions tasks blockers dependencies risks owners",
        top_k=25,
    )

    project = db.query(Project).filter(Project.id == handover.project_id).first()

    # Step 2: Execute LangGraph 3-Agent Orchestrator
    final_state = execute_handover_orchestration(
        {
            "handover_id": handover.id,
            "handover_code": handover.handover_code,
            "project_id": handover.project_id,
            "project_name": project.name if project else "PayFlow",
            "departing_role": handover.departing_role,
            "allowed_classifications": handover.allowed_classifications,
            "scoped_source_ids": scoped_doc_ids,
            "retrieved_passages": passages,
            "force_failure_agent": force_failure_agent,
        }
    )

    if final_state.get("halted") or final_state.get("errors"):
        handover.status = HandoverStatus.FAILED.value
        handover.agent_telemetry = final_state.get("agent_telemetry", {})
        record_audit_event(
            db=db,
            action="HANDOVER_RECONSTRUCTION_HALTED",
            target_type="handover",
            target_id=handover.handover_code,
            actor=actor,
            project_id=handover.project_id,
            handover_id=handover.id,
            new_state={"errors": final_state.get("errors", [])},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Agent orchestration halted; partial output blocked from publication.",
                "errors": final_state.get("errors", []),
            },
        )

    # Step 3: Deterministic Backend Validation (L6 Trust Boundary)
    validated_claims, val_summary = validate_claims_against_database(
        db=db,
        project_id=handover.project_id,
        allowed_source_doc_ids=set(scoped_doc_ids),
        allowed_classifications=set(handover.allowed_classifications),
        candidate_claims=final_state.get("candidate_claims", []),
        verification_map=final_state.get("verification_map", {}),
    )

    # Clear previous draft artefacts and persist validated records
    db.query(Claim).filter(Claim.handover_id == handover.id).delete()
    db.query(RiskOrDependency).filter(RiskOrDependency.handover_id == handover.id).delete()
    db.query(ClarificationQuestion).filter(ClarificationQuestion.handover_id == handover.id).delete()
    db.query(NextAction).filter(NextAction.handover_id == handover.id).delete()
    db.flush()

    for vc in validated_claims:
        claim_entity = Claim(
            claim_code=vc["claim_code"],
            handover_id=handover.id,
            claim_type=vc["claim_type"],
            text=vc["text"],
            rationale=vc.get("rationale"),
            owner_name=vc.get("owner_name"),
            task_status=vc.get("task_status"),
            due_date=vc.get("due_date"),
            status=vc["status"],
            review_state=ClaimReviewState.PENDING.value,
            extraction_confidence=vc.get("extraction_confidence", 0.85),
            uncertainty_flags=vc.get("uncertainty_flags", []),
            conflict_details=vc.get("conflicts", []),
            is_ai_generated=True,
        )
        db.add(claim_entity)
        db.flush()

        for ev in vc.get("validated_evidence", []):
            db.add(
                ClaimEvidenceLink(
                    claim_id=claim_entity.id,
                    source_document_id=ev["source_document_id"],
                    stable_source_id=ev["stable_source_id"],
                    source_type=ev["source_type"],
                    location=ev["location"],
                    excerpt=ev["excerpt"],
                    char_start=ev["char_start"],
                    char_end=ev["char_end"],
                    version_tag=ev["version_tag"],
                    source_updated_at=ev["source_updated_at"],
                    deterministic_verified=ev["deterministic_verified"],
                )
            )

    for rd in final_state.get("risks_and_dependencies", []):
        db.add(
            RiskOrDependency(
                handover_id=handover.id,
                record_type=rd["record_type"],
                title=rd["title"],
                description=rd["description"],
                severity=rd.get("severity", "high"),
                source_entity=rd.get("source_entity"),
                target_entity=rd.get("target_entity"),
                workaround=rd.get("workaround"),
                owner_name=rd.get("owner_name"),
                status=rd.get("status", "source_supported"),
                evidence_source_ids=rd.get("evidence_source_ids", []),
                evidence_claim_ids=rd.get("evidence_claim_ids", []),
            )
        )

    for q in final_state.get("unresolved_questions", []):
        db.add(
            ClarificationQuestion(
                handover_id=handover.id,
                related_claim_code=q.get("related_claim_code"),
                question=q.get("question") or "Clarification required on claim evidence.",
                reason=q.get("reason") or "Ambiguous or missing rationale in source passages.",
                status="open",
            )
        )

    for na in final_state.get("next_actions", []):
        db.add(
            NextAction(
                handover_id=handover.id,
                priority_rank=na.get("priority_rank", 1),
                priority=na.get("priority", "high"),
                action=na["action"],
                reason=na.get("reason", ""),
                owner=na.get("owner"),
                evidence_claim_ids=na.get("evidence_claim_ids", []),
            )
        )

    telemetry = dict(final_state.get("agent_telemetry", {}))
    telemetry["deterministic_validation"] = val_summary
    handover.agent_telemetry = telemetry
    handover.summary_text = final_state.get("project_summary", handover.summary_text)
    handover.status = HandoverStatus.READY_FOR_REVIEW.value
    handover.current_version = 1
    handover.approved_by = None
    handover.approved_at = None
    handover.acknowledged_by = None
    handover.acknowledged_at = None
    handover.acknowledgement_notes = None

    record_audit_event(
        db=db,
        action="HANDOVER_RECONSTRUCTED",
        target_type="handover",
        target_id=handover.handover_code,
        actor=actor,
        project_id=handover.project_id,
        handover_id=handover.id,
        new_state=val_summary,
    )
    db.commit()
    db.refresh(handover)
    return format_handover_draft(db, handover)


def get_handover_draft_for_user(
    db: Session,
    handover_id_or_code: str,
    user: User,
) -> HandoverDraftResponse:
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    membership = get_project_membership(db, handover.project_id, user)

    # Successor cannot access unapproved drafts
    if (
        membership.project_role == ProjectRole.SUCCESSOR.value
        and handover.status not in (HandoverStatus.APPROVED.value, HandoverStatus.ACKNOWLEDGED.value)
    ):
        record_audit_event(
            db=db,
            action="UNAPPROVED_DRAFT_ACCESS_BLOCKED",
            target_type="handover",
            target_id=handover.handover_code,
            actor=user,
            actor_role=membership.project_role,
            project_id=handover.project_id,
            handover_id=handover.id,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Handover draft is private and cannot be viewed by Successor until approved by an authorised Reviewer.",
        )

    return format_handover_draft(db, handover, allowed_classifications=membership.allowed_classifications)


def update_claim_by_reviewer(
    db: Session,
    claim_id_or_code: str,
    req: ClaimPatchRequest,
    actor: User,
    handover_id: Optional[str] = None,
) -> ClaimOutputSchema:
    query = db.query(Claim)
    if handover_id:
        query = query.filter(Claim.handover_id == handover_id)
    claim = query.filter(
        (Claim.id == claim_id_or_code) | (Claim.claim_code == claim_id_or_code)
    ).first()
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")

    handover = db.query(Handover).filter(Handover.id == claim.handover_id).first()
    if not handover:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent handover not found.")

    membership = get_project_membership(
        db,
        handover.project_id,
        actor,
        allowed_roles=[
            ProjectRole.PROJECT_LEAD.value,
            ProjectRole.REVIEWER_SME.value,
            ProjectRole.OUTGOING_DEV.value,
        ],
    )

    # Only PROJECT_LEAD or REVIEWER_SME can mark a claim as VERIFIED
    if req.status == EvidenceStatus.VERIFIED and membership.project_role not in (
        ProjectRole.PROJECT_LEAD.value,
        ProjectRole.REVIEWER_SME.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an authorised human Reviewer or Project Lead can mark a claim as 'verified'.",
        )

    prev_state = {
        "text": claim.text,
        "rationale": claim.rationale,
        "owner_name": claim.owner_name,
        "status": claim.status,
        "review_state": claim.review_state,
    }

    if req.text is not None:
        claim.text = req.text.strip()
        claim.review_state = ClaimReviewState.EDITED.value
    if req.rationale is not None:
        claim.rationale = req.rationale.strip()
    if req.owner_name is not None:
        claim.owner_name = req.owner_name.strip() or None
    if req.task_status is not None:
        claim.task_status = req.task_status.strip()
    if req.status is not None:
        claim.status = req.status.value
    if req.review_state is not None:
        claim.review_state = req.review_state.value
    if req.reviewer_notes is not None:
        claim.reviewer_notes = req.reviewer_notes.strip()

    claim.reviewed_by = actor.id
    claim.reviewed_at = datetime.now(timezone.utc)

    record_audit_event(
        db=db,
        action="CLAIM_REVIEW_UPDATED",
        target_type="claim",
        target_id=claim.claim_code,
        actor=actor,
        actor_role=membership.project_role,
        project_id=handover.project_id,
        handover_id=handover.id,
        previous_state=prev_state,
        new_state={
            "text": claim.text,
            "owner_name": claim.owner_name,
            "status": claim.status,
            "review_state": claim.review_state,
            "reviewer_notes": claim.reviewer_notes,
        },
    )
    db.commit()
    db.refresh(claim)
    return _format_claim_output(claim)


def answer_clarification_question(
    db: Session,
    handover_id_or_code: str,
    question_id: str,
    req: ClarificationAnswerRequest,
    actor: User,
) -> OpenQuestionOutputSchema:
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    membership = get_project_membership(
        db,
        handover.project_id,
        actor,
        allowed_roles=[
            ProjectRole.OUTGOING_DEV.value,
            ProjectRole.PROJECT_LEAD.value,
            ProjectRole.REVIEWER_SME.value,
        ],
    )
    question = (
        db.query(ClarificationQuestion)
        .filter(
            ClarificationQuestion.handover_id == handover.id,
            ClarificationQuestion.id == question_id,
        )
        .first()
    )
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clarification question not found.")

    prev_status = question.status
    question.answer_text = req.answer_text.strip()
    question.status = "answered" if req.mark_resolved else "open"
    question.answered_by = actor.id
    question.answered_at = datetime.now(timezone.utc)

    # Enrich related claim rationale if linked
    if question.related_claim_code:
        related_claim = (
            db.query(Claim)
            .filter(
                Claim.handover_id == handover.id,
                Claim.claim_code == question.related_claim_code,
            )
            .first()
        )
        if related_claim:
            related_claim.rationale = (
                f"{related_claim.rationale or ''} | Outgoing Clarification ({actor.email}): {question.answer_text}".strip(" |")
            )

    record_audit_event(
        db=db,
        action="CLARIFICATION_ANSWERED",
        target_type="clarification_question",
        target_id=question.id,
        actor=actor,
        actor_role=membership.project_role,
        project_id=handover.project_id,
        handover_id=handover.id,
        previous_state={"status": prev_status},
        new_state={"status": question.status, "answer_text": question.answer_text},
    )
    db.commit()
    db.refresh(question)
    return OpenQuestionOutputSchema(
        id=question.id,
        relatedClaimId=question.related_claim_code,
        question=question.question,
        reason=question.reason,
        status=question.status,
        answerText=question.answer_text,
        answeredBy=actor.email,
        answeredAt=question.answered_at,
    )


def approve_handover_package(
    db: Session,
    handover_id_or_code: str,
    req: HandoverApproveRequest,
    actor: User,
) -> HandoverDraftResponse:
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    membership = get_project_membership(
        db,
        handover.project_id,
        actor,
        allowed_roles=[ProjectRole.PROJECT_LEAD.value, ProjectRole.REVIEWER_SME.value],
    )

    if not handover.claims:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve an empty handover package before reconstruction.",
        )

    now = datetime.now(timezone.utc)
    # Mark non-rejected source-supported claims as approved/verified upon package approval
    for c in handover.claims:
        if c.review_state != ClaimReviewState.REJECTED.value:
            if c.status == EvidenceStatus.SOURCE_SUPPORTED.value:
                c.status = EvidenceStatus.VERIFIED.value
            c.review_state = ClaimReviewState.APPROVED.value
            c.reviewed_by = c.reviewed_by or actor.id
            c.reviewed_at = c.reviewed_at or now

    handover.status = HandoverStatus.APPROVED.value
    handover.approved_by = actor.id
    handover.approved_at = now
    handover.current_version += 1

    draft_snapshot = format_handover_draft(db, handover).model_dump(mode="json")
    db.add(
        HandoverVersion(
            handover_id=handover.id,
            version_number=handover.current_version,
            snapshot_payload=draft_snapshot,
            created_by=actor.id,
            change_summary=req.approval_notes,
        )
    )

    record_audit_event(
        db=db,
        action="HANDOVER_APPROVED",
        target_type="handover",
        target_id=handover.handover_code,
        actor=actor,
        actor_role=membership.project_role,
        project_id=handover.project_id,
        handover_id=handover.id,
        new_state={
            "status": handover.status,
            "version": handover.current_version,
            "approved_by": actor.email,
            "approval_notes": req.approval_notes,
        },
    )
    db.commit()
    db.refresh(handover)
    return format_handover_draft(db, handover)


def build_successor_continuation_plan(
    db: Session,
    handover_id_or_code: str,
    user: User,
) -> SuccessorContinuationPlanResponse:
    """Workflow E: Generate the 13-section Continuation Plan after human approval and second permission check."""
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    membership = get_project_membership(
        db,
        handover.project_id,
        user,
        allowed_roles=[ProjectRole.SUCCESSOR.value, ProjectRole.PROJECT_LEAD.value],
    )

    if handover.status not in (HandoverStatus.APPROVED.value, HandoverStatus.ACKNOWLEDGED.value):
        record_audit_event(
            db=db,
            action="UNAPPROVED_SUCCESSOR_VIEW_BLOCKED",
            target_type="handover",
            target_id=handover.handover_code,
            actor=user,
            actor_role=membership.project_role,
            project_id=handover.project_id,
            handover_id=handover.id,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Handover package has not been approved yet. Nothing is shared before human approval.",
        )

    # Intersect handover allowed_classifications with the viewing user's clearance
    effective_clearance = [
        lvl
        for lvl in handover.allowed_classifications
        if lvl in membership.allowed_classifications
    ]
    total_project_sources = (
        db.query(SourceDocument)
        .filter(SourceDocument.project_id == handover.project_id)
        .all()
    )
    restricted_filtered_count = sum(
        1 for d in total_project_sources if d.access_level not in effective_clearance
    )

    draft = format_handover_draft(db, handover, allowed_classifications=effective_clearance)
    active_claims = [c for c in draft.claims if c.reviewState != ClaimReviewState.REJECTED.value]

    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for c in active_claims:
        by_type.setdefault(c.type, []).append(c.model_dump(mode="json"))

    all_evidence_refs = [
        ev.model_dump(mode="json")
        for c in active_claims
        for ev in c.evidence
    ]

    sections: Dict[str, Any] = {
        "1_project_overview": by_type.get("project_overview", []),
        "2_technical_context": by_type.get("technical_context", []),
        "3_key_decisions": by_type.get("key_decision", []),
        "4_completed_and_active_tasks": by_type.get("completed_work", []) + by_type.get("active_work", []),
        "5_blocked_tasks": by_type.get("blocked_work", []),
        "6_responsibilities": {
            "departing_role": handover.departing_role,
            "transferred_claims": by_type.get("responsibility", []),
            "supporting_contacts": ["priya.nair (DevOps On-Call)"],
        },
        "7_dependencies": [
            r.model_dump(mode="json")
            for r in draft.risksAndDependencies
            if r.recordType == "dependency"
        ],
        "8_risks_and_blockers": [
            r.model_dump(mode="json")
            for r in draft.risksAndDependencies
            if r.recordType in ("risk", "blocker")
        ],
        "9_operational_information": by_type.get("operational_info", []),
        "10_unresolved_questions": [q.model_dump(mode="json") for q in draft.openQuestions],
        "11_prioritised_next_actions": [a.model_dump(mode="json") for a in draft.nextActions],
        "12_evidence_references": all_evidence_refs,
        "13_approval_information": draft.approval.model_dump(mode="json"),
    }

    return SuccessorContinuationPlanResponse(
        handoverId=draft.handoverId,
        title=draft.title,
        version=draft.currentVersion,
        accessScopeApplied=effective_clearance,
        restrictedSourcesFilteredOut=restricted_filtered_count,
        sections=sections,
        claims=active_claims,
        risksAndDependencies=draft.risksAndDependencies,
        openQuestions=draft.openQuestions,
        nextActions=draft.nextActions,
        approval=draft.approval,
    )


def acknowledge_handover_receipt(
    db: Session,
    handover_id_or_code: str,
    req: SuccessorAcknowledgeRequest,
    actor: User,
) -> HandoverDraftResponse:
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    membership = get_project_membership(
        db,
        handover.project_id,
        actor,
        allowed_roles=[ProjectRole.SUCCESSOR.value],
    )

    if handover.status not in (HandoverStatus.APPROVED.value, HandoverStatus.ACKNOWLEDGED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot acknowledge a handover that has not yet been approved.",
        )

    handover.status = HandoverStatus.ACKNOWLEDGED.value
    handover.acknowledged_by = actor.id
    handover.acknowledged_at = datetime.now(timezone.utc)
    handover.acknowledgement_notes = req.acknowledgement_notes.strip()

    record_audit_event(
        db=db,
        action="HANDOVER_RECEIPT_ACKNOWLEDGED",
        target_type="handover",
        target_id=handover.handover_code,
        actor=actor,
        actor_role=membership.project_role,
        project_id=handover.project_id,
        handover_id=handover.id,
        new_state={
            "acknowledged_by": actor.email,
            "acknowledgement_notes": handover.acknowledgement_notes,
        },
    )
    db.commit()
    db.refresh(handover)
    return format_handover_draft(db, handover, allowed_classifications=membership.allowed_classifications)
