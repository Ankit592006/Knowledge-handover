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


def test_sec01_admin_project_isolation_explicit_clearance_and_guest_demo_workflow() -> None:
    """
    Verifies SEC-01 fixes:
    1. Public self-registration cannot assign platform_role=ADMIN or GUEST_DEMO (always assigns STANDARD).
    2. Only trusted provisioning or an existing authorized Platform ADMIN can create ADMIN accounts.
    3. Platform ADMIN has no implicit project membership and no implicit RESTRICTED clearance.
    4. Explicit project membership and actual classification clearance are enforced for all resources.
    5. Legitimate ADMIN operations (user listing, global audit logs, explicit member assignment, admin provisioning) are preserved and audited.
    6. Unauthenticated Incognito Guest Demo workflow works via read-only GUEST_DEMO role limited strictly to synthetic PayFlow data.
    7. Guest Demo cannot access RESTRICTED evidence, other projects, or write/admin operations.
    """
    from app.core.database import SessionLocal
    from app.models.enums import PlatformRole
    from app.modules.auth.service import provision_admin_user
    from app.schemas.api_schemas import AdminUserCreateRequest

    with TestClient(app) as client:
        # 1. Register a Project Lead via public registration (defaults to STANDARD)
        lead_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": _unique_email("sec01.lead"),
                "password": "StrongPassword!123",
                "full_name": "Sec01 Private Project Lead",
            },
        )
        assert lead_reg.status_code == 201
        assert lead_reg.json()["user"]["platform_role"] == "STANDARD"
        lead_token = lead_reg.json()["access_token"]

        # 2. Prove public self-registration with platform_role=ADMIN is blocked (403 Forbidden)
        illegal_admin_self_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": _unique_email("illegal.admin"),
                "password": "StrongPassword!123",
                "full_name": "Unauthorized Self-Registered Admin",
                "platform_role": "ADMIN",
            },
        )
        assert illegal_admin_self_reg.status_code == 403

        # Prove non-admin STANDARD user cannot call POST /api/v1/users/admin
        illegal_admin_create = client.post(
            "/api/v1/users/admin",
            headers=_auth_header(lead_token),
            json={
                "email": _unique_email("illegal.admin2"),
                "password": "StrongPassword!123",
                "full_name": "Unauthorized Provisioned Admin",
                "platform_role": "ADMIN",
            },
        )
        assert illegal_admin_create.status_code == 403

        # 3. Provision a legitimate Platform ADMIN via trusted provisioning process
        admin_email = _unique_email("sec01.admin")
        with SessionLocal() as db:
            admin_user_resp = provision_admin_user(
                db,
                AdminUserCreateRequest(
                    email=admin_email,
                    password="StrongPassword!123",
                    full_name="Sec01 Platform Admin",
                    platform_role=PlatformRole.ADMIN,
                ),
            )
            admin_id = admin_user_resp.id

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": "StrongPassword!123"},
        )
        assert admin_login.status_code == 200
        assert admin_login.json()["user"]["platform_role"] == "ADMIN"
        admin_token = admin_login.json()["access_token"]

        # Prove existing authorized ADMIN can provision another ADMIN account via POST /api/v1/users/admin
        second_admin_resp = client.post(
            "/api/v1/users/admin",
            headers=_auth_header(admin_token),
            json={
                "email": _unique_email("sec01.admin2"),
                "password": "StrongPassword!123",
                "full_name": "Secondary Platform Admin",
                "platform_role": "ADMIN",
            },
        )
        assert second_admin_resp.status_code == 201
        assert second_admin_resp.json()["platform_role"] == "ADMIN"

        # Create private project as lead and seed sources (includes restricted-vendor-note)
        priv_slug = f"private-vault-{uuid.uuid4().hex[:6]}"
        priv_proj_resp = client.post(
            "/api/v1/projects",
            headers=_auth_header(lead_token),
            json={
                "slug": priv_slug,
                "name": "Confidential Enterprise Vault",
                "description": "Private enterprise project for SEC-01 isolation testing",
                "data_classification": "enterprise_confidential",
            },
        )
        assert priv_proj_resp.status_code == 201
        priv_proj_id = priv_proj_resp.json()["id"]

        seed_resp = client.post(
            f"/api/v1/projects/{priv_proj_id}/sources/seed-payflow",
            headers=_auth_header(lead_token),
        )
        assert seed_resp.status_code == 201
        priv_restricted_doc = next(
            s for s in seed_resp.json() if s["stable_source_id"] == "restricted-vendor-note"
        )

        priv_handover_resp = client.post(
            "/api/handovers",
            headers=_auth_header(lead_token),
            json={
                "project_id": priv_proj_id,
                "title": "Private Vault Handover",
                "scope_description": "Confidential transition package",
                "departing_role": "Principal Security Engineer",
                "allowed_classifications": ["PUBLIC", "INTERNAL"],
            },
        )
        assert priv_handover_resp.status_code == 201
        priv_handover_id = priv_handover_resp.json()["handoverId"]

        # 4. Verify ADMIN without explicit project membership is blocked from private project resources
        admin_proj_list = client.get("/api/v1/projects", headers=_auth_header(admin_token))
        assert admin_proj_list.status_code == 200
        assert all(p["id"] != priv_proj_id for p in admin_proj_list.json())

        admin_handover_list = client.get("/api/handovers", headers=_auth_header(admin_token))
        assert admin_handover_list.status_code == 200
        assert all(h["handoverId"] != priv_handover_id for h in admin_handover_list.json())

        assert (
            client.get(f"/api/v1/projects/{priv_proj_id}", headers=_auth_header(admin_token)).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/v1/projects/{priv_proj_id}/sources", headers=_auth_header(admin_token)
            ).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/v1/sources/{priv_restricted_doc['id']}", headers=_auth_header(admin_token)
            ).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/handovers/{priv_handover_id}/draft", headers=_auth_header(admin_token)
            ).status_code
            == 403
        )

        # 5. Verify legitimate ADMIN operations and audit logging
        # Standard user is blocked from admin endpoints (GET /users, global GET /audit-logs)
        assert client.get("/api/v1/users", headers=_auth_header(lead_token)).status_code == 403
        assert client.get("/api/v1/audit-logs", headers=_auth_header(lead_token)).status_code == 403

        # ADMIN can access GET /users and global GET /audit-logs
        admin_users_resp = client.get("/api/v1/users", headers=_auth_header(admin_token))
        assert admin_users_resp.status_code == 200
        assert len(admin_users_resp.json()) >= 2

        # ADMIN can explicitly assign a member to a project (audited as ADMIN_PROJECT_MEMBER_ASSIGNED)
        # Assign ADMIN as OUTGOING_DEV with ONLY ["PUBLIC", "INTERNAL"] clearance (no RESTRICTED)
        admin_assign_resp = client.post(
            f"/api/v1/projects/{priv_proj_id}/members",
            headers=_auth_header(admin_token),
            json={
                "user_id": admin_id,
                "project_role": "OUTGOING_DEV",
                "allowed_classifications": ["PUBLIC", "INTERNAL"],
            },
        )
        assert admin_assign_resp.status_code == 200

        # Even as a project member, ADMIN with ["PUBLIC", "INTERNAL"] clearance MUST be blocked from RESTRICTED sources
        admin_restricted_read = client.get(
            f"/api/v1/sources/{priv_restricted_doc['id']}",
            headers=_auth_header(admin_token),
        )
        assert admin_restricted_read.status_code == 403

        admin_restricted_upload = client.post(
            f"/api/v1/projects/{priv_proj_id}/sources/upload",
            headers=_auth_header(admin_token),
            json={
                "stable_source_id": "admin-restricted-upload-attempt",
                "source_type": "technical_doc",
                "title": "Unauthorized Restricted Upload",
                "content": "Should be blocked because clearance is only PUBLIC and INTERNAL.",
                "access_level": "RESTRICTED",
                "version_tag": "v1",
            },
        )
        assert admin_restricted_upload.status_code == 403

        # Also verify ADMIN assigned as SUCCESSOR cannot bypass the unapproved draft gate
        client.post(
            f"/api/v1/projects/{priv_proj_id}/members",
            headers=_auth_header(lead_token),
            json={
                "user_id": admin_id,
                "project_role": "SUCCESSOR",
                "allowed_classifications": ["PUBLIC", "INTERNAL"],
            },
        )
        admin_successor_draft = client.get(
            f"/api/handovers/{priv_handover_id}/draft",
            headers=_auth_header(admin_token),
        )
        assert admin_successor_draft.status_code == 403

        # Verify global audit trail captured the blocked attempts and legitimate admin actions
        global_audits = client.get("/api/v1/audit-logs", headers=_auth_header(admin_token))
        assert global_audits.status_code == 200
        global_actions = {a["action"] for a in global_audits.json()}
        assert "PRIVILEGED_SELF_REGISTRATION_BLOCKED" in global_actions
        assert "ADMIN_USER_PROVISIONED" in global_actions
        assert "UNAUTHORIZED_PROJECT_ACCESS_BLOCKED" in global_actions
        assert "UNAUTHORIZED_ADMIN_OPERATION_BLOCKED" in global_actions
        assert "ADMIN_USERS_LISTED" in global_actions
        assert "ADMIN_PROJECT_MEMBER_ASSIGNED" in global_actions
        assert "UNAUTHORIZED_SOURCE_ACCESS_BLOCKED" in global_actions
        assert "UNAPPROVED_DRAFT_ACCESS_BLOCKED" in global_actions

        # 4. Unauthenticated Incognito Guest Demo Workflow & Strict Isolation
        # Attempting to self-register as GUEST_DEMO must be rejected
        bad_guest_reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": _unique_email("fake.guest"),
                "password": "StrongPassword!123",
                "full_name": "Fake Guest",
                "platform_role": "GUEST_DEMO",
            },
        )
        assert bad_guest_reg.status_code == 403

        # Unauthenticated Incognito call to POST /api/v1/demo/bootstrap-payflow (no Authorization header)
        guest_bootstrap = client.post("/api/v1/demo/bootstrap-payflow")
        assert guest_bootstrap.status_code == 200
        guest_draft = guest_bootstrap.json()
        assert guest_draft["handoverId"] == "payflow-handover-001"
        payflow_proj_id = guest_draft["projectId"]
        guest_scoped_source_ids = {s["stable_source_id"] for s in guest_draft["scopedSources"]}
        assert "issue-104" in guest_scoped_source_ids
        assert "restricted-vendor-note" not in guest_scoped_source_ids

        # Unauthenticated Guest can list projects -> sees ONLY synthetic payflow project with GUEST_DEMO role
        guest_projects = client.get("/api/v1/projects")
        assert guest_projects.status_code == 200
        guest_proj_list = guest_projects.json()
        assert len(guest_proj_list) == 1
        assert guest_proj_list[0]["slug"] == "payflow"
        assert guest_proj_list[0]["current_user_role"] == "GUEST_DEMO"

        # Unauthenticated Guest can list PayFlow sources -> sees only PUBLIC and INTERNAL (8 sources, no restricted-vendor-note)
        guest_sources = client.get(f"/api/v1/projects/{payflow_proj_id}/sources")
        assert guest_sources.status_code == 200
        guest_source_ids = {s["stable_source_id"] for s in guest_sources.json()}
        assert "restricted-vendor-note" not in guest_source_ids
        assert len(guest_sources.json()) == 8

        # Unauthenticated Guest can inspect a PUBLIC/INTERNAL PayFlow source and view the PayFlow draft
        assert (
            client.get(f"/api/v1/sources/issue-104?project_id={payflow_proj_id}").status_code
            == 200
        )
        assert client.get("/api/handovers/payflow-handover-001/draft").status_code == 200
        assert client.get("/api/handovers/payflow-handover-001/status").status_code == 200

        # Unauthenticated Guest MUST be blocked from RESTRICTED evidence in PayFlow
        guest_restricted = client.get(
            f"/api/v1/sources/restricted-vendor-note?project_id={payflow_proj_id}"
        )
        assert guest_restricted.status_code == 403

        # Unauthenticated Guest MUST be blocked from accessing any non-PayFlow project or its handovers/sources
        assert client.get(f"/api/v1/projects/{priv_proj_id}").status_code == 403
        assert client.get(f"/api/v1/projects/{priv_proj_id}/sources").status_code == 403
        assert client.get(f"/api/handovers/{priv_handover_id}/draft").status_code == 403

        # Unauthenticated Guest MUST be blocked (401) from all write, review, approval, and admin operations
        first_claim_id = guest_draft["claims"][0]["id"]
        assert (
            client.post(
                "/api/v1/projects",
                json={"slug": "guest-illegal-proj", "name": "Illegal"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                f"/api/v1/projects/{payflow_proj_id}/sources/upload",
                json={
                    "stable_source_id": "guest-upload",
                    "source_type": "technical_doc",
                    "title": "Guest Upload",
                    "content": "Not allowed",
                    "access_level": "PUBLIC",
                },
            ).status_code
            == 401
        )
        assert (
            client.patch(
                f"/api/claims/{first_claim_id}",
                json={"status": "verified", "review_state": "approved"},
            ).status_code
            == 401
        )
        assert client.post("/api/handovers/payflow-handover-001/approve").status_code == 401
        assert client.get("/api/v1/users").status_code == 401
        assert client.get("/api/v1/audit-logs").status_code == 401

