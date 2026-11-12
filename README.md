# Knowledge Handover — Intelligent Knowledge Continuity Platform

An agentic, evidence-linked, human-approved software project handover and successor continuation platform.

> **Core Paradigm:** *Evidence before assertion; uncertainty shown, never hidden; nothing shared before human approval.*

---

## 1. Key Differentiators

- **Evidence-Linked Project Reconstruction**: Every extracted claim carries a validated `sourceId`, `location` (`body#chars:start-end`), `versionTag`, and `sourceUpdatedAt` timestamp.
- **Explicit Uncertainty, Conflict & Staleness Detection**: When records disagree (e.g., `issue-104` reports `BLOCKED` while `notes-2026-10-15` reports `IN PROGRESS`), the platform surfaces both records side-by-side with timestamps rather than silently choosing one.
- **Never Invents Facts or Owners**: Missing decision rationale (e.g., `adr-001` webhook retry backoff policy) and unassigned owners (`issue-104`) remain explicitly `null` / `unknown` and automatically generate targeted questions for the outgoing developer.
- **Deterministic Backend Trust Boundary (L6)**: Independently verifies that every cited `sourceId` exists in PostgreSQL, belongs to the scoped handover, and complies with classification clearance before persisting.
- **Mandatory Human Review & Approval Gate**: AI agents are schema-prohibited from marking claims as `verified`. Only an authorised human `REVIEWER_SME` or `PROJECT_LEAD` can mark claims `verified` and approve the handover package.
- **Role-Aware Controlled Sharing & Secret Redaction**: Enforces clearance checks (`PUBLIC`, `INTERNAL`, `RESTRICTED`) before RAG retrieval and again before generating the 13-section Successor Continuation Plan, while automatically scanning and redacting credentials (`[REDACTED_SECRET]`) at ingestion.

---

## 2. Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Axios, Vitest.
- **Backend**: Python 3.11+, FastAPI (Modular Monolith), Pydantic v2, SQLAlchemy 2.0, Alembic, Argon2id (`argon2-cffi`), PyJWT.
- **AI & RAG**: LangGraph orchestrator + 3 specialised agents (*Knowledge Extraction*, *Evidence Verification*, *Risk & Dependency Analysis*), Open-Source Model Adapter (Ollama / OpenAI-compatible local server / deterministic extractive fallback), `pgvector` semantic similarity retrieval.
- **Database**: PostgreSQL 16 + `pgvector` (with cross-dialect SQLite vector support for fast local unit/integration tests).

---

## 3. Quick Start

### Option A: Docker Compose (Recommended for Full Stack + PostgreSQL/pgvector)

```bash
cp .env.example .env
docker compose up --build
```
- **Frontend UI**: http://localhost:5173
- **FastAPI Backend & OpenAPI Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

### Option B: Local Development & Automated Tests

**Backend:**
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pytest -v
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm test
npm run dev
```

---

## 4. Complete Documentation Index (`docs/`)

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

## 5. Hackathon Code Integrity & Disclosure

- **Team**: Preeti Satish Mittal (Team Leader / AI & Backend Lead) & Ankit Madanlal Chaudhari (Frontend & Product Workflow Lead).
- **Synthetic Data Only**: The seeded `PayFlow` dataset is 100% synthetic and contains intentional test cases for conflicts, stale records, missing owners, prompt injection, and synthetic credential redaction.
