# Project Overview — Knowledge Handover Platform (Continuity OS v2.1)

> **Core Paradigm:** *"Evidence before assertion; uncertainty shown, never hidden; nothing shared before human approval."*

## 1. Problem Statement
When a senior developer, architect, or technical lead leaves a software project, changes roles, or becomes unavailable, critical project context disappears. Explicit artefacts (issues, pull requests, ADRs, meeting notes, technical docs) are scattered and frequently disagree or age, while tacit rationale, undocumented operational workarounds, and ownership gaps remain hidden.

## 2. Solution Explanation
**Knowledge Handover** reconstructs a structured, evidence-linked, contradiction-aware, and human-approved handover package from authorised project records following the **Connect & Redact → 3-Agent Reconstruct → Clarify & Annotate → Human Review & Approve → Successor Continue & Acknowledge** lifecycle.

## 3. Six Core Architectural Differentiators
1. **Strict Evidence Provenance**: Every claim links to a database-verified `sourceId`, character span (`body#chars:start-end`), `versionTag`, and `sourceUpdatedAt` timestamp.
2. **Explicit Contradiction & Staleness Detection**: Preserves conflicting sources side-by-side (`conflicting`) and flags superseded specifications (`potentially_outdated`).
3. **Never Invents Facts or Owners**: Missing decision rationale (`adr-001`) and unassigned owners (`issue-104`) remain explicitly `null` and trigger targeted Clarification Questions (`UnresolvedQuestionSchema`).
4. **Pre-LLM Secret Redaction & Prompt-Injection Isolation**: Scrubs credentials (`[REDACTED_API_KEY]`, `[REDACTED_BEARER_TOKEN]`) before storage/LLM calls and isolates embedded prompt-injection instructions (`[ADVERSARIAL_INSTRUCTION_ISOLATED]`).
5. **Mandatory Human Review & Approval Gate**: AI agents are schema-prohibited from outputting `verified`. Only `REVIEWER_SME` or `PROJECT_LEAD` can mark claims `verified` and approve the handover package.
6. **Approval-Gated 13-Section Continuation Plan**: Locked (`HTTP 403`) until human sign-off freezes an immutable `HandoverVersion` snapshot; only `SUCCESSOR` can formally acknowledge receipt.

## 4. Target Personas & Pre-Provisioned Demo Identities
1. **Project Lead (`PROJECT_LEAD` — `preeti.lead@payflow.demo`)**: Clearance `["PUBLIC", "INTERNAL", "RESTRICTED"]`. Scopes handovers, uploads sources, views all 8 sources (including `restricted-vendor-note`), runs 3-agent reconstruction, verifies claims, approves packages, views Audit Trail, and resets demo state.
2. **Outgoing Developer (`OUTGOING_DEV` — `arjun.outgoing@payflow.demo`)**: Clearance `["PUBLIC", "INTERNAL"]`. Uploads sources, triggers reconstruction, answers open Clarification Questions, and flags/annotates draft claims. Cannot mark claims `verified` or approve.
3. **Reviewer / SME (`REVIEWER_SME` — `kavita.reviewer@payflow.demo`)**: Clearance `["PUBLIC", "INTERNAL"]`. Inspects source excerpts and conflicts side-by-side, marks claims `verified` or `rejected`, approves the final handover package, and views the Audit Trail.
4. **Incoming Developer / Successor (`SUCCESSOR` — `ankit.successor@payflow.demo`)**: Clearance `["PUBLIC", "INTERNAL"]`. Blocked (`403`) from unapproved drafts; post-approval, unlocks the 13-Section Continuation Plan, exports Markdown/JSON, and holds exclusive permission to acknowledge handover receipt.
5. **Anonymous Guest Evaluator (`GUEST_DEMO`)**: Clearance `["PUBLIC", "INTERNAL"]`. Instant read-only sandbox mode scoped strictly to the synthetic `PayFlow` demo workspace (restricted to `Overview`, `Dashboard`, and `Permitted Sources`).
