# Security Engineering & Threat Model — Knowledge Handover Platform

## 1. Threat Model & Mitigations (NIST AI RMF & OWASP Top 10 for LLM Aligned)
| Threat | Mitigation Implemented |
|---|---|
| **Indirect Prompt Injection** | `sanitize_untrusted_passage()` isolates override directives (`[ADVERSARIAL_INSTRUCTION_ISOLATED]`) and wraps passages in `<untrusted_evidence>` tags. |
| **Hallucinated Citations / Invented Owners** | `validate_claims_against_database()` verifies every `source_id` against PostgreSQL and downgrades unsupported claims to `unknown`; owners are `null` unless supported by evidence. |
| **AI Self-Verification Bypass** | Pydantic validator `forbid_ai_verified_status` and L6 validator block AI from outputting `verified`; `PATCH /api/claims/{id}` enforces `PROJECT_LEAD` or `REVIEWER_SME` role. |
| **Sensitive Credential Leakage** | `scan_and_redact_secrets()` redacts Stripe keys, PATs, JWTs, AWS keys, and password assignments to `[REDACTED_SECRET]` at ingestion. |
| **Permission Leakage / IDOR** | `get_project_membership()` enforces project membership, role checks, and `allowed_classifications` before RAG retrieval and before serving the Successor view. |
| **Unapproved Draft Exposure** | `GET /api/handovers/{id}/draft` and `/successor-view` return `403 Forbidden` to `SUCCESSOR` until `status` is `approved`. |
