# Testing Strategy & Test Suite — Knowledge Handover Platform (Continuity OS v2.1)

## 1. Backend Test Suite (`backend/tests/` — 10 Comprehensive Pytest Tests)
- `backend/tests/test_ai_and_security_guards.py`:
  1. Verifies pre-indexing secret redaction (`redact_secrets_from_text`) across API keys, Bearer tokens, connection strings, and private keys.
  2. Verifies adversarial prompt-injection isolation (`sanitize_untrusted_passage`).
  3. Verifies that `ClaimVerificationResultSchema` raises a `ValidationError` if an AI agent attempts to output `evidence_status="verified"`.
  4. Verifies deterministic chunking (`chunk_document_text`) and 384-dimensional embedding cosine similarity.
- `backend/tests/test_foundation_and_e2e.py`:
  5. Verifies `/api/v1/health` and root `/` status endpoints plus HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`).
  6. Verifies authentication registration, login, token refresh rotation, and replay rejection (`401`).
  7. Verifies LangGraph stop-on-failure halting (`HTTP 503`) when an agent fails after bounded retries.
  8. Verifies the complete PayFlow E2E lifecycle: source seeding, secret redaction, 3-agent reconstruction, Layer L6 fake citation stripping, clarification Q&A, claim verification, approval gate (`403` before approval, unlocked 13-section plan after approval), export (`markdown`/`json`), exclusive `SUCCESSOR` receipt acknowledgement, and append-only audit logs.
  9. Verifies `SEC-01` explicit RBAC and classification clearance (`PUBLIC`, `INTERNAL`, `RESTRICTED`).
  10. Verifies `GUEST_DEMO` anonymous read-only sandbox restrictions, `POST /api/v1/demo/switch-role` multi-persona JWT minting, and `POST /api/v1/demo/bootstrap-payflow?reset=true` reset to `v1`.

## 2. Frontend Test Suite (`frontend/tests/App.test.tsx` — Vitest + React Testing Library)
1. Verifies all 6 `EvidenceStatusBadge` states (`source_supported`, `conflicting`, `potentially_outdated`, `inferred`, `unknown`, `verified`) using the high-contrast emerald/teal/amber/rose/zinc palette.
2. Verifies the Overview launchpad, `GUEST_DEMO (Read-Only)` badge, and 4 authenticated role persona cards.
3. Verifies that `GUEST_DEMO` navigation is strictly restricted to `Overview`, `Dashboard`, and `Permitted Sources` (hiding `Review Workspace`, `Successor Plan`, `Audit Trail`, and upload forms).
4. Verifies role-specific navigation and action gates for `OUTGOING_DEV` (can answer clarifications and flag claims; cannot mark `verified` or approve) and `REVIEWER_SME` (can mark `verified`, approve, and view `Audit Trail`).
5. Verifies the `SUCCESSOR` waiting-for-approval locked screen when unapproved, and the structured 13-section Continuation Plan cards + exclusive **Acknowledge Handover Receipt** button once approved.

## 3. Commands to Run All Tests
```bash
# Backend Test Suite
cd backend
python -m pytest -v

# Frontend Test Suite & Production Build
cd ../frontend
npm test -- --run
npm run build
```
