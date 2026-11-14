# AI Architecture — LangGraph Orchestrator, Dual-Mode Groq Adapter & L6 Trust Gate

## 1. Hybrid 3-Agent LangGraph Pipeline (`backend/app/agents/`)
- **Orchestrator (`app/agents/orchestrator/workflow.py`)**: Compiles a `StateGraph(HandoverGraphState)` executing `node_knowledge_extraction` → `node_evidence_verification` → `node_risk_dependency` with bounded retries (`LLM_MAX_RETRIES=2`) and conditional `stop-on-failure` routing (`_route_after_node`). If any agent fails after retries, orchestration halts immediately (`halted=True`), sets `handover.status = "failed"`, logs `HANDOVER_RECONSTRUCTION_HALTED`, and returns `HTTP 503` so partial output is never published.
- **Agent 1 — Knowledge Extraction Agent (`app/agents/knowledge_extraction/agent.py`)**:
  - Sanitizes untrusted chunks via `sanitize_untrusted_passage()` (`app/agents/adapter/prompt_guard.py`) to neutralize embedded prompt-injection strings (`[ADVERSARIAL_INSTRUCTION_ISOLATED]`) and wraps passages in `<untrusted_evidence source_id='...'>`.
  - Extracts `CandidateClaimSchema` items across 8 categories (`project_overview`, `technical_context`, `key_decision`, `completed_work`, `active_work`, `blocked_work`, `responsibility`, `operational_info`), preserving `owner_name=None` when unassigned, and generates `UnresolvedQuestionSchema` clarifications (`related_claim_code`, `question`, `reason`).
- **Agent 2 — Evidence Verification Agent (`app/agents/evidence_verification/agent.py`)**:
  - Cross-checks every candidate claim against retrieved source passages and their `source_updated_at` timestamps.
  - Detects status contradictions (`issue-104` `BLOCKED` vs `notes-2026-10-15` `IN PROGRESS`) and stale documentation (`doc-legacy-api` `/v1/payments/charge` vs `pr-218` `/v2/payment-intents`), attaching structured `ConflictRecordSchema` objects.
  - Enforces `@field_validator("evidence_status")` (`forbid_ai_verified_status`), which strictly prohibits any AI output from setting `evidence_status="verified"`.
- **Agent 3 — Risk & Dependency Analysis Agent (`app/agents/risk_dependency/agent.py`)**:
  - Extracts project `blocker`, `risk`, and `dependency` records (`CandidateRiskDependencySchema`) and synthesizes a priority-ranked list of onboarding steps (`CandidateNextActionSchema`) linked to claim codes.

## 2. Dual-Mode OpenAI-Compatible (Groq) + Deterministic Extractive Adapter (`app/agents/adapter/llm_adapter.py`)
`invoke_structured_model()` supports three runtime configurations via `LLM_PROVIDER`:
1. **`LLM_PROVIDER="openai_compatible"` (Production Default on Render)**:
   - Invokes Groq (`https://api.groq.com/openai/v1/chat/completions`) with `llama-3.3-70b-versatile`, `temperature=0.0`, `response_format={"type": "json_object"}`, and strict Pydantic JSON Schema validation (`response_schema.model_validate_json()`).
2. **`LLM_PROVIDER="ollama"`**:
   - Connects to local Ollama (`http://localhost:11434/api/chat`) with `qwen2.5:7b-instruct`.
3. **Automatic Deterministic Fallback (`deterministic_extractive` / `rule-grounded-extractor-v1`)**:
   - If `LLM_API_KEY` is not set in local/CI environments or if the cloud LLM is unreachable, the adapter seamlessly executes the deterministic rule-grounded extractor and records `provider_requested`, `provider_used`, `model_name`, `live_llm_invoked`, `latency_ms`, and `fallback_reason` in `agentTelemetry`.

## 3. Deterministic Backend Validation Layer — L6 Trust Boundary (`app/modules/validation/service.py`)
After the 3-agent graph finishes, `validate_claims_against_database()` independently verifies every cited `source_id` against PostgreSQL/SQLite to confirm existence, handover scope membership, and classification clearance. Unauthorised or non-existent citations are stripped (`invalid_or_unauthorised_source_id_stripped`), and claims with zero remaining valid sources are automatically downgraded to `unknown`.
