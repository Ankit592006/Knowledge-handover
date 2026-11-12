# Onboarding Guide for New Developers

## 1. What This Project Does
Knowledge Handover turns scattered software project records into an evidence-linked, conflict-aware, human-approved handover package and 13-section successor continuation plan.

## 2. Important Files to Read First
1. `backend/app/main.py` — FastAPI application factory and router mounts.
2. `backend/app/models/entities.py` — Complete 15-table relational + `pgvector` schema.
3. `backend/app/agents/orchestrator/workflow.py` — LangGraph 3-agent orchestration pipeline.
4. `backend/app/modules/validation/service.py` — Deterministic L6 source-ID and permission validator.
5. `backend/app/modules/handovers/service.py` — End-to-end reconstruction, review, clarification, approval, and successor plan assembly.
6. `frontend/src/pages/PlatformWorkspace.tsx` — Role-aware React review and successor interface.

## 3. Suggested First Task for an Incoming Developer
Run `pytest -v` in `backend/` and inspect `backend/tests/integration/test_end_to_end_workflow.py` to trace the full lifecycle from user registration to successor receipt acknowledgement.
