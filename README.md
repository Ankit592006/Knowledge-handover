# Knowledge Handover — Intelligent Knowledge Continuity Platform

An agentic, evidence-linked, human-approved software project handover and successor continuation platform.

> **Core Paradigm:** *Evidence before assertion; uncertainty shown, never hidden; nothing shared before human approval.*

---

## 1. Key Differentiators & Security Architecture

- **Evidence-Linked Project Reconstruction**: Every extracted claim carries a validated `sourceId`, `location` (`body#chars:start-end`), `versionTag`, and `sourceUpdatedAt` timestamp.
- **Explicit Uncertainty, Conflict & Staleness Detection**: When records disagree (e.g., `issue-104` reports `BLOCKED` while `notes-2026-10-15` reports `IN PROGRESS`), the platform surfaces both records side-by-side with timestamps rather than silently choosing one.
- **Never Invents Facts or Owners**: Missing decision rationale (e.g., `adr-001` webhook retry backoff policy) and unassigned owners (`issue-104`) remain explicitly `null` / `unknown` and automatically generate targeted questions for the outgoing developer.
- **Deterministic Backend Trust Boundary (L6)**: Independently verifies that every cited `sourceId` exists in the database, belongs to the scoped handover, and complies with classification clearance before persisting.
- **Mandatory Human Review & Approval Gate**: AI agents are schema-prohibited from marking claims as `verified`. Only an authorised human `REVIEWER_SME` or `PROJECT_LEAD` can mark claims `verified` and approve the handover package.
- **Strict Explicit RBAC & Classification Clearance (`SEC-01`)**:
  - Explicit `ProjectMember` membership and classification clearance (`PUBLIC`, `INTERNAL`, `RESTRICTED`) are enforced before RAG retrieval, source inspection, and handover access.
  - Platform `ADMIN` users do **not** receive implicit access to private projects or implicit `RESTRICTED` clearance; public self-registration always assigns `PlatformRole.STANDARD`, and `ADMIN` accounts can only be created via trusted provisioning (`provision_admin_user` / `POST /api/v1/users/admin`).
- **Incognito Read-Only Guest Demo Mode (`GUEST_DEMO`)**:
  - Evaluators opening the application in an Incognito browser without signing in can click **"Try Instant PayFlow Demo (Read-Only)"** on the landing page.
  - Unauthenticated requests on allowed PayFlow demo endpoints resolve to a dedicated `GUEST_DEMO` role scoped strictly to the synthetic `payflow` project (`data_classification == "synthetic_demo"`) with `["PUBLIC", "INTERNAL"]` clearance (`RESTRICTED` records such as `restricted-vendor-note`, other projects, and all write/review/approval/admin actions are blocked).

---

## 2. Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Axios, Vitest, Production Multi-Stage Docker (`node:20-alpine` build $\rightarrow$ `nginx:1.27-alpine` runtime with SPA routing and runtime `VITE_API_BASE_URL` injection via `/runtime-config.js`).
- **Backend**: Python 3.11+, FastAPI (`>=0.115.0,<0.116.0`), Starlette (`>=0.40.0,<0.42.0`), Pydantic v2, SQLAlchemy 2.0, Alembic, Argon2id (`argon2-cffi`), PyJWT.
- **AI & RAG**:
  - LangGraph `StateGraph` orchestrator + 3 specialised agents (*Knowledge Extraction*, *Evidence Verification*, *Risk & Dependency Analysis*) with stop-on-failure guarantees.
  - Configurable LLM adapter supporting `ollama`, `openai_compatible` (Groq, vLLM, OpenRouter), and `deterministic_extractive` (deterministic rule-based extractor for offline/CI reliability).
  - **Vector Storage & Embeddings Disclosure**: On PostgreSQL, chunk embeddings are stored in native `pgvector` `vector(384)` columns indexed with HNSW (`ix_document_chunks_embedding_hnsw` using `vector_cosine_ops`) and queried in SQL via the `<=>` cosine distance operator after pre-filtering by `allowed_classifications`. By default (`EMBEDDING_PROVIDER="deterministic_hash"`), 384-dimensional vectors are generated via deterministic MD5 unigram/bigram feature hashing (capturing lexical token overlap without requiring external neural model weights).
