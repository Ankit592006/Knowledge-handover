# Knowledge Handover — Intelligent Knowledge Continuity Platform (Continuity OS v2.1)

An agentic, evidence-linked, contradiction-aware, and human-approved software project handover and successor continuation platform.

> **Core Paradigm:** *Evidence before assertion; uncertainty shown, never hidden; nothing shared before human approval.*

- **Live Backend API (Render)**: `https://kh-backend-z2o3.onrender.com` ([Swagger UI `/docs`](https://kh-backend-z2o3.onrender.com/docs) · [Health Check `/api/v1/health`](https://kh-backend-z2o3.onrender.com/api/v1/health))
- **Live Frontend Web App (Render)**: `https://kh-frontend.onrender.com`
- **GitHub Repository**: `https://github.com/Ankit592006/Knowledge-handover.git`
- **Round 3 Improvements & Benchmark**: [Round 3 Implementation & Benchmark Report](docs/ROUND3_IMPROVEMENTS_AND_BENCHMARK.md) · [Committed Benchmark JSON](data/benchmarks/round3_evaluation_results.json)
- **Hackathon Final Report**: [PDF Report](Knowledge_Handover_Hackathon_Final_Report.pdf) · [Print-Ready HTML Dossier](Knowledge_Handover_Hackathon_Final_Report.html) · [Markdown Report](docs/Knowledge_Handover_Hackathon_Final_Report.md)

---

## 1. Key Differentiators & Security Architecture

1. **Evidence-Linked Project Reconstruction**:
   - Every extracted claim carries a database-validated `sourceId`, character span (`body#chars:start-end`), `versionTag`, and `sourceUpdatedAt` timestamp.
2. **Explicit Uncertainty, Contradiction & Staleness Detection**:
   - When project records disagree (e.g., `issue-104` reports `BLOCKED` on `2026-11-06` while `notes-2026-10-15` reports `IN PROGRESS` on `2026-10-15`), the platform surfaces both records side-by-side with timestamps rather than silently choosing one.
   - When newer pull requests supersede legacy specs (e.g., `pr-218` replacing `doc-legacy-api` `/v1/payments/charge` with `/v2/payment-intents`), the claim is flagged `potentially_outdated`.
3. **Never Invents Facts or Owners**:
   - Missing decision rationale (e.g., `adr-001` webhook retry backoff policy) and unassigned owners (`issue-104`) remain explicitly `null` / `unknown` and automatically generate targeted Clarification Questions (`UnresolvedQuestionSchema`) for the outgoing developer.
4. **Pre-LLM Secret Redaction & Adversarial Prompt-Injection Guard**:
   - Before any source artifact is chunked, indexed, stored, or sent to an LLM, regex redaction (`app/modules/ingestion/redaction.py`) scrubs API keys, Bearer tokens, private keys, and connection strings (`[REDACTED_API_KEY]`, `[REDACTED_BEARER_TOKEN]`), while `sanitize_untrusted_passage()` isolates embedded prompt-injection strings (`[ADVERSARIAL_INSTRUCTION_ISOLATED]`).
5. **Deterministic Backend Trust Boundary (Layer L6)**:
   - Independently verifies that every AI-cited `sourceId` exists in PostgreSQL/SQLite, belongs to the scoped handover, and complies with classification clearance before persisting. Strips any invalid citation and downgrades unsupported claims to `unknown`.
6. **Mandatory Human Review & Approval Gate**:
   - AI agents are schema-prohibited via Pydantic `@field_validator` from marking claims as `verified`. Only an authorised human `REVIEWER_SME` or `PROJECT_LEAD` can mark claims `verified` and approve the handover package (freezing an immutable `HandoverVersion` snapshot).
7. **Strict Explicit RBAC, 4-Persona Backend Role Switcher & Guest Demo (`SEC-01`)**:
   - Explicit `ProjectMember` membership and classification clearance (`PUBLIC`, `INTERNAL`, `RESTRICTED`) are enforced before RAG retrieval, source inspection, and handover access.
   - Evaluators can switch between **4 real database-backed JWT role sessions** (`PROJECT_LEAD`, `OUTGOING_DEV`, `REVIEWER_SME`, `SUCCESSOR`) via `POST /api/v1/demo/switch-role` or explore in **Anonymous Read-Only Guest Demo Mode (`GUEST_DEMO`)**.
   - **Exclusive Successor Receipt Sign-Off**: Only the authenticated `SUCCESSOR` role can formally acknowledge handover receipt (`POST /api/handovers/{id}/acknowledge`) after the package has passed the Human Approval Gate.

---

## 2. Technology Stack

- **Frontend (`frontend/`)**:
  - React 18, TypeScript, Vite, Tailwind CSS, Axios, Vitest + React Testing Library.
  - **Book-Professional Editorial Typography**: Pairs *Libre Baskerville* display headings, optical-sized *Source Serif 4* body prose, and *JetBrains Mono* technical source IDs and provenance citations.
  - **Role-Aware Workspace UI**: 5-Step End-to-End Lifecycle Progress Bar, Role-Specific Navigation Tabs, Interactive Evidence Inspector Modal, Structured 13-Section Continuation Plan Cards, and Centered Login/Register Modal Dialog with One-Click Persona Switching.
- **Backend (`backend/`)**:
  - Python 3.11+, FastAPI (`>=0.115.0,<0.116.0`), Pydantic v2, SQLAlchemy 2.0, Alembic, Argon2id (`argon2-cffi`), PyJWT (`HS256` access tokens + rotating SHA-256 refresh tokens).
- **AI & RAG (`backend/app/agents/`)**:
  - **LangGraph `StateGraph` Orchestrator** coordinating 3 specialised agents:
    1. **Agent 1 — Knowledge Extraction Agent** (`app/agents/knowledge_extraction/agent.py`)
    2. **Agent 2 — Evidence Verification Agent** (`app/agents/evidence_verification/agent.py`)
    3. **Agent 3 — Risk & Dependency Analysis Agent** (`app/agents/risk_dependency/agent.py`)
  - **Dual-Mode LLM Adapter (`app/agents/adapter/llm_adapter.py`)**:
    - Default Cloud OpenAI-Compatible Inference (`LLM_PROVIDER="openai_compatible"`) using **Groq `llama-3.3-70b-versatile`** (`https://api.groq.com/openai/v1`) with strict JSON Schema validation (`temperature=0.0`).
    - Also supports local **Ollama** (`qwen2.5:7b-instruct`) and automatic fallback to the **Deterministic Extractive Engine** (`rule-grounded-extractor-v1`) so offline tests and live demos never fail if an external API is unreachable.
  - **Vector Storage & Embeddings**: Native `pgvector` `vector(384)` columns with HNSW cosine indexing (`ix_document_chunks_embedding_hnsw`) on PostgreSQL, with cross-dialect JSON cosine fallback on SQLite.

---

## 3. Role-Based Capabilities & Demo Personas

| Project Role | Pre-Provisioned Demo Identity | Clearance Scope | Visible Tabs & Permitted Actions |
|---|---|---|---|
| **`PROJECT_LEAD`** | **Preeti Mittal** (`preeti.lead@payflow.demo`) | `PUBLIC`, `INTERNAL`, `RESTRICTED` | `Overview`, `Lead Command`, `Sources & Ingestion` (all 8 sources including `restricted-vendor-note`), `Review Workspace`, `Successor Plan`, `Audit Trail`. Can upload sources, run 3-agent reconstruction, verify claims, approve package, and reset demo to `v1`. |
| **`OUTGOING_DEV`** | **Arjun Mehta** (`arjun.outgoing@payflow.demo`) | `PUBLIC`, `INTERNAL` | `Overview`, `Outgoing Studio`, `Sources & Ingestion` (7 sources), `Clarifications & Draft`. Can upload sources, run reconstruction, answer open clarification questions, and flag claims. Cannot mark claims `verified` or approve. |
| **`REVIEWER_SME`** | **Kavita Rao** (`kavita.reviewer@payflow.demo`) | `PUBLIC`, `INTERNAL` | `Overview`, `Reviewer Console`, `Permitted Sources` (read-only), `Review Workspace`, `Audit Trail`. Can inspect evidence, mark claims `verified` or `rejected`, and approve the handover package. |
| **`SUCCESSOR`** | **Ankit Chaudhari** (`ankit.successor@payflow.demo`) | `PUBLIC`, `INTERNAL` | `Overview`, `Onboarding Hub`, `Permitted Sources` (read-only), `Successor Plan`. Blocked (`403`) until package is approved; once approved, unlocks all 13 Continuation Plan sections, exports Markdown/JSON, and exclusively acknowledges handover receipt. |
| **`GUEST_DEMO`** | **Anonymous Read-Only Evaluator** | `PUBLIC`, `INTERNAL` | `Overview`, `Dashboard`, `Permitted Sources` (read-only). Zero write, review, approval, or audit access. |

---

## 4. Quick Start

### Option A: Docker Compose (Full Stack + PostgreSQL/pgvector + Production Nginx Frontend)

```bash
cp .env.example .env
docker compose up --build
```
- **Frontend UI (Nginx SPA)**: http://localhost:5173
- **FastAPI Backend & OpenAPI Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

### Option B: Local Development & Automated Tests

**Backend (SQLite or PostgreSQL + pgvector):**
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Run database migrations:
alembic upgrade head

# Run backend test suite (10 tests: AI guards, unit/foundation, E2E + SEC-01 RBAC & Guest Demo):
python -m pytest -v

# Start development server:
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm ci
npm test -- --run
npm run build
npm run dev
```

---

## 5. Environment Variables Summary (`.env.example`)

| Variable | Default / Example | Description |
|---|---|---|
| `APP_ENV` | `development` / `production` | Application runtime environment |
| `DATABASE_URL` | `postgresql+psycopg://kh_user:...@localhost:5432/knowledge_handover` | SQLAlchemy connection URL (`postgresql+psycopg://` or `sqlite:///`) |
| `JWT_SECRET_KEY` | *(32+ byte secret)* | Secret key used to sign HS256 JWT access tokens |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed CORS origins |
| `LLM_PROVIDER` | `openai_compatible` | `openai_compatible` (Groq/vLLM/OpenRouter), `ollama`, or `deterministic_extractive` |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Base URL for OpenAI-compatible or Ollama inference server |
| `LLM_API_KEY` | *(Groq API key `gsk_...`)* | API key when using `openai_compatible` cloud provider (auto-falls back to deterministic extractor if empty) |
| `LLM_MODEL_NAME` | `llama-3.3-70b-versatile` | Target LLM model identifier (`llama-3.3-70b-versatile` or `qwen2.5:7b-instruct`) |
| `EMBEDDING_PROVIDER` | `deterministic_hash` | Embedding generator (`deterministic_hash` uses 384-dim MD5 feature hashing) |
| `EMBEDDING_DIMENSION` | `384` | Vector dimension matching `pgvector` `vector(384)` schema |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API base URL consumed by the frontend at build/runtime |

---

## 6. Production Render Deployment (`render.yaml`)

[`render.yaml`](render.yaml) defines the production Render Blueprint:
- **Database**: `kh-postgres` (`databaseName: knowledge_handover`, `user: kh_user`)
- **Backend Web Service**: `kh-backend` (`rootDir: backend`, health check `/api/v1/health`, `LLM_PROVIDER="openai_compatible"`, `LLM_BASE_URL="https://api.groq.com/openai/v1"`, `LLM_MODEL_NAME="llama-3.3-70b-versatile"`)
- **Frontend Static Site**: `kh-frontend` (`rootDir: frontend`, `buildCommand: npm ci && npm run build`, SPA rewrite `/* -> /index.html`, `VITE_API_BASE_URL` linked to `kh-backend`)

---

## 7. Complete Documentation Index (`docs/`)

1. [Knowledge_Handover_Hackathon_Final_Report.md](docs/Knowledge_Handover_Hackathon_Final_Report.md) — **Complete Hackathon Project Report & Round 1 Traceability Matrix**
2. [PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) — Problem statement, solution overview, and 5 role personas
3. [ARCHITECTURE.md](docs/ARCHITECTURE.md) — 8-layer modular monolith architecture and 16 backend modules
4. [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) — 15 SQLAlchemy 2.0 ORM tables and `pgvector` schema
5. [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) — Full REST API reference (`/api/v1` and `/api`)
6. [AUTHENTICATION_AUTHORIZATION.md](docs/AUTHENTICATION_AUTHORIZATION.md) — Argon2id, JWT, `SEC-01` RBAC, and 4-persona role switcher
7. [AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md) — LangGraph 3-Agent pipeline, Groq adapter, and L6 trust boundary
8. [DATA_FLOW.md](docs/DATA_FLOW.md) — End-to-end request and data lifecycle
9. [TESTING.md](docs/TESTING.md) — Backend `pytest` and Frontend `vitest` suites
10. [SECURITY.md](docs/SECURITY.md) — Secret redaction, prompt-injection isolation, and clearance filtering
11. [SETUP_GUIDE.md](docs/SETUP_GUIDE.md) — Local, Docker, and cloud deployment setup
12. [DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) — Codebase conventions and extension guide
13. [DECISIONS.md](docs/DECISIONS.md) — Architectural Decision Records (ADRs)
14. [CHANGELOG.md](docs/CHANGELOG.md) — Release history through v2.1.0
15. [KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) — Operational notes and environment disclosures
16. [PROJECT_STATUS.md](docs/PROJECT_STATUS.md) — Phase completion and requirement checklist
17. [ONBOARDING_FOR_NEW_DEVELOPER.md](docs/ONBOARDING_FOR_NEW_DEVELOPER.md) — Developer quick-onboarding guide
18. [DEMO_GUIDE.md](docs/DEMO_GUIDE.md) — Step-by-step live judge demonstration walkthrough

---

## 8. Hackathon Team & Disclosure

- **Team**:
  - **Preeti Satish Mittal** — Team Leader, AI Multi-Agent Architecture, RAG & Backend Security Lead
  - **Ankit Madanlal Chaudhari** — Frontend Architecture, Role-Aware Product Workflow & UX Lead
- **Synthetic Data Only**: The seeded `PayFlow` dataset is 100% synthetic and contains intentional test cases for status conflicts (`issue-104` vs `notes-2026-10-15`), stale API docs (`doc-legacy-api` vs `pr-218`), unassigned owners, undecided ADR retry parameters (`adr-001`), adversarial prompt injection, and synthetic credential redaction (`restricted-vendor-note`).
