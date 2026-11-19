"""
Automated Verification Suite for Round 3 Section 10.1 ("Three Major Improvements for Round 3"):
1. Improvement 1: Live GitHub Connector with Pre-Storage Secret Redaction & Retrieval-Time Permission/Revocation Checks
2. Improvement 2: Second-Pass Citation-Support Verification (supported/weak/mismatch), Reviewer Feedback Loop & Evaluation Harness
3. Improvement 3: Evidence-Backed Dependency Map (with Unknown Owner Gaps) & Side-by-Side Handover Version Comparison (v1 vs v2)
"""

from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.modules.validation.service import evaluate_citation_support


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_round3_improvement_1_github_connector_redaction_and_revocation() -> None:
    """
    Section 10.1 Improvement 1 Measurement:
    - End-to-end import of a public test repository into a reviewable handover;
    - Redaction check on planted secrets before storage;
    - Access test showing revoked content disappears from the successor view and blocks successor source reads.
    """
    with TestClient(app) as client:
        # Authenticate as PROJECT_LEAD and SUCCESSOR via the genuine demo role switcher
        lead_resp = client.post("/api/v1/demo/switch-role", json={"project_role": "PROJECT_LEAD"})
        assert lead_resp.status_code == 200
        lead_token = lead_resp.json()["access_token"]
        project_id = lead_resp.json()["user"]["memberships"][0]["project_id"]

        succ_resp = client.post("/api/v1/demo/switch-role", json={"project_role": "SUCCESSOR"})
        assert succ_resp.status_code == 200
        succ_token = succ_resp.json()["access_token"]

        # Reset PayFlow demo to clean v1 draft
        reset_resp = client.post(
            "/api/v1/demo/bootstrap-payflow?reset=true",
            headers=_auth_header(lead_token),
        )
        assert reset_resp.status_code == 200

        # 1. Import repository artifacts via GitHub Connector with planted secret test enabled
        gh_resp = client.post(
            f"/api/v1/projects/{project_id}/sources/github-import",
            headers=_auth_header(lead_token),
            json={
                "repo_full_name": "Ankit592006/Knowledge-handover",
                "include_issues": True,
                "include_pulls": True,
                "doc_paths": ["README.md"],
                "access_level": "INTERNAL",
                "plant_test_secret_for_verification": True,
                "max_items_per_category": 2,
            },
        )
        assert gh_resp.status_code == 201
        gh_data = gh_resp.json()
        assert gh_data["imported_count"] >= 2
        assert gh_data["total_redacted_secrets_count"] >= 2

        imported_source_id = gh_data["sources"][0]["stable_source_id"]
        first_redacted_text = gh_data["sources"][0]["content_redacted"]
        # Verify raw planted secrets were scrubbed prior to storage
        assert ("ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8") not in first_redacted_text
        assert ("sk_" + "live_99aabbccddeeff00112233445566") not in first_redacted_text
        assert "[REDACTED" in first_redacted_text

        # 2. Reconstruct & Approve the handover so Successor View is unlocked
        rec_resp = client.post(
            "/api/handovers/payflow-handover-001/reconstruct",
            headers=_auth_header(lead_token),
        )
        assert rec_resp.status_code == 200

        app_resp = client.post(
            "/api/handovers/payflow-handover-001/approve",
            headers=_auth_header(lead_token),
            json={"approval_notes": "Approved with imported GitHub repository records."},
        )
        assert app_resp.status_code == 200

        # Before revocation: Successor can read the imported GitHub source and sees 0 revoked sources
        src_before = client.get(
            f"/api/v1/sources/{imported_source_id}?project_id={project_id}",
            headers=_auth_header(succ_token),
        )
        assert src_before.status_code == 200

        plan_before = client.get(
            "/api/handovers/payflow-handover-001/successor-view",
            headers=_auth_header(succ_token),
        )
        assert plan_before.status_code == 200
        assert plan_before.json()["revokedSourcesFilteredOut"] == 0

        # 3. Project Lead revokes repository access on the imported GitHub source
        revoke_resp = client.patch(
            f"/api/v1/projects/{project_id}/sources/{imported_source_id}/access",
            headers=_auth_header(lead_token),
            json={
                "access_revoked": True,
                "revocation_reason": "GitHub App installation token permission revoked.",
            },
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["metadata_json"]["access_revoked"] is True

        # Retrieval-time check: Revoked source immediately disappears from Successor's source list,
        # direct detail read is blocked (403), and Successor Continuation Plan excludes its citations!
        src_after = client.get(
            f"/api/v1/sources/{imported_source_id}?project_id={project_id}",
            headers=_auth_header(succ_token),
        )
        assert src_after.status_code == 403

        list_after = client.get(
            f"/api/v1/projects/{project_id}/sources",
            headers=_auth_header(succ_token),
        )
        assert list_after.status_code == 200
        succ_visible_ids = [s["stable_source_id"] for s in list_after.json()]
        assert imported_source_id not in succ_visible_ids

        plan_after = client.get(
            "/api/handovers/payflow-handover-001/successor-view",
            headers=_auth_header(succ_token),
        )
        assert plan_after.status_code == 200
        plan_after_data = plan_after.json()
        assert plan_after_data["revokedSourcesFilteredOut"] >= 1
        all_plan_evidence_ids = [
            ev["sourceId"]
            for clm in plan_after_data["claims"]
            for ev in clm["evidence"]
        ]
        assert imported_source_id not in all_plan_evidence_ids


def test_round3_improvement_2_citation_support_verification_and_evaluation_harness() -> None:
    """
    Section 10.1 Improvement 2 Measurement:
    - Second-pass support check for each claim labelled 'supported', 'weak', or 'mismatch';
    - Reviewer-flagged mismatches recorded and fed back;
    - Repeatable evaluation harness comparing Baseline (L6.1) vs Post-Improvement (L6.2) committed to repo.
    """
    # 1. Direct unit verification of L6.2 evaluate_citation_support()
    sup_label, sup_score, _ = evaluate_citation_support(
        claim_text="Stripe PaymentIntents v2 core adapter and PostgreSQL idempotency ledger table migration are completed.",
        excerpt="Completed milestones: Stripe PaymentIntents v2 core adapter (merged in PR-218) and PostgreSQL idempotency ledger table migration.",
    )
    assert sup_label == "supported"
    assert sup_score >= 0.45

    weak_label, weak_score, _ = evaluate_citation_support(
        claim_text="Automated blue-green canary rollback script triggers pager alerts within 15 seconds during settlement deployment traffic drain.",
        excerpt="During settlement deployment traffic drain, operators monitor Redis and Alembic migration logs manually.",
    )
    assert weak_label == "weak"
    assert 0.22 <= weak_score < 0.45

    mis_label, mis_score, _ = evaluate_citation_support(
        claim_text="Kubernetes HorizontalPodAutoscaler scales GraphQL subscription gateway pods to 64 replicas on CPU threshold 75%.",
        excerpt="PayFlow is the core payment orchestration and merchant settlement microservice for checkout flows.",
    )
    assert mis_label == "mismatch"
    assert mis_score < 0.22

    with TestClient(app) as client:
        rev_resp = client.post("/api/v1/demo/switch-role", json={"project_role": "REVIEWER_SME"})
        assert rev_resp.status_code == 200
        rev_token = rev_resp.json()["access_token"]

        draft_resp = client.post(
            "/api/v1/demo/bootstrap-payflow?reset=true",
            headers=_auth_header(rev_token),
        )
        assert draft_resp.status_code == 200
        claims = draft_resp.json()["claims"]
        assert len(claims) >= 5
        first_claim = claims[0]
        assert first_claim["citationSupportStatus"] in ("supported", "weak", "mismatch")
        assert first_claim["evidence"][0]["supportStatus"] in ("supported", "weak", "mismatch")

        # 2. Reviewer flags a citation mismatch and feeds it back
        flag_resp = client.patch(
            f"/api/claims/{first_claim['id']}?handover_id=payflow-handover-001",
            headers=_auth_header(rev_token),
            json={
                "flag_citation_mismatch": True,
                "citation_support_override": "mismatch",
                "reviewer_notes": "Flagged citation mismatch during Round 3 verification test.",
            },
        )
        assert flag_resp.status_code == 200
        flagged_claim = flag_resp.json()
        assert flagged_claim["reviewerFlaggedMismatch"] is True
        assert flagged_claim["citationSupportStatus"] == "mismatch"
        assert "reviewer_flagged_citation_mismatch" in flagged_claim["uncertainty"]

        # 3. Repeatable Evaluation Harness endpoint & committed benchmark file check
        eval_resp = client.get("/api/v1/evaluation/payflow-benchmark")
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["baselineMetrics"]["citationMismatchDetectionRate"] == 0.0
        assert eval_data["postImprovementMetrics"]["citationMismatchDetectionRate"] == 1.0
        assert eval_data["postImprovementMetrics"]["unflaggedMismatchCount"] == 0
        assert (
            eval_data["postImprovementMetrics"]["extractionPrecision"]
            > eval_data["baselineMetrics"]["extractionPrecision"]
        )
        assert (
            eval_data["postImprovementMetrics"]["avgReviewTimeSecondsPerHandover"]
            < eval_data["baselineMetrics"]["avgReviewTimeSecondsPerHandover"]
        )

        committed_benchmark = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "benchmarks"
            / "round3_evaluation_results.json"
        )
        assert committed_benchmark.exists()


