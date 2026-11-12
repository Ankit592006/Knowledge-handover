# System Architecture — Knowledge Handover Platform

## 1. Modular Monolith Design
The backend (`backend/app/`) is organised as a single deployable FastAPI modular monolith with strict separation between deterministic business logic (`app/modules/`) and multi-agent AI orchestration (`app/agents/`).

## 2. 16 Core Backend Modules
1. `app/modules/auth` — Argon2id hashing, JWT access tokens, rotating SHA-256 refresh tokens.
2. `app/modules/users` — User profile and role lookup.
3. `app/modules/projects` — Project workspaces and `ProjectMember` clearance assignments.
4. `app/modules/ingestion` — Synthetic PayFlow seeding and custom source upload.
5. `app/modules/processing` — Regex/key-value secret scanning & redaction (`[REDACTED_SECRET]`), SHA-256 deduplication.
6. `app/modules/embeddings` — Offset-preserving chunking (`char_start`, `char_end`, `page_number`) and 384-dim embeddings.
7. `app/modules/retrieval` — Permission-filtered vector similarity search (`pgvector` / cross-dialect cosine similarity).
8. `app/agents/orchestrator` — LangGraph state machine (`HandoverGraphState`) with bounded retries and stop-on-failure.
9. `app/agents/knowledge_extraction` — Agent 1: Candidate claims, owners, and open questions.
10. `app/agents/evidence_verification` — Agent 2: Claim-to-source verification, conflict pairs, staleness detection.
11. `app/agents/risk_dependency` — Agent 3: Blockers, operational risks, dependencies, and prioritised next actions.
12. `app/modules/validation` — Deterministic Backend Validator (verifies source IDs exist in DB and strips unauthorised citations).
13. `app/modules/review` & `app/modules/handovers` — Human review edits, clarification loop, approval gate, and version snapshots.
14. `app/modules/continuation` — 13-section Successor Continuation Plan builder and receipt acknowledgement.
15. `app/modules/audit` — Append-only audit log (`audit_logs`).
16. `app/modules/reporting` — JSON and Markdown handover package export.
