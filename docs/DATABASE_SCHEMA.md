# Database Schema — PostgreSQL + pgvector

## 1. Tables Implemented (`backend/app/models/entities.py`)
1. `users` — Primary user identity and `platform_role` (`ADMIN`, `STANDARD`).
2. `refresh_tokens` — SHA-256 hashed refresh tokens with `expires_at` and `revoked_at`.
3. `projects` — Project workspace metadata (`slug`, `name`, `data_classification`).
4. `project_members` — Scoped project role (`PROJECT_LEAD`, `OUTGOING_DEV`, `REVIEWER_SME`, `SUCCESSOR`) and `allowed_classifications` JSON array (`PUBLIC`, `INTERNAL`, `RESTRICTED`).
5. `source_documents` — Normalised and secret-redacted source records with unique `(project_id, stable_source_id)` constraint.
6. `document_chunks` — Offset-tracked passages (`char_start`, `char_end`, `page_number`) and `embedding` (`EmbeddingVectorType(384)` using `pgvector.sqlalchemy.Vector(384)` on PostgreSQL).
7. `handovers` — Scoped handover state machine (`initiated` → `sources_connected` → `reconstructing` → `ready_for_review` → `approved` → `acknowledged` / `failed`).
8. `handover_sources` — Join table binding authorised `source_documents` to a `handover`.
9. `claims` — Extracted and reviewed project claims with 6-state `status` (`source_supported`, `verified`, `conflicting`, `potentially_outdated`, `inferred`, `unknown`) and `review_state`.
10. `claim_evidence_links` — Provenance links connecting each claim to a verified `source_document_id`, `location`, `excerpt`, and `source_updated_at`.
11. `risks_and_dependencies` — Extracted blockers, operational risks, and component/approval dependencies.
12. `clarification_questions` — Missing-context questions and outgoing developer answers.
13. `next_actions` — Priority-ranked successor actions linked to `evidence_claim_ids`.
14. `handover_versions` — Immutable JSON snapshots created on human approval.
15. `audit_logs` — Append-only audit trail recording actor, role, action, previous state, and new state.
