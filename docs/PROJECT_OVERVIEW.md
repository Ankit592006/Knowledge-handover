# Project Overview — Knowledge Handover Platform

## 1. Problem Statement
When a developer leaves a software project, changes roles, or becomes unavailable, critical project context disappears. Explicit artefacts (issues, pull requests, ADRs, meeting notes, technical docs) are scattered and frequently disagree or age, while tacit rationale and ownership gaps remain hidden.

## 2. Solution Explanation
Knowledge Handover reconstructs a structured, evidence-linked, human-reviewed handover package from authorised project records following the **Connect → Reconstruct → Clarify → Verify → Review/Approve → Handover/Continue** workflow.

## 3. Target Personas
1. **Project Lead (`PROJECT_LEAD`)**: Scopes handovers, assigns roles/clearances, reviews blockers, and approves packages.
2. **Outgoing Developer (`OUTGOING_DEV`)**: Connects sources, reviews extracted draft claims, and answers targeted clarification questions.
3. **Reviewer / SME (`REVIEWER_SME`)**: Inspects source excerpts and conflicts side-by-side, edits/rejects claims, marks claims `verified`, and approves the final handover.
4. **Incoming Developer / Successor (`SUCCESSOR`)**: Views only approved, permission-filtered 13-section Continuation Plans and acknowledges receipt.
5. **Platform Administrator (`ADMIN`)**: Manages platform accounts and seeds synthetic demo workspaces.
