# API Documentation — Knowledge Handover Platform (Continuity OS v2.1)

All endpoints are mounted at both `/api/v1` and `/api` (satisfying Round 1 Proposal Section 6.4 exact paths). Interactive OpenAPI documentation is served at `/docs` and `/redoc`.

## 1. System Health & Root Status
- `GET /` — Root service metadata, environment status, and discovery links (`/api/v1/health`, `/docs`, `/redoc`, `/api/handovers`).
- `GET /api/v1/health` (and `GET /api/health`) — Database connectivity, dialect (`postgresql` vs `sqlite`), `pgvector` extension status, active `llm_provider` (`openai_compatible`), and `llm_model` (`llama-3.3-70b-versatile`).

## 2. Live Demo & Multi-Persona Session Endpoints
- `POST /api/v1/demo/bootstrap-payflow` (and `?reset=true`) — Seeds/ensures the synthetic PayFlow workspace, 4 demo user personas, and `payflow-handover-001` package. Passing `?reset=true` resets the handover back to a clean unapproved `v1` draft (`ready_for_review` / `not_approved`) while preserving the append-only audit trail (`DEMO_HANDOVER_RESET_TO_V1`).
- `POST /api/v1/demo/switch-role` — Body: `{ "project_role": "PROJECT_LEAD" | "OUTGOING_DEV" | "REVIEWER_SME" | "SUCCESSOR" }`. Mints a real database-backed HS256 JWT access token and rotating refresh token for the selected PayFlow persona and records `DEMO_ROLE_SESSION_SWITCHED` in `audit_logs`.

## 3. Core Handover Lifecycle Endpoints
- `POST /api/handovers` — Create a scoped handover workspace.
- `POST /api/handovers/{id}/sources/import` — Import selected synthetic or uploaded sources into handover scope.
- `POST /api/handovers/{id}/reconstruct` — Execute permission-filtered RAG retrieval + LangGraph 3-Agent orchestration + Layer L6 deterministic database validation.
- `GET /api/handovers/{id}/status` — Retrieve lightweight handover lifecycle status (`status`, `currentVersion`, `agentTelemetry`, `updatedAt`) accessible to all project members including `SUCCESSOR` prior to approval.
- `GET /api/handovers/{id}/draft` — Retrieve structured draft, claims, conflicts, risks, open questions, and next actions (returns `403 Forbidden` for `SUCCESSOR` before human approval).
- `PATCH /api/claims/{id}?handover_id={hid}` — Update claim review state (`verified`, `needs_clarification`, `rejected`) and reviewer notes (`verified` restricted strictly to `PROJECT_LEAD` and `REVIEWER_SME`).
- `POST /api/handovers/{id}/clarifications/{question_id}` — Submit outgoing developer or lead answer to an open clarification question and enrich the linked claim's rationale.
- `POST /api/handovers/{id}/approve` — Approve reviewed handover package (`PROJECT_LEAD` / `REVIEWER_SME` only), freeze an immutable `HandoverVersion` snapshot, and unlock the Successor Continuation Plan.
- `GET /api/handovers/{id}/successor-view` — Retrieve the 13-Section role-filtered Successor Continuation Plan (`403 Forbidden` until approved).
- `POST /api/handovers/{id}/acknowledge` — Record formal handover receipt acknowledgement (strictly restricted to `ProjectRole.SUCCESSOR`).
- `GET /api/v1/handovers/{id}/export?format_type=markdown|json` — Export approved handover package as Markdown or JSON.
- `GET /api/v1/handovers/{id}/audit-logs` — Retrieve append-only governance audit trail (`PROJECT_LEAD` and `REVIEWER_SME` only).

## 4. Authentication, Projects & Source Ingestion Endpoints
- `POST /api/v1/auth/register` / `POST /api/v1/auth/login` / `POST /api/v1/auth/refresh` / `POST /api/v1/auth/logout` / `GET /api/v1/auth/me`
- `POST /api/v1/projects` / `GET /api/v1/projects` / `GET /api/v1/projects/{id}` / `POST /api/v1/projects/{id}/members`
- `POST /api/v1/projects/{id}/sources/seed-payflow` / `POST /api/v1/projects/{id}/sources/upload` / `GET /api/v1/projects/{id}/sources` / `GET /api/v1/sources/{id}`
