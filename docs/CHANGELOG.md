# Changelog — Knowledge Handover Platform

## [2.1.0] — 2026-11-14
### Added & Upgraded
- **Live Groq OpenAI-Compatible LLM Integration (`LLM_PROVIDER="openai_compatible"`)**: Configured `render.yaml`, `backend/app/core/config.py`, and `app/agents/adapter/llm_adapter.py` to use Groq (`https://api.groq.com/openai/v1` with `llama-3.3-70b-versatile`) with strict `UnresolvedQuestionSchema` JSON validation and automatic `< 1ms` offline fallback to `rule-grounded-extractor-v1`.
- **Genuine 4-Persona Backend Role Switcher (`POST /api/v1/demo/switch-role`)**: Issues real database-backed HS256 JWTs and refresh tokens for `PROJECT_LEAD` (`preeti.lead@payflow.demo`), `OUTGOING_DEV` (`arjun.outgoing@payflow.demo`), `REVIEWER_SME` (`kavita.reviewer@payflow.demo`), and `SUCCESSOR` (`ankit.successor@payflow.demo`), plus anonymous read-only `GUEST_DEMO`.
- **One-Click Demo Reset (`POST /api/v1/demo/bootstrap-payflow?reset=true`)**: Resets `payflow-handover-001` back to a clean unapproved `v1` draft while preserving the append-only `audit_logs` history.
- **Role-Specific Navigation & Exclusive Successor Receipt**: Enforced role-tailored tabs, structured 13-Section Continuation Plan cards (`renderContinuationSectionContent`), 5-step Lifecycle Progress Bar, and exclusive `SUCCESSOR` permission on `POST /api/handovers/{id}/acknowledge`.
- **Centered Login / Register Modal Dialog**: Redesigned the authentication UI in `PlatformWorkspace.tsx` into a centered modal dialog with a segmented Login/Register mode switcher, full-width labeled inputs, inline error feedback, and a 2×2 Instant Persona quick-login grid.
- **Book-Professional Editorial Typography**: Configured *Libre Baskerville* headings, optical-sized *Source Serif 4* body prose, and *JetBrains Mono* citations across `frontend/index.html`, `frontend/tailwind.config.js`, and `frontend/src/index.css`.
- **Hackathon Final Project Report**: Generated `Knowledge_Handover_Hackathon_Final_Report.pdf`, `Knowledge_Handover_Hackathon_Final_Report.html`, `docs/Knowledge_Handover_Hackathon_Final_Report.md`, and `generate_project_report_pdf.py`.

## [1.0.0] — 2026-11-12
### Added
- Initial FastAPI Modular Monolith with 15 SQLAlchemy 2.0 ORM tables, Alembic migrations, and `pgvector` support.
- Argon2id password hashing, JWT access tokens, rotating SHA-256 refresh tokens, and 5-persona project RBAC.
- Synthetic **PayFlow** dataset (`app/modules/ingestion/service.py`) covering conflicting statuses, stale API docs, unassigned blockers, missing retry policy rationale, prompt-injection payloads, and synthetic restricted secrets.
- LangGraph 3-Agent Orchestrator (*Knowledge Extraction Agent*, *Evidence Verification Agent*, *Risk & Dependency Agent*) and Layer L6 Deterministic Backend Validator.
