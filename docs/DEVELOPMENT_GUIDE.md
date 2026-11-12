# Development Guide — Knowledge Handover Platform

## 1. Repository Structure
- `backend/app/core/` — Configuration, database session, Argon2/JWT security.
- `backend/app/models/` — SQLAlchemy 2.0 entities and domain enums.
- `backend/app/schemas/` — Request/response Pydantic v2 schemas.
- `backend/app/modules/` — Deterministic domain services (`auth`, `projects`, `ingestion`, `processing`, `validation`, `handovers`, `audit`).
- `backend/app/agents/` — LangGraph orchestrator, 3 specialised agents, prompt guard, and open-source model adapter.
- `frontend/src/` — React + TypeScript + Tailwind UI components, hooks, and pages.

## 2. How to Add a New AI Agent or Check
1. Define strict input/output Pydantic schemas in `backend/app/agents/schemas.py`.
2. Implement the agent module under `backend/app/agents/<agent_name>/` using `invoke_structured_model()`.
3. Register the node in `backend/app/agents/orchestrator/workflow.py` and add deterministic verification in `backend/app/modules/validation/service.py`.