def test_round3_improvement_3_dependency_map_and_version_comparison() -> None:
    """
    Section 10.1 Improvement 3 Measurement:
    - All seeded dependencies (Finance Ops sandbox cert, Risk-Engine v1.4) appear with evidence;
    - No edge without source or explicit 'inferred' label;
    - Unknown owners remain unknown gaps;
    - Version diff test between draft (v1) and approved (v2) snapshots.
    """
    with TestClient(app) as client:
        lead_resp = client.post("/api/v1/demo/switch-role", json={"project_role": "PROJECT_LEAD"})
        lead_token = lead_resp.json()["access_token"]

        # Reset to clean v1 draft
        draft_v1_resp = client.post(
            "/api/v1/demo/bootstrap-payflow?reset=true",
            headers=_auth_header(lead_token),
        )
        assert draft_v1_resp.status_code == 200
        draft_v1 = draft_v1_resp.json()
        assert draft_v1["currentVersion"] == 1

        # 1. Verify Evidence-Backed Dependency Map
        dep_resp = client.get(
            "/api/handovers/payflow-handover-001/dependency-map",
            headers=_auth_header(lead_token),
        )
        assert dep_resp.status_code == 200
        dep_map = dep_resp.json()

        assert dep_map["summary"]["unlabeledEdgesCount"] == 0
        assert dep_map["summary"]["unknownOwnerGapsCount"] >= 1

        node_labels = " | ".join(n["label"] for n in dep_map["nodes"])
        assert "Finance Ops" in node_labels
        assert "Risk-Engine v1.4" in node_labels
        assert "UNKNOWN OWNER GAP" in node_labels

        # Every single edge must carry either source evidence or explicit 'inferred' supportStatus
        for edge in dep_map["edges"]:
            assert edge["supportStatus"] in ("source_supported", "inferred")
            if edge["supportStatus"] == "source_supported":
                assert len(edge["evidenceSourceIds"]) >= 1

        # 2. Answer a clarification question, verify a conflicting claim, and approve handover (creating v2 snapshot)
        open_q = draft_v1["openQuestions"][0]
        ans_resp = client.post(
            f"/api/handovers/payflow-handover-001/clarifications/{open_q['id']}",
            headers=_auth_header(lead_token),
            json={
                "answer_text": "Confirmed 3 exponential backoff retries (5s, 30s, 300s) with 7-day DLQ TTL.",
                "mark_resolved": True,
            },
        )
        assert ans_resp.status_code == 200

        conflicting_claim = next(
            (c for c in draft_v1["claims"] if c["status"] == "conflicting"),
            draft_v1["claims"][0],
        )
        patch_resp = client.patch(
            f"/api/claims/{conflicting_claim['id']}?handover_id=payflow-handover-001",
            headers=_auth_header(lead_token),
            json={
                "status": "verified",
                "review_state": "approved",
                "owner_name": "Ankit Chaudhari",
                "reviewer_notes": "Resolved conflict in favour of newer ISSUE-104 BLOCKED status.",
            },
        )
        assert patch_resp.status_code == 200

        approve_resp = client.post(
            "/api/handovers/payflow-handover-001/approve",
            headers=_auth_header(lead_token),
            json={"approval_notes": "Approved v2 snapshot after conflict resolution and clarification."},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["currentVersion"] == 2

        # 3. Compare v1 (Initial AI Draft) vs v2 (Approved Package)
        diff_resp = client.get(
            "/api/handovers/payflow-handover-001/versions/compare?base_version=1&target_version=2",
            headers=_auth_header(lead_token),
        )
        assert diff_resp.status_code == 200
        diff_data = diff_resp.json()
        assert diff_data["baseVersion"] == 1
        assert diff_data["targetVersion"] == 2
        assert diff_data["summaryMetrics"]["changedClaimsCount"] >= 1
        assert diff_data["summaryMetrics"]["statusChangesCount"] >= 1
        assert diff_data["summaryMetrics"]["rationaleEnrichedCount"] >= 1
        assert diff_data["summaryMetrics"]["ownerChangesCount"] >= 1
