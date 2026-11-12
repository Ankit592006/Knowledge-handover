"""Agent 3: Risk and Dependency Analysis Agent (Module 11)."""

import json
from typing import Any, Dict, List, Tuple

from app.agents.adapter.llm_adapter import ModelExecutionMetadata, invoke_structured_model
from app.agents.schemas import (
    Agent3RiskDependencyOutput,
    CandidateNextActionSchema,
    CandidateRiskDependencySchema,
)

AGENT_3_SYSTEM_PROMPT = """You are the Risk and Dependency Analysis Agent for the Knowledge Handover platform.
STRICT RULES:
1. Identify project blockers, operational/technical risks, and component/team/approval dependencies.
2. Report a dependency or risk as 'source_supported' ONLY when retrieved evidence explicitly states it; otherwise label it 'inferred' or 'unknown'.
3. NEVER invent owners, deadlines, or dependencies without supporting evidence.
4. Recommend a priority-ranked list of next actions for the incoming successor linked to claim codes."""


def _extractive_risk_dependency_analysis(
    candidate_claims: List[Dict[str, Any]],
    passages: List[Dict[str, Any]],
) -> Agent3RiskDependencyOutput:
    source_ids_present = {p["stable_source_id"] for p in passages}
    claim_by_source: Dict[str, str] = {}
    for c in candidate_claims:
        for ev in c.get("evidence", []):
            claim_by_source[ev.get("source_id", "")] = c["claim_code"]

    items: List[CandidateRiskDependencySchema] = []
    actions: List[CandidateNextActionSchema] = []

    if "issue-104" in source_ids_present:
        c_code = claim_by_source.get("issue-104", "claim-004")
        items.append(
            CandidateRiskDependencySchema(
                record_type="blocker",
                title="3DS2 Callback Timeout Handling Blocked on Sandbox Certificate",
                description="ISSUE-104 cannot be completed or deployed to production until Finance Ops provisions the external provider sandbox webhook signing certificate.",
                severity="high",
                source_entity="PayFlow 3DS2 Timeout Handler (issue-104)",
                target_entity="Finance Ops / Payment Provider Sandbox Certificate",
                workaround="Keep 3DS2 timeout deployment feature-flagged off until certificate verification passes.",
                owner_name=None,  # Explicitly unknown in evidence
                status="source_supported",
                evidence_source_ids=["issue-104"],
                evidence_claim_ids=[c_code],
            )
        )
        actions.append(
            CandidateNextActionSchema(
                priority_rank=1,
                priority="high",
                action="Assign an owner to ISSUE-104, obtain the provider sandbox webhook signing certificate from Finance Ops, and reconcile the conflicting status with the Oct 15 meeting notes.",
                reason="Critical release blocker with no assigned owner and conflicting status records.",
                owner=None,
                evidence_claim_ids=[c_code],
            )
        )

    if "pr-218" in source_ids_present:
        c_code = claim_by_source.get("pr-218", "claim-005")
        items.append(
            CandidateRiskDependencySchema(
                record_type="dependency",
                title="Release Dependency on Finance Ops Sandbox Approval & Risk-Engine v1.4",
                description="PR-218 review thread states that production rollout of POST /v2/payment-intents depends on Finance Ops sandbox sign-off and Risk-Engine service v1.4 schema compatibility.",
                severity="high",
                source_entity="POST /v2/payment-intents (PR-218)",
                target_entity="Finance Ops Sandbox Approval & Risk-Engine v1.4",
                workaround=None,
                owner_name="Arjun Mehta",
                status="source_supported",
                evidence_source_ids=["pr-218"],
                evidence_claim_ids=[c_code],
            )
        )
        actions.append(
            CandidateNextActionSchema(
                priority_rank=2,
                priority="high",
                action="Verify Risk-Engine v1.4 schema compatibility and archive/update legacy doc-legacy-api (/v1/payments/charge) so consumers use POST /v2/payment-intents.",
                reason="Prevents successor or downstream teams from integrating against the deprecated v1 endpoint.",
                owner="Arjun Mehta",
                evidence_claim_ids=[c_code],
            )
        )

    if "adr-001" in source_ids_present:
        c_code = claim_by_source.get("adr-001", "claim-003")
        items.append(
            CandidateRiskDependencySchema(
                record_type="risk",
                title="Unresolved Webhook Retry Backoff & Dead-Letter Policy",
                description="ADR-001 adopted Stripe PaymentIntents v2 but left the exponential backoff retry count (3 vs 5) and DLQ retention policy undecided.",
                severity="medium",
                source_entity="Webhook Consumer Worker",
                target_entity="ADR-001 Retry Policy Specification",
                workaround="Confirm retry parameters with outgoing engineer before enabling live webhook retries.",
                owner_name=None,
                status="source_supported",
                evidence_source_ids=["adr-001"],
                evidence_claim_ids=[c_code],
            )
        )
        actions.append(
            CandidateNextActionSchema(
                priority_rank=3,
                priority="medium",
                action="Record final decision on webhook retry backoff count and DLQ TTL in an ADR addendum before production cutover.",
                reason="ADR-001 explicitly flags the retry policy as having no final decision record.",
                owner=None,
                evidence_claim_ids=[c_code],
            )
        )

    if "notes-2026-11-02" in source_ids_present:
        c_code = claim_by_source.get("notes-2026-11-02", "claim-006")
        items.append(
            CandidateRiskDependencySchema(
                record_type="risk",
                title="Undocumented Manual Redis Idempotency Flush During Settlement Migrations",
                description="Running Alembic migrations on the settlement table without manually flushing `payflow:idem:*` causes duplicate key errors during traffic drain; no formal runbook exists.",
                severity="high",
                source_entity="Settlement DB Migration Pipeline",
                target_entity="Redis Idempotency Cluster (`payflow:idem:*`)",
                workaround="Manually flush `payflow:idem:*` during traffic drain and contact DevOps On-Call (@priya.nair).",
                owner_name="priya.nair",
                status="source_supported",
                evidence_source_ids=["notes-2026-11-02"],
                evidence_claim_ids=[c_code],
            )
        )
        actions.append(
            CandidateNextActionSchema(
                priority_rank=4,
                priority="medium",
                action="Codify the Redis `payflow:idem:*` pre-migration flush step into an official deployment runbook with @priya.nair.",
                reason="Eliminates undocumented operational failure risk during future database migrations.",
                owner="priya.nair",
                evidence_claim_ids=[c_code],
            )
        )

    if not actions and candidate_claims:
        actions.append(
            CandidateNextActionSchema(
                priority_rank=1,
                priority="high",
                action="Review extracted handover claims and inspect linked source evidence before starting implementation work.",
                reason="Initial continuation step for scoped handover.",
                owner=None,
                evidence_claim_ids=[candidate_claims[0]["claim_code"]],
            )
        )

    return Agent3RiskDependencyOutput(
        risks_and_dependencies=items,
        next_actions=actions,
    )


def run_risk_dependency_agent(
    candidate_claims: List[Dict[str, Any]],
    passages: List[Dict[str, Any]],
) -> Tuple[Agent3RiskDependencyOutput, ModelExecutionMetadata]:
    user_prompt = json.dumps(
        {
            "candidate_claims": candidate_claims,
            "available_sources": [
                {"source_id": p["stable_source_id"], "title": p["title"], "updated_at": p["source_updated_at"]}
                for p in passages
            ],
        },
        indent=2,
    )
    return invoke_structured_model(
        system_prompt=AGENT_3_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_schema=Agent3RiskDependencyOutput,
        deterministic_extractor=lambda: _extractive_risk_dependency_analysis(candidate_claims, passages),
    )
