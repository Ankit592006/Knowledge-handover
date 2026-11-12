# End-to-End Data Flow — Source Ingestion to Successor Handover

1. **Source Ingestion & Redaction**: Sources are parsed by `scan_and_redact_secrets()`, replacing credentials (e.g., `sk_live_...`, `webhook_secret`) with `[REDACTED_SECRET]`.
2. **Chunking & Vector Indexing**: Documents are split into offset-preserving passages (`char_start`, `char_end`, `page_number`, `location_label`) and embedded into 384-dim vectors in `document_chunks`.
3. **Permission-Filtered Retrieval**: When reconstruction begins, `retrieve_scoped_chunks()` filters chunks by `handover.allowed_classifications` *before* vector similarity ranking.
4. **Prompt Injection Isolation**: Retrieved passages are sanitized by `sanitize_untrusted_passage()` and wrapped in `<untrusted_evidence>` tags.
5. **3-Agent LangGraph Execution & Deterministic Validation**: Agents 1, 3, and 2 populate `HandoverGraphState`, followed by `validate_claims_against_database()`.
6. **Human Review & Clarification Loop**: Outgoing Developer answers open questions; Reviewer/SME inspects side-by-side conflicts, marks claims `verified`, and approves the handover.
7. **Successor Continuation Plan**: `build_successor_continuation_plan()` re-verifies the Successor's clearance, excludes restricted records, assembles the 13-section package, and records receipt acknowledgement.
