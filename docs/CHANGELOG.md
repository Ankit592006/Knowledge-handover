# Changelog — Knowledge Handover Platform

## [1.0.0] — 2026-11-12
### Added
- Complete repository folder structure (`backend/`, `frontend/`, `data/`, `docs/`, `scripts/`, `.github/workflows/`).
- FastAPI Modular Monolith with 15 SQLAlchemy 2.0 ORM tables, Alembic migrations, and `pgvector` support.
- Argon2id password hashing, JWT access tokens, rotating SHA-256 refresh tokens, and 5-persona project RBAC.
- Synthetic **PayFlow** dataset (`app/seeds/payflow_data.py`) with 9 realistic records covering conflicting statuses, stale API docs, unassigned blockers, missing retry policy rationale, prompt-injection test payloads, and synthetic restricted secrets.
- Automatic secret scanning & redaction (`[REDACTED_SECRET]`), offset-preserving chunking, and permission-filtered RAG retrieval.
- LangGraph 3-Agent Orchestrator (*Knowledge Extraction Agent*, *Risk & Dependency Agent*, *Evidence Verification Agent*) with Open-Source Model Adapter and Deterministic Backend Validator.
- Human Review Workspace, Outgoing Developer Clarification Loop, Approval Gate, 13-Section Successor Continuation Plan, Receipt Acknowledgement, and Append-Only Audit Log.
- React + TypeScript + Tailwind CSS frontend (`PlatformWorkspace.tsx`, `EvidenceInspectorModal.tsx`, `EvidenceStatusBadge.tsx`) and automated test suites (`pytest` + `vitest`).
