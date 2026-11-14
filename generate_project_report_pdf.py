"""
Zero-Dependency Native PDF Report Generator for Knowledge Handover.
Generates 'Knowledge_Handover_Hackathon_Final_Report.pdf' (4-Page Book-Serif A4 PDF)
using only the Python standard library.

Usage:
    python generate_project_report_pdf.py
"""

from pathlib import Path
import textwrap


def pdf_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


class PageBuilder:
    def __init__(self, page_num: int, total_pages: int = 4) -> None:
        self.lines: list[str] = []
        self.y = 790.0
        self.page_num = page_num
        self.total_pages = total_pages
        # Top running header bar
        self.lines.append("0.02 0.30 0.23 rg 36 806 523 18 re f")
        self.lines.append("BT /F2 8.5 Tf 1 1 1 rg 44 812 Td (KNOWLEDGE HANDOVER - FINAL HACKATHON PROJECT REPORT  |  CONTINUITY OS v2.1) Tj ET")
        # Footer
        self.lines.append("0.75 0.78 0.82 RG 0.6 w 36 38 m 559 38 l S")
        footer_left = "Team: Preeti Satish Mittal (Lead) & Ankit Madanlal Chaudhari  |  https://kh-backend-z2o3.onrender.com"
        footer_right = f"Page {page_num} of {total_pages}"
        self.lines.append(f"BT /F1 8 Tf 0.35 0.38 0.42 rg 36 26 Td ({pdf_escape(footer_left)}) Tj ET")
        self.lines.append(f"BT /F2 8 Tf 0.02 0.30 0.23 rg 505 26 Td ({pdf_escape(footer_right)}) Tj ET")

    def add_cover_banner(self) -> None:
        # Deep emerald cover box
        self.lines.append("0.93 0.99 0.96 rg 36 692 523 104 re f")
        self.lines.append("0.02 0.37 0.27 RG 1.2 w 36 692 523 104 re S")
        self.lines.append("BT /F2 16 Tf 0.01 0.22 0.16 rg 48 774 Td (Knowledge Handover: Intelligent Continuity Platform) Tj ET")
        self.lines.append("BT /F3 10 Tf 0.02 0.37 0.27 rg 48 757 Td (Agentic, Evidence-Linked, Contradiction-Aware & Human-Approved Engineering Handovers) Tj ET")
        self.lines.append("BT /F2 9 Tf 0.08 0.12 0.18 rg 48 739 Td (Core Paradigm: \"Evidence before assertion; uncertainty shown, never hidden; nothing shared before human approval.\") Tj ET")
        self.lines.append("BT /F1 8.5 Tf 0.15 0.20 0.26 rg 48 722 Td (Team: Preeti Satish Mittal \\(Team Leader, AI & Backend\\)  |  Ankit Madanlal Chaudhari \\(Frontend & Workflow Lead\\)) Tj ET")
        self.lines.append("BT /F4 8 Tf 0.02 0.35 0.25 rg 48 705 Td (Live API: https://kh-backend-z2o3.onrender.com  |  Repo: https://github.com/Ankit592006/Knowledge-handover) Tj ET")
        self.y = 674.0

    def section(self, title: str) -> None:
        self.y -= 8.0
        self.lines.append(f"BT /F2 12 Tf 0.02 0.30 0.23 rg 36 {self.y:.1f} Td ({pdf_escape(title)}) Tj ET")
        self.y -= 4.0
        self.lines.append(f"0.02 0.37 0.27 RG 1.0 w 36 {self.y:.1f} m 559 {self.y:.1f} l S")
        self.y -= 13.0

    def subsection(self, title: str) -> None:
        self.y -= 4.0
        self.lines.append(f"BT /F2 10 Tf 0.04 0.35 0.26 rg 36 {self.y:.1f} Td ({pdf_escape(title)}) Tj ET")
        self.y -= 12.0

    def paragraph(self, text: str, width: int = 98, font: str = "F1", size: float = 9.2, leading: float = 12.2) -> None:
        for line in textwrap.wrap(text, width=width):
            self.lines.append(f"BT /{font} {size} Tf 0.10 0.12 0.16 rg 36 {self.y:.1f} Td ({pdf_escape(line)}) Tj ET")
            self.y -= leading
        self.y -= 2.0

    def bullet(self, label: str, body: str, width: int = 92) -> None:
        full = f"{label}: {body}" if label else body
        wrapped = textwrap.wrap(full, width=width)
        for i, line in enumerate(wrapped):
            prefix = "* " if i == 0 else "  "
            font = "F2" if (i == 0 and not body) else "F1"
            self.lines.append(f"BT /{font} 8.9 Tf 0.10 0.12 0.16 rg 42 {self.y:.1f} Td ({pdf_escape(prefix + line)}) Tj ET")
            self.y -= 11.6
        self.y -= 1.5

    def code_line(self, text: str) -> None:
        self.lines.append(f"BT /F4 8.0 Tf 0.04 0.28 0.20 rg 44 {self.y:.1f} Td ({pdf_escape(text)}) Tj ET")
        self.y -= 10.8

    def build_stream(self) -> bytes:
        return "\n".join(self.lines).encode("ascii", errors="replace")


