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
    is_source_revoked,
    retrieve_scoped_chunks,
    seed_payflow_sources_for_project,
)
from app.modules.validation.service import (
    evaluate_citation_support,
    validate_claims_against_database,
)
from app.schemas.api_schemas import (
    ApprovalBlockSchema,
    ClaimOutputSchema,
    ClaimPatchRequest,
    ClaimVersionDiffSchema,
    ClarificationAnswerRequest,
    ConflictPairSchema,
    DependencyGraphEdgeSchema,
    DependencyGraphNodeSchema,
    DependencyMapResponse,
    EvidenceReferenceSchema,
    HandoverApproveRequest,
    HandoverCreateRequest,
    HandoverDraftResponse,
    HandoverSourceImportRequest,
    HandoverVersionBriefSchema,
    HandoverVersionDiffResponse,
    NextActionOutputSchema,
    OpenQuestionOutputSchema,
    RiskDependencyOutputSchema,
    SuccessorAcknowledgeRequest,
    SuccessorContinuationPlanResponse,
)


def _format_claim_output(
    claim: Claim,
    visible_links: Optional[List[ClaimEvidenceLink]] = None,
) -> ClaimOutputSchema:
    links_to_render = visible_links if visible_links is not None else list(claim.evidence_links)
    flags = list(claim.uncertainty_flags or [])
    reviewer_flagged_mismatch = "reviewer_flagged_citation_mismatch" in flags

    override_status: Optional[str] = None
    for fl in flags:
        if fl.startswith("citation_support_override:"):
            override_status = fl.split(":", 1)[1]

    ev_refs: List[EvidenceReferenceSchema] = []
    verdicts: List[str] = []
    scores: List[float] = []

    for link in links_to_render:
        sup_status, sup_score, sup_expl = evaluate_citation_support(
            claim_text=claim.text,
            excerpt=link.excerpt,
        )
        if reviewer_flagged_mismatch or override_status == "mismatch":
            sup_status = "mismatch"
            sup_score = min(sup_score, 0.15)
            sup_expl = "Reviewer flagged citation mismatch: Excerpt marked as non-substantiating during human review."
        elif override_status in ("supported", "weak"):
            sup_status = override_status

        verdicts.append(sup_status)
        scores.append(sup_score)
        ev_refs.append(
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
                supportStatus=sup_status,
                supportScore=sup_score,
                supportExplanation=sup_expl,
            )
        )

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

    overall_support = "supported"
    if reviewer_flagged_mismatch or override_status == "mismatch" or not verdicts or all(v == "mismatch" for v in verdicts):
        overall_support = "mismatch"
    elif override_status == "weak" or "supported" not in verdicts:
        overall_support = "weak"

    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

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
        uncertainty=flags,
        conflicts=conflicts,
        reviewState=claim.review_state,
        extractionConfidence=claim.extraction_confidence,
        isAiGenerated=claim.is_ai_generated,
        reviewerNotes=claim.reviewer_notes,
        reviewedBy=claim.reviewed_by,
        reviewedAt=claim.reviewed_at,
        citationSupportStatus=overall_support,
        citationSupportScore=avg_score,
        reviewerFlaggedMismatch=reviewer_flagged_mismatch,
    )


