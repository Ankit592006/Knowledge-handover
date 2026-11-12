# Testing Strategy & Test Suite — Knowledge Handover Platform

## 1. Test Files Implemented
- `backend/tests/unit/test_foundation.py` — Verifies database schema creation (all 15 tables), `/api/v1/health` and `/api/health` readiness, and HTTP security headers (`X-Content-Type-Options`, `X-Frame-Options`).
- `backend/tests/ai/test_ai_and_security_guards.py` — Verifies that `ClaimVerificationResultSchema` rejects `verified` from AI agents, tests secret redaction (`scan_and_redact_secrets`), tests prompt-injection isolation (`sanitize_untrusted_passage`), and verifies offset chunking + semantic vector cosine similarity.
- `backend/tests/integration/test_end_to_end_workflow.py` — End-to-end journey test covering 5 user personas, token refresh replay prevention, cross-project IDOR blocking, PayFlow synthetic seeding, secret redaction, LangGraph agent failure stop-on-failure (`503`), full 3-agent reconstruction, conflict & staleness detection, unknown owner preservation, outgoing developer clarification, reviewer verification & approval, successor 13-section view, receipt acknowledgement, and append-only audit log verification.
- `frontend/tests/App.test.tsx` — Vitest component tests for the 6-state `EvidenceStatusBadge` and main workflow overview rendering.

## 2. Commands to Run Tests
```bash
# Backend Test Suite
cd backend
pytest -v

# Frontend Test Suite
cd frontend
npm test
```

## 3. Execution Status Note
Because the current Windows agent environment does not include `powershell` on `%PATH%` for tool subprocess spawning, automated test files have been written in full and configured in `.github/workflows/ci.yml` for execution via local terminal or CI.
