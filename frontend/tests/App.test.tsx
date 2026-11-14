import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { EvidenceStatusBadge } from "../src/components/EvidenceStatusBadge";
import { apiClient, clearAuthTokens } from "../src/lib/apiClient";
import App from "../src/App";

const mockPayFlowDraft = {
  id: "handover-uuid-001",
  handoverId: "payflow-handover-001",
  projectId: "proj-payflow-001",
  title: "PayFlow v2.1 Payment Integration Handover",
  scopeDescription: "Transition package for payment orchestration and 3DS2 callbacks.",
  departingRole: "Senior Payment Integration Engineer (Arjun Mehta)",
  status: "ready_for_review",
  currentVersion: 1,
  project: {
    name: "PayFlow Payment Gateway & Settlement Service",
    dataClassification: "synthetic_demo",
    asOf: "2026-10-20T00:00:00Z",
  },
  summary: {
    executive_overview: "PayFlow handover package with 6 extracted claims and 1 open conflict.",
    safety_notice: "No claim is marked verified without human reviewer approval.",
  },
  claims: [
    {
      id: "claim-uuid-001",
      claimId: "claim-001",
      type: "blocked_work",
      text: "3DS2 timeout callback retry worker is blocked awaiting Finance Ops certificate.",
      rationale: "Blocked in ISSUE-104.",
      owner: null,
      taskStatus: "blocked",
      dueDate: null,
      status: "conflicting" as const,
      evidence: [
        {
          sourceId: "issue-104",
          sourceType: "synthetic_issue",
          location: "lines 1-4",
          excerpt: "Status: BLOCKED on Finance Ops certificate.",
          charStart: 0,
          charEnd: 42,
          versionTag: "v1",
          sourceUpdatedAt: "2026-10-18T10:00:00Z",
          deterministicVerified: true,
        },
      ],
      uncertainty: ["unassigned_owner"],
      conflicts: [
        {
          conflictType: "status_contradiction",
          sourceAId: "issue-104",
          sourceAExcerpt: "Status: BLOCKED",
          sourceATimestamp: "2026-10-18T10:00:00Z",
          sourceBId: "notes-2026-10-15",
          sourceBExcerpt: "3DS2 callback is done",
          sourceBTimestamp: "2026-10-15T10:00:00Z",
          explanation: "ISSUE-104 (newer) states BLOCKED whereas meeting note states done.",
        },
      ],
      reviewState: "pending" as const,
      extractionConfidence: 0.92,
      isAiGenerated: true,
      reviewerNotes: null,
      reviewedBy: null,
      reviewedAt: null,
    },
  ],
  risksAndDependencies: [
    {
      id: "risk-001",
      recordType: "blocker" as const,
      title: "3DS2 mTLS Certificate Pending",
      description: "Blocked on Finance Ops.",
      severity: "high" as const,
      sourceEntity: "PayFlow",
      targetEntity: "Finance Ops",
      workaround: "Use sandbox stub in staging.",
      owner: null,
      status: "conflicting" as const,
      evidenceSourceIds: ["issue-104"],
      evidenceClaimIds: ["claim-001"],
    },
  ],
  openQuestions: [
    {
      id: "q-001",
      relatedClaimId: "claim-001",
      question: "Who owns the 3DS2 callback retry worker after Arjun departs?",
      reason: "Owner is unassigned in ISSUE-104.",
      status: "open" as const,
      answerText: null,
      answeredBy: null,
      answeredAt: null,
    },
  ],
  nextActions: [],
  approval: {
    status: "not_approved" as const,
    reviewer: null,
    approvedAt: null,
  },
  agentTelemetry: {},
  scopedSources: [
    {
      id: "src-104",
      project_id: "proj-payflow-001",
      stable_source_id: "issue-104",
      source_type: "synthetic_issue",
      title: "ISSUE-104: 3DS2 Callback Timeout Handling",
      content_redacted: "Status: BLOCKED awaiting mTLS cert from Finance Ops.",
      access_level: "INTERNAL" as const,
      version_tag: "v1",
      author_handle: "arjun.mehta",
      redacted_secrets_count: 0,
      source_updated_at: "2026-10-18T10:00:00Z",
      chunk_count: 1,
    },
  ],
};

const mockSources = mockPayFlowDraft.scopedSources;

