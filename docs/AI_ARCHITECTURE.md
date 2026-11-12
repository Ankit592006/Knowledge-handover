# AI Architecture — LangGraph Orchestrator & 3 Specialised Agents

## 1. Hybrid Multi-Agent Pipeline (`backend/app/agents/`)
- **Orchestrator (`app/agents/orchestrator/workflow.py`)**: Compiles a `StateGraph(HandoverGraphState)` executing `knowledge_extraction` → `risk_dependency` → `evidence_verification` with bounded retries (`LLM_MAX_RETRIES`) and conditional `stop-on-failure` routing. If any required agent fails, `publication_blocked=True` and status transitions to `failed`.
- **Agent 1 — Knowledge Extraction Agent (`app/agents/knowledge_extraction/agent.py`)**: Extracts schema-constrained candidate claims, decisions, completed/active/blocked tasks, evidence-backed owners (`None` when unstated), and unresolved clarification questions.
- **Agent 3 — Risk & Dependency Analysis Agent (`app/agents/risk_dependency/agent.py`)**: Extracts blockers, operational risks, evidence-backed dependencies, and priority-ranked next actions.
- **Agent 2 — Evidence Verification Agent (`app/agents/evidence_verification/agent.py`)**: Verifies claim-to-source links, detects status contradictions (`issue-104` vs `notes-2026-10-15`) and stale documentation (`doc-legacy-api` vs `pr-218`), and assigns one of `source_supported`, `conflicting`, `potentially_outdated`, `inferred`, or `unknown`. Schema validator `forbid_ai_verified_status` strictly prevents any AI output from setting `verified`.

## 2. Deterministic Backend Validation (`app/modules/validation/service.py`)
After Agent 2 completes, the deterministic validator checks every cited `source_id` against PostgreSQL to confirm existence and classification clearance. Unauthorised or non-existent citations are stripped and unsupported claims are downgraded to `unknown`.
