"""Deterministic Backend Validation Layer (L6.1 Provenance + L6.2 Second-Pass Citation-Support Verification)."""

import re
from typing import Any, Dict, List, Set, Tuple
from sqlalchemy.orm import Session

from app.models.entities import SourceDocument

_STOPWORDS: Set[str] = {
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
    "has", "have", "had", "not", "but", "all", "can", "will", "into", "before",
    "after", "during", "while", "when", "where", "which", "who", "whom", "whose",
    "must", "should", "would", "could", "our", "their", "its", "via", "using",
    "used", "uses", "been", "being", "also", "than", "then", "only", "such",
}

_SYNONYM_GROUPS: List[Set[str]] = [
    {"payment", "payments", "checkout", "transaction", "transactions", "charge"},
    {"blocked", "blocker", "awaiting", "pending", "unassigned"},
    {"outdated", "deprecated", "deprecates", "superseded", "superseding", "legacy", "replaces"},
    {"migration", "migrations", "alembic", "schema"},
    {"flush", "flushing", "clear", "clearing", "idem", "idempotency"},
    {"retry", "retries", "backoff", "exponential", "dlq", "timeout"},
    {"certificate", "cert", "signing", "sandbox", "webhook"},
]


def _tokenize_meaningful(text: str) -> Set[str]:
    raw_tokens = re.findall(r"[a-z0-9_:/-]+", text.lower())
    out: Set[str] = set()
    for tok in raw_tokens:
        cleaned = tok.strip("-_:/")
        if len(cleaned) >= 2 and cleaned not in _STOPWORDS:
            out.add(cleaned)
    return out


def _expand_synonyms(tokens: Set[str]) -> Set[str]:
    expanded = set(tokens)
    for grp in _SYNONYM_GROUPS:
        if expanded.intersection(grp):
            expanded.update(grp)
    return expanded


def evaluate_citation_support(
    claim_text: str,
    excerpt: str,
    doc_content: str = "",
) -> Tuple[str, float, str]:
    """
    Round 3 Improvement 2 (L6.2 Second-Pass Citation-Support Check):
    Verify whether the cited excerpt actually supports the claim text, rather than merely pointing to an existing document.
    Returns (support_status: 'supported' | 'weak' | 'mismatch', support_score: float, explanation: str).
    """
    if not claim_text.strip() or not (excerpt.strip() or doc_content.strip()):
        return (
            "mismatch",
            0.0,
            "Empty claim or empty source excerpt cannot substantiate assertion.",
        )

    claim_tokens = _tokenize_meaningful(claim_text)
    if not claim_tokens:
        return ("weak", 0.35, "Claim contains insufficient technical tokens for strict entailment.")

    excerpt_tokens = _tokenize_meaningful(excerpt)
    doc_tokens = _tokenize_meaningful(doc_content[:2500]) if doc_content else set()

    expanded_excerpt = _expand_synonyms(excerpt_tokens)
    expanded_doc = _expand_synonyms(excerpt_tokens.union(doc_tokens))

    direct_hits = claim_tokens.intersection(expanded_excerpt)
    context_hits = claim_tokens.intersection(expanded_doc)

    direct_ratio = len(direct_hits) / max(len(claim_tokens), 1)
    context_ratio = len(context_hits) / max(len(claim_tokens), 1)

    # Boost for exact technical anchors ONLY when the cited excerpt itself has meaningful lexical overlap (>= 20%)
    technical_anchors = [
        t for t in claim_tokens if any(ch.isdigit() for ch in t) or "/" in t or ":" in t or "-" in t
    ]
    anchor_hits_in_excerpt = [
        a for a in technical_anchors if a in expanded_excerpt
    ]
    if direct_ratio < 0.20:
        # Cited excerpt shares < 20% of the claim's concepts -> citation does not substantiate the claim
        score = round(max(0.05, direct_ratio * 0.85), 2)
        return (
            "mismatch",
            score,
            "Citation mismatch: Cited excerpt has insufficient concept overlap with the claim assertion (provenance pointer only, not proof).",
        )

    anchor_bonus = (
        0.20
        if (technical_anchors and len(anchor_hits_in_excerpt) >= len(technical_anchors) * 0.5)
        else 0.0
    )

    raw_score = (direct_ratio * 0.68) + (context_ratio * 0.22) + anchor_bonus
    # Normalize score to [0.0, 0.99]
    support_score = round(min(0.98, max(0.05, raw_score * 1.25)), 2)

    if support_score >= 0.45:
        matched_sample = ", ".join(sorted(list(direct_hits))[:5])
        return (
            "supported",
            support_score,
            f"Second-pass L6.2 check passed: Excerpt directly substantiates key claim concepts ({matched_sample}).",
        )
    if support_score >= 0.22:
        matched_sample = ", ".join(sorted(list(context_hits))[:4]) or "partial context"
        return (
            "weak",
            support_score,
            f"Weak citation support: Excerpt shares partial context ({matched_sample}) but does not fully prove all claim details.",
        )
    return (
        "mismatch",
        support_score,
        "Citation mismatch: Cited excerpt does not substantiate the claim assertion (provenance pointer only, not proof).",
    )