const mockApprovedPlan = {
  handoverId: "payflow-handover-001",
  title: "PayFlow v2.1 Payment Integration Handover",
  version: 2,
  accessScopeApplied: ["PUBLIC", "INTERNAL"],
  restrictedSourcesFilteredOut: 1,
  sections: {
    "1_project_overview": [
      {
        id: "c-ov-1",
        claimId: "claim-ov-001",
        text: "PayFlow orchestrates 3DS2 payment flows and settlement ledger batches.",
        status: "verified",
        owner: "Arjun Mehta",
        evidence: [{ sourceId: "issue-104" }],
      },
    ],
    "5_blocked_tasks": [
      {
        id: "c-blk-1",
        claimId: "claim-001",
        text: "3DS2 timeout callback retry worker is blocked awaiting Finance Ops certificate.",
        status: "verified",
        taskStatus: "blocked",
        owner: null,
        evidence: [{ sourceId: "issue-104" }],
      },
    ],
    "6_responsibilities": {
      departing_role: "Senior Payment Integration Engineer (Arjun Mehta)",
      transferred_claims: [
        {
          claimId: "claim-resp-01",
          text: "Primary on-call escalation for settlement batch reconciliation.",
          owner: "Ankit Chaudhari",
        },
      ],
      supporting_contacts: ["priya.nair (DevOps On-Call)"],
    },
    "8_risks_and_blockers": mockPayFlowDraft.risksAndDependencies,
    "11_prioritised_next_actions": [
      {
        id: "act-001",
        priorityRank: 1,
        priority: "high",
        action: "Escalate Finance Ops mTLS certificate provisioning",
        reason: "Unblocks ISSUE-104 retry worker deployment",
        owner: "Ankit Chaudhari",
      },
    ],
    "13_approval_information": {
      status: "approved",
      reviewer: "kavita.reviewer@payflow.demo",
      approvedAt: "2026-10-20T12:00:00Z",
      acknowledgedBy: null,
      acknowledgementNotes: null,
    },
  },
  claims: mockPayFlowDraft.claims,
  risksAndDependencies: mockPayFlowDraft.risksAndDependencies,
  openQuestions: mockPayFlowDraft.openQuestions,
  nextActions: [
    {
      id: "act-001",
      priorityRank: 1,
      priority: "high",
      action: "Follow up with Finance Ops on 3DS2 mTLS certificate",
      reason: "Critical blocker in ISSUE-104",
      owner: "Ankit Chaudhari",
      evidenceClaimIds: ["claim-001"],
    },
  ],
  approval: {
    status: "approved",
    reviewer: "kavita.reviewer@payflow.demo",
    approvedAt: "2026-10-20T12:00:00Z",
  },
};

