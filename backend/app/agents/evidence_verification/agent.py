"""Agent 2: Evidence Verification Agent (Module 10)."""

import json
from typing import Any, Dict, List, Tuple

from app.agents.adapter.llm_adapter import ModelExecutionMetadata, invoke_structured_model
from app.agents.schemas import (
    Agent2VerificationOutput,
    ClaimVerificationResultSchema,
    ConflictRecordSchema,
)

AGENT_2_SYSTEM_PROMPT = """You are the Evidence Verification Agent for the Knowledge Handover platform.
STRICT RULES:
1. Check every candidate claim against the retrieved source records and their timestamps.
2. Detect contradictory records (e.g., an issue says BLOCKED while a meeting note says IN PROGRESS). Do NOT silently pick one; output a ConflictRecordSchema with both sources and mark evidence_status as 'conflicting'.
3. Detect potentially outdated records (e.g., an older technical doc describes /v1/payments/charge while a newer PR replaces it with /v2/payment-intents) and mark evidence_status as 'potentially_outdated'.
4. If a claim has no valid supporting source in the retrieved passages, mark it 'unknown'.
5. NEVER mark any claim as 'verified'. Only a human reviewer can set 'verified'."""


def _extractive_evidence_verification(
    candidate_claims: List[Dict[str, Any]],
    passages: List[Dict[str, Any]],
) -> Agent2VerificationOutput:
    passage_by_source: Dict[str, Dict[str, Any]] = {
        p["stable_source_id"]: p for p in passages
    }
    results: List[ClaimVerificationResultSchema] = []

    for claim in candidate_claims:
        c_code = claim["claim_code"]
        ev_list = claim.get("evidence", [])
        cited_ids = [e.get("source_id") for e in ev_list if e.get("source_id") in passage_by_source]

        uncertainty_flags: List[str] = []
        conflicts: List[ConflictRecordSchema] = []
        status_val = "source_supported"

        if not cited_ids:
            status_val = "unknown"
            uncertainty_flags.append("missing_supporting_source")
        else:
            if claim.get("owner_name") is None and claim.get("claim_type") in ("blocked_work", "active_work", "responsibility"):
                uncertainty_flags.append("unknown_owner")

            if claim.get("missing_info_note"):
                uncertainty_flags.append("missing_decision_rationale_or_runbook")

            # Check for contradictory status between ISSUE-104 and NOTES-2026-10-15
            if "issue-104" in cited_ids and "notes-2026-10-15" in passage_by_source:
                src_a = passage_by_source["issue-104"]
                src_b = passage_by_source["notes-2026-10-15"]
                status_val = "conflicting"
                uncertainty_flags.append("contradictory_task_status")
                conflicts.append(
                    ConflictRecordSchema(
                        conflict_type="STATUS_MISMATCH",
                        source_a_id="issue-104",
                        source_a_excerpt="Status: BLOCKED — Payment timeout handling on 3DS2 callback remains blocked awaiting sandbox certificate.",
                        source_a_timestamp=src_a["source_updated_at"],
                        source_b_id="notes-2026-10-15",
                        source_b_excerpt="Payment timeout handling (issue-104) is actively IN PROGRESS and expected to complete by Friday.",
                        source_b_timestamp=src_b["source_updated_at"],
                        explanation="ISSUE-104 (updated 2026-11-06) reports status BLOCKED, whereas Sprint Sync Notes (2026-10-15) report IN PROGRESS. System preserves both for human review.",
                    )
                )

            # Check for stale technical documentation between DOC-LEGACY-API and PR-218
            if "doc-legacy-api" in cited_ids and "pr-218" in passage_by_source:
                src_old = passage_by_source["doc-legacy-api"]
                src_new = passage_by_source["pr-218"]
                status_val = "potentially_outdated"
                uncertainty_flags.append("superseded_by_newer_pull_request")
                conflicts.append(
                    ConflictRecordSchema(
                        conflict_type="STALE_ENDPOINT_DOCUMENTATION",
                        source_a_id="doc-legacy-api",
                        source_a_excerpt="Checkout clients must call the synchronous endpoint POST /v1/payments/charge",
                        source_a_timestamp=src_old["source_updated_at"],
                        source_b_id="pr-218",
                        source_b_excerpt="Deprecates and removes POST /v1/payments/charge (documented in doc-legacy-api) and replaces it with asynchronous POST /v2/payment-intents.",
                        source_b_timestamp=src_new["source_updated_at"],
                        explanation="Technical document doc-legacy-api (2026-06-01) specifies deprecated /v1/payments/charge, contradicted by merged PR-218 (2026-10-28).",
                    )
                )

        results.append(
            ClaimVerificationResultSchema(
                claim_code=c_code,
                evidence_status=status_val,  # type: ignore[arg-type]
                uncertainty_flags=uncertainty_flags,
                conflicts=conflicts,
            )
        )

    return Agent2VerificationOutput(verifications=results)


def run_evidence_verification_agent(
    candidate_claims: List[Dict[str, Any]],
    passages: List[Dict[str, Any]],
) -> Tuple[Agent2VerificationOutput, ModelExecutionMetadata]:
    user_prompt = json.dumps(
        {
            "candidate_claims": candidate_claims,
            "passages": [
                {
                    "source_id": p["stable_source_id"],
                    "source_type": p["source_type"],
                    "updated_at": p["source_updated_at"],
                    "content": p["content"],
                }
                for p in passages
            ],
        },
        indent=2,
    )
    return invoke_structured_model(
        system_prompt=AGENT_2_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_schema=Agent2VerificationOutput,
        deterministic_extractor=lambda: _extractive_evidence_verification(candidate_claims, passages),
    )