def build_pages() -> list[bytes]:
    # PAGE 1
    p1 = PageBuilder(1, 4)
    p1.add_cover_banner()
    p1.section("1. Executive Summary & Problem Statement")
    p1.paragraph(
        "When a senior engineer, architect, or technical lead leaves a software project, critical tacit knowledge evaporates. "
        "Architectural rationale, undocumented operational workarounds, in-flight blockers, and cross-team dependencies remain "
        "scattered across fragmented ADRs, pull requests, issue trackers, sprint notes, and commit logs."
    )
    p1.bullet("1. Manual Handovers Are Incomplete & Stale", "Engineers under deadline pressure omit operational edge cases (such as manual Redis flushes before database migrations) or cite deprecated endpoints.")
    p1.bullet("2. Generic LLM Summarizers Hallucinate & Hide Conflicts", "Standard RAG tools blend older and newer records into fluent prose, hiding contradictions between sprint notes and issue trackers.")
    p1.bullet("3. Unassigned Owners & Missing Rationale Are Fabricated", "Generic LLMs guess owners or deadlines instead of explicitly reporting 'owner: null' and prompting the outgoing developer for clarification.")
    p1.bullet("4. Secret Leakage & Clearance Violations", "Commit notes and hotfix logs often contain live API keys, Bearer tokens, or RESTRICTED vendor findings that must never leak to external LLMs or unauthorized roles.")

    p1.section("2. Six Core Architectural Differentiators (Why This Solution Wins)")
    p1.bullet("D1 - Strict Evidence Provenance", "Every extracted claim links to a database-verified sourceId, character span (body#chars:start-end), versionTag, and sourceUpdatedAt timestamp.")
    p1.bullet("D2 - Explicit Contradiction & Staleness Detection", "When records disagree (e.g., ISSUE-104 says BLOCKED while NOTES-2026-10-15 says IN PROGRESS), Agent 2 preserves both excerpts side-by-side and marks the claim 'conflicting' or 'potentially_outdated'.")
    p1.bullet("D3 - Zero Fabricated Owners or Decisions", "Missing decision rationale (ADR-001 retry backoff policy) and unassigned owners (ISSUE-104) remain explicitly null and trigger targeted Clarification Questions.")
    p1.bullet("D4 - Deterministic Backend L6 Trust Boundary", "Independently validates every AI-cited sourceId against scoped project records in PostgreSQL/SQLite, stripping any hallucinated or unauthorized citation.")
    p1.bullet("D5 - Mandatory Human Review & Approval Gate", "AI agents are schema-prohibited via Pydantic field validators from marking any claim 'verified'. Only a human REVIEWER_SME or PROJECT_LEAD can verify claims and approve the package.")
    p1.bullet("D6 - Pre-LLM Secret Scrubbing & Prompt-Injection Isolation", "Regex redaction scrubs API keys, tokens, DB URLs, and private keys before storage or LLM calls, while sanitize_untrusted_passage() isolates embedded prompt-injection attacks.")

    # PAGE 2
    p2 = PageBuilder(2, 4)
    p2.section("3. End-to-End 8-Layer System Architecture & Technology Stack")
    p2.bullet("L1 - Role-Aware React 18 SPA (TypeScript + Vite + Tailwind)", "Book-professional editorial UI (Libre Baskerville, Source Serif 4, JetBrains Mono), 5-Step Lifecycle Stepper, Evidence Inspector Modal, 13-Section Continuation Renderer, and Centered Auth Modal.")
    p2.bullet("L2 - FastAPI Security Gateway", "Dual-mounted routers (/api/v1 and /api), security headers (nosniff, DENY), Argon2id password hashing, HS256 JWT + Refresh Token rotation, and GUEST_DEMO read-only sandbox.")
    p2.bullet("L3 - Explicit RBAC & Classification Clearance Gate (SEC-01)", "Enforces explicit ProjectMember roles and filters documents/chunks by PUBLIC, INTERNAL, and RESTRICTED clearance BEFORE RAG context assembly.")
    p2.bullet("L4 - Ingestion, Secret Redaction & Vector Indexing", "Scrubs credentials ([REDACTED_API_KEY], [REDACTED_BEARER_TOKEN]), chunks documents (800 chars, 120 overlap), and generates 384-dim embeddings.")
    p2.bullet("L5 - LangGraph 3-Agent StateGraph Orchestrator", "Coordinates Agent 1 (Knowledge Extraction), Agent 2 (Evidence Verification), and Agent 3 (Risk & Dependency Analysis) with bounded retries and stop-on-failure guarantees.")
    p2.bullet("L6 - Deterministic Validation Layer", "Verifies every cited sourceId against the database, computes exact char_start/char_end offsets, downgrades uncited claims to 'unknown', and blocks AI 'verified' status.")
    p2.bullet("L7 - Human Review, Approval & Snapshot Engine", "Handles claim verification, clarification Q&A resolution, immutable HandoverVersion JSON snapshots, Markdown/JSON export, and Successor receipt sign-off.")
    p2.bullet("L8 - Hybrid Persistence & Append-Only Audit Trail", "PostgreSQL 16 + pgvector HNSW index (vector(384)) in production with SQLite cross-dialect support for local/CI tests, plus an immutable AuditLog table.")

    p2.section("4. Deep Dive: LangGraph 3-Agent Pipeline & Groq LLM Adapter")
    p2.subsection("4.1 Specialized Multi-Agent Responsibilities")
    p2.bullet("Agent 1 - Knowledge Extraction Agent", "Wraps passages in <untrusted_evidence> tags after prompt-injection sanitization. Extracts claims across 8 categories (project_overview, technical_context, key_decision, completed_work, active_work, blocked_work, responsibility, operational_info) and outputs UnresolvedQuestionSchema items.")
    p2.bullet("Agent 2 - Evidence Verification Agent", "Cross-checks claims against passage timestamps. Flags status contradictions (ConflictRecordSchema with both sources) and stale documentation (PR-218 superseding doc-legacy-api). Enforces Pydantic validator forbidding 'verified'.")
    p2.bullet("Agent 3 - Risk & Dependency Analysis Agent", "Identifies project blockers, operational risks, and cross-team dependencies (Finance Ops sandbox cert, Risk-Engine v1.4) and ranks Next Actions for the incoming successor.")
    p2.subsection("4.2 Dual-Mode OpenAI-Compatible (Groq) + Deterministic Extractive Adapter")
    p2.paragraph(
        "Configured via LLM_PROVIDER='openai_compatible' in production on Render, invoke_structured_model() calls Groq "
        "(https://api.groq.com/openai/v1/chat/completions) using 'llama-3.3-70b-versatile' at temperature=0.0 with strict "
        "Pydantic JSON Schema validation. Also supports local Ollama ('qwen2.5:7b-instruct') and automatic fallback to the "
        "deterministic rule-grounded extractor ('rule-grounded-extractor-v1') so demos and CI tests never fail."
    )

    # PAGE 3
    p3 = PageBuilder(3, 4)
    p3.section("5. Security Architecture: 5-Role RBAC Matrix & Clearance Scope (SEC-01)")
    p3.bullet("PROJECT_LEAD (preeti.lead@payflow.demo)", "Clearance: [PUBLIC, INTERNAL, RESTRICTED]. Full governance: views all 8 sources (including restricted-vendor-note), uploads sources, runs agents, verifies claims, approves package, views Audit Trail & Successor Plan.")
    p3.bullet("OUTGOING_DEV (arjun.outgoing@payflow.demo)", "Clearance: [PUBLIC, INTERNAL]. Outgoing Studio: uploads sources, runs reconstruction, answers Clarification Questions, flags claims. Cannot mark claims 'verified' or approve.")
    p3.bullet("REVIEWER_SME (kavita.reviewer@payflow.demo)", "Clearance: [PUBLIC, INTERNAL]. Reviewer Console: inspects evidence, marks claims 'verified' or 'rejected', approves handover package (freezing snapshot vN), and inspects Audit Trail.")
    p3.bullet("SUCCESSOR (ankit.successor@payflow.demo)", "Clearance: [PUBLIC, INTERNAL]. Onboarding Hub: blocked (HTTP 403) while unapproved. Once approved, unlocks the 13-Section Continuation Plan, exports Markdown/JSON, and exclusively acknowledges handover receipt.")
    p3.bullet("GUEST_DEMO (Anonymous Evaluator)", "Clearance: [PUBLIC, INTERNAL]. Read-only sandbox scoped strictly to synthetic PayFlow demo. Navigation limited to Overview, Dashboard, and Permitted Sources (7 sources).")

    p3.section("6. Traceability Against Round 1 Proposal (100% Completed)")
    p3.subsection("6.1 Functional Requirements (FR-01 to FR-11)")
    p3.code_line("FR-01 [COMPLETED] Scoped Source Ingestion & Chunking (PUBLIC, INTERNAL, RESTRICTED)")
    p3.code_line("FR-02 [COMPLETED] Structured Claim & Decision Extraction across 8 Engineering Categories")
    p3.code_line("FR-03 [COMPLETED] Mandatory Evidence Attribution (sourceId, char offsets, versionTag)")
    p3.code_line("FR-04 [COMPLETED] Cross-Artifact Contradiction Detection (ISSUE-104 vs NOTES-2026-10-15)")
    p3.code_line("FR-05 [COMPLETED] 6-State Evidence Vocabulary (source_supported, conflicting, potentially_outdated, inferred, unknown, verified)")
    p3.code_line("FR-06 [COMPLETED] Targeted Clarification Prompting & Dynamic Claim Rationale Enrichment")
    p3.code_line("FR-07 [COMPLETED] Interactive Evidence Inspector Modal with Verbatim Excerpts & Conflict Diffs")
    p3.code_line("FR-08 [COMPLETED] Mandatory Human Review & Approval Gate with Immutable Version Snapshots")
    p3.code_line("FR-09 [COMPLETED] Approval-Gated 13-Section Successor Continuation Plan (HTTP 403 until approved)")
    p3.code_line("FR-10 [COMPLETED] Pre-Indexing Secret Redaction & Adversarial Prompt-Injection Guard")
    p3.code_line("FR-11 [COMPLETED] Self-Contained Handover Export in Markdown and JSON Formats")

    p3.subsection("6.2 Non-Functional Requirements (NFR-1 to NFR-7) & 3-Improvement Framework")
    p3.bullet("NFR-1 to NFR-7 Delivered", "Sub-30s reconstruction with millisecond per-agent telemetry; 100% Pydantic v2 schema validation; zero silent fabrication; pre-LLM secret redaction; immutable audit logs; automatic deterministic fallback; <= 2 clicks to inspect verbatim source evidence.")
    p3.bullet("Round 1 Section 9.2 - Three Improvements Delivered", "(1) Pre-Indexing Secret & Credential Redaction Gate + Prompt Guard, (2) Cross-Artifact Contradiction & Staleness Detection Engine, (3) Targeted Clarification Loop & Approval-Gated 13-Section Continuation Plan.")

    # PAGE 4
    p4 = PageBuilder(4, 4)
    p4.section("7. The 13-Section Approval-Gated Successor Continuation Plan")
    p4.code_line("Sec 01: Project Overview & Service Charter        | Sec 08: Risks, Blockers & Cross-Team Dependencies")
    p4.code_line("Sec 02: Technical Context & Active API Surface    | Sec 09: Contradictions & Outdated Documentation Audit")
    p4.code_line("Sec 03: Key Architectural Decisions & Rationale   | Sec 10: Clarification Q&A Log (Outgoing Dev Answers)")
    p4.code_line("Sec 04: Completed Milestones & Delivered Work     | Sec 11: Prioritised Next Actions (Day-1 Onboarding)")
    p4.code_line("Sec 05: Active & Blocked Work Items (ISSUE-104)   | Sec 12: Authorised Source Inventory & Redaction Stats")
    p4.code_line("Sec 06: Ownership Transfer & On-Call Contacts     | Sec 13: Human Approval & Successor Receipt Sign-Off")
    p4.code_line("Sec 07: Operational Runbooks & DB Migration Steps |")

    p4.section("8. Ten Extra Production Features Built Beyond Round 1 Proposal")
    p4.bullet("1. Genuine 4-Persona Backend Role Switcher", "POST /api/v1/demo/switch-role mints real database JWTs for Project Lead, Outgoing Dev, Reviewer SME, and Successor.")
    p4.bullet("2. One-Click Live Demo Reset", "POST /api/v1/demo/bootstrap-payflow?reset=true resets PayFlow to a clean v1 draft while preserving audit history.")
    p4.bullet("3. 3-Tier Classification Clearance Enforcement", "RESTRICTED source (restricted-vendor-note) is visible to PROJECT_LEAD (8 sources) and hidden from other roles (7 sources).")
    p4.bullet("4. Adversarial Prompt-Injection Isolation", "Detects and neutralizes embedded LLM override instructions ([ADVERSARIAL_INSTRUCTION_ISOLATED]) inside uploaded docs.")
    p4.bullet("5. Per-Agent Telemetry & Provenance Cards", "Displays latency (ms), attempt counts, active LLM provider (Groq vs fallback), and L6 citation validation stats.")
    p4.bullet("6. Interactive 5-Step Lifecycle Stepper", "Tracks progress across Sources -> Reconstruction -> Review -> Approval -> Successor Receipt.")
    p4.bullet("7. Governance Audit Trail Explorer", "Dedicated Audit Trail UI tab showing append-only actor, role, timestamp, and state diff records.")
    p4.bullet("8. Book-Professional Typography System", "Pairs Libre Baskerville headings, Source Serif 4 body prose, and JetBrains Mono citations.")
    p4.bullet("9. Native pgvector HNSW + Cross-Dialect SQLite", "Production vector(384) HNSW cosine search on PostgreSQL with seamless SQLite support for local/CI tests.")
    p4.bullet("10. Cloud-Native Render Blueprint & Docker Suite", "One-click deployment via render.yaml (kh-postgres, kh-backend, kh-frontend) and multi-stage Dockerfiles.")

    p4.section("9. Database Schema, REST API Surface & Automated Verification")
    p4.paragraph(
        "Database Entities (15 tables/models): users, refresh_tokens, projects, project_members, source_documents, "
        "document_chunks (vector(384)), handovers, handover_sources, claims, claim_evidence_links, risks_and_dependencies, "
        "clarification_questions, next_actions, handover_versions, and audit_logs."
    )
    p4.paragraph(
        "Automated Verification: 10 Backend Pytest integration/security tests (secret redaction, prompt injection guard, "
        "L6 fake citation stripping, AI verified prohibition, LangGraph halt-on-failure, E2E lifecycle, SEC-01 RBAC) + "
        "Frontend Vitest suite verifying all 6 evidence status badges and role-gated navigation."
    )

    return [p1.build_stream(), p2.build_stream(), p3.build_stream(), p4.build_stream()]


def generate_pdf(output_path: Path) -> None:
    streams = build_pages()
    objects: list[bytes] = []

    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R 5 0 R 7 0 R 9 0 R] /Count 4 >>")

    # 3..10: 4 Pages + 4 Content Streams
    for idx, stream_bytes in enumerate(streams):
        page_obj_num = 3 + idx * 2
        content_obj_num = page_obj_num + 1
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 11 0 R /F2 12 0 R /F3 13 0 R /F4 14 0 R >> >> "
            f"/Contents {content_obj_num} 0 R >>"
        ).encode("ascii")
        objects.append(page_dict)
        stream_obj = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream"
        )
        objects.append(stream_obj)

    # 11..14: Standard Type1 Book & Mono Fonts
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, obj_bytes in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj_bytes)
        out.extend(b"\nendobj\n")

    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    output_path.write_bytes(bytes(out))
    print(f"Generated {output_path} ({len(out):,} bytes)")


if __name__ == "__main__":
    generate_pdf(Path(__file__).resolve().parent / "Knowledge_Handover_Hackathon_Final_Report.pdf")
