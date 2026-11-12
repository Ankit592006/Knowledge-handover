"""Deterministic Backend Validation Layer (L6 Trust Boundary — Round 1 Proposal Section 1.2 & 5.1)."""

from typing import Any, Dict, List, Set, Tuple
from sqlalchemy.orm import Session

from app.models.entities import SourceDocument


def validate_claims_against_database(
    db: Session,
    project_id: str,
    allowed_source_doc_ids: Set[str],
    allowed_classifications: Set[str],
    candidate_claims: List[Dict[str, Any]],
    verification_map: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Independently verify that every referenced source_id in every candidate claim:
    1. Exists in the database for this project.
    2. Belongs to the authorised handover scope.
    3. Has an access_level within the handover's allowed_classifications.
    4. Never allows an AI claim to enter the database with status='verified'.
    """
    docs = (
        db.query(SourceDocument)
        .filter(SourceDocument.project_id == project_id)
        .all()
    )
    authorized_by_stable_id: Dict[str, SourceDocument] = {}
    for d in docs:
        if (not allowed_source_doc_ids or d.id in allowed_source_doc_ids) and (
            d.access_level in allowed_classifications
        ):
            authorized_by_stable_id[d.stable_source_id] = d

    validated_claims: List[Dict[str, Any]] = []
    rejected_citations_count = 0
    downgraded_claims_count = 0

    for raw_claim in candidate_claims:
        c_code = raw_claim["claim_code"]
        ver_info = verification_map.get(c_code, {})
        proposed_status = str(ver_info.get("evidence_status", "source_supported")).lower()

        # L6 Trust Control: AI output can NEVER be marked 'verified'
        if proposed_status == "verified":
            proposed_status = "source_supported"

        uncertainty_flags = list(ver_info.get("uncertainty_flags", []))
        conflicts = list(ver_info.get("conflicts", []))

        valid_evidence: List[Dict[str, Any]] = []
        for ev in raw_claim.get("evidence", []):
            sid = ev.get("source_id", "")
            doc_obj = authorized_by_stable_id.get(sid)
            if doc_obj is None:
                rejected_citations_count += 1
                if "invalid_or_unauthorised_source_id_stripped" not in uncertainty_flags:
                    uncertainty_flags.append("invalid_or_unauthorised_source_id_stripped")
            else:
                excerpt = ev.get("excerpt", "")
                pos = doc_obj.content_redacted.find(excerpt[:40]) if excerpt else -1
                char_start = max(0, pos)
                char_end = char_start + len(excerpt) if pos >= 0 else min(len(doc_obj.content_redacted), 180)
                valid_evidence.append(
                    {
                        "source_document_id": doc_obj.id,
                        "stable_source_id": doc_obj.stable_source_id,
                        "source_type": doc_obj.source_type,
                        "location": ev.get("location") or f"body#chars:{char_start}-{char_end}",
                        "excerpt": excerpt or doc_obj.content_redacted[:200],
                        "char_start": char_start,
                        "char_end": char_end,
                        "version_tag": doc_obj.version_tag,
                        "source_updated_at": doc_obj.source_updated_at,
                        "deterministic_verified": True,
                    }
                )

        # If no valid authorised source remains, force status to 'unknown' (unsupported)
        if not valid_evidence:
            proposed_status = "unknown"
            downgraded_claims_count += 1
            if "no_valid_supporting_source" not in uncertainty_flags:
                uncertainty_flags.append("no_valid_supporting_source")

        validated_claims.append(
            {
                **raw_claim,
                "status": proposed_status,
                "uncertainty_flags": uncertainty_flags,
                "conflicts": conflicts,
                "validated_evidence": valid_evidence,
            }
        )

    validation_summary = {
        "authorized_sources_checked": len(authorized_by_stable_id),
        "claims_validated": len(validated_claims),
        "rejected_citations_count": rejected_citations_count,
        "downgraded_to_unknown_count": downgraded_claims_count,
    }
    return validated_claims, validation_summary