- **Database**: PostgreSQL 16+ with `pgvector` in production/Docker, with cross-dialect `JSON` fallback on SQLite for fast local unit/integration tests (`/api/v1/health` reports `pgvector_enabled: true` only when connected to PostgreSQL with the `vector` extension installed).

---

## 3. Quick Start

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

# Run database migrations (for PostgreSQL, ensure `CREATE EXTENSION IF NOT EXISTS vector;` is enabled):
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
npm test
npm run build
npm run dev
```

---

## 4. Environment Variables Summary (`.env.example`)

| Variable | Default / Example | Description |
|---|---|---|
| `APP_ENV` | `development` / `production` | Application runtime environment |
| `DATABASE_URL` | `postgresql+psycopg://kh_user:...@localhost:5432/knowledge_handover` | SQLAlchemy connection URL (`postgresql+psycopg://` or `sqlite:///`) |
| `JWT_SECRET_KEY` | *(32+ byte secret)* | Secret key used to sign HS256 JWT access tokens |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed CORS origins |
| `LLM_PROVIDER` | `deterministic_extractive` | `ollama`, `openai_compatible`, or `deterministic_extractive` |
| `LLM_BASE_URL` | `http://localhost:11434` / `https://api.groq.com/openai/v1` | Base URL for Ollama or OpenAI-compatible inference server |
| `LLM_API_KEY` | *(empty or API key)* | API key when using `openai_compatible` provider |
| `LLM_MODEL_NAME` | `qwen2.5:7b-instruct` / `llama-3.3-70b-versatile` | Target LLM model identifier |
| `EMBEDDING_PROVIDER` | `deterministic_hash` | Embedding generator (`deterministic_hash` uses 384-dim MD5 feature hashing) |
| `EMBEDDING_DIMENSION` | `384` | Vector dimension matching `pgvector` `vector(384)` schema |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API base URL consumed by the frontend at build/runtime |

---

## 5. Production Render Deployment (`render.yaml`)

[`render.yaml`](render.yaml) defines the production Render Blueprint with the existing service and database names:

- **Database**: `kh-postgres` (`databaseName: knowledge_handover`, `user: kh_user`)
- **Backend Web Service**: `kh-backend` (`rootDir: backend`, health check `/api/v1/health`, connected to `kh-postgres` with `EMBEDDING_PROVIDER="deterministic_hash"`, `EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"`, `EMBEDDING_DIMENSION="384"`)
- **Frontend Static Site**: `kh-frontend` (`rootDir: frontend`, `buildCommand: npm ci && npm run build`, SPA rewrite `/* -> /index.html`, `VITE_API_BASE_URL` linked to `kh-backend`)

---

## 6. Complete Documentation Index (`docs/`)

1. [PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
2. [ARCHITECTURE.md](docs/ARCHITECTURE.md)
3. [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)
4. [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)
5. [AUTHENTICATION_AUTHORIZATION.md](docs/AUTHENTICATION_AUTHORIZATION.md)
6. [AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md)
7. [DATA_FLOW.md](docs/DATA_FLOW.md)
8. [TESTING.md](docs/TESTING.md)
9. [SECURITY.md](docs/SECURITY.md)
10. [SETUP_GUIDE.md](docs/SETUP_GUIDE.md)
11. [DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)
12. [DECISIONS.md](docs/DECISIONS.md)
13. [CHANGELOG.md](docs/CHANGELOG.md)
14. [KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)
15. [PROJECT_STATUS.md](docs/PROJECT_STATUS.md)
16. [ONBOARDING_FOR_NEW_DEVELOPER.md](docs/ONBOARDING_FOR_NEW_DEVELOPER.md)
17. [DEMO_GUIDE.md](docs/DEMO_GUIDE.md)

---

## 7. Hackathon Code Integrity & Disclosure

- **Team**: Preeti Satish Mittal (Team Leader / AI & Backend Lead) & Ankit Madanlal Chaudhari (Frontend & Product Workflow Lead).
- **Synthetic Data Only**: The seeded `PayFlow` dataset is 100% synthetic and contains intentional test cases for conflicts, stale records, missing owners, prompt injection, and synthetic credential redaction.

