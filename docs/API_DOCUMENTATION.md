# API Documentation — Knowledge Handover Platform

All endpoints are mounted at both `/api/v1` and `/api` (matching Round 1 Proposal Section 6.4). Interactive OpenAPI documentation is served at `/docs` and `/redoc`.

## 1. Core Handover & Proposal Endpoints
- `POST /api/handovers` — Create a scoped handover workspace.
- `POST /api/handovers/{id}/sources/import` — Import selected synthetic or uploaded sources into scope.
- `POST /api/handovers/{id}/reconstruct` — Run permission-filtered RAG + LangGraph 3-Agent orchestration + deterministic validation.
- `GET /api/handovers/{id}/draft` — Retrieve structured draft, claims, conflicts, risks, open questions, and next actions (blocked for `SUCCESSOR` before approval).
- `PATCH /api/claims/{id}` — Edit claim text/owner, resolve conflicts, reject claim, or mark `verified` (`PROJECT_LEAD` / `REVIEWER_SME` only).
- `POST /api/handovers/{id}/clarifications/{question_id}` — Submit outgoing developer answer to an open clarification question.
- `POST /api/handovers/{id}/approve` — Approve reviewed handover package, create version snapshot, and unlock successor view.
- `GET /api/handovers/{id}/successor-view` — Retrieve 13-section role-filtered Successor Continuation Plan.
- `POST /api/handovers/{id}/acknowledge` — Record successor receipt acknowledgement.

## 2. Authentication, Projects, Sources & Audit Endpoints
- `GET /api/v1/health` — Database, `pgvector`, and LLM provider readiness.
- `POST /api/v1/auth/register` / `POST /api/v1/auth/login` / `POST /api/v1/auth/refresh` / `POST /api/v1/auth/logout` / `GET /api/v1/auth/me`
- `POST /api/v1/projects` / `GET /api/v1/projects` / `GET /api/v1/projects/{id}` / `POST /api/v1/projects/{id}/members`
- `POST /api/v1/projects/{id}/sources/seed-payflow` / `POST /api/v1/projects/{id}/sources/upload` / `GET /api/v1/projects/{id}/sources` / `GET /api/v1/sources/{id}`
- `GET /api/v1/handovers/{id}/audit-logs` / `GET /api/v1/handovers/{id}/export?format_type=json|markdown`
- `POST /api/v1/demo/bootstrap-payflow` — One-click PayFlow demo initializer.