def validate_claims_against_database(
    db: Session,
    project_id: str,
    allowed_source_doc_ids: Set[str],
    allowed_classifications: Set[str],
    candidate_claims: List[Dict[str, Any]],
    verification_map: Dict[str, Dict[str, Any]],
    enforce_support_verification: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    L6.1 + L6.2 Deterministic Trust Boundary:
    1. Independently verify that every referenced source_id exists in the database, is not revoked,
       belongs to the authorised handover scope, and complies with allowed_classifications.
    2. Never allows an AI claim to enter the database with status='verified'.
    3. Executes L6.2 Second-Pass Citation-Support Verification ('supported' | 'weak' | 'mismatch')
       on every citation and downgrades claims with mismatched citations.
    """
    docs = (
        db.query(SourceDocument)
        .filter(SourceDocument.project_id == project_id)
        .all()
    )
    authorized_by_stable_id: Dict[str, SourceDocument] = {}
    for d in docs:
        is_revoked = bool((d.metadata_json or {}).get("access_revoked", False))
        if (
            not is_revoked
            and (not allowed_source_doc_ids or d.id in allowed_source_doc_ids)
            and (d.access_level in allowed_classifications)
        ):
            authorized_by_stable_id[d.stable_source_id] = d

    validated_claims: List[Dict[str, Any]] = []
    rejected_citations_count = 0
    downgraded_claims_count = 0
    supported_citations_count = 0
    weak_citations_count = 0
    mismatched_citations_count = 0

    for raw_claim in candidate_claims:
        c_code = raw_claim["claim_code"]
        c_text = raw_claim.get("text", "")
        ver_info = verification_map.get(c_code, {})
        proposed_status = str(ver_info.get("evidence_status", "source_supported")).lower()

        # L6 Trust Control: AI output can NEVER be marked 'verified'
        if proposed_status == "verified":
            proposed_status = "source_supported"

        uncertainty_flags = list(ver_info.get("uncertainty_flags", []))
        conflicts = list(ver_info.get("conflicts", []))

        valid_evidence: List[Dict[str, Any]] = []
        claim_support_verdicts: List[str] = []
        claim_support_scores: List[float] = []

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
                char_end = (
                    char_start + len(excerpt)
                    if pos >= 0
                    else min(len(doc_obj.content_redacted), 180)
                )
                resolved_excerpt = excerpt or doc_obj.content_redacted[:200]

                support_status, support_score, support_explanation = evaluate_citation_support(
                    claim_text=c_text,
                    excerpt=resolved_excerpt,
                    doc_content=doc_obj.content_redacted,
                )
                claim_support_verdicts.append(support_status)
                claim_support_scores.append(support_score)

                if support_status == "supported":
                    supported_citations_count += 1
                elif support_status == "weak":
                    weak_citations_count += 1
                else:
                    mismatched_citations_count += 1

                valid_evidence.append(
                    {
                        "source_document_id": doc_obj.id,
                        "stable_source_id": doc_obj.stable_source_id,
                        "source_type": doc_obj.source_type,
                        "location": ev.get("location") or f"body#chars:{char_start}-{char_end}",
                        "excerpt": resolved_excerpt,
                        "char_start": char_start,
                        "char_end": char_end,
                        "version_tag": doc_obj.version_tag,
                        "source_updated_at": doc_obj.source_updated_at,
                        "deterministic_verified": True,
                        "support_status": support_status,
                        "support_score": support_score,
                        "support_explanation": support_explanation,
                    }
                )

        # If no valid authorised source remains, force status to 'unknown' (unsupported)
        if not valid_evidence:
            proposed_status = "unknown"
            downgraded_claims_count += 1
            if "no_valid_supporting_source" not in uncertainty_flags:
                uncertainty_flags.append("no_valid_supporting_source")
        elif enforce_support_verification:
            # Second-pass L6.2 enforcement: downgrade claims whose citations are all 'mismatch' or only 'weak'
            if all(v == "mismatch" for v in claim_support_verdicts):
                proposed_status = "unknown"
                downgraded_claims_count += 1
                if "citation_support_mismatch_detected" not in uncertainty_flags:
                    uncertainty_flags.append("citation_support_mismatch_detected")
            elif "supported" not in claim_support_verdicts and any(
                v == "weak" for v in claim_support_verdicts
            ):
                if proposed_status == "source_supported":
                    proposed_status = "inferred"
                if "citation_support_weak" not in uncertainty_flags:
                    uncertainty_flags.append("citation_support_weak")

        overall_support = "supported"
        if not valid_evidence or all(v == "mismatch" for v in claim_support_verdicts):
            overall_support = "mismatch"
        elif "supported" not in claim_support_verdicts:
            overall_support = "weak"

        avg_support_score = (
            round(sum(claim_support_scores) / len(claim_support_scores), 2)
            if claim_support_scores
            else 0.0
        )

        validated_claims.append(
            {
                **raw_claim,
                "status": proposed_status,
                "uncertainty_flags": uncertainty_flags,
                "conflicts": conflicts,
                "validated_evidence": valid_evidence,
                "citation_support_status": overall_support,
                "citation_support_score": avg_support_score,
            }
        )

    validation_summary = {
        "authorized_sources_checked": len(authorized_by_stable_id),
        "claims_validated": len(validated_claims),
        "rejected_citations_count": rejected_citations_count,
        "downgraded_to_unknown_count": downgraded_claims_count,
        "l6_2_second_pass_support": {
            "enabled": enforce_support_verification,
            "supported_citations_count": supported_citations_count,
            "weak_citations_count": weak_citations_count,
            "mismatched_citations_count": mismatched_citations_count,
        },
    }
    return validated_claims, validation_summary
