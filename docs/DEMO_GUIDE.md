# Judge Demonstration Guide — Knowledge Handover Platform (Continuity OS v2.1)

## 3-Minute End-to-End Live Walkthrough

1. **Open the Live Platform (or Start Locally)**:
   - **Live Cloud URL**: `https://kh-frontend.onrender.com` (Backend API: `https://kh-backend-z2o3.onrender.com/docs`)
   - **Local**: Run `uvicorn app.main:app --reload --port 8000` in `backend/` and `npm run dev` in `frontend/`, then open `http://localhost:5173`.
2. **Explore Anonymous Read-Only Guest Demo (`GUEST_DEMO`)**:
   - On the **Overview** launchpad, click **Try Instant PayFlow Demo (Read-Only)**.
   - Notice that navigation is strictly limited to `Overview`, `Dashboard`, and `Permitted Sources` (7 sources — `restricted-vendor-note` is filtered out).
3. **Switch to Outgoing Developer (`OUTGOING_DEV` — Arjun Mehta)**:
   - Use the top **Active Role Identity** selector (or click **Login / Register** to open the centered Auth Modal) and select **OUTGOING_DEV — Arjun**.
   - Navigate to **Clarifications & Draft**: answer an open AI-generated clarification question (e.g., ADR-001 webhook retry backoff policy) and click **Submit Answer**. Observe that the linked claim rationale is immediately enriched.
   - Notice that Arjun can flag claims (`Flag Unresolved`), but **Mark Verified** and **Approve Handover Package** buttons are hidden and blocked (`403`) for `OUTGOING_DEV`.
4. **Switch to Reviewer / SME (`REVIEWER_SME` — Kavita Rao)**:
   - Switch **Active Role Identity** to **REVIEWER_SME — Kavita**.
   - In **Review Workspace**, click **Inspect Evidence & Conflicts** on `claim-004` (`issue-104` vs `notes-2026-10-15`) to view verbatim source excerpts and conflicting timestamps side-by-side in the **Evidence Inspector Modal**.
   - Click **Mark Verified** on the reviewed claims, then click **Approve Handover Package & Unlock Successor View**. This freezes an immutable `v2` snapshot.
5. **Switch to Incoming Successor (`SUCCESSOR` — Ankit Chaudhari)**:
   - Switch **Active Role Identity** to **SUCCESSOR — Ankit**.
   - In **Successor Plan**, inspect the unlocked **13-Section Continuation Plan** rendered as book-professional cards (including *06 · Ownership Transfer*, *08 · Risks & Blockers*, and *11 · Prioritised Next Actions*).
   - Click **Export Markdown** or **Export JSON**, then click **Acknowledge Handover Receipt** (exclusively available to `SUCCESSOR`). Notice the 5-step Lifecycle Progress Bar advances to **05 Successor Receipt (Completed)**.
6. **Switch to Project Lead (`PROJECT_LEAD` — Preeti Mittal) & Inspect Audit Trail / Reset Demo**:
   - Switch to **PROJECT_LEAD — Preeti**, open **Sources & Ingestion** to see all **8 sources** (including `RESTRICTED` `restricted-vendor-note` with `3 Secrets Redacted`), and open **Audit Trail** to inspect every recorded action.
   - Click **Reset v1** in the top bar (`POST /api/v1/demo/bootstrap-payflow?reset=true`) to reset the demo back to an unapproved `v1` draft for the next evaluator!
