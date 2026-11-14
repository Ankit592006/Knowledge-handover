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
    text: "PayFlow handover package with 6 extracted claims and 1 open conflict.",
    reviewState: "pending",
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
      access_level: "INTERNAL",
      version_tag: "v1",
      author_handle: "arjun.mehta",
      redacted_secrets_count: 0,
      source_updated_at: "2026-10-18T10:00:00Z",
      chunk_count: 1,
    },
  ],
};

describe("Knowledge Handover Frontend Suite", () => {
  beforeEach(() => {
    clearAuthTokens();
    vi.restoreAllMocks();
  });

  it("renders all 6 evidence status vocabulary badges accurately", () => {
    const { rerender } = render(
      <EvidenceStatusBadge status="source_supported" isAiGenerated={true} />
    );
    expect(screen.getByText("Source-supported")).toBeDefined();
    expect(screen.getByText("AI-Generated Draft")).toBeDefined();

    rerender(<EvidenceStatusBadge status="conflicting" isAiGenerated={true} />);
    expect(screen.getByText("Conflicting")).toBeDefined();

    rerender(<EvidenceStatusBadge status="potentially_outdated" isAiGenerated={true} />);
    expect(screen.getByText("Potentially outdated")).toBeDefined();

    rerender(<EvidenceStatusBadge status="verified" isAiGenerated={false} />);
    expect(screen.getByText("Verified (Human)")).toBeDefined();
    expect(screen.getByText("Human-Reviewed")).toBeDefined();
  });

  it("renders the main landing workflow overview, Guest Demo read-only badge, and instant demo button", () => {
    render(<App />);
    expect(
      screen.getByText(/Prevent Critical Project Knowledge From Leaving With People/i)
    ).toBeDefined();
    expect(screen.getByText("01 CONNECT")).toBeDefined();
    expect(screen.getByText("02 RECONSTRUCT")).toBeDefined();
    expect(screen.getByText("03 CLARIFY")).toBeDefined();
    expect(screen.getByText("04 VERIFY & REVIEW")).toBeDefined();
    expect(screen.getByText("05 HANDOVER")).toBeDefined();

    // Unauthenticated guest sees GUEST_DEMO badge, Login / Register button, and Instant Demo button
    expect(screen.getByTestId("guest-demo-badge").textContent).toContain("GUEST_DEMO (Read-Only)");
    expect(screen.getByText("Try Instant PayFlow Demo (Read-Only)")).toBeDefined();
    expect(screen.getByText("Login / Register")).toBeDefined();
    // Role Perspective Switcher is NOT shown to unauthenticated guests
    expect(screen.queryByLabelText("Role Perspective Switcher")).toBeNull();
  });

  it("allows unauthenticated Guest Demo entry, navigation across Review/Sources/Dashboard, and enforces read-only restrictions", async () => {
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
      data: mockPayFlowDraft,
    } as any);
    const getSpy = vi.spyOn(apiClient, "get").mockRejectedValueOnce({
      response: {
        status: 403,
        data: {
          detail: "Successor view is locked until human Reviewer approves the handover package.",
        },
      },
    });

    render(<App />);

    // Click Try Instant PayFlow Demo (Read-Only) on landing page
    fireEvent.click(screen.getByText("Try Instant PayFlow Demo (Read-Only)"));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/v1/demo/bootstrap-payflow");
      expect(screen.getByText("PayFlow v2.1 Payment Integration Handover")).toBeDefined();
    });

    // In Review Workspace as Guest Demo:
    // Read-only banner is shown; write/review actions are hidden
    expect(
      screen.getByText(/Read-Only Guest Demo — Sign in to verify claims & approve package/i)
    ).toBeDefined();
    expect(
      screen.queryByText("Approve Handover Package & Unlock Successor View")
    ).toBeNull();
    expect(screen.queryByText("Mark Verified")).toBeNull();
    expect(screen.queryByText("Flag Unresolved")).toBeNull();
    expect(screen.queryByText("Reject Claim")).toBeNull();
    expect(screen.queryByText("Submit Answer")).toBeNull();
    expect(
      screen.getByText(/Read-only in Guest Demo mode\. Sign in as Outgoing Developer/i)
    ).toBeDefined();

    // Navigate to Sources & Redaction tab as Guest Demo
    fireEvent.click(screen.getByText(/Sources & Redaction/i));
    expect(
      screen.getByText("ISSUE-104: 3DS2 Callback Timeout Handling")
    ).toBeDefined();
    // Custom source upload form is hidden for Guest Demo
    expect(screen.queryByText("Ingest Source & Re-Run Reconstruction")).toBeNull();
    expect(
      screen.getByText(/Read-Only Guest Demo Scope \(PUBLIC & INTERNAL\):/i)
    ).toBeDefined();

    // Navigate to Dashboard tab as Guest Demo
    fireEvent.click(screen.getByText("Dashboard"));
    expect(screen.getByText(/Welcome, Engineer \(GUEST_DEMO\)/i)).toBeDefined();
    expect(screen.getByText("payflow-handover-001")).toBeDefined();

    // Clicking Successor Plan when unapproved displays clear sign-in / approval message
    fireEvent.click(screen.getByText("Successor Plan"));
    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith("/api/handovers/payflow-handover-001/successor-view");
      expect(
        screen.getByText(
          /Sign in as a Reviewer or Project Lead to verify claims and approve the handover package/i
        )
      ).toBeDefined();
    });
  });

  it("unlocks full review, upload, clarification, and approval controls after authenticated login", async () => {
    vi.spyOn(apiClient, "post")
      .mockResolvedValueOnce({
        data: {
          access_token: "jwt-access-token",
          refresh_token: "jwt-refresh-token",
          user: {
            id: "user-lead-001",
            email: "preeti.lead@payflow.demo",
            full_name: "Preeti Satish Mittal",
            platform_role: "STANDARD",
            is_active: true,
            created_at: "2026-10-20T00:00:00Z",
            memberships: [
              {
                project_id: "proj-payflow-001",
                project_slug: "payflow",
                project_name: "PayFlow",
                project_role: "PROJECT_LEAD",
                allowed_classifications: ["PUBLIC", "INTERNAL", "RESTRICTED"],
              },
            ],
          },
        },
      } as any)
      .mockResolvedValueOnce({
        data: mockPayFlowDraft,
      } as any);

    render(<App />);

    // Navigate to Login / Register tab and submit registration/login
    fireEvent.click(screen.getByText("Login / Register"));
    fireEvent.click(screen.getByText("Register & Continue"));

    await waitFor(() => {
      expect(
        screen.getByText(/Welcome, Preeti Satish Mittal \(PROJECT_LEAD\)/i)
      ).toBeDefined();
    });

    // Guest Demo badge is gone; Role Perspective Switcher is visible
    expect(screen.queryByTestId("guest-demo-badge")).toBeNull();
    expect(screen.getByLabelText("Role Perspective Switcher")).toBeDefined();

    // Bootstrap PayFlow from Dashboard as authenticated Project Lead
    fireEvent.click(
      screen.getByText("Seed PayFlow Dataset & Run 3-Agent Reconstruction")
    );

    await waitFor(() => {
      expect(
        screen.getByText("Approve Handover Package & Unlock Successor View")
      ).toBeDefined();
    });

    // Authenticated Project Lead sees claim verification and clarification controls
    expect(screen.getByText("Mark Verified")).toBeDefined();
    expect(screen.getByText("Flag Unresolved")).toBeDefined();
    expect(screen.getByText("Reject Claim")).toBeDefined();
    expect(screen.getByText("Submit Answer")).toBeDefined();

    // Authenticated Project Lead sees custom source upload form on Sources tab
    fireEvent.click(screen.getByText(/Sources & Redaction/i));
    expect(screen.getByText("Ingest Source & Re-Run Reconstruction")).toBeDefined();
  });
});

