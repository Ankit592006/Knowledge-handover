"""Comprehensive Backend Test Suite: Auth, RBAC, Ingestion, Secret Redaction, Multi-Agent LangGraph, Review & Successor Handover."""

import uuid
from fastapi.testclient import TestClient

from app.main import app


def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@payflow.demo"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_complete_end_to_end_handover_journey_and_security_controls() -> None:
    """
    Tests the complete journey required by Master Prompt Section 13 & Round 1 Proposal Section 8.3:
    Register -> Login -> Create Project -> Assign Roles (Lead, Outgoing, Reviewer, Successor) ->
    Seed PayFlow Sources -> Verify Secret Redaction -> Create Handover -> Run LangGraph 3 Agents ->
    Verify Conflict Detection, Stale Doc Detection, Unknown Owner Preservation, Prompt Injection Isolation ->
    Block Unapproved Successor View -> Answer Clarification -> Reviewer Edit & Approve ->
    Successor Views Continuation Plan (Restricted Source Excluded) -> Acknowledge Receipt -> Verify Audit Trail.
    """
    with TestClient(app) as client:
        # 1. Register 4 personas: Project Lead, Outgoing Dev, Reviewer/SME, Successor
        lead_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": _unique_email("preeti.lead"),
                "password": "StrongPassword!123",
                "full_name": "Preeti Satish Mittal (Project Lead)",
                "platform_role": "STANDARD",
            },
        )
        assert lead_reg.status_code == 201
        lead_token = lead_reg.json()["access_token"]
        lead_id = lead_reg.json()["user"]["id"]

        outgoing_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": _unique_email("arjun.outgoing"),
                "password": "StrongPassword!123",
                "full_name": "Arjun Mehta (Outgoing Engineer)",
                "platform_role": "STANDARD",
            },
        )
        assert outgoing_reg.status_code == 201
        outgoing_token = outgoing_reg.json()["access_token"]
        outgoing_id = outgoing_reg.json()["user"]["id"]

        reviewer_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": _unique_email("sme.reviewer"),
                "password": "StrongPassword!123",
                "full_name": "Kavita Rao (Reviewer / SME)",
                "platform_role": "STANDARD",
            },
        )
        assert reviewer_reg.status_code == 201
        reviewer_token = reviewer_reg.json()["access_token"]
        reviewer_id = reviewer_reg.json()["user"]["id"]

        successor_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": _unique_email("ankit.successor"),
                "password": "StrongPassword!123",
                "full_name": "Ankit Chaudhari (Incoming Successor)",
                "platform_role": "STANDARD",
            },
        )
        assert successor_reg.status_code == 201
        successor_token = successor_reg.json()["access_token"]
        successor_id = successor_reg.json()["user"]["id"]

        # Unauthenticated User / External Project User (for IDOR / cross-project isolation testing)
        outsider_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": _unique_email("outsider"),
                "password": "StrongPassword!123",
                "full_name": "External User",
                "platform_role": "STANDARD",
            },
        )
        outsider_token = outsider_reg.json()["access_token"]

        # 2. Test Login & Refresh Token Rotation
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": lead_reg.json()["user"]["email"], "password": "StrongPassword!123"},
        )
        assert login_resp.status_code == 200
        old_refresh = login_resp.json()["refresh_token"]
        refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert refresh_resp.status_code == 200
        # Re-using rotated refresh token must fail (401)
        replay_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert replay_resp.status_code == 401

        # 3. Create PayFlow Project as Project Lead
        proj_slug = f"payflow-{uuid.uuid4().hex[:6]}"
        proj_resp = client.post(
            "/api/v1/projects",
            headers=_auth_header(lead_token),
            json={
                "slug": proj_slug,
                "name": "PayFlow Payment Gateway",
                "description": "Payment orchestration microservice handover test",
                "data_classification": "synthetic_demo",
            },
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]

        # Outsider must be blocked from accessing this project (IDOR / Cross-project isolation)
        outsider_proj = client.get(f"/api/v1/projects/{project_id}", headers=_auth_header(outsider_token))
        assert outsider_proj.status_code == 403

        # 4. Assign project roles & classification clearances
        client.post(
            f"/api/v1/projects/{project_id}/members",
            headers=_auth_header(lead_token),
            json={
                "user_id": outgoing_id,
                "project_role": "OUTGOING_DEV",
                "allowed_classifications": ["PUBLIC", "INTERNAL"],
            },
        )
        client.post(
            f"/api/v1/projects/{project_id}/members",
            headers=_auth_header(lead_token),
            json={
                "user_id": reviewer_id,
                "project_role": "REVIEWER_SME",
                "allowed_classifications": ["PUBLIC", "INTERNAL"],
            },
        )
        client.post(
            f"/api/v1/projects/{project_id}/members",
            headers=_auth_header(lead_token),
            json={
                "user_id": successor_id,
                "project_role": "SUCCESSOR",
                "allowed_classifications": ["PUBLIC", "INTERNAL"],
            },
        )

        # 5. Seed Synthetic PayFlow Dataset & Verify Secret Scanning/Redaction
        seed_resp = client.post(
            f"/api/v1/projects/{project_id}/sources/seed-payflow",
            headers=_auth_header(lead_token),
        )
        assert seed_resp.status_code == 201
        seeded_sources = seed_resp.json()
        assert len(seeded_sources) == 9

        restricted_doc = next(s for s in seeded_sources if s["stable_source_id"] == "restricted-vendor-note")
        assert restricted_doc["redacted_secrets_count"] >= 2
        assert "sk_live_SYNTHETIC" not in restricted_doc["content_redacted"]
        assert "[REDACTED_SECRET]" in restricted_doc["content_redacted"]

        # Successor with PUBLIC/INTERNAL clearance must be blocked from viewing RESTRICTED source directly
        sec_source_check = client.get(
            f"/api/v1/sources/{restricted_doc['id']}",
            headers=_auth_header(successor_token),
        )
        assert sec_source_check.status_code == 403

        # 6. Create Scoped Handover via Round 1 Proposal endpoint POST /api/handovers
        handover_resp = client.post(
            "/api/handovers",
            headers=_auth_header(lead_token),
            json={
                "project_id": project_id,
                "title": "PayFlow v2.1 Release Transition",
                "scope_description": "Payment integration, 3DS2 callbacks, and settlement database operations.",
                "departing_role": "Outgoing Lead Payment Engineer",
                "outgoing_user_id": outgoing_id,
                "successor_user_id": successor_id,
                "allowed_classifications": ["PUBLIC", "INTERNAL"],
            },
        )
        assert handover_resp.status_code == 201
        handover_id = handover_resp.json()["handoverId"]

        # 7. Import Authorised Sources (POST /api/handovers/{id}/sources/import)
        import_resp = client.post(
            f"/api/handovers/{handover_id}/sources/import",
            headers=_auth_header(lead_token),
            json={"source_ids": [], "seed_payflow_if_empty": False},
        )
        assert import_resp.status_code == 200
        # Restricted source must NOT be in scopedSources because handover scope is PUBLIC + INTERNAL
        scoped_ids = {s["stable_source_id"] for s in import_resp.json()["scopedSources"]}
        assert "restricted-vendor-note" not in scoped_ids
        assert "issue-104" in scoped_ids

        # 8. Test Agent Failure Stop-on-Failure Guarantee
        fail_resp = client.post(
            f"/api/handovers/{handover_id}/reconstruct?force_failure_agent=evidence_verification",
            headers=_auth_header(lead_token),
        )
        assert fail_resp.status_code == 503

        # 9. Run Full 3-Agent Reconstruction (POST /api/handovers/{id}/reconstruct)
        recon_resp = client.post(
            f"/api/handovers/{handover_id}/reconstruct",
            headers=_auth_header(lead_token),
        )
        assert recon_resp.status_code == 200
        draft = recon_resp.json()
        assert draft["status"] == "ready_for_review"
        assert draft["approval"]["status"] == "not_approved"

        # Verify Synthetic Demo Acceptance Checklist (Round 1 Proposal Section 8.3):
        claims = draft["claims"]
        assert len(claims) >= 6

        # (a) No AI claim is marked 'verified' before human review (even with prompt injection note present)
        assert all(c["status"] != "verified" for c in claims)

        # (b) Intentionally blocked issue-104 appears as blocked with unknown (None) owner AND conflicting status
        blocked_claim = next(c for c in claims if c["type"] == "blocked_work")
        assert blocked_claim["taskStatus"] == "blocked"
        assert blocked_claim["owner"] is None
        assert blocked_claim["status"] == "conflicting"
        assert len(blocked_claim["conflicts"]) >= 1
        assert blocked_claim["conflicts"][0]["sourceAId"] == "issue-104"
        assert blocked_claim["conflicts"][0]["sourceBId"] == "notes-2026-10-15"

        # (c) Stale technical document (doc-legacy-api) is flagged as potentially_outdated against PR-218
        stale_claim = next(c for c in claims if c["type"] == "technical_context")
        assert stale_claim["status"] == "potentially_outdated"

        # (d) Prompt injection attempt did not invent fake source-9999-fake or leak restricted vendor note
        all_cited_sources = {ev["sourceId"] for c in claims for ev in c["evidence"]}
        assert "source-9999-fake" not in all_cited_sources
        assert "restricted-vendor-note" not in all_cited_sources

        # 10. Successor MUST be blocked from viewing draft or successor-view before human approval
        unapproved_draft_view = client.get(
            f"/api/handovers/{handover_id}/draft",
            headers=_auth_header(successor_token),
        )
        assert unapproved_draft_view.status_code == 403

        unapproved_succ_view = client.get(
            f"/api/handovers/{handover_id}/successor-view",
            headers=_auth_header(successor_token),
        )
        assert unapproved_succ_view.status_code == 403

        # 11. Outgoing Developer answers a clarification question
        open_q = draft["openQuestions"][0]
        clarify_resp = client.post(
            f"/api/handovers/{handover_id}/clarifications/{open_q['id']}",
            headers=_auth_header(outgoing_token),
            json={
                "answer_text": "Use 3 exponential backoff retries (5s, 30s, 300s) and a 72-hour DLQ TTL.",
                "mark_resolved": True,
            },
        )
        assert clarify_resp.status_code == 200
        assert clarify_resp.json()["status"] == "answered"

        # Outgoing Developer CANNOT mark a claim as 'verified' (only Reviewer or Lead can)
        forbidden_verify = client.patch(
            f"/api/claims/{blocked_claim['id']}",
            headers=_auth_header(outgoing_token),
            json={"status": "verified"},
        )
        assert forbidden_verify.status_code == 403

        # 12. Reviewer / SME edits & verifies the blocked claim and resolves conflict
        reviewer_patch = client.patch(
            f"/api/claims/{blocked_claim['id']}",
            headers=_auth_header(reviewer_token),
            json={
                "status": "verified",
                "review_state": "approved",
                "reviewer_notes": "Confirmed with team: Oct 15 meeting note was outdated; ISSUE-104 is indeed BLOCKED on Finance Ops certificate.",
            },
        )
        assert reviewer_patch.status_code == 200
        assert reviewer_patch.json()["status"] == "verified"

        # 13. Reviewer Approves the Handover Package (POST /api/handovers/{id}/approve)
        approve_resp = client.post(
            f"/api/handovers/{handover_id}/approve",
            headers=_auth_header(reviewer_token),
            json={"approval_notes": "All claims verified against sources; ready for successor."},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["approval"]["status"] == "approved"
        assert approve_resp.json()["currentVersion"] == 2

        # 14. Successor Views the Approved 13-Section Continuation Plan (GET /api/handovers/{id}/successor-view)
        succ_view = client.get(
            f"/api/handovers/{handover_id}/successor-view",
            headers=_auth_header(successor_token),
        )
        assert succ_view.status_code == 200
        plan = succ_view.json()
        assert plan["restrictedSourcesFilteredOut"] >= 1
        assert "1_project_overview" in plan["sections"]
        assert "5_blocked_tasks" in plan["sections"]
        assert "11_prioritised_next_actions" in plan["sections"]
        assert len(plan["nextActions"]) >= 3

        # 15. Successor Acknowledges Receipt
        ack_resp = client.post(
            f"/api/handovers/{handover_id}/acknowledge",
            headers=_auth_header(successor_token),
            json={"acknowledgement_notes": "Reviewed all 13 sections, blockers, and next actions. Ready to take over."},
        )
        assert ack_resp.status_code == 200
        assert ack_resp.json()["approval"]["status"] == "acknowledged"

        # 16. Verify Append-Only Audit Trail & Export
        audit_resp = client.get(
            f"/api/v1/handovers/{handover_id}/audit-logs",
            headers=_auth_header(lead_token),
        )
        assert audit_resp.status_code == 200
        audit_actions = [a["action"] for a in audit_resp.json()]
        assert "HANDOVER_CREATED" in audit_actions
        assert "HANDOVER_RECONSTRUCTED" in audit_actions
        assert "CLAIM_REVIEW_UPDATED" in audit_actions
        assert "HANDOVER_APPROVED" in audit_actions
        assert "HANDOVER_RECEIPT_ACKNOWLEDGED" in audit_actions

        export_md = client.get(
            f"/api/v1/handovers/{handover_id}/export?format_type=markdown",
            headers=_auth_header(successor_token),
        )
        assert export_md.status_code == 200
        assert "Prioritised Next Actions" in export_md.json()["content"]
