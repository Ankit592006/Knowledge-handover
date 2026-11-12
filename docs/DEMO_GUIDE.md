# Judge Demonstration Guide — Knowledge Handover Platform

## 1. 3-Minute End-to-End Judge Walkthrough

1. **Start the Platform**:
   - Run `docker compose up --build` (or start `uvicorn app.main:app --port 8000` in `backend/` and `npm run dev` in `frontend/`).
   - Open `http://localhost:5173`.
2. **Register / Sign In**:
   - Click **Get Started — Login / Register** and click **Register & Continue** (pre-filled with `preeti.lead@payflow.demo`).
3. **One-Click PayFlow Seeding & 3-Agent Reconstruction**:
   - On the Dashboard, click **Seed PayFlow Dataset & Run 3-Agent Reconstruction**.
   - This seeds the 9 synthetic PayFlow artefacts, redacts pasted credentials in `restricted-vendor-note`, excludes `RESTRICTED` records from the `PUBLIC/INTERNAL` handover scope, and runs the LangGraph 3-Agent pipeline.
4. **Inspect Conflicts, Stale Docs & Unknown Owners in the Review Workspace**:
   - Locate `claim-004` (*Payment timeout handling on 3DS2 callback remains blocked*). Observe:
     - Status badge: **`Conflicting`** (`AI-Generated Draft`).
     - Owner: **`UNKNOWN (Unassigned in evidence)`** — never invented!
     - Click **Inspect Citations & Conflicts** to view `issue-104` (`BLOCKED`, 2026-11-06) side-by-side with `notes-2026-10-15` (`IN PROGRESS`, 2026-10-15).
   - Locate `claim-005` (*Checkout payment creation uses POST /v2/payment-intents*). Observe status **`Potentially outdated`** flagging `doc-legacy-api` (`/v1/payments/charge`) against `pr-218`.
5. **Answer Clarification Question (Outgoing Developer)**:
   - Scroll to **Outgoing Developer Clarification Loop**, enter a retry policy answer for ADR-001, and click **Submit Answer**.
6. **Verify Claims & Approve Package (Reviewer / Project Lead)**:
   - Click **Mark Verified** on `claim-004`, then click **Approve Handover Package & Unlock Successor View**.
7. **Successor Continuation Plan & Receipt Acknowledgement**:
   - Switch the top-right **Perspective** dropdown to **Successor (Incoming Dev)**.
   - Inspect the **Prioritised Next Actions**, verify that `1 Restricted Source Excluded` is enforced, and click **Acknowledge Handover Receipt**.
8. **Verify Append-Only Audit Trail**:
   - Click **Audit Trail** in the top navigation bar to inspect every recorded action and state transition.