describe("Knowledge Handover Role-Aware Frontend Suite", () => {
  beforeEach(() => {
    clearAuthTokens();
    vi.restoreAllMocks();
  });

  it("renders all 6 evidence status vocabulary badges with emerald/teal/amber/rose/zinc classes (no blue/purple/violet)", () => {
    const { container, rerender } = render(
      <EvidenceStatusBadge status="source_supported" isAiGenerated={true} />
    );
    expect(screen.getByText("Source-supported")).toBeDefined();
    expect(screen.getByText("AI-Generated Draft")).toBeDefined();
    expect(container.innerHTML).not.toMatch(/sky-|blue-|indigo-|purple-|violet-/);

    rerender(<EvidenceStatusBadge status="conflicting" isAiGenerated={true} />);
    expect(screen.getByText("Conflicting")).toBeDefined();

    rerender(<EvidenceStatusBadge status="potentially_outdated" isAiGenerated={true} />);
    expect(screen.getByText("Potentially outdated")).toBeDefined();

    rerender(<EvidenceStatusBadge status="inferred" isAiGenerated={true} />);
    expect(screen.getByText("Inferred")).toBeDefined();
    expect(container.innerHTML).not.toMatch(/sky-|blue-|indigo-|purple-|violet-/);

    rerender(<EvidenceStatusBadge status="verified" isAiGenerated={false} />);
    expect(screen.getByText("Verified (Human)")).toBeDefined();
    expect(screen.getByText("Human-Reviewed")).toBeDefined();
  });

  it("renders the Overview launchpad, Guest Demo read-only badge, and 4 authenticated role persona cards", () => {
    render(<App />);
    expect(screen.getByText(/Verifiable Engineering Handovers/i)).toBeDefined();
    expect(screen.getByText("GUEST_DEMO (Read-Only)")).toBeDefined();
    expect(screen.getByText("Try Instant PayFlow Demo (Read-Only)")).toBeDefined();
    expect(screen.getByText("Switch to Project Lead")).toBeDefined();
    expect(screen.getByText("Switch to Outgoing Dev")).toBeDefined();
    expect(screen.getByText("Switch to Reviewer / SME")).toBeDefined();
    expect(screen.getByText("Switch to Successor")).toBeDefined();
  });

  it("strictly restricts Guest Demo navigation to Overview, Dashboard, and Permitted Sources (no Review Workspace, Successor Plan, or Audit Trail)", async () => {
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
      data: mockPayFlowDraft,
    } as any);
    const getSpy = vi.spyOn(apiClient, "get").mockResolvedValueOnce({
      data: mockSources,
    } as any);

    render(<App />);
    fireEvent.click(screen.getByText("Try Instant PayFlow Demo (Read-Only)"));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/v1/demo/bootstrap-payflow");
      expect(getSpy).toHaveBeenCalledWith("/api/v1/projects/proj-payflow-001/sources");
      expect(
        screen.getByText("Guest Demo — Anonymous Read-Only Evaluator")
      ).toBeDefined();
    });

    // Unauthorized navigation tabs MUST NOT be displayed in Guest Demo mode
    expect(screen.queryByText("Review Workspace")).toBeNull();
    expect(screen.queryByText("Clarifications & Draft")).toBeNull();
    expect(screen.queryByText("Successor Plan")).toBeNull();
    expect(screen.queryByText("Audit Trail")).toBeNull();
    expect(screen.queryByText("Reset Demo Draft to v1")).toBeNull();

    // Navigate to Permitted Sources tab as Guest Demo: source upload form is hidden
    fireEvent.click(screen.getByText("Permitted Sources"));
    expect(screen.queryByText("Upload, Redact Secrets & Index Chunks")).toBeNull();
    expect(screen.getByText(/READ-ONLY SOURCE SCOPE · GUEST_DEMO/i)).toBeDefined();
  });

  it("enforces role-specific navigation for OUTGOING_DEV and REVIEWER_SME without exposing Successor Plan or Successor-only controls", async () => {
    const postSpy = vi.spyOn(apiClient, "post");
    const getSpy = vi.spyOn(apiClient, "get");

    // 1. Switch to OUTGOING_DEV
    postSpy
      .mockResolvedValueOnce({
        data: {
          access_token: "jwt-outgoing",
          refresh_token: "refresh-outgoing",
          user: {
            id: "user-outgoing-001",
            email: "arjun.outgoing@payflow.demo",
            full_name: "Arjun Mehta (Outgoing Engineer)",
            platform_role: "STANDARD",
            is_active: true,
            created_at: "2026-10-20T00:00:00Z",
            memberships: [
              {
                project_id: "proj-payflow-001",
                project_slug: "payflow",
                project_name: "PayFlow",
                project_role: "OUTGOING_DEV",
                allowed_classifications: ["PUBLIC", "INTERNAL"],
              },
            ],
          },
        },
      } as any)
      .mockResolvedValueOnce({
        data: mockPayFlowDraft,
      } as any);
    getSpy.mockResolvedValueOnce({ data: mockSources } as any);

    render(<App />);
    fireEvent.click(screen.getByText("Switch to Outgoing Dev"));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/v1/demo/switch-role", {
        project_role: "OUTGOING_DEV",
      });
      expect(
        screen.getByText("Outgoing Developer Clarification & Draft Annotation Studio")
      ).toBeDefined();
    });

    // OUTGOING_DEV can answer clarifications and flag claims, but CANNOT mark verified, approve, or see Successor Plan / Audit Trail
    expect(screen.getByText("Submit Answer")).toBeDefined();
    expect(screen.getByText("Flag Unresolved")).toBeDefined();
    expect(screen.queryByText("Mark Verified")).toBeNull();
    expect(
      screen.queryByText("Approve Handover Package & Unlock Successor View")
    ).toBeNull();
    expect(screen.queryByText("Successor Plan")).toBeNull();
    expect(screen.queryByText("Audit Trail")).toBeNull();

    // OUTGOING_DEV can access source upload form
    fireEvent.click(screen.getByText("Sources & Ingestion"));
    expect(screen.getByText("Upload, Redact Secrets & Index Chunks")).toBeDefined();

    // 2. Switch to REVIEWER_SME via the header Role Selector
    postSpy
      .mockResolvedValueOnce({
        data: {
          access_token: "jwt-reviewer",
          refresh_token: "refresh-reviewer",
          user: {
            id: "user-reviewer-001",
            email: "kavita.reviewer@payflow.demo",
            full_name: "Kavita Rao (Reviewer / SME)",
            platform_role: "STANDARD",
            is_active: true,
            created_at: "2026-10-20T00:00:00Z",
            memberships: [
              {
                project_id: "proj-payflow-001",
                project_slug: "payflow",
                project_name: "PayFlow",
                project_role: "REVIEWER_SME",
                allowed_classifications: ["PUBLIC", "INTERNAL"],
              },
            ],
          },
        },
      } as any)
      .mockResolvedValueOnce({
        data: mockPayFlowDraft,
      } as any);
    getSpy.mockResolvedValueOnce({ data: mockSources } as any);

    fireEvent.change(screen.getByLabelText("Active Role Identity"), {
      target: { value: "REVIEWER_SME" },
    });

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/v1/demo/switch-role", {
        project_role: "REVIEWER_SME",
      });
      expect(
        screen.getByText("Approve Handover Package & Unlock Successor View")
      ).toBeDefined();
    });

    // REVIEWER_SME sees Mark Verified, Approve button, and Audit Trail tab, but NOT Successor Plan or source upload
    expect(screen.getByText("Mark Verified")).toBeDefined();
    expect(screen.getByText("Audit Trail")).toBeDefined();
    expect(screen.queryByText("Successor Plan")).toBeNull();

    fireEvent.click(screen.getByText("Permitted Sources"));
    expect(screen.queryByText("Upload, Redact Secrets & Index Chunks")).toBeNull();
    expect(screen.getByText(/READ-ONLY SOURCE SCOPE · REVIEWER_SME/i)).toBeDefined();
  });

  it("shows Successor waiting-for-approval state when unapproved, and structured 13-section plan + Successor-only acknowledgement once approved", async () => {
    const postSpy = vi.spyOn(apiClient, "post");
    const getSpy = vi.spyOn(apiClient, "get");

    // 1. Switch to SUCCESSOR while handover status is 'ready_for_review' (unapproved)
    postSpy.mockResolvedValueOnce({
      data: {
        access_token: "jwt-successor",
        refresh_token: "refresh-successor",
        user: {
          id: "user-successor-001",
          email: "ankit.successor@payflow.demo",
          full_name: "Ankit Chaudhari (Incoming Successor)",
          platform_role: "STANDARD",
          is_active: true,
          created_at: "2026-10-20T00:00:00Z",
          memberships: [
            {
              project_id: "proj-payflow-001",
              project_slug: "payflow",
              project_name: "PayFlow",
              project_role: "SUCCESSOR",
              allowed_classifications: ["PUBLIC", "INTERNAL"],
            },
          ],
        },
      },
    } as any);

    getSpy
      .mockResolvedValueOnce({
        data: [{ id: "proj-payflow-001", slug: "payflow", name: "PayFlow" }],
      } as any)
      .mockResolvedValueOnce({
        data: mockSources,
      } as any)
      .mockResolvedValueOnce({
        data: {
          handoverId: "payflow-handover-001",
          status: "ready_for_review",
          currentVersion: 1,
          updatedAt: "2026-10-20T10:00:00Z",
        },
      } as any);

    render(<App />);
    fireEvent.click(screen.getByText("Switch to Successor"));

    await waitFor(() => {
      expect(
        screen.getByText("Successor Continuation Plan Is Locked Pending Human Sign-Off")
      ).toBeDefined();
      expect(screen.getByText("WAITING FOR HUMAN APPROVAL GATE")).toBeDefined();
    });

    // Review Workspace and Audit Trail tabs are hidden for SUCCESSOR
    expect(screen.queryByText("Review Workspace")).toBeNull();
    expect(screen.queryByText("Audit Trail")).toBeNull();

    // 2. Refresh after handover is approved -> renders structured 13-section cards (not raw JSON) and Acknowledge button
    getSpy
      .mockResolvedValueOnce({
        data: {
          handoverId: "payflow-handover-001",
          status: "approved",
          currentVersion: 2,
          updatedAt: "2026-10-20T12:00:00Z",
        },
      } as any)
      .mockResolvedValueOnce({
        data: mockApprovedPlan,
      } as any);

    fireEvent.click(screen.getByText("Refresh Approval Status"));

    await waitFor(() => {
      expect(screen.getByText(/APPROVED CONTINUATION PLAN · v2/i)).toBeDefined();
      expect(
        screen.getByText(/Follow up with Finance Ops on 3DS2 mTLS certificate/i)
      ).toBeDefined();
      expect(
        screen.getByText("06 · Ownership Transfer & On-Call Responsibilities")
      ).toBeDefined();
      expect(
        screen.getByText("priya.nair (DevOps On-Call)")
      ).toBeDefined();
      expect(screen.getByText("Acknowledge Handover Receipt")).toBeDefined();
    });
  });
});
