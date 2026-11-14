# Security Engineering & Threat Model — Knowledge Handover Platform (`SEC-01`)

## 1. Threat Model & Mitigations (NIST AI RMF & OWASP Top 10 for LLM Aligned)

| Threat | Mitigation Implemented in Codebase |
|---|---|
| **Indirect Prompt Injection** | `sanitize_untrusted_passage()` (`app/agents/adapter/prompt_guard.py`) isolates override directives (`[ADVERSARIAL_INSTRUCTION_ISOLATED]`) and wraps passages in `<untrusted_evidence source_id='...'>` tags before LLM context assembly. |
| **Hallucinated Citations / Invented Owners** | Layer L6 `validate_claims_against_database()` (`app/modules/validation/service.py`) verifies every cited `source_id` against PostgreSQL/SQLite, strips unauthorised or non-existent citations, and downgrades unsupported claims to `unknown`; owners remain `null` unless explicitly stated in evidence. |
| **AI Self-Verification Bypass** | Pydantic validator `forbid_ai_verified_status` (`app/agents/schemas.py`) and the L6 validator block AI from outputting `verified`; `PATCH /api/claims/{id}` enforces `PROJECT_LEAD` or `REVIEWER_SME` role before setting `verified`. |
| **Sensitive Credential Leakage** | `redact_secrets_from_text()` (`app/modules/ingestion/redaction.py`) scrubs Stripe keys (`sk_live_`, `rk_live_`), GitHub PATs (`ghp_`), Bearer JWTs, AWS keys (`AKIA`), DB connection URLs, and private keys before storage, chunking, or external LLM calls. |
| **Permission Leakage / IDOR (`SEC-01`)** | `get_project_membership()` (`app/core/security.py`) enforces explicit `ProjectMember` membership, role checks, and `allowed_classifications` (`PUBLIC`, `INTERNAL`, `RESTRICTED`) before RAG retrieval and before serving source documents or Successor views. Platform `ADMIN` users do not receive implicit access to private projects or `RESTRICTED` clearance. |
| **Unapproved Draft Exposure** | `GET /api/handovers/{id}/draft` and `GET /api/handovers/{id}/successor-view` return `403 Forbidden` to `SUCCESSOR` until human sign-off transitions status to `approved`. |
| **Exclusive Successor Receipt Sign-Off** | `POST /api/handovers/{id}/acknowledge` strictly requires `ProjectRole.SUCCESSOR`, preventing other roles from forging successor receipt acknowledgement. |
