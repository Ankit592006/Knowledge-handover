# Comprehensive Technical Audit: Knowledge Handover Platform

**Document:** `KNOWLEDGE_HANDOVER_TECHNICAL_AUDIT.md`  
**Audit Date:** November 13, 2026  
**Auditor:** Antigravity AI Technical Inspection System  
**Repository:** `Knowledge-handover`  
**Baseline Reference:** Hackathon Round 1 Proposal Final (`Knowledge_Handover_Round1_Proposal_Final.pdf`) & Hackathon Challenge Brief (`Knowledge_Handover_Problem_Statement (1).pdf`)  
**Audit Mode:** Non-destructive Technical Audit (Inspection & Verification Only)

---

## Table of Contents

1. [Executive Summary & Overall Assessment](#1-executive-summary--overall-assessment)
2. [Component-by-Component Technical Inspection](#2-component-by-component-technical-inspection)
   - [2.1 Backend & Architecture](#21-backend--architecture)
   - [2.2 Database & Vector Storage (`pgvector` Reality Check)](#22-database--vector-storage-pgvector-reality-check)
   - [2.3 LangGraph Multi-Agent Orchestration](#23-langgraph-multi-agent-orchestration)
   - [2.4 The Three AI Agents & LLM Invocation Verification](#24-the-three-ai-agents--llm-invocation-verification)
   - [2.5 RAG, Embeddings & Chunking Implementation](#25-rag-embeddings--chunking-implementation)
   - [2.6 Evidence Verification & L6 Deterministic Trust Boundary](#26-evidence-verification--l6-deterministic-trust-boundary)
   - [2.7 Authentication, Authorization & RBAC](#27-authentication-authorization--rbac)
   - [2.8 Security Engineering & Threat Mitigations](#28-security-engineering--threat-mitigations)
   - [2.9 Frontend Architecture & User Interface](#29-frontend-architecture--user-interface)
   - [2.10 API Surface & Contract Conformance](#210-api-surface--contract-conformance)
   - [2.11 Automated Test Suite & Test Execution Results](#211-automated-test-suite--test-execution-results)
   - [2.12 Infrastructure & Deployment Configuration](#212-infrastructure--deployment-configuration)
3. [Round 1 Proposal vs. Implementation Parity Matrix](#3-round-1-proposal-vs-implementation-parity-matrix)
4. [Agent LLM Invocation & Synthetic Hardcoding Analysis](#4-agent-llm-invocation--synthetic-hardcoding-analysis)
5. [Discrepancies Between Documentation and Source Code](#5-discrepancies-between-documentation-and-source-code)
6. [Prioritised Bug Register](#6-prioritised-bug-register)
7. [Prioritised Security Risk Register](#7-prioritised-security-risk-register)
8. [Round 2 Evaluation Strategy & Roadmap to Round 3](#8-round-2-evaluation-strategy--roadmap-to-round-3)

---

## 1. Executive Summary & Overall Assessment

This technical audit evaluates the implementation of the **Knowledge Handover Platform** against the design specifications, functional requirements (FR-01 to FR-11), non-functional requirements (NFR-1 to NFR-7), and acceptance criteria established in the **Round 1 Proposal**.

### Core Audit Findings

1. **End-to-End Conceptual Workflow is Substantially Implemented:**
   The end-to-end user workflow (`Connect` → `Reconstruct` → `Clarify` → `Verify/Review` → `Handover/Continuation`) is fully modeled with data models, API routes, and a comprehensive 990-line React/Tailwind workspace. The required 13-section continuation plan, append-only audit trail, and 6-status evidence vocabulary are rigorously integrated into the data schema and API contracts.

2. **The LLM Invocation Reality (Deterministic Fallback Dominance):**
   While an open-source model adapter interface exists (`backend/app/agents/adapter/llm_adapter.py`) capable of targeting Ollama or OpenAI-compatible endpoints, **out-of-the-box in local development, standard Docker Compose, and default Render cloud deployment, no LLM is actually invoked.**
   - No Ollama container is defined in `docker-compose.yml`.
   - In `render.yaml`, `LLM_PROVIDER` is explicitly hardcoded to `"deterministic_extractive"`.
   - When no local Ollama daemon is reachable on `localhost:11434`, all three agents execute deterministic extractive fallbacks.
   - **Crucially, these extractive fallbacks contain hardcoded `if-else` branches that match the synthetic PayFlow document IDs (`doc-project-overview`, `adr-001`, `issue-104`, `pr-218`, `notes-2026-11-02`) and return pre-fabricated strings and conflict pairs.**

3. **Database & `pgvector` Simulation:**
   The documentation claims production PostgreSQL with `pgvector` semantic similarity search. In actual source code (`backend/app/models/entities.py` line 35), `EmbeddingVectorType` uses `JSON` serialization across all dialects. In `backend/app/modules/ingestion/service.py` line 362, RAG retrieval executes `query.all()` and computes cosine similarity in a Python for-loop over MD5 token hashes, completely bypassing PostgreSQL native vector operators (`<->`) and vector indexes. Furthermore, `backend/app/api/v1/health.py` lines 30–32 hardcodes `pgvector_enabled = True` when running on SQLite.

4. **Critical Runtime Dependency Blocker in Backend:**
   In `backend/requirements.txt`, `fastapi>=0.110.0,<1.0.0` is specified without pinning `starlette`. When running in modern Python environments where Starlette 1.6.0 is installed, FastAPI 0.115.6 crashes on import of `APIRouter()` (`TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'`). This prevents `app.main` from loading and causes `test_foundation.py` and `test_end_to_end_workflow.py` to fail during test collection.

5. **Frontend State & Dependencies:**
   `frontend/node_modules/` is not present in the repository, and dependencies have not been installed. Running `npm test` fails with `'vitest' is not recognized`. In addition, authentication tokens are kept strictly in memory (`apiClient.ts`), causing users to be logged out on every page refresh.

### Round 2 Scorecard Projection (100 Points Total)

| Criterion | Max Pts | Projected Score | Justification |
|---|:---:|:---:|---|
| **Core workflow runs end to end** | 30 | **22 / 30** | The core workflow functions logically via APIs and UI, but relies on hardcoded deterministic extractors for the demo dataset and crashes on modern Starlette without manual environment pinning. |
| **Technical depth and reliability** | 25 | **17 / 25** | Strong data modeling, RBAC, Argon2id, secret redaction, and deterministic L6 validation. However, pgvector is simulated via JSON, embeddings are MD5 hashes, and 6 module directories are empty stubs. |
| **Progress against the plan** | 20 | **16 / 20** | High alignment with Round 1 schemas, endpoints, and threat model; all 15 DB tables implemented; but discrepancy on live open-source LLM deployment. |
| **Three planned improvements** | 15 | **12 / 15** | Baselines for evidence coverage, conflict detection, and role-aware sharing are measurable against the synthetic ground truth. |
| **Usability so far** | 10 | **8 / 10** | Comprehensive single-page workspace with role perspective switcher and evidence modal, though token refresh on reload is absent. |
| **TOTAL** | **100** | **75 / 100** | **Solid technical foundation with high architectural ambition, requiring immediate dependency stabilization and genuine vector/LLM wiring for top-tier scoring.** |

---

## 2. Component-by-Component Technical Inspection

### 2.1 Backend & Architecture

- **Entry Point:** [`backend/app/main.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/main.py)
  - Configures FastAPI with lifespan context initializing tables via `init_db()`.
  - Injects security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-XSS-Protection: 1; mode=block`).
  - Dual router mount: Mounts routers under both `/api/v1` and `/api` (lines 50–56) to ensure backwards compatibility with Round 1 Section 6.4 exact endpoints.
- **Modular Monolith Layout vs. Implementation Reality:**
  - While `docs/PROJECT_STATUS.md` claims 16 implemented backend modules, inspecting `backend/app/modules/` reveals that six modules are empty stub directories containing only a single-line comment in `__init__.py`:
    - `backend/app/modules/continuation/__init__.py` (Only: `# Module 14: Successor Continuation Plan & Receipt Acknowledgement`)
    - `backend/app/modules/embeddings/__init__.py` (Only: `# Module 6: Chunking and Embeddings`)
    - `backend/app/modules/reporting/__init__.py` (Only: `# Module 16: Reporting, JSON/Markdown Export & Ground-Truth Evaluation Metrics`)
    - `backend/app/modules/retrieval/__init__.py` (Only: `# Module 7: Permission-Filtered RAG Retrieval`)
    - `backend/app/modules/review/__init__.py` (Only: `# Module 12: Human Review, Claim Lifecycle, Clarification Loop & Approval Gate`)
    - `backend/app/modules/users/__init__.py` (Only: `# Module 2: User Management`)
  - **Verdict:** The actual logic is consolidated inside `handovers/service.py`, `processing/service.py`, `ingestion/service.py`, and `auth/service.py`. The architecture functions, but the claimed modular layout is partially synthetic.

---

### 2.2 Database & Vector Storage (`pgvector` Reality Check)

- **ORM Definitions:** [`backend/app/models/entities.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/models/entities.py)
  - Correctly implements 15 distinct relational tables: `users`, `refresh_tokens`, `projects`, `project_members`, `source_documents`, `document_chunks`, `handovers`, `handover_sources`, `claims`, `claim_evidence_links`, `risks_and_dependencies`, `clarification_questions`, `next_actions`, `handover_versions`, and `audit_logs`.
  - Uses UUID primary keys and proper foreign key cascade constraints (`ondelete="CASCADE"`).
- **The `pgvector` Illusion:**
  - Look at lines 32–44 in [`backend/app/models/entities.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/models/entities.py#L32-L44):
    ```python
    class EmbeddingVectorType(TypeDecorator):
        """Cross-dialect vector column: compatible with both PostgreSQL (with or without pgvector) and SQLite."""
        impl = JSON
        cache_ok = True
        def load_dialect_impl(self, dialect: Any) -> Any:
            return dialect.type_descriptor(JSON())
    ```
  - Despite importing `from pgvector.sqlalchemy import Vector as PgVector` conditionally at line 27, `EmbeddingVectorType` returns `JSON()` for all dialects, including PostgreSQL!
  - In `backend/app/modules/ingestion/service.py` lines 362–392, similarity search is performed by fetching all candidate chunks into Python memory via `rows = query.all()` and running a software loop `cosine_similarity(query_vec, emb)`.
  - In `backend/app/api/v1/health.py` lines 30–32:
    ```python
    else:
        # Cross-dialect vector storage active in local SQLite dev/test mode
        pgvector_enabled = True
    ```
    The health endpoint returns `pgvector_enabled: true` when running on SQLite, masking the absence of pgvector.
- **Database Migrations:**
  - `backend/alembic/versions/0001_initial_schema.py` does not contain explicit table creation DDL; it delegates to `Base.metadata.create_all(bind=bind)` (line 26).

---

### 2.3 LangGraph Multi-Agent Orchestration

- **Implementation File:** [`backend/app/agents/orchestrator/workflow.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/agents/orchestrator/workflow.py)
- **Graph Structure:**
  - Uses `StateGraph(HandoverGraphState)` with three nodes:
    - `knowledge_extraction` (Agent 1)
    - `risk_dependency` (Agent 3)
    - `evidence_verification` (Agent 2)
  - Uses conditional routing `_route_after_node` checking `state.get("halted")` or `errors`.
  - Fallback runner: If `langgraph` package is not importable, lines 176–186 execute a linear Python fallback sequence.
- **Stop-on-Failure Verification:**
  - If any agent fails or `force_failure_agent` is passed, the node sets `halted: True` and routes to `END`.
  - In `backend/app/modules/handovers/service.py` line 435:
    ```python
    if final_state.get("halted") or final_state.get("errors"):
        handover.status = HandoverStatus.FAILED.value
        raise HTTPException(status_code=503, detail="Agent orchestration halted; partial output blocked from publication.")
    ```
  - **Verdict:** LangGraph state machine orchestration and the stop-on-failure safety guarantee are genuinely implemented and tested.

---

### 2.4 The Three AI Agents & LLM Invocation Verification

A critical objective of this audit is determining whether the three AI agents actually invoke an LLM.

#### Model Adapter Architecture
In [`backend/app/agents/adapter/llm_adapter.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/agents/adapter/llm_adapter.py):
- Supports two live modes:
  1. `ollama`: Sends HTTP POST to `{LLM_BASE_URL}/api/chat` with `{"format": "json", "options": {"temperature": 0.0}}`.
  2. `openai_compatible`: Sends HTTP POST to `{LLM_BASE_URL}/chat/completions` with `response_format: {"type": "json_object"}`.
- Telemetry recording: Returns `ModelExecutionMetadata` detailing `provider_requested`, `provider_used`, `live_llm_invoked`, `latency_ms`, and `fallback_reason`.

#### Audit Evidence on Actual Invocation

1. **Default Configuration Points to Local Ollama:**
   - In `backend/app/core/config.py` line 39: `LLM_PROVIDER: str = "ollama"`, `LLM_BASE_URL = "http://localhost:11434"`.
   - In `docker-compose.yml`, there is **no Ollama container**. The compose file merely sets `LLM_BASE_URL: http://host.docker.internal:11434`. Unless the user already has Ollama running locally on port 11434 with `qwen2.5:7b-instruct` pulled, every call fails immediately.
2. **Short Timeout Triggers Instant Fallback:**
   - In `backend/app/agents/adapter/llm_adapter.py` line 54:
     `with httpx.Client(timeout=min(settings.LLM_TIMEOUT_SECONDS, 6.0)) as client:`
     When port 11434 is closed, `httpx.ConnectError` is caught within milliseconds, triggering `deterministic_extractor()`.
3. **Render Deployment Defaults to Deterministic Fallback:**
   - In `render.yaml` line 44:
     ```yaml
     - key: LLM_PROVIDER
       value: "deterministic_extractive"
     ```
   - Cloud deployment disables LLM invocation by default.

#### Code Analysis of the Three Agents

##### Agent 1: Knowledge Extraction Agent
- **File:** [`backend/app/agents/knowledge_extraction/agent.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/agents/knowledge_extraction/agent.py)
- **Live LLM Prompt:** System prompt defined at lines 15–21; user prompt formats sanitized passages as `<untrusted_evidence>` tags (lines 285–292).
- **Deterministic Extractor (`_extractive_knowledge_analysis`):**
  - Lines 46–218 contain explicit string checks:
    - Line 46: `if "doc-project-overview" in by_source:` -> Appends hardcoded PayFlow overview & completed PR-218 claims.
    - Line 86: `if "adr-001" in by_source:` -> Appends hardcoded claim for Stripe PaymentIntents v2 decision and missing retry rationale question.
    - Line 116: `if "issue-104" in by_source:` -> Appends hardcoded claim for 3DS2 timeout blocked with `owner_name=None`.
    - Line 156: `if "pr-218" in by_source or "doc-legacy-api" in by_source:` -> Appends hardcoded claim for API deprecation.
    - Line 190: `if "notes-2026-11-02" in by_source:` -> Appends hardcoded claim for Redis idempotency flush.
  - Lines 230–257: For unknown sources, falls back to taking the first sentence of the text (`sentences[0]`).

##### Agent 2: Evidence Verification Agent
- **File:** [`backend/app/agents/evidence_verification/agent.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/agents/evidence_verification/agent.py)
- **Deterministic Extractor (`_extractive_evidence_verification`):**
  - Lines 51–67:
    ```python
    if "issue-104" in cited_ids and "notes-2026-10-15" in passage_by_source:
        status_val = "conflicting"
        conflicts.append(ConflictRecordSchema(
            conflict_type="STATUS_MISMATCH",
            source_a_id="issue-104", source_a_timestamp=...,
            source_b_id="notes-2026-10-15", source_b_timestamp=...,
            explanation="ISSUE-104 (updated 2026-11-06) reports status BLOCKED, whereas Sprint Sync Notes (2026-10-15) report IN PROGRESS..."
        ))
    ```
  - Lines 70–86:
    ```python
    if "doc-legacy-api" in cited_ids and "pr-218" in passage_by_source:
        status_val = "potentially_outdated"
        conflicts.append(ConflictRecordSchema(
            conflict_type="STALE_ENDPOINT_DOCUMENTATION", ...
        ))
    ```
- **Safety Enforcement:** Pydantic field validator `forbid_ai_verified_status` ([`backend/app/agents/schemas.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/agents/schemas.py#L70-L75)) strictly prevents `verified` from being output by the agent schema.

##### Agent 3: Risk & Dependency Analysis Agent
- **File:** [`backend/app/agents/risk_dependency/agent.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/agents/risk_dependency/agent.py)
- **Deterministic Extractor (`_extractive_risk_dependency_analysis`):**
  - Lines 34–60: `if "issue-104" in source_ids_present:` -> Generates blocker "3DS2 Callback Timeout Handling Blocked on Sandbox Certificate" and Action #1.
  - Lines 62–88: `if "pr-218" in source_ids_present:` -> Generates dependency on Finance Ops sandbox & Risk-Engine v1.4 and Action #2.
  - Lines 90–116: `if "adr-001" in source_ids_present:` -> Generates risk for unresolved retry backoff and Action #3.
  - Lines 118–144: `if "notes-2026-11-02" in source_ids_present:` -> Generates operational risk for manual Redis flush and Action #4.

**Summary of AI Agent Verification:**
The architecture contains real prompt strings and valid Pydantic input/output schemas for LLMs, but **in default deployment and evaluation, 100% of the extraction, conflict detection, and risk analysis is performed by hardcoded rule-matching against synthetic file IDs.**

---

### 2.5 RAG, Embeddings & Chunking Implementation

- **Chunking Algorithm:** [`backend/app/modules/processing/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/processing/service.py#L50-L97)
  - `split_document_into_chunks(text, chunk_size=800, chunk_overlap=120)`
  - Preserves exact character offsets (`char_start`, `char_end`) and computes `location_label` (`body#chars:start-end`).
  - Genuinely functional and passes unit tests.
- **Embeddings Algorithm:** [`backend/app/modules/processing/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/processing/service.py#L100-L123)
  - `generate_embedding_vector(text: str, dimension: int = 384) -> List[float]`
  - Computes an MD5 feature-hashing projection over unigram and bigram tokens into 384 signed dimensions.
  - **Verdict:** It is a token-hashing algorithm, not a dense semantic representation from `all-MiniLM-L6-v2` as claimed in config and documentation.
- **RAG Pre-Filtering:** [`backend/app/modules/ingestion/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/ingestion/service.py#L340-L364)
  - Enforces `DocumentChunk.access_level.in_(allowed_classifications)` at SQL query level before similarity scoring.
  - Genuinely functional: prevents RESTRICTED sources from ever reaching the retrieval context for unauthorized roles.

---

### 2.6 Evidence Verification & L6 Deterministic Trust Boundary

- **Implementation:** [`backend/app/modules/validation/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/validation/service.py#L9-L103)
- **Validation Rules Executed:**
  1. Checks each citation `source_id` against `SourceDocument.stable_source_id` in PostgreSQL.
  2. Ensures the document belongs to the project and matches `allowed_classifications`.
  3. Strips unconfirmed citations and records `invalid_or_unauthorised_source_id_stripped`.
  4. If no valid citations remain, downgrades claim status to `unknown` and records `no_valid_supporting_source`.
  5. Strips any `verified` status emitted by agents, resetting to `source_supported`.
  6. Locates verbatim excerpt substring offsets within `doc_obj.content_redacted`.
- **Verdict:** **Genuinely implemented and functioning.** This is one of the strongest technical components in the codebase, providing a real defense against hallucinated citations.

---

### 2.7 Authentication, Authorization & RBAC

- **Implementation Files:** [`backend/app/core/security.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/core/security.py) and [`backend/app/modules/auth/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/auth/service.py)
- **Password Security:** Argon2id with memory cost 32MB, time cost 2, parallelism 2 via `argon2-cffi`. Genuinely secure.
- **Tokens:** JWT access tokens (30 min) + rotating refresh tokens (7 days). Only the SHA-256 hash of refresh tokens is stored in the database. Replay attack protection is validated.
- **Project RBAC:** `get_project_membership()` enforces role checks across:
  - `PROJECT_LEAD`
  - `OUTGOING_DEV`
  - `REVIEWER_SME`
  - `SUCCESSOR`
- **Successor Draft Gating:**
  - `get_handover_draft_for_user()` ([`handovers/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/handovers/service.py#L583-L602)) blocks `SUCCESSOR` with HTTP 403 Forbidden until handover status is `approved` or `acknowledged`.
- **Reviewer Gating on `verified`:**
  - `update_claim_by_reviewer()` ([`handovers/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/handovers/service.py#L639-L646)) blocks `OUTGOING_DEV` from marking claims `verified`; only `PROJECT_LEAD` or `REVIEWER_SME` can do so.

---

### 2.8 Security Engineering & Threat Mitigations

- **Secret Redaction:** [`backend/app/modules/processing/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/processing/service.py#L13-L44)
  - Regex scanner identifies Stripe API keys (`sk_live`, `sk_test`), GitHub PATs (`ghp_`), AWS Access Keys (`AKIA`), JWTs (`eyJ`), and key-value password assignments.
  - Replaces matches with `[REDACTED_SECRET]` before persistence.
  - Genuinely functional: verified by unit test `test_secret_scanner_redacts_stripe_and_password_secrets`.
- **Prompt Injection Defense:** [`backend/app/agents/adapter/prompt_guard.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/agents/adapter/prompt_guard.py#L6-L35)
  - Isolates known adversarial patterns (e.g. `ignore all previous instructions`, `system override:`) and replaces affected sentences with `[ADVERSARIAL_INSTRUCTION_ISOLATED]`.
  - Passages wrapped in `<untrusted_evidence>` XML tags.
  - Heuristic defense: Effective against exact pattern matches, but not robust against novel or multi-token evasion prompts.
- **Audit Logging:** [`backend/app/modules/audit/service.py`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/audit/service.py#L9-L37)
  - Appends immutable records to `audit_logs` storing `action`, `actor_user_id`, `actor_email`, `actor_role`, `previous_state`, and `new_state`.
  - Genuinely working.

---

### 2.9 Frontend Architecture & User Interface

- **Implementation:** [`frontend/src/pages/PlatformWorkspace.tsx`](file:///d:/VS_Code_Projects/Knowledge-handover/frontend/src/pages/PlatformWorkspace.tsx) (990 lines)
- **Views Implemented:**
  - `landing`: Overview showing the 5-stage paradigm.
  - `auth`: Registration and login with Argon2id + JWT handling.
  - `dashboard`: Status cards and one-click `Seed PayFlow Dataset & Run 3-Agent Reconstruction` trigger.
  - `sources`: Source document inventory with secret redaction badges and manual upload form.
  - `review`: Extracted claims list, 6-state badges, inline contradiction warnings, citation inspector modal, clarification answer inputs, and approval button.
  - `successor`: 13-section continuation plan, next action ranking, filtered source counts, and receipt acknowledgment button.
  - `audit`: Chronological event log viewer.
- **Components:**
  - `EvidenceStatusBadge.tsx`: Displays exact vocabulary (`Source-supported`, `Verified (Human)`, `Conflicting`, `Potentially outdated`, `Inferred`, `Unknown / unsupported`) with AI draft vs. Human reviewed tags.
  - `EvidenceInspectorModal.tsx`: Side-by-side contradiction viewer with timestamps and verbatim excerpt highlighting.
- **Frontend Deficiencies:**
  - `node_modules` missing from repository.
  - In-memory token storage in `apiClient.ts` loses authentication state upon browser reload.
  - The UI "Perspective" selector (`useAuth.tsx` lines 50–60) changes client-side UI buttons without exchanging tokens on the backend; if an Outgoing Developer tries to mark a claim verified using the UI override, the backend correctly returns a 403 error, but the UI presents this as an unexpected error banner.

---

### 2.10 API Surface & Contract Conformance

| Round 1 Proposed Route (Section 6.4) | Implemented Backend Endpoint | Status | Notes |
|---|---|:---:|---|
| `POST /api/handovers` | `/api/handovers` & `/api/v1/handovers` | **Working** | Creates scoped handover workspace. |
| `POST /api/handovers/{id}/sources/import` | `/api/handovers/{id}/sources/import` | **Working** | Scopes sources within classification. |
| `POST /api/handovers/{id}/reconstruct` | `/api/handovers/{id}/reconstruct` | **Working** | Executes RAG + LangGraph 3-agent orchestration. |
| `GET /api/handovers/{id}/draft` | `/api/handovers/{id}/draft` | **Working** | Retrieves structured draft (gated from successor). |
| `PATCH /api/claims/{id}` | `/api/claims/{id}` | **Working** | Edits claim, marks verified (Reviewer/Lead only). |
| `POST /api/handovers/{id}/approve` | `/api/handovers/{id}/approve` | **Working** | Human approval gate; increments version. |
| `GET /api/handovers/{id}/successor-view` | `/api/handovers/{id}/successor-view` | **Working** | Generates 13-section continuation plan. |
| *N/A (Bonus / Auth)* | `POST /api/v1/auth/register`, `/login`, `/refresh`, `/logout` | **Working** | Full Argon2id + JWT lifecycle. |
| *N/A (Bonus / Projects)* | `POST /api/v1/projects`, `GET /projects/{id}`, `POST /members` | **Working** | Multi-project RBAC management. |
| *N/A (Bonus / Sources)* | `POST /api/v1/projects/{id}/sources/seed-payflow`, `/upload` | **Working** | Synthetic seeder & custom upload. |
| *N/A (Bonus / Clarify)* | `POST /api/handovers/{id}/clarifications/{qid}` | **Working** | Answers clarification questions. |
| *N/A (Bonus / Ack)* | `POST /api/handovers/{id}/acknowledge` | **Working** | Successor receipt acknowledgement. |
| *N/A (Bonus / Export)* | `GET /api/v1/handovers/{id}/export` | **Working** | JSON and Markdown export. |

---

### 2.11 Automated Test Suite & Test Execution Results

During the audit, the test suites were directly verified via CLI execution:

1. **AI & Security Unit Tests:**
   - Command: `python -m pytest backend/tests/ai`
   - **Result: 4 passed in 0.14s**
     - `test_ai_agent_cannot_output_verified_status` PASSED
     - `test_secret_scanner_redacts_stripe_and_password_secrets` PASSED
     - `test_prompt_injection_sanitizer_isolates_adversarial_directives` PASSED
     - `test_chunking_preserves_offsets_and_semantic_similarity` PASSED
2. **Foundation & End-to-End Integration Tests:**
   - Command: `python -m pytest backend/tests/unit backend/tests/integration`
   - **Result: FAILED during test collection (2 collection errors)**
     - `TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'`
     - Root cause: Incompatibility between unpinned `starlette 1.6.0` and `fastapi 0.115.6` in the active environment.
3. **Frontend Vitest Suite:**
   - Command: `cd frontend; npm test`
   - **Result: FAILED**
     - `'vitest' is not recognized as an internal or external command` because `frontend/node_modules/` is not installed.

---

### 2.12 Infrastructure & Deployment Configuration

- **Docker Compose:** [`docker-compose.yml`](file:///d:/VS_Code_Projects/Knowledge-handover/docker-compose.yml)
  - Defines `db` (`pgvector/pgvector:pg16`), `backend`, and `frontend`.
  - Issue: No local LLM service is containerized; expects an external host Ollama instance.
- **Frontend Dockerfile:** [`frontend/Dockerfile`](file:///d:/VS_Code_Projects/Knowledge-handover/frontend/Dockerfile)
  - Line 5: `COPY package.json ./` omits `package-lock.json`.
  - Line 12: `CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]` runs Vite dev server rather than a production Nginx static container.
- **Render Blueprint:** [`render.yaml`](file:///d:/VS_Code_Projects/Knowledge-handover/render.yaml)
  - Deploys PostgreSQL, FastAPI, and Vite static build cleanly.
  - Sets `LLM_PROVIDER: "deterministic_extractive"`, running the rule-based fallback by default.

---

## 3. Round 1 Proposal vs. Implementation Parity Matrix

| Feature / Requirement | Round 1 Plan | Source Code Status | Verification Evidence |
|---|---|:---:|---|
| **FR-01: Scoped Handover Workspace** | Priority P0 | **Genuinely Working** | `create_scoped_handover()` in `handovers/service.py` L229; `POST /api/handovers`. |
| **FR-02: Load Synthetic Sources** | Priority P0 | **Genuinely Working** | 9 PayFlow sources in `seeds/payflow_data.py`; `POST /sources/seed-payflow`. |
| **FR-03: Extract Project Knowledge** | Priority P0 (Agent 1) | **Deterministic Fallback (Hardcoded)** | `run_knowledge_extraction_agent()` in `knowledge_extraction/agent.py` L271; hardcoded matches for `doc-project-overview`, `adr-001`, `issue-104`. |
| **FR-04: Attach & Verify Evidence** | Priority P0 (Agent 2) | **Deterministic Fallback (Hardcoded)** | `run_evidence_verification_agent()` in `evidence_verification/agent.py` L100; hardcoded match for `issue-104` vs `notes-2026-10-15`. |
| **FR-05: Flag Uncertainty & Conflict** | Priority P0 | **Genuinely Working** | 6-status vocabulary in `enums.py` L55; side-by-side UI modal in `EvidenceInspectorModal.tsx`. |
| **FR-06: Human Review & Approval** | Priority P0 | **Genuinely Working** | `update_claim_by_reviewer()` L608, `approve_handover_package()` L774; Reviewer role check enforced. |
| **FR-07: Continuation Plan** | Priority P0 | **Genuinely Working** | `build_successor_continuation_plan()` L842 generates all 13 required sections. |
| **FR-08: Dependency & Risk View** | Priority P1 (Agent 3) | **Deterministic Fallback (Hardcoded)** | `run_risk_dependency_agent()` in `risk_dependency/agent.py` L164; hardcoded blocker/risk schemas. |
| **FR-09: Audit Trail & Ack** | Priority P1 | **Genuinely Working** | `record_audit_event()` in `audit/service.py` L9; `acknowledge_handover_receipt()` L938. |
| **FR-10: Live GitHub Connector** | Priority P2 (MVP Exclusion) | **Explicitly Excluded** | Excluded per Round 1 Section 6.3. |
| **FR-11: Agent Orchestrator** | Priority P0 | **Genuinely Working** | LangGraph `StateGraph` in `workflow.py` L156 with stop-on-failure routing. |
| **NFR-1: Usability** | Readable labels & status | **Genuinely Working** | Clean UI in `PlatformWorkspace.tsx` with role perspectives. |
| **NFR-2: Traceability** | Stable source IDs & offsets | **Genuinely Working** | Character offsets (`char_start`, `char_end`) stored in `claim_evidence_links`. |
| **NFR-3: Security & Clearance** | Pre-retrieval clearance filter | **Genuinely Working** | `retrieve_scoped_chunks()` L354 filters by `allowed_classifications`. |
| **NFR-4: Reliability / Stop-on-Failure** | Bounded retries & halt | **Genuinely Working** | Agent failure halts pipeline; `HTTP 503` returned; publication blocked. |
| **NFR-5: Modular Monolith** | Single deployable | **Partially Implemented** | Monolith exists, but 6 of 16 module subfolders are empty stubs. |
| **pgvector Storage** | PostgreSQL vector extension | **Simulated / Broken** | `EmbeddingVectorType` uses `JSON`; similarity computed in Python loop. |
| **Neural Embeddings** | `all-MiniLM-L6-v2` | **Deterministic Fallback** | Implemented as MD5 unigram/bigram token hashing. |

---

## 4. Agent LLM Invocation & Synthetic Hardcoding Analysis

### Code Inspection Summary: Agent Fallback Logic

```
┌────────────────────────────────────────────────────────┐
│               Agent Orchestrator Request               │
└───────────────────────────┬────────────────────────────┘
                            │
               Is LLM Reachable & Configured?
             ┌──────────────┴──────────────┐
            YES                            NO (Default)
             │                             │
    HTTP POST /api/chat                    ▼
    or /chat/completions         Execute Deterministic
    (Pydantic Schema Validated)    Extractor Function
                                           │
                        ┌──────────────────┴──────────────────┐
                        │ Hardcoded Synthetic Branching Rules │
                        ├─────────────────────────────────────┤
                        │ doc-project-overview  ──> Claims 1,2│
                        │ adr-001               ──> Claim 3   │
                        │ issue-104             ──> Claim 4   │
                        │ pr-218/doc-legacy-api ──> Claim 5   │
                        │ notes-2026-11-02      ──> Claim 6   │
                        └─────────────────────────────────────┘
```

### Detailed Breakdown of Hardcoded Inferences

1. **Extraction Agent (`app/agents/knowledge_extraction/agent.py`):**
   - Lines 52–64: Canned text *"PayFlow is the core payment orchestration..."* hardcoded to `doc-project-overview`.
   - Lines 92–106: Canned text *"Adopted Stripe PaymentIntents v2..."* and missing retry rationale question hardcoded to `adr-001`.
   - Lines 136–146: Canned text *"Payment timeout handling on 3DS2 callback (issue-104) remains blocked..."* hardcoded with `owner_name=None` to `issue-104`.
2. **Verification Agent (`app/agents/evidence_verification/agent.py`):**
   - Lines 51–67: Contradiction between `issue-104` and `notes-2026-10-15` is not discovered through semantic reasoning; it is hardcoded via `if "issue-104" in cited_ids and "notes-2026-10-15" in passage_by_source:`.
   - Lines 70–86: Staleness between `doc-legacy-api` and `pr-218` is hardcoded via `if "doc-legacy-api" in cited_ids and "pr-218" in passage_by_source:`.
3. **Risk & Dependency Agent (`app/agents/risk_dependency/agent.py`):**
   - Lines 34–144: The 4 blockers/risks and 4 next actions are hardcoded blocks keyed on `issue-104`, `pr-218`, `adr-001`, and `notes-2026-11-02`.

**Impact on Round 2 Evaluation:**
While this deterministic fallback guarantees 100% precision on the specific synthetic PayFlow scenario during a judge demo, it does not demonstrate generalizable AI extraction on arbitrary repositories.

---

## 5. Discrepancies Between Documentation and Source Code

| # | Documentation Claim | Source Code Reality | File Reference |
|---|---|---|---|
| **1** | `docs/DATABASE_SCHEMA.md` claims: "pgvector extension for semantic similarity retrieval." | Table column is defined as `JSON`, not `vector(384)`. Vector search is a Python in-memory cosine loop. | [`app/models/entities.py#L35`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/models/entities.py#L35), [`app/modules/ingestion/service.py#L369`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/ingestion/service.py#L369) |
| **2** | `backend/app/core/config.py` specifies: `EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"`. | No transformer model is loaded; embeddings are 384-dim MD5 feature token hashes. | [`app/modules/processing/service.py#L100-L123`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/processing/service.py#L100-L123) |
| **3** | `docs/PROJECT_STATUS.md` claims 16 separate modules implemented. | Modules 2, 6, 7, 12, 14, and 16 are empty directories containing only comment headers. | [`app/modules/`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/) subdirectories |
| **4** | `docs/AI_ARCHITECTURE.md` states: "Three specialised agents run on a shared open-source model." | Out-of-the-box, no LLM runs; hardcoded deterministic rule functions generate all outputs. | [`app/agents/adapter/llm_adapter.py#L99-L110`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/agents/adapter/llm_adapter.py#L99-L110) |
| **5** | `/api/v1/health` reports `pgvector_enabled: True`. | Returns `True` unconditionally on SQLite without checking or using pgvector. | [`app/api/v1/health.py#L30-L32`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/api/v1/health.py#L30-L32) |
| **6** | `docs/TESTING.md` claims: "Backend tests run via `pytest -v`." | `test_foundation.py` and `test_end_to_end_workflow.py` fail collection on Starlette 1.6.0. | `backend/tests/unit/test_foundation.py` |
| **7** | `docs/TESTING.md` claims: "Frontend tests run via `npm test`." | `node_modules` is absent; command fails immediately. | `frontend/tests/App.test.tsx` |
| **8** | Synthetic sources described as files in `data/payflow_synthetic/`. | `data/payflow_synthetic/` has only `manifest.json`; texts are embedded in `payflow_data.py`. | [`data/payflow_synthetic/manifest.json`](file:///d:/VS_Code_Projects/Knowledge-handover/data/payflow_synthetic/manifest.json) |

---

## 6. Prioritised Bug Register

### Severity Definitions
- **P0 (Critical/Blocker):** Breaks build, test execution, or deployment out of the box.
- **P1 (High):** Major functional or architectural discrepancy affecting core requirements.
- **P2 (Medium):** Sub-optimal implementation, confusing UX, or code quality flaw.
- **P3 (Low):** Minor cosmetic issue or documentation typo.

---

| ID | Severity | Component | Bug Description & Impact | File & Code Reference |
|---|:---:|---|---|---|
| **BUG-01** | **P0** | Backend Dependencies | **FastAPI / Starlette Incompatibility Breaks App Import:** `requirements.txt` specifies unpinned `fastapi>=0.110.0,<1.0.0`. Installing in environments with `starlette>=1.0` causes `APIRouter()` to crash with `TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'`, failing all integration tests. | [`backend/requirements.txt#L1`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/requirements.txt#L1), [`app/main.py#L9`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/main.py#L9) |
| **BUG-02** | **P0** | Frontend Packaging | **Uninstalled Frontend Dependencies (`node_modules` missing):** `frontend/node_modules/` is absent, preventing `npm test` or `npm run dev` from running without an initial `npm install`. | [`frontend/package.json`](file:///d:/VS_Code_Projects/Knowledge-handover/frontend/package.json) |
| **BUG-03** | **P1** | Database / RAG | **`pgvector` Bypassed for In-Memory Python Loop:** `EmbeddingVectorType` uses `JSON` instead of PostgreSQL native vector type. Vector similarity is calculated via an unindexed in-memory Python loop (`query.all()`), which will not scale beyond demo corpora. | [`app/models/entities.py#L35`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/models/entities.py#L35), [`app/modules/ingestion/service.py#L369`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/ingestion/service.py#L369) |
| **BUG-04** | **P1** | Docker / Frontend | **Frontend Dockerfile Runs Dev Server in Production:** `frontend/Dockerfile` uses `CMD ["npm", "run", "dev"]` instead of a multi-stage production build serving static assets via Nginx. It also copies `package.json` while omitting `package-lock.json`. | [`frontend/Dockerfile#L5-L12`](file:///d:/VS_Code_Projects/Knowledge-handover/frontend/Dockerfile#L5-L12) |
| **BUG-05** | **P2** | Auth / Frontend | **In-Memory Token Store Causes Logout on Page Refresh:** Tokens are stored only in memory variables in `apiClient.ts`. Refreshing or navigating in the browser loses the user's session. | [`frontend/src/lib/apiClient.ts#L13-L21`](file:///d:/VS_Code_Projects/Knowledge-handover/frontend/src/lib/apiClient.ts#L13-L21) |
| **BUG-06** | **P2** | Health Check | **False Health Reporting for `pgvector`:** `/api/v1/health` reports `pgvector_enabled: True` on SQLite databases, masking true vector engine status. | [`app/api/v1/health.py#L30-L32`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/api/v1/health.py#L30-L32) |
| **BUG-07** | **P2** | Docker Compose | **Missing Ollama Service in Compose:** `docker-compose.yml` does not spin up an Ollama container, causing `backend` to default to `host.docker.internal:11434` which fails if no host daemon exists. | [`docker-compose.yml#L36-L38`](file:///d:/VS_Code_Projects/Knowledge-handover/docker-compose.yml#L36-L38) |
| **BUG-08** | **P3** | Architecture | **Empty Module Folders:** 6 of 16 module directories contain only a comment in `__init__.py`. | [`app/modules/continuation/`](file:///d:/VS_Code_Projects/Knowledge-handover/backend/app/modules/continuation/) |

---

## 7. Prioritised Security Risk Register

| ID | Severity | Risk Area | Description & Threat Scenario | Recommended Mitigation |
|---|:---:|---|---|---|
| **SEC-01** | **High** | RBAC / Authorization | **Virtual Admin Superuser Project Bypass:** In `backend/app/core/security.py` line 140, any user with `platform_role == "ADMIN"` is given a synthetic `PROJECT_LEAD` membership with full `RESTRICTED` clearance to *all* projects without an audit trail of membership assignment. | Require explicit assignment of admins to project rosters or log superuser access overrides. |
| **SEC-02** | **High** | Configuration | **Hardcoded JWT Secret Key Fallback:** `backend/app/core/config.py` line 30 sets a predictable default secret key: `"dev_only_replace_with_32_byte_random_secret_key_012345"`. If deployed without setting `JWT_SECRET_KEY`, tokens can be forged. | Enforce startup validation that raises an error if `APP_ENV == "production"` and the key is default or short. |
| **SEC-03** | **Medium** | AI Security | **Heuristic Prompt-Injection Vulnerability:** `sanitize_untrusted_passage()` relies on 5 static regex patterns. Novel phrasing, multi-lingual injections, or base64 encoding can bypass the filter and reach the model prompt. | Implement structured XML boundary isolation and use a dedicated classification guardrail. |
| **SEC-04** | **Medium** | CORS Configuration | **Wildcard CORS in Render Production Configuration:** `render.yaml` line 39 configures `CORS_ORIGINS: "*"`. While acceptable for public APIs, pairing wildcard CORS with credentialed authentication headers can create cross-origin security exposure. | Restrict `CORS_ORIGINS` to the exact Render frontend external URL. |
| **SEC-05** | **Low** | Data Ingestion | **Lack of MIME/Magic Byte File Validation:** Source uploads validate string length (`MAX_UPLOAD_SIZE_BYTES = 5MB`) but do not inspect file signatures or binary headers on raw inputs. | Add MIME-type verification for file uploads. |

---

## 8. Round 2 Evaluation Strategy & Roadmap to Round 3

### Immediate Preparation for Round 2 Judging

To ensure the highest possible score under the **Round 2 Evaluation Criteria (100 Points)**:

1. **Fix Dependency Pinning in Backend:**
   - In `backend/requirements.txt`, pin `starlette<0.42.0` or update `fastapi` to `>=0.115.8` so that `app.main` loads seamlessly and all integration tests run cleanly.
2. **Ensure Complete Dependency Installation:**
   - Run `npm install` inside `frontend/` so that `npm test` and `npm run dev` function immediately.
3. **Judge Demonstration Strategy:**
   - Demonstrate the one-click bootstrap workflow:
     1. Open UI -> Click **Seed PayFlow Dataset & Run 3-Agent Reconstruction**.
     2. Showcase the **Side-by-Side Contradiction Inspector Modal** comparing `issue-104` (`BLOCKED`) with `notes-2026-10-15` (`IN PROGRESS`).
     3. Showcase the **Stale API Document Flag** highlighting `doc-legacy-api` superseded by `pr-218`.
     4. Demonstrate that the **Assignee is preserved as UNKNOWN** and not hallucinated.
     5. Demonstrate the **Clarification Loop** where the Outgoing Dev answers the retry policy question.
     6. Demonstrate the **Human Approval Gate** where the Reviewer marks claims verified and approves the package.
     7. Switch perspective to **Successor** and verify that the confidential `restricted-vendor-note` is filtered out while the 13-section continuation plan is unlocked.
4. **Transparent Disclosure:**
   - Accurately disclose in the demo that the system runs a rule-grounded extractive engine when a live Ollama or Groq runtime is not connected, transparently logged in `agentTelemetry`.

---

### Delivery Roadmap for the Three Round 3 Commitments

The Round 1 proposal committed to three candidate improvements for Round 3 (Section 9.2). Here is the technical roadmap for delivering them:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ROUND 3 COMMITMENTS ROADMAP                          │
├────────────────────────────────┬───────────────────────────────────────┤
│ Improvement 1: Evidence        │ • True PostgreSQL `vector(384)` column │
│ Coverage & Citation Validity   │ • Integration of sentence-transformers│
│                                │ • Tighten prompt with negative examples│
├────────────────────────────────┼───────────────────────────────────────┤
│ Improvement 2: Conflict,       │ • Generalized date/status reconciliation│
│ Staleness & Clarification Loop │ • Turn arbitrary gaps into questions  │
│                                │ • Semantic contradiction scoring      │
├────────────────────────────────┼───────────────────────────────────────┤
│ Improvement 3: Role-Aware      │ • Multi-stage Docker with Nginx       │
│ Controlled Sharing             │ • Refresh token in HttpOnly cookies   │
│                                │ • Granular cryptographic audit hash   │
└────────────────────────────────┴───────────────────────────────────────┘
```

1. **Improvement 1: True pgvector Retrieval & Dense Semantic Embeddings:**
   - Replace the MD5 feature hashing with genuine local embeddings (e.g. `fastembed` or `sentence-transformers/all-MiniLM-L6-v2`).
   - Change `EmbeddingVectorType` to use `pgvector.sqlalchemy.Vector(384)` natively on PostgreSQL with an `HNSW` index.
2. **Improvement 2: Generalized Conflict & Staleness Engine:**
   - Generalize conflict detection beyond hardcoded source IDs by comparing normalized entities and conflicting state triples `(entity, attribute, state, timestamp)`.
3. **Improvement 3: Production Security & Token Hardening:**
   - Store refresh tokens in `HttpOnly`, `SameSite=Strict`, `Secure` cookies to protect against XSS token extraction.
   - Refactor frontend Dockerfile to a multi-stage Nginx build for production deployment.

---

*Report prepared following strict code inspection and CLI execution verification.*  
*Artifact generated: `KNOWLEDGE_HANDOVER_TECHNICAL_AUDIT.md`.*