def format_handover_draft(
    db: Session,
    handover: Handover,
    allowed_classifications: Optional[List[str]] = None,
) -> HandoverDraftResponse:
    project = db.query(Project).filter(Project.id == handover.project_id).first()
    effective_scope = set(allowed_classifications or handover.allowed_classifications)

    # Round 3 Improvement 1: Retrieval-time permission & revocation re-check
    scoped_docs: List[SourceDocument] = [
        hs.source_document
        for hs in handover.scoped_sources
        if hs.source_document
        and hs.source_document.access_level in effective_scope
        and not is_source_revoked(hs.source_document)
    ]
    visible_stable_ids = {sd.stable_source_id for sd in scoped_docs}

    claims_out: List[ClaimOutputSchema] = []
    for c in sorted(handover.claims, key=lambda x: x.claim_code):
        # Filter out claims that rely exclusively on restricted or revoked sources outside effective_scope
        visible_links = [
            lnk
            for lnk in c.evidence_links
            if any(sd.id == lnk.source_document_id for sd in scoped_docs)
        ]
        if c.evidence_links and not visible_links:
            continue
        claims_out.append(_format_claim_output(c, visible_links=visible_links))

    risks_out: List[RiskDependencyOutputSchema] = []
    for r in handover.risks_and_dependencies:
        ev_sids = [sid for sid in (r.evidence_source_ids or []) if not visible_stable_ids or sid in visible_stable_ids]
        if (r.evidence_source_ids or []) and not ev_sids:
            continue
        risks_out.append(
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
                evidenceSourceIds=ev_sids,
                evidenceClaimIds=r.evidence_claim_ids or [],
            )
        )

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
    db.flush()

    # Round 3 Improvement 3: Freeze baseline v1 AI Draft Snapshot upon reconstruction for Version Diffing
    v1_draft_response = format_handover_draft(db, handover)
    v1_payload = v1_draft_response.model_dump(mode="json")
    existing_v1 = (
        db.query(HandoverVersion)
        .filter(
            HandoverVersion.handover_id == handover.id,
            HandoverVersion.version_number == 1,
        )
        .first()
    )
    if existing_v1:
        existing_v1.snapshot_payload = v1_payload
        existing_v1.change_summary = "Initial 3-Agent AI Reconstruction Draft (v1)"
        existing_v1.created_by = actor.id
    else:
        db.add(
            HandoverVersion(
                handover_id=handover.id,
                version_number=1,
                snapshot_payload=v1_payload,
                created_by=actor.id,
                change_summary="Initial 3-Agent AI Reconstruction Draft (v1)",
            )
        )

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
        resolved_handover = get_handover_by_id_or_code(db, handover_id)
        query = query.filter(Claim.handover_id == resolved_handover.id)
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

    # Round 3 Improvement 2: Reviewer-flagged citation mismatch feedback loop
    current_flags = list(claim.uncertainty_flags or [])
    if req.flag_citation_mismatch is True:
        if "reviewer_flagged_citation_mismatch" not in current_flags:
            current_flags.append("reviewer_flagged_citation_mismatch")
        telemetry = dict(handover.agent_telemetry or {})
        telemetry["reviewer_mismatch_feedback_count"] = int(
            telemetry.get("reviewer_mismatch_feedback_count", 0)
        ) + 1
        handover.agent_telemetry = telemetry
    elif req.flag_citation_mismatch is False:
        current_flags = [f for f in current_flags if f != "reviewer_flagged_citation_mismatch"]

    if req.citation_support_override in ("supported", "weak", "mismatch"):
        current_flags = [f for f in current_flags if not f.startswith("citation_support_override:")]
        current_flags.append(f"citation_support_override:{req.citation_support_override}")
        if req.citation_support_override == "mismatch" and "reviewer_flagged_citation_mismatch" not in current_flags:
            current_flags.append("reviewer_flagged_citation_mismatch")

    claim.uncertainty_flags = current_flags
    claim.reviewed_by = actor.id
    claim.reviewed_at = datetime.now(timezone.utc)

    record_audit_event(
        db=db,
        action="CITATION_MISMATCH_FLAGGED_BY_REVIEWER" if req.flag_citation_mismatch else "CLAIM_REVIEW_UPDATED",
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
            "uncertainty_flags": claim.uncertainty_flags,
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
    revoked_filtered_count = sum(
        1 for d in total_project_sources if is_source_revoked(d)
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
        revokedSourcesFilteredOut=revoked_filtered_count,
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


# -----------------------------------------------------------------------------
# Round 3 Improvement 3: Evidence-Backed Dependency Map & Version Comparison
# -----------------------------------------------------------------------------
def build_evidence_backed_dependency_map(
    db: Session,
    handover_id_or_code: str,
    user: User,
) -> DependencyMapResponse:
    """
    Construct an interactive map of people, components, teams, and tasks whose edges each carry
    source evidence or an explicit 'inferred' label, with unknown owners shown as explicit gaps.
    """
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    membership = get_project_membership(db, handover.project_id, user)

    if (
        membership.project_role == ProjectRole.SUCCESSOR.value
        and handover.status not in (HandoverStatus.APPROVED.value, HandoverStatus.ACKNOWLEDGED.value)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dependency map is locked for Successor until handover package is approved.",
        )

    draft = format_handover_draft(
        db,
        handover,
        allowed_classifications=membership.allowed_classifications,
    )

    nodes_by_id: Dict[str, DependencyGraphNodeSchema] = {}
    edges: List[DependencyGraphEdgeSchema] = []

    def ensure_node(
        node_id: str,
        label: str,
        category: str,
        node_status: str = "source_supported",
        owner: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        if node_id not in nodes_by_id:
            nodes_by_id[node_id] = DependencyGraphNodeSchema(
                nodeId=node_id,
                label=label,
                category=category,
                status=node_status,
                owner=owner,
                evidenceSourceIds=list(dict.fromkeys(source_ids or [])),
                metadata=meta or {},
            )
        else:
            existing = nodes_by_id[node_id]
            merged_sources = list(dict.fromkeys(existing.evidenceSourceIds + (source_ids or [])))
            existing.evidenceSourceIds = merged_sources
        return node_id

    edge_counter = 1

    def add_edge(
        src_node: str,
        tgt_node: str,
        relationship: str,
        support_status: str,
        severity: str,
        ev_sources: List[str],
        ev_claims: List[str],
        explanation: str,
    ) -> None:
        nonlocal edge_counter
        # Enforce Section 10.1 Invariant: No edge without source evidence or explicit 'inferred' label
        normalized_support = "source_supported" if (ev_sources and support_status != "inferred") else "inferred"
        edges.append(
            DependencyGraphEdgeSchema(
                edgeId=f"edge-{edge_counter:03d}",
                sourceNodeId=src_node,
                targetNodeId=tgt_node,
                relationship=relationship,
                supportStatus=normalized_support,
                severity=severity,
                evidenceSourceIds=list(dict.fromkeys(ev_sources)),
                evidenceClaimIds=list(dict.fromkeys(ev_claims)),
                explanation=explanation,
            )
        )
        edge_counter += 1

    # 1. Add Risk, Blocker & Cross-Team Dependency Nodes & Edges (e.g. Finance Ops sandbox cert, Risk-Engine v1.4)
    for rd in draft.risksAndDependencies:
        src_label = rd.sourceEntity or rd.title
        tgt_label = rd.targetEntity or "Downstream Dependency Target"
        src_id = f"comp-{src_label.lower().replace(' ', '-')[:40]}"
        tgt_id = f"team-{tgt_label.lower().replace(' ', '-')[:40]}"

        ev_sids = list(rd.evidenceSourceIds or [])
        ev_cids = list(rd.evidenceClaimIds or [])
        sup_label = "source_supported" if (ev_sids and rd.status != "inferred") else "inferred"

        ensure_node(
            node_id=src_id,
            label=src_label,
            category="component",
            node_status="blocked" if rd.recordType == "blocker" else sup_label,
            owner=rd.owner,
            source_ids=ev_sids,
            meta={"recordType": rd.recordType, "severity": rd.severity},
        )
        ensure_node(
            node_id=tgt_id,
            label=tgt_label,
            category="team_or_external",
            node_status=sup_label,
            owner=rd.owner,
            source_ids=ev_sids,
            meta={"recordType": rd.recordType},
        )

        rel_type = (
            "BLOCKS"
            if rd.recordType == "blocker"
            else "DEPENDS_ON"
            if rd.recordType == "dependency"
            else "REQUIRES_RUNBOOK"
        )
        add_edge(
            src_node=src_id,
            tgt_node=tgt_id,
            relationship=rel_type,
            support_status=sup_label,
            severity=rd.severity,
            ev_sources=ev_sids,
            ev_claims=ev_cids,
            explanation=rd.description,
        )

        # Link owner or explicit UNKNOWN OWNER GAP node for each risk/blocker/dependency
        if rd.owner:
            person_id = f"person-{rd.owner.lower().replace(' ', '-')}"
            ensure_node(
                node_id=person_id,
                label=f"{rd.owner} (Assigned Owner)",
                category="person",
                node_status="source_supported",
                owner=rd.owner,
                source_ids=ev_sids,
            )
            add_edge(
                src_node=src_id,
                tgt_node=person_id,
                relationship="OWNED_BY",
                support_status=sup_label,
                severity="low",
                ev_sources=ev_sids,
                ev_claims=ev_cids,
                explanation=f"Explicitly assigned to {rd.owner} in source evidence.",
            )
        else:
            gap_id = f"gap-unassigned-{rd.id[:8]}"
            ensure_node(
                node_id=gap_id,
                label=f"UNKNOWN OWNER GAP ({src_label})",
                category="unknown_owner_gap",
                node_status="unknown_gap",
                owner=None,
                source_ids=ev_sids,
                meta={"gapReason": "No assignee or long-term owner named in retrieved evidence."},
            )
            add_edge(
                src_node=src_id,
                tgt_node=gap_id,
                relationship="UNASSIGNED_OWNER_GAP",
                support_status=sup_label,
                severity="high",
                ev_sources=ev_sids,
                ev_claims=ev_cids,
                explanation="Owner is unassigned in source evidence; preserved as an explicit ownership gap.",
            )

    # 2. Add Task/Claim Nodes & Ownership / Conflict Edges
    for clm in draft.claims:
        ev_sids = [e.sourceId for e in clm.evidence]
        sup_label = "source_supported" if (ev_sids and clm.status != "inferred") else "inferred"
        task_node_id = f"task-{clm.claimId}"

        ensure_node(
            node_id=task_node_id,
            label=f"[{clm.claimId.upper()}] {clm.type.replace('_', ' ').title()}",
            category="task_or_decision",
            node_status="blocked" if clm.taskStatus == "blocked" else sup_label,
            owner=clm.owner,
            source_ids=ev_sids,
            meta={"claimText": clm.text, "claimStatus": clm.status},
        )

        if clm.owner:
            person_id = f"person-{clm.owner.lower().replace(' ', '-')}"
            ensure_node(
                node_id=person_id,
                label=f"{clm.owner} (Assigned Owner)",
                category="person",
                node_status="source_supported",
                owner=clm.owner,
                source_ids=ev_sids,
            )
            add_edge(
                src_node=task_node_id,
                tgt_node=person_id,
                relationship="OWNED_BY",
                support_status=sup_label,
                severity="low",
                ev_sources=ev_sids,
                ev_claims=[clm.claimId],
                explanation=f"Claim {clm.claimId} owner verified as {clm.owner}.",
            )
        else:
            gap_id = f"gap-claim-{clm.claimId}"
            ensure_node(
                node_id=gap_id,
                label=f"UNKNOWN OWNER GAP ({clm.claimId.upper()})",
                category="unknown_owner_gap",
                node_status="unknown_gap",
                owner=None,
                source_ids=ev_sids,
                meta={"gapReason": f"Claim {clm.claimId} has no owner in source evidence."},
            )
            add_edge(
                src_node=task_node_id,
                tgt_node=gap_id,
                relationship="UNASSIGNED_OWNER_GAP",
                support_status=sup_label,
                severity="high",
                ev_sources=ev_sids,
                ev_claims=[clm.claimId],
                explanation=f"Claim {clm.claimId} has no owner in evidence; unknown owner shown as explicit gap.",
            )

    nodes_list = list(nodes_by_id.values())
    unknown_gap_nodes = [n for n in nodes_list if n.category == "unknown_owner_gap"]
    source_supported_edges = [e for e in edges if e.supportStatus == "source_supported"]
    inferred_edges = [e for e in edges if e.supportStatus == "inferred"]

    return DependencyMapResponse(
        handoverId=draft.handoverId,
        nodes=nodes_list,
        edges=edges,
        summary={
            "totalNodes": len(nodes_list),
            "totalEdges": len(edges),
            "sourceSupportedEdgesCount": len(source_supported_edges),
            "inferredEdgesCount": len(inferred_edges),
            "unknownOwnerGapsCount": len(unknown_gap_nodes),
            "unlabeledEdgesCount": 0,
        },
    )


def compare_handover_versions(
    db: Session,
    handover_id_or_code: str,
    user: User,
    base_version: int = 1,
    target_version: Optional[int] = None,
) -> HandoverVersionDiffResponse:
    """
    Side-by-side comparison of two handover versions (e.g., v1 Initial AI Draft vs. v2 Approved Snapshot
    or live reviewed draft), highlighting changed claims, statuses, rationale enrichments, and reviewer decisions.
    """
    handover = get_handover_by_id_or_code(db, handover_id_or_code)
    membership = get_project_membership(db, handover.project_id, user)

    saved_versions = (
        db.query(HandoverVersion)
        .filter(HandoverVersion.handover_id == handover.id)
        .order_by(HandoverVersion.version_number.asc())
        .all()
    )

    live_draft = format_handover_draft(
        db,
        handover,
        allowed_classifications=membership.allowed_classifications,
    ).model_dump(mode="json")

    version_map: Dict[int, Dict[str, Any]] = {}
    briefs: List[HandoverVersionBriefSchema] = []

    for sv in saved_versions:
        creator = db.query(User).filter(User.id == sv.created_by).first()
        creator_email = creator.email if creator else sv.created_by
        payload = sv.snapshot_payload or {}
        version_map[sv.version_number] = {
            "payload": payload,
            "change_summary": sv.change_summary,
            "created_by": creator_email,
            "created_at": sv.created_at,
        }
        briefs.append(
            HandoverVersionBriefSchema(
                versionNumber=sv.version_number,
                changeSummary=sv.change_summary,
                createdBy=creator_email,
                createdAt=sv.created_at,
                claimsCount=len(payload.get("claims", [])),
            )
        )

    if 1 not in version_map:
        version_map[1] = {
            "payload": live_draft,
            "change_summary": "Initial 3-Agent AI Reconstruction Draft (v1)",
            "created_by": "system@payflow.demo",
            "created_at": handover.created_at,
        }
        briefs.insert(
            0,
            HandoverVersionBriefSchema(
                versionNumber=1,
                changeSummary="Initial 3-Agent AI Reconstruction Draft (v1)",
                createdBy="system@payflow.demo",
                createdAt=handover.created_at,
                claimsCount=len(live_draft.get("claims", [])),
            ),
        )

    # Always make the live current state selectable as the highest version (or live draft vN+1 if unapproved edits exist)
    max_saved_ver = max(version_map.keys())
    live_virtual_ver = max_saved_ver + 1 if max_saved_ver == 1 else max_saved_ver
    if live_virtual_ver not in version_map:
        version_map[live_virtual_ver] = {
            "payload": live_draft,
            "change_summary": f"Current Reviewed Workspace State (v{live_virtual_ver} Live)",
            "created_by": user.email,
            "created_at": handover.updated_at,
        }
        briefs.append(
            HandoverVersionBriefSchema(
                versionNumber=live_virtual_ver,
                changeSummary=f"Current Reviewed Workspace State (v{live_virtual_ver} Live)",
                createdBy=user.email,
                createdAt=handover.updated_at,
                claimsCount=len(live_draft.get("claims", [])),
            )
        )

    resolved_base_ver = base_version if base_version in version_map else min(version_map.keys())
    resolved_target_ver = (
        target_version
        if (target_version is not None and target_version in version_map)
        else max(version_map.keys())
    )

    base_entry = version_map[resolved_base_ver]
    target_entry = version_map[resolved_target_ver]

    base_claims_by_code: Dict[str, Dict[str, Any]] = {
        c.get("claimId", c.get("claim_code", "")): c
        for c in base_entry["payload"].get("claims", [])
    }
    target_claims_by_code: Dict[str, Dict[str, Any]] = {
        c.get("claimId", c.get("claim_code", "")): c
        for c in target_entry["payload"].get("claims", [])
    }

    all_codes = sorted(set(base_claims_by_code.keys()).union(set(target_claims_by_code.keys())))

    claim_diffs: List[ClaimVersionDiffSchema] = []
    changed_claims_count = 0
    status_changes_count = 0
    review_decision_changes_count = 0
    rationale_enriched_count = 0
    owner_changes_count = 0
    text_edits_count = 0

    for code in all_codes:
        if not code:
            continue
        b_clm = base_claims_by_code.get(code)
        t_clm = target_claims_by_code.get(code)
        change_types: List[str] = []

        if b_clm and not t_clm:
            change_types.append("REMOVED_OR_REVOKED")
            changed_claims_count += 1
        elif t_clm and not b_clm:
            change_types.append("ADDED")
            changed_claims_count += 1
        elif b_clm and t_clm:
            if b_clm.get("status") != t_clm.get("status"):
                change_types.append("STATUS_CHANGED")
                status_changes_count += 1
            if b_clm.get("reviewState") != t_clm.get("reviewState"):
                change_types.append("REVIEW_DECISION_CHANGED")
                review_decision_changes_count += 1
            if (b_clm.get("text") or "").strip() != (t_clm.get("text") or "").strip():
                change_types.append("TEXT_EDITED")
                text_edits_count += 1
            if (b_clm.get("rationale") or "").strip() != (t_clm.get("rationale") or "").strip():
                change_types.append("RATIONALE_ENRICHED")
                rationale_enriched_count += 1
            if (b_clm.get("owner") or None) != (t_clm.get("owner") or None):
                change_types.append("OWNER_UPDATED")
                owner_changes_count += 1
            if t_clm.get("reviewerFlaggedMismatch") and not b_clm.get("reviewerFlaggedMismatch"):
                change_types.append("CITATION_MISMATCH_FLAGGED")

            if change_types:
                changed_claims_count += 1
            else:
                change_types.append("UNCHANGED")

        active_ref = t_clm or b_clm or {}
        ev_ids = [
            e.get("sourceId", "")
            for e in active_ref.get("evidence", [])
            if e.get("sourceId")
        ]

        claim_diffs.append(
            ClaimVersionDiffSchema(
                claimCode=code,
                claimType=active_ref.get("type", "technical_context"),
                changeTypes=change_types,
                beforeText=b_clm.get("text") if b_clm else None,
                afterText=t_clm.get("text") if t_clm else None,
                beforeRationale=b_clm.get("rationale") if b_clm else None,
                afterRationale=t_clm.get("rationale") if t_clm else None,
                beforeStatus=b_clm.get("status") if b_clm else None,
                afterStatus=t_clm.get("status") if t_clm else None,
                beforeReviewState=b_clm.get("reviewState") if b_clm else None,
                afterReviewState=t_clm.get("reviewState") if t_clm else None,
                beforeOwner=b_clm.get("owner") if b_clm else None,
                afterOwner=t_clm.get("owner") if t_clm else None,
                reviewerNotes=t_clm.get("reviewerNotes") if t_clm else None,
                evidenceSourceIds=ev_ids,
            )
        )

    return HandoverVersionDiffResponse(
        handoverId=handover.handover_code,
        baseVersion=resolved_base_ver,
        targetVersion=resolved_target_ver,
        baseChangeSummary=base_entry["change_summary"],
        targetChangeSummary=target_entry["change_summary"],
        availableVersions=briefs,
        summaryMetrics={
            "totalClaimsCompared": len(claim_diffs),
            "changedClaimsCount": changed_claims_count,
            "statusChangesCount": status_changes_count,
            "reviewDecisionChangesCount": review_decision_changes_count,
            "rationaleEnrichedCount": rationale_enriched_count,
            "ownerChangesCount": owner_changes_count,
            "textEditsCount": text_edits_count,
        },
        claimDiffs=claim_diffs,
    )
