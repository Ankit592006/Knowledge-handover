import React, { useEffect, useMemo, useState } from "react";
import { EvidenceInspectorModal } from "../components/EvidenceInspectorModal";
import { EvidenceStatusBadge } from "../components/EvidenceStatusBadge";
import { useAuth } from "../hooks/useAuth";
import { apiClient } from "../lib/apiClient";
import {
  AccessClassification,
  AuditLogItem,
  ClaimItem,
  EvidenceStatus,
  HandoverDraft,
  ProjectRole,
  SourceDocumentItem,
  SuccessorContinuationPlan,
} from "../lib/types";

type ActiveTab =
  | "landing"
  | "dashboard"
  | "sources"
  | "review"
  | "successor"
  | "audit";

interface HandoverLiveStatus {
  handoverId: string;
  status: string;
  currentVersion: number;
  agentTelemetry?: Record<string, unknown>;
  updatedAt: string;
}

interface RoleMetadata {
  role: ProjectRole;
  title: string;
  shortLabel: string;
  personaName: string;
  personaEmail: string;
  clearanceSummary: string;
  tagline: string;
  responsibilities: string[];
  restrictedNote: string;
}

const ROLE_METADATA: Record<ProjectRole, RoleMetadata> = {
  PROJECT_LEAD: {
    role: "PROJECT_LEAD",
    title: "Project Lead — Governance & Continuity Command",
    shortLabel: "Project Lead",
    personaName: "Preeti Satish Mittal",
    personaEmail: "preeti.lead@payflow.demo",
    clearanceSummary: "PUBLIC · INTERNAL · RESTRICTED",
    tagline:
      "Full lifecycle governance: configure scope, inspect restricted records, verify claims, approve the handover package, and audit every action.",
    responsibilities: [
      "Upload & inspect all project sources (including RESTRICTED clearance records)",
      "Trigger 3-Agent LangGraph reconstruction and monitor pipeline telemetry",
      "Verify claims, resolve source conflicts, and approve the handover package",
      "Inspect the append-only Audit Trail across all roles and state transitions",
    ],
    restrictedNote:
      "Full clearance including RESTRICTED vendor notes (cannot acknowledge receipt on behalf of Successor).",
  },
  OUTGOING_DEV: {
    role: "OUTGOING_DEV",
    title: "Outgoing Engineer — Source Ingestion & Tacit Context Studio",
    shortLabel: "Outgoing Dev",
    personaName: "Arjun Mehta",
    personaEmail: "arjun.outgoing@payflow.demo",
    clearanceSummary: "PUBLIC · INTERNAL",
    tagline:
      "Contribute engineering artefacts, run AI reconstruction, and answer open clarification questions before transitioning off the project.",
    responsibilities: [
      "Upload issues, PRs, architecture notes, and technical docs (auto-redacted for secrets)",
      "Trigger 3-Agent LangGraph reconstruction to draft evidence-linked claims",
      "Answer open clarification questions to resolve missing operational parameters",
      "Flag unresolved or inaccurate draft claims for Reviewer / SME attention",
    ],
    restrictedNote:
      "Cannot mark claims Verified, cannot approve the handover package, and cannot access Successor Plan or Audit Logs.",
  },
  REVIEWER_SME: {
    role: "REVIEWER_SME",
    title: "Reviewer / SME — Evidence Verification & Approval Gate",
    shortLabel: "Reviewer / SME",
    personaName: "Kavita Rao",
    personaEmail: "kavita.reviewer@payflow.demo",
    clearanceSummary: "PUBLIC · INTERNAL",
    tagline:
      "Audit AI-extracted claims against deterministic source citations, adjudicate contradicting records, and approve the package for the successor.",
    responsibilities: [
      "Inspect side-by-side contradictions (e.g. ISSUE-104 vs Oct 15 meeting note) and stale docs",
      "Mark accurate claims as Verified (Human-Reviewed) or reject unsupported claims",
      "Approve the handover package to create a versioned snapshot and unlock the Successor View",
      "Inspect the immutable Audit Trail for compliance verification",
    ],
    restrictedNote:
      "Read-only source access (cannot upload new sources, access Successor-only controls, or acknowledge receipt).",
  },
  SUCCESSOR: {
    role: "SUCCESSOR",
    title: "Incoming Successor — Onboarding & Continuation Hub",
    shortLabel: "Successor",
    personaName: "Ankit Chaudhari",
    personaEmail: "ankit.successor@payflow.demo",
    clearanceSummary: "PUBLIC · INTERNAL",
    tagline:
      "Protected from unverified AI drafts until human approval. Once approved, review the 13-section continuation plan and acknowledge receipt.",
    responsibilities: [
      "Wait for Reviewer / Project Lead approval before accessing reconstructed handover claims",
      "Browse permitted PUBLIC and INTERNAL source documents while review is in progress",
      "Study the approved 13-Section Continuation Plan, prioritised next actions, and blockers",
      "Export the handover package (Markdown / JSON) and formally acknowledge receipt",
    ],
    restrictedNote:
      "Strictly blocked (HTTP 403) from unapproved AI drafts, Review Workspace, RESTRICTED sources, and Audit Logs.",
  },
  GUEST_DEMO: {
    role: "GUEST_DEMO",
    title: "Guest Demo — Anonymous Read-Only Evaluator",
    shortLabel: "Guest Demo (Read-Only)",
    personaName: "Anonymous Evaluator",
    personaEmail: "guest.demo@payflow.demo",
    clearanceSummary: "PUBLIC · INTERNAL (Read-Only)",
    tagline:
      "Zero-setup read-only evaluation mode scoped strictly to synthetic PayFlow PUBLIC & INTERNAL overview and sources. Switch to an authenticated role above to access Review, Approval, or Successor workflows.",
    responsibilities: [
      "Inspect the synthetic PayFlow executive dashboard, blockers, and permitted sources",
      "Verify that RESTRICTED sources and secret tokens are excluded from read-only guest scope",
      "Switch to Project Lead, Outgoing Dev, Reviewer/SME, or Successor for live interactive workflows",
    ],
    restrictedNote:
      "Anonymous read-only mode: Review Workspace, Successor Plan, Audit Trail, and all write actions are restricted.",
  },
};

const SECTION_META: Record<
  string,
  { title: string; subtitle: string }
> = {
  "1_project_overview": {
    title: "01 · Project Overview & Architecture Context",
    subtitle: "High-level service boundary, core mission, and architecture baseline.",
  },
  "2_technical_context": {
    title: "02 · Technical Context & API Surface",
    subtitle: "Runtime stack, endpoints, schema conventions, and staleness flags.",
  },
  "3_key_decisions": {
    title: "03 · Key Architectural Decisions & Rationale",
    subtitle: "Design choices, idempotency guarantees, and ADR provenance.",
  },
  "4_completed_and_active_tasks": {
    title: "04 · Completed & Active Engineering Work",
    subtitle: "Delivered milestones and in-flight engineering tasks.",
  },
  "5_blocked_tasks": {
    title: "05 · Blocked Tasks & External Bottlenecks",
    subtitle: "Work items halted on external dependencies or contradicting status records.",
  },
  "6_responsibilities": {
    title: "06 · Ownership Transfer & On-Call Responsibilities",
    subtitle: "Departing engineer role, transferred operational duties, and escalation contacts.",
  },
  "7_dependencies": {
    title: "07 · External & Cross-Team Dependencies",
    subtitle: "Upstream/downstream services, certificates, and partner team dependencies.",
  },
  "8_risks_and_blockers": {
    title: "08 · Operational Risks & Critical Blockers",
    subtitle: "High-severity delivery risks, mitigations, and active workarounds.",
  },
  "9_operational_information": {
    title: "09 · Runbooks, Alerts & Operational Context",
    subtitle: "Retry policies, dead-letter queue parameters, and production operational notes.",
  },
  "10_unresolved_questions": {
    title: "10 · Clarification Q&A & Knowledge Transfer Log",
    subtitle: "Questions raised during AI grounding and authoritative answers from the team.",
  },
  "11_prioritised_next_actions": {
    title: "11 · Prioritised Next Actions for Incoming Successor",
    subtitle: "Ordered execution checklist for the incoming engineer's first sprint.",
  },
  "12_evidence_references": {
    title: "12 · Validated Source Provenance Index",
    subtitle: "Deterministically verified source documents, offsets, and excerpts backing this plan.",
  },
  "13_approval_information": {
    title: "13 · Human Approval & Successor Receipt Record",
    subtitle: "Formal reviewer sign-off metadata and successor acknowledgement status.",
  },
};

export const PlatformWorkspace: React.FC = () => {
  const {
    user,
    effectiveRole,
    allowedClassifications,
    isAuthenticated,
    login,
    register,
    switchDemoRole,
    refreshProfile,
  } = useAuth();

  const [activeTab, setActiveTab] = useState<ActiveTab>("landing");
  const [draft, setDraft] = useState<HandoverDraft | null>(null);
  const [handoverStatus, setHandoverStatus] = useState<HandoverLiveStatus | null>(null);
  const [sources, setSources] = useState<SourceDocumentItem[]>([]);
  const [payflowProjectId, setPayflowProjectId] = useState<string | null>(null);
  const [continuationPlan, setContinuationPlan] = useState<SuccessorContinuationPlan | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [exportedMarkdown, setExportedMarkdown] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  // Auth form state
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState<string>("preeti.lead@payflow.demo");
  const [authPassword, setAuthPassword] = useState<string>("PayFlow_Demo_Role_Password_#2026!");
  const [authName, setAuthName] = useState<string>("Preeti Satish Mittal");

  // Upload source form state
  const [newSourceId, setNewSourceId] = useState<string>("note-handover-addendum");
  const [newSourceTitle, setNewSourceTitle] = useState<string>(
    "Outgoing Engineer Addendum — Webhook DLQ Tuning"
  );
  const [newSourceType, setNewSourceType] = useState<string>("technical_doc");
  const [newSourceAccess, setNewSourceAccess] = useState<AccessClassification>("INTERNAL");
  const [newSourceContent, setNewSourceContent] = useState<string>(
    "Webhook retry worker should use 3 exponential backoff attempts (5s, 30s, 300s). Temporary token sk_live_SYNTHETIC999888777666 must never be logged."
  );

  // Clarification answers & reviewer notes
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [claimNotes, setClaimNotes] = useState<Record<string, string>>({});
  const [approvalNotes, setApprovalNotes] = useState<string>(
    "All claims verified against deterministic source citations; contradictions documented for successor."
  );
  const [ackNotes, setAckNotes] = useState<string>(
    "Reviewed the 13-section continuation plan, blocked tasks, and prioritised next actions. Ready to assume ownership."
  );

  // Evidence Inspector Modal
  const [inspectedClaim, setInspectedClaim] = useState<ClaimItem | null>(null);

  const formatApiError = (err: any, fallback: string): string => {
    const detail = err?.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      return detail.map((d: any) => d?.msg || JSON.stringify(d)).join("; ");
    }
    if (detail && typeof detail === "object") {
      return (detail as any).message || JSON.stringify(detail);
    }
    if (typeof err?.message === "string" && err.message.trim()) return err.message;
    return fallback;
  };

  // Role-based capability flags (strictly aligned with backend RBAC enforcement)
  const isReadOnlyGuest = !isAuthenticated || effectiveRole === "GUEST_DEMO";
  const canUploadSource =
    isAuthenticated && (effectiveRole === "PROJECT_LEAD" || effectiveRole === "OUTGOING_DEV");
  const canRunReconstruct =
    isAuthenticated &&
    (effectiveRole === "PROJECT_LEAD" ||
      effectiveRole === "OUTGOING_DEV" ||
      effectiveRole === "REVIEWER_SME");
  const canAccessReviewWorkspace =
    isAuthenticated &&
    (effectiveRole === "PROJECT_LEAD" ||
      effectiveRole === "OUTGOING_DEV" ||
      effectiveRole === "REVIEWER_SME");
  const canEditOrFlagClaims =
    isAuthenticated &&
    (effectiveRole === "PROJECT_LEAD" ||
      effectiveRole === "OUTGOING_DEV" ||
      effectiveRole === "REVIEWER_SME");
  const canVerifyClaims =
    isAuthenticated && (effectiveRole === "PROJECT_LEAD" || effectiveRole === "REVIEWER_SME");
  const canAnswerClarifications =
    isAuthenticated &&
    (effectiveRole === "PROJECT_LEAD" ||
      effectiveRole === "OUTGOING_DEV" ||
      effectiveRole === "REVIEWER_SME");
  const canApproveHandover =
    isAuthenticated && (effectiveRole === "PROJECT_LEAD" || effectiveRole === "REVIEWER_SME");
  const canViewSuccessorPlan =
    isAuthenticated && (effectiveRole === "SUCCESSOR" || effectiveRole === "PROJECT_LEAD");
  // Strictly only SUCCESSOR can acknowledge receipt of the handover package
  const canAcknowledgeHandover = isAuthenticated && effectiveRole === "SUCCESSOR";
  const canViewAuditLogs =
    isAuthenticated && (effectiveRole === "PROJECT_LEAD" || effectiveRole === "REVIEWER_SME");

  const currentApprovalStatus =
    continuationPlan?.approval?.status ||
    draft?.approval?.status ||
    (handoverStatus?.status === "approved" || handoverStatus?.status === "acknowledged"
      ? handoverStatus.status
      : "not_approved");

  const isHandoverApproved =
    currentApprovalStatus === "approved" ||
    currentApprovalStatus === "acknowledged" ||
    handoverStatus?.status === "approved" ||
    handoverStatus?.status === "acknowledged";

  const unansweredQuestionsCount =
    draft?.openQuestions.filter((q) => q.status !== "answered").length ?? 0;

  // Role-aware visible navigation tabs (strictly hides unauthorized tabs per role)
  const visibleTabs = useMemo(() => {
    const tabs: { id: ActiveTab; label: string; badge?: string }[] = [
      { id: "landing", label: "Overview" },
      {
        id: "dashboard",
        label:
          effectiveRole === "PROJECT_LEAD"
            ? "Lead Command"
            : effectiveRole === "OUTGOING_DEV"
            ? "Outgoing Studio"
            : effectiveRole === "REVIEWER_SME"
            ? "Reviewer Console"
            : effectiveRole === "SUCCESSOR"
            ? "Onboarding Hub"
            : "Dashboard",
      },
      {
        id: "sources",
        label: canUploadSource ? "Sources & Ingestion" : "Permitted Sources",
        badge: sources.length > 0 ? String(sources.length) : undefined,
      },
    ];

    // Review Workspace is strictly restricted to authenticated PROJECT_LEAD, OUTGOING_DEV, and REVIEWER_SME
    if (canAccessReviewWorkspace) {
      tabs.push({
        id: "review",
        label:
          effectiveRole === "OUTGOING_DEV"
            ? "Clarifications & Draft"
            : "Review Workspace",
        badge:
          effectiveRole === "OUTGOING_DEV" && unansweredQuestionsCount > 0
            ? `${unansweredQuestionsCount} Open`
            : draft?.claims.length
            ? String(draft.claims.length)
            : undefined,
      });
    }

    // Successor Plan tab is strictly restricted to SUCCESSOR and PROJECT_LEAD
    if (canViewSuccessorPlan) {
      tabs.push({
        id: "successor",
        label: "Successor Plan",
        badge: isHandoverApproved ? "Unlocked" : "Gated",
      });
    }

    // Audit Trail tab is strictly restricted to PROJECT_LEAD and REVIEWER_SME
    if (canViewAuditLogs) {
      tabs.push({
        id: "audit",
        label: "Audit Trail",
      });
    }

    return tabs;
  }, [
    effectiveRole,
    canUploadSource,
    canAccessReviewWorkspace,
    canViewSuccessorPlan,
    canViewAuditLogs,
    sources.length,
    unansweredQuestionsCount,
    draft?.claims.length,
    isHandoverApproved,
  ]);

  // Keep activeTab valid when switching roles
  useEffect(() => {
    const allowedIds = new Set(visibleTabs.map((t) => t.id));
    if (!allowedIds.has(activeTab)) {
      if (effectiveRole === "SUCCESSOR") {
        setActiveTab("successor");
      } else {
        setActiveTab("dashboard");
      }
    }
  }, [effectiveRole, visibleTabs, activeTab]);

  // Load workspace data cleanly for any role (including SUCCESSOR when handover is not yet approved)
  const syncWorkspaceForRole = async (
    targetRole: ProjectRole,
    options?: { forceReset?: boolean; targetTab?: ActiveTab }
  ) => {
    try {
      setLoading(true);
      setErrorMsg(null);

      if (targetRole === "SUCCESSOR") {
        const projResp = await apiClient.get("/api/v1/projects");
        const payflowProj =
          projResp.data.find((p: { slug: string; id: string }) => p.slug === "payflow") ||
          projResp.data[0];

        if (payflowProj) {
          setPayflowProjectId(payflowProj.id);
          const srcResp = await apiClient.get<SourceDocumentItem[]>(
            `/api/v1/projects/${payflowProj.id}/sources`
          );
          setSources(srcResp.data);
        }

        const statusResp = await apiClient.get<HandoverLiveStatus>(
          "/api/handovers/payflow-handover-001/status"
        );
        setHandoverStatus(statusResp.data);

        if (
          statusResp.data.status === "approved" ||
          statusResp.data.status === "acknowledged"
        ) {
          const [planResp, draftResp] = await Promise.all([
            apiClient.get<SuccessorContinuationPlan>(
              "/api/handovers/payflow-handover-001/successor-view"
            ),
            apiClient.get<HandoverDraft>("/api/handovers/payflow-handover-001/draft"),
          ]);
          setContinuationPlan(planResp.data);
          setDraft(draftResp.data);
          setStatusBanner(
            `Authenticated as Incoming Successor (${ROLE_METADATA.SUCCESSOR.personaEmail}). Approved Continuation Plan v${planResp.data.version} is unlocked.`
          );
        } else {
          setContinuationPlan(null);
          setDraft(null);
          setStatusBanner(
            `Authenticated as Incoming Successor (${ROLE_METADATA.SUCCESSOR.personaEmail}). Handover is currently '${statusResp.data.status}' — waiting for Reviewer / Project Lead approval.`
          );
        }

        if (options?.targetTab) {
          setActiveTab(options.targetTab);
        }
        return;
      }

      const bootstrapUrl = options?.forceReset
        ? "/api/v1/demo/bootstrap-payflow?reset=true"
        : "/api/v1/demo/bootstrap-payflow";
      const resp = await apiClient.post<HandoverDraft>(bootstrapUrl);
      const loadedDraft = resp.data;
      setDraft(loadedDraft);
      setPayflowProjectId(loadedDraft.projectId);
      setHandoverStatus({
        handoverId: loadedDraft.handoverId,
        status: loadedDraft.status,
        currentVersion: loadedDraft.currentVersion,
        agentTelemetry: loadedDraft.agentTelemetry,
        updatedAt: new Date().toISOString(),
      });

      const srcResp = await apiClient.get<SourceDocumentItem[]>(
        `/api/v1/projects/${loadedDraft.projectId}/sources`
      );
      setSources(srcResp.data);

      if (
        targetRole === "PROJECT_LEAD" &&
        (loadedDraft.approval.status === "approved" ||
          loadedDraft.approval.status === "acknowledged")
      ) {
        try {
          const planResp = await apiClient.get<SuccessorContinuationPlan>(
            `/api/handovers/${loadedDraft.handoverId}/successor-view`
          );
          setContinuationPlan(planResp.data);
        } catch {
          setContinuationPlan(null);
        }
      } else {
        setContinuationPlan(null);
      }

      if (options?.targetTab) {
        setActiveTab(options.targetTab);
      }
    } catch (err: any) {
      setErrorMsg(
        formatApiError(err, "Failed to synchronise workspace with backend.")
      );
    } finally {
      setLoading(false);
    }
  };

  // Switch between genuine backend demo identities (or anonymous Guest Demo)
  const handleSelectRoleSession = async (
    targetRole: ProjectRole,
    preferredTab?: ActiveTab
  ) => {
    try {
      setLoading(true);
      setErrorMsg(null);
      setExportedMarkdown(null);

      await switchDemoRole(targetRole);

      const defaultTabForRole: ActiveTab =
        preferredTab ||
        (targetRole === "SUCCESSOR"
          ? "successor"
          : targetRole === "OUTGOING_DEV"
          ? "review"
          : targetRole === "REVIEWER_SME"
          ? "review"
          : "dashboard");

      await syncWorkspaceForRole(targetRole, { targetTab: defaultTabForRole });

      const meta = ROLE_METADATA[targetRole];
      if (targetRole === "GUEST_DEMO") {
        setStatusBanner(
          "Switched to Anonymous Read-Only Guest Demo session. Navigation is restricted to Overview, Dashboard, and Permitted Sources."
        );
      } else if (targetRole !== "SUCCESSOR") {
        setStatusBanner(
          `Authenticated backend session switched to ${meta.shortLabel}: ${meta.personaName} (${meta.personaEmail}) with [${meta.clearanceSummary}] clearance.`
        );
      }
    } catch (err: any) {
      setErrorMsg(
        formatApiError(err, `Failed to switch role session to ${targetRole}.`)
      );
    } finally {
      setLoading(false);
    }
  };

  const handleBootstrapGuestDemo = async () => {
    await handleSelectRoleSession("GUEST_DEMO", "dashboard");
  };

  const handleResetDemoPackage = async () => {
    await syncWorkspaceForRole(effectiveRole, {
      forceReset: true,
      targetTab: "dashboard",
    });
    setContinuationPlan(null);
    setExportedMarkdown(null);
    setStatusBanner(
      "PayFlow handover package reset to clean initial v1 draft (status: ready_for_review, approval: not_approved)."
    );
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setErrorMsg(null);
      let profile;
      if (authMode === "login") {
        profile = await login(authEmail, authPassword);
      } else {
        profile = await register(authEmail, authPassword, authName);
      }
      setShowAuthModal(false);
      const roleOnPayflow: ProjectRole =
        profile.memberships?.find((m) => m.project_slug === "payflow")?.project_role ||
        profile.memberships?.[0]?.project_role ||
        "PROJECT_LEAD";
      await syncWorkspaceForRole(roleOnPayflow, {
        targetTab: roleOnPayflow === "SUCCESSOR" ? "successor" : "dashboard",
      });
      await refreshProfile();
      setStatusBanner(
        `Signed in as ${profile.full_name} (${profile.email}) with backend role ${roleOnPayflow}.`
      );
    } catch (err: any) {
      setErrorMsg(formatApiError(err, "Authentication failed."));
    } finally {
      setLoading(false);
    }
  };

  const handleUploadSource = async (e: React.FormEvent) => {
    e.preventDefault();
    const projectId = draft?.projectId || payflowProjectId;
    if (!projectId) return;
    try {
      setLoading(true);
      setErrorMsg(null);
      await apiClient.post(`/api/v1/projects/${projectId}/sources/upload`, {
        stable_source_id: newSourceId,
        source_type: newSourceType,
        title: newSourceTitle,
        content: newSourceContent,
        access_level: newSourceAccess,
        version_tag: "v1",
      });
      const srcResp = await apiClient.get<SourceDocumentItem[]>(
        `/api/v1/projects/${projectId}/sources`
      );
      setSources(srcResp.data);
      setStatusBanner(
        `Source '${newSourceId}' uploaded by ${user?.email || effectiveRole}, scanned for secrets, chunked, and indexed.`
      );
    } catch (err: any) {
      setErrorMsg(formatApiError(err, "Source upload failed."));
    } finally {
      setLoading(false);
    }
  };

  const handleReRunAgents = async () => {
    const handoverId = draft?.handoverId || handoverStatus?.handoverId || "payflow-handover-001";
    try {
      setLoading(true);
      setErrorMsg(null);
      if (effectiveRole === "PROJECT_LEAD" || effectiveRole === "OUTGOING_DEV") {
        await apiClient.post(`/api/handovers/${handoverId}/sources/import`, {
          source_ids: [],
          seed_payflow_if_empty: true,
        });
      }
      const resp = await apiClient.post<HandoverDraft>(
        `/api/handovers/${handoverId}/reconstruct`
      );
      setDraft(resp.data);
      setContinuationPlan(null);
      setHandoverStatus({
        handoverId: resp.data.handoverId,
        status: resp.data.status,
        currentVersion: resp.data.currentVersion,
        agentTelemetry: resp.data.agentTelemetry,
        updatedAt: new Date().toISOString(),
      });
      setStatusBanner(
        "3-Agent LangGraph Pipeline (Extraction -> Verification -> Grounding) completed. Draft v1 is ready for review."
      );
    } catch (err: any) {
      setErrorMsg(formatApiError(err, "Agent reconstruction failed."));
    } finally {
      setLoading(false);
    }
  };

  const handleClaimAction = async (
    claim: ClaimItem,
    newStatus: string,
    newReviewState: string
  ) => {
    if (!draft) return;
    try {
      setLoading(true);
      setErrorMsg(null);
      const notes =
        claimNotes[claim.id] ??
        claim.reviewerNotes ??
        `Reviewed by ${ROLE_METADATA[effectiveRole].shortLabel} (${user?.email || effectiveRole}).`;
      const resp = await apiClient.patch<ClaimItem>(
        `/api/claims/${claim.id}?handover_id=${draft.handoverId}`,
        {
          status: newStatus,
          review_state: newReviewState,
          reviewer_notes: notes,
        }
      );
      setDraft({
        ...draft,
        claims: draft.claims.map((c) => (c.id === claim.id ? resp.data : c)),
      });
      setStatusBanner(
        `Claim ${claim.claimId} updated by ${user?.email} to status='${newStatus}', reviewState='${newReviewState}'.`
      );
    } catch (err: any) {
      setErrorMsg(formatApiError(err, "Claim update failed (check role permissions)."));
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerClarification = async (questionId: string) => {
    if (!draft) return;
    const answerText = clarificationAnswers[questionId];
    if (!answerText || answerText.trim().length < 2) return;
    try {
      setLoading(true);
      setErrorMsg(null);
      await apiClient.post(
        `/api/handovers/${draft.handoverId}/clarifications/${questionId}`,
        {
          answer_text: answerText,
          mark_resolved: true,
        }
      );
      const refreshed = await apiClient.get<HandoverDraft>(
        `/api/handovers/${draft.handoverId}/draft`
      );
      setDraft(refreshed.data);
      setStatusBanner(
        `Clarification response recorded by ${user?.email} (${effectiveRole}) and linked claim rationale enriched.`
      );
    } catch (err: any) {
      setErrorMsg(formatApiError(err, "Failed to submit clarification."));
    } finally {
      setLoading(false);
    }
  };

  const handleApproveHandover = async () => {
    if (!draft) return;
    try {
      setLoading(true);
      setErrorMsg(null);
      const resp = await apiClient.post<HandoverDraft>(
        `/api/handovers/${draft.handoverId}/approve`,
        {
          approval_notes: approvalNotes,
        }
      );
      setDraft(resp.data);
      setHandoverStatus({
        handoverId: resp.data.handoverId,
        status: resp.data.status,
        currentVersion: resp.data.currentVersion,
        agentTelemetry: resp.data.agentTelemetry,
        updatedAt: new Date().toISOString(),
      });
      if (effectiveRole === "PROJECT_LEAD") {
        const planResp = await apiClient.get<SuccessorContinuationPlan>(
          `/api/handovers/${draft.handoverId}/successor-view`
        );
        setContinuationPlan(planResp.data);
      }
      setStatusBanner(
        `Handover Package Approved (v${resp.data.currentVersion}) by ${user?.email} (${effectiveRole})! Switch to Incoming Successor (Ankit) to review the 13-Section Continuation Plan and acknowledge receipt.`
      );
    } catch (err: any) {
      setErrorMsg(
        formatApiError(
          err,
          "Approval failed. Only REVIEWER_SME or PROJECT_LEAD can approve handovers."
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSuccessorPlan = async () => {
    const handoverId = draft?.handoverId || handoverStatus?.handoverId || "payflow-handover-001";
    try {
      setLoading(true);
      setErrorMsg(null);
      const statusResp = await apiClient.get<HandoverLiveStatus>(
        `/api/handovers/${handoverId}/status`
      );
      setHandoverStatus(statusResp.data);
      const resp = await apiClient.get<SuccessorContinuationPlan>(
        `/api/handovers/${handoverId}/successor-view`
      );
      setContinuationPlan(resp.data);
      setActiveTab("successor");
    } catch (err: any) {
      setErrorMsg(
        formatApiError(
          err,
          "Successor View is locked until a Reviewer/SME or Project Lead approves the handover package."
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleExportPackage = async (formatType: "markdown" | "json") => {
    const handoverId =
      continuationPlan?.handoverId ||
      draft?.handoverId ||
      handoverStatus?.handoverId ||
      "payflow-handover-001";
    try {
      setLoading(true);
      setErrorMsg(null);
      const resp = await apiClient.get(
        `/api/v1/handovers/${handoverId}/export?format_type=${formatType}`
      );
      if (formatType === "markdown") {
        setExportedMarkdown(resp.data.content);
      } else {
        setExportedMarkdown(JSON.stringify(resp.data.payload, null, 2));
      }
      setStatusBanner(`Generated ${formatType.toUpperCase()} export of the approved handover package.`);
    } catch (err: any) {
      setErrorMsg(formatApiError(err, "Failed to export handover package."));
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledgeReceipt = async () => {
    const handoverId =
      continuationPlan?.handoverId ||
      draft?.handoverId ||
      handoverStatus?.handoverId ||
      "payflow-handover-001";
    try {
      setLoading(true);
      setErrorMsg(null);
      const resp = await apiClient.post<HandoverDraft>(
        `/api/handovers/${handoverId}/acknowledge`,
        {
          acknowledgement_notes: ackNotes,
        }
      );
      setDraft(resp.data);
      setHandoverStatus({
        handoverId: resp.data.handoverId,
        status: resp.data.status,
        currentVersion: resp.data.currentVersion,
        agentTelemetry: resp.data.agentTelemetry,
        updatedAt: new Date().toISOString(),
      });
      const planResp = await apiClient.get<SuccessorContinuationPlan>(
        `/api/handovers/${handoverId}/successor-view`
      );
      setContinuationPlan(planResp.data);
      setStatusBanner(
        `Successor Receipt Acknowledged by ${user?.email} (SUCCESSOR)! Knowledge continuity lifecycle is complete and recorded in the immutable audit trail.`
      );
    } catch (err: any) {
      setErrorMsg(formatApiError(err, "Acknowledgement failed."));
    } finally {
      setLoading(false);
    }
  };

  const handleLoadAuditLogs = async () => {
    const handoverId = draft?.handoverId || handoverStatus?.handoverId || "payflow-handover-001";
    try {
      setLoading(true);
      setErrorMsg(null);
      const resp = await apiClient.get<AuditLogItem[]>(
        `/api/v1/handovers/${handoverId}/audit-logs`
      );
      setAuditLogs(resp.data);
      setActiveTab("audit");
    } catch (err: any) {
      setErrorMsg(
        formatApiError(
          err,
          "Audit logs require PROJECT_LEAD or REVIEWER_SME permissions."
        )
      );
    } finally {
      setLoading(false);
    }
  };

  // Lifecycle Stepper Computation
  const lifecycleSteps = useMemo(() => {
    const hasSources = sources.length > 0 || (draft?.scopedSources?.length ?? 0) > 0;
    const isReconstructed =
      Boolean(draft && draft.claims.length > 0) ||
      Boolean(
        handoverStatus &&
          ["ready_for_review", "in_review", "approved", "acknowledged"].includes(
            handoverStatus.status
          )
      );
    const verifiedClaimsCount =
      draft?.claims.filter((c) => c.status === "verified").length ??
      continuationPlan?.claims.filter((c) => c.status === "verified").length ??
      0;
    const isApproved =
      currentApprovalStatus === "approved" || currentApprovalStatus === "acknowledged";
    const isAcknowledged =
      currentApprovalStatus === "acknowledged" ||
      handoverStatus?.status === "acknowledged";

    return [
      {
        step: "01",
        title: "Sources & Redaction",
        detail: hasSources ? `${sources.length || 8} Scoped Records` : "Not Seeded",
        done: hasSources,
        active: !hasSources,
      },
      {
        step: "02",
        title: "3-Agent Reconstruction",
        detail: isReconstructed ? "LangGraph Complete" : "Awaiting Run",
        done: isReconstructed,
        active: hasSources && !isReconstructed,
      },
      {
        step: "03",
        title: "Clarifications & Review",
        detail: isReconstructed
          ? `${verifiedClaimsCount} Verified · ${unansweredQuestionsCount} Open Qs`
          : "Pending Draft",
        done:
          isApproved ||
          (isReconstructed && verifiedClaimsCount > 0 && unansweredQuestionsCount === 0),
        active: isReconstructed && !isApproved,
      },
      {
        step: "04",
        title: "Human Approval Gate",
        detail: isApproved
          ? `Approved (v${continuationPlan?.version || draft?.currentVersion || 2})`
          : "Awaiting Sign-Off",
        done: isApproved,
        active: isReconstructed && !isApproved,
      },
      {
        step: "05",
        title: "Successor Receipt",
        detail: isAcknowledged ? "Acknowledged" : isApproved ? "Ready to Sign" : "Locked",
        done: isAcknowledged,
        active: isApproved && !isAcknowledged,
      },
    ];
  }, [
    sources.length,
    draft,
    handoverStatus,
    continuationPlan,
    currentApprovalStatus,
    unansweredQuestionsCount,
  ]);

  // Structured human-readable renderer for each of the 13 Continuation Plan sections
  const renderContinuationSectionContent = (sectionKey: string, val: unknown) => {
    if (val === null || val === undefined) {
      return (
        <p className="text-xs text-zinc-400 italic">
          No records in this section for the current scope.
        </p>
      );
    }

    // Section 6: Responsibilities object { departing_role, transferred_claims, supporting_contacts }
    if (
      sectionKey === "6_responsibilities" &&
      typeof val === "object" &&
      !Array.isArray(val)
    ) {
      const respObj = val as {
        departing_role?: string;
        transferred_claims?: Array<Record<string, any>>;
        supporting_contacts?: string[];
      };
      return (
        <div className="space-y-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-neutral-950 p-3">
            <div>
              <span className="font-mono text-[10px] uppercase text-zinc-400">
                Departing Role
              </span>
              <p className="font-semibold text-white">
                {respObj.departing_role || "Senior Payment Integration Engineer"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[10px] uppercase text-zinc-400">
                Supporting Contacts:
              </span>
              {(respObj.supporting_contacts || []).map((contact, idx) => (
                <span
                  key={idx}
                  className="rounded border border-emerald-500/30 bg-emerald-950/30 px-2 py-0.5 font-mono text-[11px] text-emerald-300"
                >
                  {contact}
                </span>
              ))}
            </div>
          </div>
          {respObj.transferred_claims && respObj.transferred_claims.length > 0 ? (
            <div className="space-y-2">
              {respObj.transferred_claims.map((tc, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-zinc-800/90 bg-neutral-950 p-3 space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-emerald-400">
                      {tc.claimId || `RESP-${idx + 1}`}
                    </span>
                    <span className="font-mono text-[11px] text-zinc-400">
                      Assigned: {tc.owner || "Incoming Successor"}
                    </span>
                  </div>
                  <p className="text-zinc-200">{tc.text}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-400">
              All operational responsibilities transfer to Incoming Successor upon receipt acknowledgement.
            </p>
          )}
        </div>
      );
    }

    // Section 13: Approval & Acknowledgement Record object
    if (
      sectionKey === "13_approval_information" &&
      typeof val === "object" &&
      !Array.isArray(val)
    ) {
      const appObj = val as Record<string, any>;
      return (
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 text-xs">
          <div className="rounded-lg border border-zinc-800 bg-neutral-950 p-3">
            <span className="font-mono text-[10px] uppercase text-zinc-400">
              Approval Gate Status
            </span>
            <p className="mt-0.5 font-mono font-bold uppercase text-emerald-400">
              {String(appObj.status || "approved")}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-neutral-950 p-3">
            <span className="font-mono text-[10px] uppercase text-zinc-400">
              Approved By Reviewer
            </span>
            <p className="mt-0.5 font-mono text-zinc-200">
              {String(appObj.reviewer || "Authorised Reviewer")}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-neutral-950 p-3">
            <span className="font-mono text-[10px] uppercase text-zinc-400">
              Successor Receipt Status
            </span>
            <p className="mt-0.5 font-mono text-teal-300">
              {appObj.acknowledgedBy
                ? `Acknowledged by ${appObj.acknowledgedBy}`
                : "Pending Successor Acknowledgement"}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-neutral-950 p-3">
            <span className="font-mono text-[10px] uppercase text-zinc-400">
              Acknowledgement Notes
            </span>
            <p className="mt-0.5 text-zinc-300">
              {String(appObj.acknowledgementNotes || "Awaiting sign-off notes.")}
            </p>
          </div>
        </div>
      );
    }

    // Array sections (Claims, Risks/Dependencies, Questions, Next Actions, Evidence References)
    if (Array.isArray(val)) {
      if (val.length === 0) {
        return (
          <div className="rounded-lg border border-zinc-800/80 bg-neutral-950 p-3 text-xs text-zinc-400">
            No items flagged in this category for the current handover package.
          </div>
        );
      }

      return (
        <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
          {val.map((item: any, idx: number) => {
            // Claim-like item
            if (item && typeof item === "object" && ("claimId" in item || "text" in item)) {
              const evidenceList = Array.isArray(item.evidence) ? item.evidence : [];
              return (
                <div
                  key={item.id || item.claimId || idx}
                  className="rounded-lg border border-zinc-800 bg-neutral-950 p-3 text-xs space-y-1.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {item.claimId && (
                        <span className="font-mono font-bold text-emerald-400">
                          {item.claimId}
                        </span>
                      )}
                      {item.status && (
                        <EvidenceStatusBadge
                          status={item.status as EvidenceStatus}
                          isAiGenerated={item.isAiGenerated}
                        />
                      )}
                    </div>
                    {item.taskStatus && (
                      <span className="rounded border border-zinc-700 bg-zinc-900 px-2 py-0.5 font-mono text-[10px] uppercase text-zinc-300">
                        Task: {item.taskStatus}
                      </span>
                    )}
                  </div>
                  <p className="text-zinc-100 leading-relaxed">{item.text}</p>
                  {item.rationale && (
                    <p className="text-[11px] text-zinc-400">
                      <strong>Rationale:</strong> {item.rationale}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 font-mono text-[11px] text-zinc-400">
                    <span>Owner: {item.owner || "UNKNOWN (Unassigned)"}</span>
                    {evidenceList.length > 0 && (
                      <span className="text-emerald-300">
                        Sources: {evidenceList.map((e: any) => e.sourceId).join(", ")}
                      </span>
                    )}
                  </div>
                </div>
              );
            }

            // Risk / Dependency item
            if (item && typeof item === "object" && "recordType" in item && "title" in item) {
              return (
                <div
                  key={item.id || idx}
                  className="rounded-lg border border-zinc-800 bg-neutral-950 p-3 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-white">
                      [{String(item.recordType).toUpperCase()}] {item.title}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                        item.severity === "critical" || item.severity === "high"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                          : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                      }`}
                    >
                      {item.severity || "high"}
                    </span>
                  </div>
                  <p className="text-zinc-300">{item.description}</p>
                  {item.workaround && (
                    <p className="text-[11px] text-teal-300">
                      <strong>Workaround / Mitigation:</strong> {item.workaround}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-zinc-400">
                    <span>Owner: {item.owner || "UNKNOWN (Unassigned)"}</span>
                    {Array.isArray(item.evidenceSourceIds) && (
                      <span>Sources: {item.evidenceSourceIds.join(", ")}</span>
                    )}
                  </div>
                </div>
              );
            }

            // Clarification Question item
            if (item && typeof item === "object" && "question" in item) {
              return (
                <div
                  key={item.id || idx}
                  className="rounded-lg border border-zinc-800 bg-neutral-950 p-3 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-white">{item.question}</span>
                    <span
                      className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                        item.status === "answered"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-amber-500/20 text-amber-300"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400">Reason: {item.reason}</p>
                  {item.answerText ? (
                    <div className="rounded border border-emerald-500/30 bg-emerald-950/20 p-2 text-emerald-200">
                      <strong>Clarification ({item.answeredBy || "Team"}):</strong>{" "}
                      {item.answerText}
                    </div>
                  ) : (
                    <p className="font-mono text-[11px] text-amber-300">
                      Open item for engineering follow-up.
                    </p>
                  )}
                </div>
              );
            }

            // Next Action item
            if (item && typeof item === "object" && "action" in item) {
              return (
                <div
                  key={item.id || idx}
                  className="rounded-lg border border-zinc-800 bg-neutral-950 p-3 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-white">
                      #{item.priorityRank || idx + 1} — {item.action}
                    </span>
                    <span className="rounded border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-emerald-300">
                      {item.priority || "high"}
                    </span>
                  </div>
                  {item.reason && <p className="text-zinc-400">{item.reason}</p>}
                  <div className="font-mono text-[11px] text-zinc-400">
                    Owner: {item.owner || "Incoming Successor"}
                  </div>
                </div>
              );
            }

            // Evidence Reference item
            if (item && typeof item === "object" && "sourceId" in item) {
              return (
                <div
                  key={idx}
                  className="rounded-lg border border-zinc-800 bg-neutral-950 p-3 text-xs space-y-1"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="rounded border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 font-mono font-bold text-emerald-300">
                      {item.sourceId}
                    </span>
                    <span className="font-mono text-[11px] text-zinc-400">
                      {item.sourceType} · {item.location} · {item.versionTag || "v1"}
                    </span>
                  </div>
                  {item.excerpt && (
                    <p className="font-mono text-[11px] text-zinc-300 border-l-2 border-emerald-500 pl-2">
                      &ldquo;{item.excerpt}&rdquo;
                    </p>
                  )}
                </div>
              );
            }

            return (
              <div
                key={idx}
                className="rounded-lg border border-zinc-800 bg-neutral-950 p-3 text-xs text-zinc-200"
              >
                {typeof item === "string" ? item : Object.values(item || {}).join(" · ")}
              </div>
            );
          })}
        </div>
      );
    }

    // Generic structured object fallback (e.g. custom object in unit test)
    if (typeof val === "object") {
      return (
        <div className="grid grid-cols-1 gap-2 text-xs">
          {Object.entries(val as Record<string, unknown>).map(([k, v]) => (
            <div
              key={k}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-neutral-950 px-3 py-2"
            >
              <span className="font-mono text-[11px] uppercase text-zinc-400">
                {k.replace(/_/g, " ")}
              </span>
              <span className="font-medium text-zinc-200">{String(v ?? "N/A")}</span>
            </div>
          ))}
        </div>
      );
    }

    return <p className="text-xs text-zinc-200">{String(val)}</p>;
  };

  const roleMeta = ROLE_METADATA[effectiveRole];

  return (
    <div className="min-h-screen bg-neutral-950 text-zinc-100 flex flex-col">
      {/* Top Futuristic Command Header */}
      <header className="sticky top-0 z-30 border-b border-zinc-800/90 bg-neutral-950/90 backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            {/* Brand Identity */}
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 font-mono text-sm font-black text-neutral-950 shadow-lg shadow-emerald-500/20">
                KH
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-base font-bold tracking-tight text-white">
                    Knowledge Handover
                  </h1>
                  <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
                    Continuity OS v2.1
                  </span>
                </div>
                <p className="text-xs text-zinc-400">
                  Role-Aware Evidence-Linked Continuity · Human-Gated Approval
                </p>
              </div>
            </div>

            {/* Genuine Backend Role Session Switcher */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/90 px-3 py-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">
                  Active Role Identity:
                </span>
                <select
                  aria-label="Active Role Identity"
                  value={effectiveRole}
                  disabled={loading}
                  onChange={(e) =>
                    handleSelectRoleSession(e.target.value as ProjectRole)
                  }
                  className="rounded-lg border border-emerald-500/40 bg-neutral-950 px-2.5 py-1 text-xs font-semibold text-emerald-300 focus:border-emerald-400 focus:outline-none"
                >
                  <option value="PROJECT_LEAD">
                    PROJECT_LEAD — Preeti (Full Governance & Restricted Scope)
                  </option>
                  <option value="OUTGOING_DEV">
                    OUTGOING_DEV — Arjun (Source Upload & Clarifications)
                  </option>
                  <option value="REVIEWER_SME">
                    REVIEWER_SME — Kavita (Claim Verification & Package Approval)
                  </option>
                  <option value="SUCCESSOR">
                    SUCCESSOR — Ankit (Approved 13-Section Plan & Receipt)
                  </option>
                  <option value="GUEST_DEMO">
                    GUEST_DEMO — Anonymous Read-Only Evaluator
                  </option>
                </select>
              </div>

              {/* Active Identity & Clearance Pill */}
              {isAuthenticated ? (
                <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-950/25 px-3 py-1.5 text-xs">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="font-medium text-zinc-200">{user?.email}</span>
                  <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                    {effectiveRole}
                  </span>
                  <button
                    onClick={() => handleSelectRoleSession("GUEST_DEMO", "landing")}
                    className="ml-1 text-zinc-400 hover:text-rose-400 font-medium"
                    title="Sign out to anonymous mode"
                  >
                    Sign Out
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="rounded-lg border border-amber-500/30 bg-amber-950/30 px-2.5 py-1 text-xs font-mono text-amber-300">
                    GUEST_DEMO (Read-Only)
                  </span>
                  <button
                    onClick={() => setShowAuthModal(!showAuthModal)}
                    className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:border-emerald-500/40 hover:text-emerald-300 transition"
                  >
                    Login / Register
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Role-Specific Navigation Bar */}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800/80 pt-2.5">
            <nav aria-label="Workspace Navigation" className="flex flex-wrap items-center gap-1.5">
              {visibleTabs.map((t) => {
                const isActive = activeTab === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => {
                      if (t.id === "audit") {
                        handleLoadAuditLogs();
                      } else if (
                        t.id === "successor" &&
                        effectiveRole === "PROJECT_LEAD" &&
                        isHandoverApproved
                      ) {
                        handleLoadSuccessorPlan();
                      } else {
                        setActiveTab(t.id);
                      }
                    }}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      isActive
                        ? "bg-emerald-500 text-neutral-950 shadow-md shadow-emerald-500/20"
                        : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                    }`}
                  >
                    <span>{t.label}</span>
                    {t.badge && (
                      <span
                        className={`rounded px-1.5 py-0.2 font-mono text-[10px] ${
                          isActive
                            ? "bg-neutral-950/25 text-neutral-950 font-bold"
                            : "bg-zinc-800 text-emerald-300"
                        }`}
                      >
                        {t.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>

            <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-400">
              <span>Clearance Scope:</span>
              {(isAuthenticated ? allowedClassifications : ["PUBLIC", "INTERNAL"]).map((c) => (
                <span
                  key={c}
                  className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${
                    c === "RESTRICTED"
                      ? "border-rose-500/40 bg-rose-950/40 text-rose-300"
                      : "border-emerald-500/30 bg-emerald-950/30 text-emerald-300"
                  }`}
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* Optional Custom Login / Register Modal */}
      {showAuthModal && (
        <div className="border-b border-zinc-800 bg-zinc-900/95 px-4 py-4">
          <div className="mx-auto max-w-5xl space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs font-semibold text-emerald-300">
                Authenticate via Custom Account or Instant Role Persona
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] text-zinc-400">Instant Demo Personas:</span>
                {(
                  ["PROJECT_LEAD", "OUTGOING_DEV", "REVIEWER_SME", "SUCCESSOR"] as ProjectRole[]
                ).map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => {
                      setShowAuthModal(false);
                      handleSelectRoleSession(r);
                    }}
                    className="rounded border border-emerald-500/30 bg-emerald-950/40 px-2 py-1 text-[11px] font-mono text-emerald-300 hover:bg-emerald-500 hover:text-neutral-950 transition"
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>

            <form
              onSubmit={handleAuthSubmit}
              className="flex flex-wrap items-end gap-3 pt-1"
            >
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setAuthMode("login")}
                  className={`rounded px-2.5 py-1 text-xs font-semibold ${
                    authMode === "login"
                      ? "bg-emerald-500 text-neutral-950"
                      : "bg-zinc-800 text-zinc-400"
                  }`}
                >
                  Login
                </button>
                <button
                  type="button"
                  onClick={() => setAuthMode("register")}
                  className={`rounded px-2.5 py-1 text-xs font-semibold ${
                    authMode === "register"
                      ? "bg-emerald-500 text-neutral-950"
                      : "bg-zinc-800 text-zinc-400"
                  }`}
                >
                  Register
                </button>
              </div>
              {authMode === "register" && (
                <div>
                  <label className="block text-[11px] text-zinc-400">Full Name</label>
                  <input
                    type="text"
                    value={authName}
                    onChange={(e) => setAuthName(e.target.value)}
                    className="mt-1 rounded border border-zinc-700 bg-neutral-950 px-2.5 py-1 text-xs text-white"
                    required
                  />
                </div>
              )}
              <div>
                <label className="block text-[11px] text-zinc-400">Email</label>
                <input
                  type="email"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  className="mt-1 rounded border border-zinc-700 bg-neutral-950 px-2.5 py-1 text-xs text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400">Password</label>
                <input
                  type="password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  className="mt-1 rounded border border-zinc-700 bg-neutral-950 px-2.5 py-1 text-xs text-white"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="rounded bg-emerald-500 px-4 py-1.5 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
              >
                {authMode === "login" ? "Sign In" : "Create Account"}
              </button>
              <button
                type="button"
                onClick={() => setShowAuthModal(false)}
                className="text-xs text-zinc-400 hover:text-white"
              >
                Close
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Status & Error Feedback Banners */}
      {statusBanner && (
        <div className="border-b border-emerald-500/30 bg-emerald-950/30 px-4 py-2 text-center text-xs text-emerald-200 flex items-center justify-center gap-3">
          <span>{statusBanner}</span>
          <button
            onClick={() => setStatusBanner(null)}
            className="font-mono text-[11px] underline text-emerald-400 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}
      {errorMsg && (
        <div className="border-b border-rose-500/40 bg-rose-950/40 px-4 py-2.5 text-center text-xs text-rose-200 flex items-center justify-center gap-3">
          <span>
            <strong>Backend Security / Validation Gate:</strong> {errorMsg}
          </span>
          <button
            onClick={() => setErrorMsg(null)}
            className="font-mono text-[11px] underline text-rose-300 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Content Container */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 space-y-6">
        {/* Global End-to-End Handover Continuity Pipeline Stepper */}
        {(draft || handoverStatus || activeTab !== "landing") && (
          <section
            aria-label="Handover Continuity Pipeline"
            className="kh-surface p-4 space-y-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-400">
                  End-to-End Handover Lifecycle
                </span>
                <span className="rounded border border-zinc-700 bg-neutral-950 px-2 py-0.5 font-mono text-[11px] text-zinc-300">
                  Handover: {draft?.handoverId || handoverStatus?.handoverId || "payflow-handover-001"}
                </span>
                <span
                  className={`rounded border px-2 py-0.5 font-mono text-[11px] font-semibold ${
                    isHandoverApproved
                      ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                      : "border-amber-500/40 bg-amber-500/15 text-amber-300"
                  }`}
                >
                  Status: {draft?.status || handoverStatus?.status || "ready_for_review"} (v
                  {draft?.currentVersion || handoverStatus?.currentVersion || 1})
                </span>
              </div>

              <div className="flex items-center gap-2">
                {!isReadOnlyGuest && effectiveRole !== "SUCCESSOR" && (draft || handoverStatus) && (
                  <button
                    onClick={handleResetDemoPackage}
                    disabled={loading}
                    className="rounded-lg border border-zinc-700 bg-neutral-950 px-2.5 py-1 text-[11px] font-medium text-zinc-300 hover:border-emerald-500/40 hover:text-emerald-300"
                  >
                    Reset Demo Draft to v1
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-5">
              {lifecycleSteps.map((s) => (
                <div
                  key={s.step}
                  className={`rounded-lg border p-2.5 transition-all ${
                    s.done
                      ? "border-emerald-500/40 bg-emerald-950/20"
                      : s.active
                      ? "border-teal-400/50 bg-zinc-900"
                      : "border-zinc-800/80 bg-neutral-950/60 opacity-75"
                  }`}
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className={s.done ? "text-emerald-400 font-bold" : "text-zinc-400"}>
                      STEP {s.step}
                    </span>
                    <span
                      className={`rounded px-1.5 py-0.2 text-[10px] font-semibold ${
                        s.done
                          ? "bg-emerald-500/20 text-emerald-300"
                          : s.active
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-zinc-800 text-zinc-400"
                      }`}
                    >
                      {s.done ? "COMPLETE" : s.active ? "ACTIVE" : "LOCKED"}
                    </span>
                  </div>
                  <div className="mt-1 text-xs font-semibold text-white">{s.title}</div>
                  <div className="mt-0.5 text-[11px] text-zinc-400">{s.detail}</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* TAB 1: OVERVIEW / ROLE LAUNCHPAD */}
        {activeTab === "landing" && (
          <div className="space-y-8 py-2">
            <div className="kh-surface-elevated p-8 text-center space-y-5">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1 text-xs font-semibold text-emerald-300">
                <span>Role-Aware Knowledge Continuity Platform</span>
                <span>·</span>
                <span className="font-mono">LangGraph 3-Agent Pipeline</span>
              </div>
              <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-5xl">
                Verifiable Engineering Handovers.{" "}
                <span className="bg-gradient-to-r from-emerald-400 to-teal-300 bg-clip-text text-transparent">
                  Zero Silent Hallucinations.
                </span>
              </h2>
              <p className="mx-auto max-w-3xl text-sm text-zinc-300 leading-relaxed sm:text-base">
                Every claim is deterministically anchored to authorised repository, issue, pull request,
                and architecture records. Contradictions and stale documents are surfaced side-by-side,
                and the <strong>Incoming Successor</strong> is protected by a mandatory{" "}
                <strong>Human Reviewer Approval Gate</strong>.
              </p>

              {/* Primary Launch Actions */}
              <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                <button
                  onClick={handleBootstrapGuestDemo}
                  disabled={loading}
                  className="rounded-xl bg-emerald-500 px-6 py-3 text-sm font-bold text-neutral-950 shadow-lg shadow-emerald-500/25 hover:bg-emerald-400 transition disabled:opacity-50"
                >
                  {loading
                    ? "Initialising Synthetic PayFlow Workspace..."
                    : "Try Instant PayFlow Demo (Read-Only)"}
                </button>
                <button
                  onClick={() => handleSelectRoleSession("PROJECT_LEAD", "dashboard")}
                  disabled={loading}
                  className="rounded-xl border border-emerald-500/40 bg-zinc-900 px-5 py-3 text-sm font-semibold text-emerald-300 hover:bg-emerald-950/40 transition disabled:opacity-50"
                >
                  Enter as Project Lead (Full Governance)
                </button>
              </div>
            </div>

            {/* Interactive Role Matrix — Direct Authenticated Persona Switching */}
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-lg font-bold text-white">
                    Choose a Genuine Backend Role Persona
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Each card authenticates a dedicated database identity with its own JWT, clearance
                    scope, navigation tabs, and backend-enforced permissions.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                {(
                  [
                    "PROJECT_LEAD",
                    "OUTGOING_DEV",
                    "REVIEWER_SME",
                    "SUCCESSOR",
                  ] as ProjectRole[]
                ).map((r) => {
                  const meta = ROLE_METADATA[r];
                  const isCurrent = isAuthenticated && effectiveRole === r;
                  return (
                    <div
                      key={r}
                      className={`flex flex-col justify-between rounded-xl border p-5 transition-all ${
                        isCurrent
                          ? "border-emerald-400 bg-emerald-950/20 shadow-lg shadow-emerald-500/10"
                          : "border-zinc-800 bg-zinc-900/75 hover:border-emerald-500/40"
                      }`}
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-300">
                            {meta.role}
                          </span>
                          {isCurrent && (
                            <span className="rounded bg-emerald-500 px-2 py-0.5 font-mono text-[10px] font-bold text-neutral-950">
                              ACTIVE
                            </span>
                          )}
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-white">{meta.shortLabel}</h4>
                          <p className="font-mono text-[11px] text-teal-300">
                            {meta.personaName} · {meta.personaEmail}
                          </p>
                          <p className="mt-1 font-mono text-[10px] text-zinc-400">
                            Clearance: {meta.clearanceSummary}
                          </p>
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed">{meta.tagline}</p>
                        <ul className="space-y-1.5 border-t border-zinc-800/80 pt-2.5 text-[11px] text-zinc-400">
                          {meta.responsibilities.map((item, i) => (
                            <li key={i} className="flex items-start gap-1.5">
                              <span className="text-emerald-400">▸</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="mt-4 pt-3 border-t border-zinc-800/80">
                        <button
                          onClick={() => handleSelectRoleSession(r)}
                          disabled={loading}
                          className={`w-full rounded-lg py-2 text-xs font-bold transition ${
                            isCurrent
                              ? "bg-emerald-500 text-neutral-950"
                              : "border border-emerald-500/40 bg-neutral-950 text-emerald-300 hover:bg-emerald-500 hover:text-neutral-950"
                          }`}
                        >
                          {isCurrent
                            ? `Open ${meta.shortLabel} Workspace`
                            : `Switch to ${meta.shortLabel}`}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: ROLE-AWARE DASHBOARD */}
        {activeTab === "dashboard" && (
          <div className="space-y-6">
            {/* Role Identity & Responsibility Banner */}
            <div className="kh-surface-elevated p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2 max-w-3xl">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-emerald-500 px-2.5 py-0.5 font-mono text-xs font-bold text-neutral-950">
                      {roleMeta.role}
                    </span>
                    <span className="font-mono text-xs text-emerald-300">
                      {isAuthenticated ? user?.email : roleMeta.personaEmail}
                    </span>
                    <span className="rounded border border-zinc-700 bg-neutral-950 px-2 py-0.5 font-mono text-[11px] text-zinc-300">
                      Clearance: {roleMeta.clearanceSummary}
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-white">{roleMeta.title}</h2>
                  <p className="text-xs text-zinc-300 leading-relaxed">{roleMeta.tagline}</p>
                  <p className="text-[11px] font-mono text-amber-300/90">
                    RBAC Enforcement Boundary: {roleMeta.restrictedNote}
                  </p>
                </div>

                {/* Role-Specific Primary CTA */}
                <div className="flex flex-wrap items-center gap-2">
                  {effectiveRole === "OUTGOING_DEV" && (
                    <>
                      <button
                        onClick={() => setActiveTab("sources")}
                        className="rounded-lg border border-emerald-500/40 bg-neutral-950 px-3.5 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-950/50"
                      >
                        1. Upload Sources
                      </button>
                      <button
                        onClick={() => setActiveTab("review")}
                        className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                      >
                        2. Answer Open Clarifications ({unansweredQuestionsCount})
                      </button>
                    </>
                  )}
                  {effectiveRole === "REVIEWER_SME" && (
                    <>
                      <button
                        onClick={() => setActiveTab("review")}
                        className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                      >
                        Verify Claims & Approve Package
                      </button>
                      <button
                        onClick={handleLoadAuditLogs}
                        className="rounded-lg border border-zinc-700 bg-neutral-950 px-3.5 py-2 text-xs font-semibold text-zinc-200 hover:border-emerald-500/40"
                      >
                        Inspect Audit Trail
                      </button>
                    </>
                  )}
                  {effectiveRole === "PROJECT_LEAD" && (
                    <>
                      {canRunReconstruct && (
                        <button
                          onClick={handleReRunAgents}
                          disabled={loading}
                          className="rounded-lg border border-emerald-500/40 bg-neutral-950 px-3.5 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-950/50"
                        >
                          Re-Run 3-Agent Pipeline
                        </button>
                      )}
                      <button
                        onClick={() => setActiveTab("review")}
                        className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                      >
                        Open Review & Approval Gate
                      </button>
                    </>
                  )}
                  {effectiveRole === "SUCCESSOR" && (
                    <button
                      onClick={() => setActiveTab("successor")}
                      className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                    >
                      {isHandoverApproved
                        ? "Open Approved 13-Section Continuation Plan"
                        : "View Approval Gate Status"}
                    </button>
                  )}
                  {effectiveRole === "GUEST_DEMO" && (
                    <button
                      onClick={() => handleSelectRoleSession("OUTGOING_DEV", "review")}
                      className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                    >
                      Authenticate as Outgoing Dev / Reviewer →
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* If workspace not yet loaded */}
            {!draft && !handoverStatus ? (
              <div className="kh-surface p-10 text-center space-y-4">
                <p className="text-sm text-zinc-300">
                  No handover package loaded in the current view yet.
                </p>
                <button
                  onClick={() => syncWorkspaceForRole(effectiveRole)}
                  disabled={loading}
                  className="rounded-xl bg-emerald-500 px-5 py-2.5 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                >
                  Load PayFlow Handover Package
                </button>
              </div>
            ) : effectiveRole === "SUCCESSOR" && !isHandoverApproved ? (
              /* SUCCESSOR DASHBOARD WHEN HANDOVER IS NOT YET APPROVED */
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <div className="lg:col-span-2 kh-surface p-6 border-amber-500/40 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="rounded border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 font-mono text-xs font-semibold text-amber-300">
                      HUMAN APPROVAL GATE ACTIVE · DRAFT LOCKED
                    </span>
                    <span className="font-mono text-xs text-zinc-400">
                      Backend Status: {handoverStatus?.status || "ready_for_review"}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-white">
                    Waiting for Reviewer / Project Lead Sign-Off
                  </h3>
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    As the <strong>Incoming Successor</strong>, you are protected from unverified AI
                    reconstructions. The backend enforces a strict authorization gate (
                    <code className="text-emerald-300">HTTP 403 Forbidden</code> on{" "}
                    <code className="text-emerald-300">/api/handovers/payflow-handover-001/draft</code>{" "}
                    and <code className="text-emerald-300">/successor-view</code>) until{" "}
                    <strong>Kavita Rao (Reviewer / SME)</strong> or{" "}
                    <strong>Preeti Satish Mittal (Project Lead)</strong> verifies the claims and
                    approves the package.
                  </p>
                  <div className="flex flex-wrap items-center gap-3 pt-2">
                    <button
                      onClick={() => setActiveTab("sources")}
                      className="rounded-lg border border-zinc-700 bg-neutral-950 px-4 py-2 text-xs font-semibold text-zinc-200 hover:border-emerald-500/40"
                    >
                      Browse Permitted Sources ({sources.length})
                    </button>
                    <button
                      onClick={() => handleSelectRoleSession("REVIEWER_SME", "review")}
                      className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                    >
                      Switch to Reviewer / SME to Approve Now →
                    </button>
                  </div>
                </div>

                <div className="kh-surface p-6 space-y-3">
                  <h4 className="text-sm font-bold text-white">Successor Readiness Checklist</h4>
                  <ul className="space-y-2 text-xs text-zinc-300">
                    <li className="flex items-center justify-between border-b border-zinc-800 pb-2">
                      <span>Project Membership Verified</span>
                      <span className="font-mono text-emerald-400">PASS</span>
                    </li>
                    <li className="flex items-center justify-between border-b border-zinc-800 pb-2">
                      <span>Permitted PUBLIC / INTERNAL Sources</span>
                      <span className="font-mono text-emerald-400">{sources.length} Ready</span>
                    </li>
                    <li className="flex items-center justify-between border-b border-zinc-800 pb-2">
                      <span>RESTRICTED Sources Filtered Out</span>
                      <span className="font-mono text-emerald-400">Enforced</span>
                    </li>
                    <li className="flex items-center justify-between">
                      <span>13-Section Continuation Plan</span>
                      <span className="font-mono text-amber-300">Awaiting Approval</span>
                    </li>
                  </ul>
                </div>
              </div>
            ) : (
              /* KPI & SUMMARY CARDS FOR LOADED DRAFT */
              draft && (
                <>
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                    <div className="kh-surface p-4">
                      <span className="text-[11px] font-mono uppercase text-zinc-400">
                        Scoped Sources
                      </span>
                      <p className="mt-1 text-2xl font-bold text-white">
                        {draft.scopedSources.length}
                      </p>
                      <span className="text-[11px] text-emerald-400">
                        {allowedClassifications.includes("RESTRICTED")
                          ? `${sources.length} visible in project`
                          : "Restricted excluded"}
                      </span>
                    </div>
                    <div className="kh-surface p-4">
                      <span className="text-[11px] font-mono uppercase text-zinc-400">
                        Extracted Claims
                      </span>
                      <p className="mt-1 text-2xl font-bold text-teal-300">
                        {draft.claims.length}
                      </p>
                      <span className="text-[11px] text-zinc-400">
                        {draft.claims.filter((c) => c.status === "verified").length} human-verified
                      </span>
                    </div>
                    <div className="kh-surface p-4">
                      <span className="text-[11px] font-mono uppercase text-zinc-400">
                        Conflicts Surfaced
                      </span>
                      <p className="mt-1 text-2xl font-bold text-rose-400">
                        {draft.claims.filter((c) => c.status === "conflicting").length}
                      </p>
                      <span className="text-[11px] text-rose-300">Side-by-side citations</span>
                    </div>
                    <div className="kh-surface p-4">
                      <span className="text-[11px] font-mono uppercase text-zinc-400">
                        Stale Docs Flagged
                      </span>
                      <p className="mt-1 text-2xl font-bold text-amber-400">
                        {draft.claims.filter((c) => c.status === "potentially_outdated").length}
                      </p>
                      <span className="text-[11px] text-amber-300">Timestamp checked</span>
                    </div>
                    <div className="kh-surface p-4">
                      <span className="text-[11px] font-mono uppercase text-zinc-400">
                        Open Clarifications
                      </span>
                      <p className="mt-1 text-2xl font-bold text-emerald-300">
                        {unansweredQuestionsCount}
                      </p>
                      <span className="text-[11px] text-zinc-400">
                        of {draft.openQuestions.length} total questions
                      </span>
                    </div>
                    <div className="kh-surface p-4">
                      <span className="text-[11px] font-mono uppercase text-zinc-400">
                        Approval Gate
                      </span>
                      <p className="mt-1 text-lg font-bold text-emerald-400 uppercase font-mono">
                        {draft.approval.status}
                      </p>
                      <span className="text-[11px] text-zinc-400">
                        Snapshot v{draft.currentVersion}
                      </span>
                    </div>
                  </div>

                  {/* Executive Summary & Blockers / Risks Grid */}
                  <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    <div className="kh-surface p-6 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-base font-bold text-white">
                          Executive Continuity Summary
                        </h3>
                        <span className="font-mono text-xs text-emerald-400">
                          {draft.departingRole}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-300 leading-relaxed">
                        {String(
                          draft.summary?.executive_overview ||
                            draft.summary?.text ||
                            draft.scopeDescription
                        )}
                      </p>
                      <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3.5 text-xs text-emerald-200">
                        <strong>Deterministic Safety Guarantee:</strong>{" "}
                        {String(
                          draft.summary?.safety_notice ||
                            "No claim is marked verified without human reviewer approval."
                        )}
                      </div>
                    </div>

                    <div className="kh-surface p-6 space-y-3">
                      <h3 className="text-base font-bold text-white">
                        Blockers, Risks & External Dependencies ({draft.risksAndDependencies.length})
                      </h3>
                      <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
                        {draft.risksAndDependencies.map((r) => (
                          <div
                            key={r.id}
                            className="rounded-lg border border-zinc-800 bg-neutral-950/90 p-3 text-xs space-y-1"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-white">
                                [{r.recordType.toUpperCase()}] {r.title}
                              </span>
                              <span
                                className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                                  r.severity === "critical" || r.severity === "high"
                                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                    : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                }`}
                              >
                                {r.severity}
                              </span>
                            </div>
                            <p className="text-zinc-300">{r.description}</p>
                            <div className="flex flex-wrap gap-3 text-[11px] font-mono text-zinc-400 pt-1">
                              <span>Owner: {r.owner || "UNKNOWN (Unassigned)"}</span>
                              <span>Sources: {r.evidenceSourceIds.join(", ")}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              )
            )}
          </div>
        )}

        {/* TAB 3: SOURCES & SECRET REDACTION */}
        {activeTab === "sources" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Role-Gated Upload Panel: Only visible to PROJECT_LEAD and OUTGOING_DEV */}
              {canUploadSource ? (
                <form
                  onSubmit={handleUploadSource}
                  className="kh-surface-elevated p-5 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white">
                      Ingest & Redact New Source
                    </h3>
                    <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] text-emerald-300">
                      {effectiveRole}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400">
                    Raw tokens, API keys, and private keys are automatically scrubbed prior to
                    chunking and vector indexing.
                  </p>
                  <div>
                    <label className="block text-xs text-zinc-300">Stable Source ID</label>
                    <input
                      type="text"
                      value={newSourceId}
                      onChange={(e) => setNewSourceId(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-zinc-700 bg-neutral-950 px-3 py-1.5 text-xs text-white font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-300">Title</label>
                    <input
                      type="text"
                      value={newSourceTitle}
                      onChange={(e) => setNewSourceTitle(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-zinc-700 bg-neutral-950 px-3 py-1.5 text-xs text-white"
                      required
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-zinc-300">Source Type</label>
                      <select
                        value={newSourceType}
                        onChange={(e) => setNewSourceType(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-zinc-700 bg-neutral-950 px-2 py-1.5 text-xs text-white"
                      >
                        <option value="technical_doc">technical_doc</option>
                        <option value="meeting_note">meeting_note</option>
                        <option value="adr">adr</option>
                        <option value="pull_request">pull_request</option>
                        <option value="synthetic_issue">synthetic_issue</option>
                        <option value="uploaded_file">uploaded_file</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-300">Classification</label>
                      <select
                        value={newSourceAccess}
                        onChange={(e) =>
                          setNewSourceAccess(e.target.value as AccessClassification)
                        }
                        className="mt-1 w-full rounded-lg border border-zinc-700 bg-neutral-950 px-2 py-1.5 text-xs text-white"
                      >
                        <option value="PUBLIC">PUBLIC</option>
                        <option value="INTERNAL">INTERNAL</option>
                        {allowedClassifications.includes("RESTRICTED") && (
                          <option value="RESTRICTED">RESTRICTED</option>
                        )}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-300">
                      Raw Content (Secrets will be replaced with [REDACTED_SECRET])
                    </label>
                    <textarea
                      rows={4}
                      value={newSourceContent}
                      onChange={(e) => setNewSourceContent(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-zinc-700 bg-neutral-950 p-2.5 text-xs text-white font-mono"
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full rounded-lg bg-emerald-500 py-2 text-xs font-bold text-neutral-950 hover:bg-emerald-400 disabled:opacity-40"
                  >
                    Upload, Redact Secrets & Index Chunks
                  </button>
                </form>
              ) : (
                <div className="kh-surface p-5 space-y-3">
                  <span className="rounded border border-zinc-700 bg-neutral-950 px-2 py-0.5 font-mono text-[10px] text-emerald-300">
                    READ-ONLY SOURCE SCOPE · {effectiveRole}
                  </span>
                  <h3 className="text-sm font-bold text-white">
                    Clearance-Filtered Source Repository
                  </h3>
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    Your current role (<strong>{roleMeta.shortLabel}</strong>) has read-only access
                    to project sources matching your clearance (
                    <code className="text-emerald-300">{roleMeta.clearanceSummary}</code>).
                  </p>
                  <div className="rounded-lg border border-zinc-800 bg-neutral-950 p-3 text-xs text-zinc-400 space-y-1">
                    <div>
                      • Source upload requires <strong>PROJECT_LEAD</strong> or{" "}
                      <strong>OUTGOING_DEV</strong>.
                    </div>
                    <div>
                      • Any <code className="text-rose-300">RESTRICTED</code> vendor notes are
                      filtered out at the SQL query layer unless your membership includes{" "}
                      <code className="text-rose-300">RESTRICTED</code> clearance.
                    </div>
                  </div>
                </div>
              )}

              {/* Source List */}
              <div className="lg:col-span-2 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-white">
                    Permitted Project Sources ({sources.length})
                  </h3>
                  <span className="text-xs font-mono text-zinc-400">
                    Showing records matching [
                    {(isAuthenticated ? allowedClassifications : ["PUBLIC", "INTERNAL"]).join(", ")}
                    ]
                  </span>
                </div>
                {sources.map((src) => (
                  <div key={src.id} className="kh-surface p-4 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="rounded border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 font-mono text-xs font-bold text-emerald-300">
                          {src.stable_source_id}
                        </span>
                        <span className="text-sm font-semibold text-white">{src.title}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span
                          className={`rounded px-2 py-0.5 font-mono font-semibold ${
                            src.access_level === "RESTRICTED"
                              ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                              : "bg-zinc-800 text-zinc-300"
                          }`}
                        >
                          {src.access_level}
                        </span>
                        {src.redacted_secrets_count > 0 && (
                          <span className="rounded bg-amber-500/20 px-2 py-0.5 font-mono text-amber-300 border border-amber-500/30">
                            {src.redacted_secrets_count} Secret(s) Redacted
                          </span>
                        )}
                      </div>
                    </div>
                    <pre className="whitespace-pre-wrap rounded-lg border border-zinc-800/90 bg-neutral-950 p-3 font-mono text-xs text-zinc-300">
                      {src.content_redacted}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: REVIEW & CLARIFICATION WORKSPACE (Strictly Authenticated Lead, Outgoing, Reviewer) */}
        {activeTab === "review" && canAccessReviewWorkspace && draft && (
          <div className="space-y-6">
            {/* Role-Aware Review Header & Approval Action Bar */}
            <div className="kh-surface-elevated p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-emerald-500/20 border border-emerald-500/40 px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-300">
                      {effectiveRole} WORKSPACE
                    </span>
                    <h3 className="text-base font-bold text-white">
                      {effectiveRole === "OUTGOING_DEV"
                        ? "Outgoing Developer Clarification & Draft Annotation Studio"
                        : "Human-in-the-Loop Evidence Review & Approval Gate"}
                    </h3>
                  </div>
                  <p className="mt-1 text-xs text-zinc-300">
                    {effectiveRole === "OUTGOING_DEV"
                      ? "Answer open clarification questions below to enrich linked claims, and flag any draft statements that require SME attention. Only a Reviewer/SME or Project Lead can mark claims Verified or approve the package."
                      : "Inspect source citations and side-by-side conflicts, mark accurate claims as Verified (Human-Reviewed), and approve the handover package to unlock the Successor Continuation Plan."}
                  </p>
                </div>

                {/* Approve Handover Package Control — strictly visible only to PROJECT_LEAD and REVIEWER_SME */}
                {canApproveHandover && (
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="text"
                      aria-label="Approval Notes"
                      value={approvalNotes}
                      onChange={(e) => setApprovalNotes(e.target.value)}
                      placeholder="Reviewer sign-off notes..."
                      className="w-64 rounded-lg border border-zinc-700 bg-neutral-950 px-3 py-2 text-xs text-white"
                    />
                    <button
                      onClick={handleApproveHandover}
                      disabled={loading}
                      className="rounded-xl bg-emerald-500 px-5 py-2.5 text-xs font-bold text-neutral-950 shadow-lg shadow-emerald-500/25 hover:bg-emerald-400"
                    >
                      Approve Handover Package & Unlock Successor View
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Targeted Clarification Questions */}
            <div className="kh-surface p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white">
                    Targeted Clarification Questions ({draft.openQuestions.length})
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Generated by Agent 3 (Uncertainty & Grounding) for missing owners, unresolved
                    parameters, or contradicting records.
                  </p>
                </div>
                <span className="rounded border border-emerald-500/30 bg-emerald-950/30 px-2.5 py-1 font-mono text-xs text-emerald-300">
                  {unansweredQuestionsCount} Open ·{" "}
                  {draft.openQuestions.filter((q) => q.status === "answered").length} Answered
                </span>
              </div>

              <div className="space-y-3">
                {draft.openQuestions.map((q) => (
                  <div
                    key={q.id}
                    className={`rounded-xl border p-4 space-y-2 ${
                      q.status === "answered"
                        ? "border-emerald-500/30 bg-emerald-950/10"
                        : "border-amber-500/30 bg-neutral-950"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-white">{q.question}</span>
                      <span
                        className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                          q.status === "answered"
                            ? "bg-emerald-500/20 text-emerald-300"
                            : "bg-amber-500/20 text-amber-300"
                        }`}
                      >
                        {q.status}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400">Reason: {q.reason}</p>
                    {q.answerText ? (
                      <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/25 p-3 text-xs text-emerald-200">
                        <strong>Recorded Clarification ({q.answeredBy}):</strong> {q.answerText}
                      </div>
                    ) : canAnswerClarifications ? (
                      <div className="flex flex-wrap gap-2 pt-1">
                        <input
                          type="text"
                          placeholder="Provide authoritative engineering clarification..."
                          value={clarificationAnswers[q.id] || ""}
                          onChange={(e) =>
                            setClarificationAnswers({
                              ...clarificationAnswers,
                              [q.id]: e.target.value,
                            })
                          }
                          className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-white"
                        />
                        <button
                          onClick={() => handleAnswerClarification(q.id)}
                          disabled={loading}
                          className="rounded-lg bg-emerald-500 px-4 py-1.5 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                        >
                          Submit Answer
                        </button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>

            {/* Claims List with Provenance & Role-Permitted Actions */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-white">
                  Extracted Handover Claims ({draft.claims.length})
                </h3>
                <span className="text-xs font-mono text-zinc-400">
                  Click &ldquo;Inspect Citations & Conflicts&rdquo; on any claim to verify source
                  provenance
                </span>
              </div>

              {draft.claims.map((claim) => (
                <div
                  key={claim.id}
                  className="kh-surface p-5 space-y-3 hover:border-zinc-700"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-emerald-400">
                        {claim.claimId}
                      </span>
                      <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs font-mono text-zinc-300">
                        {claim.type}
                      </span>
                      <EvidenceStatusBadge
                        status={claim.status}
                        isAiGenerated={claim.isAiGenerated}
                      />
                      <span className="rounded border border-zinc-700 bg-neutral-950 px-2 py-0.5 font-mono text-[11px] text-zinc-400">
                        Review State: {claim.reviewState}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => setInspectedClaim(claim)}
                        className="rounded-lg border border-emerald-500/40 bg-emerald-950/30 px-3 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-500 hover:text-neutral-950 transition"
                      >
                        Inspect Citations & Conflicts ({claim.evidence.length})
                      </button>

                      {/* Mark Verified: ONLY shown for REVIEWER_SME and PROJECT_LEAD */}
                      {canVerifyClaims && (
                        <button
                          onClick={() =>
                            handleClaimAction(claim, "verified", "approved")
                          }
                          disabled={loading}
                          className="rounded-lg bg-emerald-500/20 border border-emerald-500/40 px-3 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-500 hover:text-neutral-950 transition disabled:opacity-40"
                        >
                          Mark Verified
                        </button>
                      )}

                      {/* Flag Unresolved / Reject: shown for PROJECT_LEAD, REVIEWER_SME, and OUTGOING_DEV */}
                      {canEditOrFlagClaims && (
                        <>
                          <button
                            onClick={() =>
                              handleClaimAction(
                                claim,
                                "unknown",
                                "clarification_requested"
                              )
                            }
                            disabled={loading}
                            className="rounded-lg bg-amber-500/15 border border-amber-500/40 px-2.5 py-1 text-xs font-medium text-amber-300 hover:bg-amber-500/25 disabled:opacity-40"
                          >
                            Flag Unresolved
                          </button>
                          <button
                            onClick={() =>
                              handleClaimAction(claim, "unknown", "rejected")
                            }
                            disabled={loading}
                            className="rounded-lg bg-rose-500/15 border border-rose-500/40 px-2.5 py-1 text-xs font-medium text-rose-300 hover:bg-rose-500/25 disabled:opacity-40"
                          >
                            Reject Claim
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  <p className="text-sm text-zinc-100 leading-relaxed">{claim.text}</p>
                  {claim.rationale && (
                    <p className="text-xs text-zinc-400">
                      <strong>Engineering Rationale:</strong> {claim.rationale}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-zinc-400">
                    <span>
                      Owner:{" "}
                      <strong className="text-zinc-200">
                        {claim.owner ?? "UNKNOWN (Unassigned)"}
                      </strong>
                    </span>
                    <span>
                      Task Status:{" "}
                      <strong className="text-zinc-200">{claim.taskStatus || "n/a"}</strong>
                    </span>
                    <span>
                      Citations:{" "}
                      {claim.evidence.map((e) => e.sourceId).join(", ") || "None"}
                    </span>
                    {claim.reviewerNotes && (
                      <span className="text-emerald-300">
                        Note: &ldquo;{claim.reviewerNotes}&rdquo;
                      </span>
                    )}
                  </div>

                  {claim.conflicts.length > 0 && (
                    <div className="rounded-lg border border-rose-500/40 bg-rose-950/20 p-3 text-xs text-rose-200">
                      <strong>Contradiction Detected ({claim.conflicts[0].conflictType}):</strong>{" "}
                      {claim.conflicts[0].explanation}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: SUCCESSOR 13-SECTION CONTINUATION PLAN (Strictly SUCCESSOR and PROJECT_LEAD) */}
        {activeTab === "successor" && canViewSuccessorPlan && (
          <div className="space-y-6">
            {!continuationPlan ? (
              /* WAITING FOR APPROVAL STATE (Clear, informative, role-aware) */
              <div className="kh-surface-elevated p-8 space-y-5 border-amber-500/40">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="rounded border border-amber-500/40 bg-amber-500/15 px-3 py-1 font-mono text-xs font-bold uppercase text-amber-300">
                    WAITING FOR HUMAN APPROVAL GATE
                  </span>
                  <span className="font-mono text-xs text-zinc-400">
                    Current Backend Status:{" "}
                    <strong className="text-amber-300">
                      {handoverStatus?.status || draft?.status || "ready_for_review"}
                    </strong>{" "}
                    (v{handoverStatus?.currentVersion || draft?.currentVersion || 1})
                  </span>
                </div>

                <div className="space-y-2 max-w-3xl">
                  <h3 className="text-xl font-bold text-white">
                    Successor Continuation Plan Is Locked Pending Human Sign-Off
                  </h3>
                  <p className="text-sm text-zinc-300 leading-relaxed">
                    To prevent unverified AI summaries or unresolved source contradictions from
                    misleading the incoming engineer, the backend blocks{" "}
                    <code className="text-emerald-300">
                      GET /api/handovers/payflow-handover-001/successor-view
                    </code>{" "}
                    until a <strong>Reviewer / SME</strong> or <strong>Project Lead</strong> approves
                    the package.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-3 pt-2">
                  <div className="rounded-xl border border-zinc-800 bg-neutral-950 p-4 space-y-1">
                    <span className="font-mono text-[11px] text-emerald-400">STEP 1 · DONE</span>
                    <h4 className="text-xs font-bold text-white">Sources & AI Reconstruction</h4>
                    <p className="text-xs text-zinc-400">
                      PayFlow sources have been redacted and processed by the 3-Agent LangGraph
                      pipeline.
                    </p>
                  </div>
                  <div className="rounded-xl border border-amber-500/40 bg-amber-950/15 p-4 space-y-1">
                    <span className="font-mono text-[11px] text-amber-300">
                      STEP 2 · IN PROGRESS
                    </span>
                    <h4 className="text-xs font-bold text-white">
                      Reviewer / Lead Verification & Approval
                    </h4>
                    <p className="text-xs text-zinc-300">
                      A Reviewer/SME or Project Lead must verify claims and click{" "}
                      <strong>Approve Handover Package</strong>.
                    </p>
                  </div>
                  <div className="rounded-xl border border-zinc-800 bg-neutral-950 p-4 space-y-1">
                    <span className="font-mono text-[11px] text-zinc-400">STEP 3 · NEXT</span>
                    <h4 className="text-xs font-bold text-white">
                      13-Section Plan & Successor Receipt
                    </h4>
                    <p className="text-xs text-zinc-400">
                      Once approved, the Incoming Successor will inspect the 13-section plan and
                      formally acknowledge receipt.
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 pt-2">
                  {canApproveHandover ? (
                    <button
                      onClick={() => setActiveTab("review")}
                      className="rounded-xl bg-emerald-500 px-5 py-2.5 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                    >
                      Go to Review Workspace to Approve Package →
                    </button>
                  ) : (
                    <button
                      onClick={() => handleSelectRoleSession("REVIEWER_SME", "review")}
                      className="rounded-xl bg-emerald-500 px-5 py-2.5 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                    >
                      Switch to Reviewer / SME (Kavita) to Approve Package →
                    </button>
                  )}
                  <button
                    onClick={() => setActiveTab("sources")}
                    className="rounded-xl border border-zinc-700 bg-neutral-950 px-4 py-2.5 text-xs font-semibold text-zinc-200 hover:border-emerald-500/40"
                  >
                    Browse Permitted PUBLIC & INTERNAL Sources ({sources.length})
                  </button>
                  <button
                    onClick={handleLoadSuccessorPlan}
                    disabled={loading}
                    className="rounded-xl border border-emerald-500/30 bg-zinc-900 px-4 py-2.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-950/40"
                  >
                    Refresh Approval Status
                  </button>
                </div>
              </div>
            ) : (
              /* APPROVED 13-SECTION SUCCESSOR CONTINUATION PLAN */
              <>
                <div className="kh-surface-elevated p-6 space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded bg-emerald-500 px-2.5 py-0.5 font-mono text-xs font-bold text-neutral-950">
                          APPROVED CONTINUATION PLAN · v{continuationPlan.version}
                        </span>
                        <span className="rounded border border-emerald-500/30 bg-emerald-950/30 px-2.5 py-0.5 font-mono text-xs text-emerald-300">
                          Status: {continuationPlan.approval.status.toUpperCase()}
                        </span>
                      </div>
                      <h3 className="text-xl font-bold text-white">{continuationPlan.title}</h3>
                      <p className="text-xs font-mono text-zinc-400">
                        Access Scope Enforced: [{continuationPlan.accessScopeApplied.join(", ")}] ·
                        Restricted Sources Filtered Out:{" "}
                        <strong className="text-emerald-300">
                          {continuationPlan.restrictedSourcesFilteredOut}
                        </strong>{" "}
                        · Approved By:{" "}
                        <strong className="text-zinc-200">
                          {continuationPlan.approval.reviewer || "Reviewer"}
                        </strong>
                      </p>
                    </div>

                    {/* Export Controls */}
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => handleExportPackage("markdown")}
                        disabled={loading}
                        className="rounded-lg border border-emerald-500/40 bg-neutral-950 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-950/50"
                      >
                        Export Markdown
                      </button>
                      <button
                        onClick={() => handleExportPackage("json")}
                        disabled={loading}
                        className="rounded-lg border border-zinc-700 bg-neutral-950 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:border-emerald-500/40"
                      >
                        Export JSON
                      </button>
                    </div>
                  </div>

                  {/* Successor Receipt Acknowledgement Action Bar — Strictly SUCCESSOR only */}
                  {continuationPlan.approval.status === "acknowledged" ? (
                    <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/25 p-4 text-xs text-emerald-200 flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <strong>Handover Receipt Formally Acknowledged</strong> by{" "}
                        <span className="font-mono">{continuationPlan.approval.acknowledgedBy}</span>
                        {continuationPlan.approval.acknowledgementNotes && (
                          <span> — &ldquo;{continuationPlan.approval.acknowledgementNotes}&rdquo;</span>
                        )}
                      </div>
                      <span className="rounded bg-emerald-500 px-2 py-0.5 font-mono text-[10px] font-bold text-neutral-950">
                        CONTINUITY COMPLETE
                      </span>
                    </div>
                  ) : canAcknowledgeHandover ? (
                    <div className="rounded-xl border border-emerald-500/40 bg-neutral-950 p-4 flex flex-wrap items-center justify-between gap-3">
                      <div className="space-y-1">
                        <div className="text-xs font-bold text-emerald-300">
                          Incoming Successor Sign-Off & Receipt Acknowledgement
                        </div>
                        <p className="text-xs text-zinc-400">
                          Confirm that you have reviewed the 13-section continuation plan, blocked
                          tasks, and prioritised next actions.
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <input
                          type="text"
                          aria-label="Acknowledgement Notes"
                          value={ackNotes}
                          onChange={(e) => setAckNotes(e.target.value)}
                          className="w-72 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-white"
                        />
                        <button
                          onClick={handleAcknowledgeReceipt}
                          disabled={loading}
                          className="rounded-xl bg-emerald-500 px-5 py-2 text-xs font-bold text-neutral-950 hover:bg-emerald-400"
                        >
                          Acknowledge Handover Receipt
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-zinc-800 bg-neutral-950 p-3 text-xs text-zinc-400 flex items-center justify-between">
                      <span>
                        Receipt acknowledgement is reserved exclusively for the{" "}
                        <strong>Incoming Successor (Ankit Chaudhari)</strong>.
                      </span>
                      <button
                        onClick={() => handleSelectRoleSession("SUCCESSOR", "successor")}
                        className="rounded-lg border border-emerald-500/40 bg-emerald-950/30 px-3 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-500 hover:text-neutral-950"
                      >
                        Switch to Incoming Successor (Ankit) to Acknowledge →
                      </button>
                    </div>
                  )}

                  {exportedMarkdown && (
                    <div className="rounded-xl border border-zinc-700 bg-neutral-950 p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-emerald-400">
                          Exported Handover Package Artifact
                        </span>
                        <button
                          onClick={() => setExportedMarkdown(null)}
                          className="text-xs text-zinc-400 hover:text-white"
                        >
                          Close Preview
                        </button>
                      </div>
                      <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap font-mono text-xs text-zinc-200">
                        {exportedMarkdown}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Prioritised Next Actions & Verified Claims */}
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <div className="kh-surface p-5 space-y-3">
                    <h4 className="text-sm font-bold text-emerald-400 uppercase tracking-wider font-mono">
                      Prioritised Next Actions for Successor ({continuationPlan.nextActions.length})
                    </h4>
                    <div className="space-y-2.5">
                      {continuationPlan.nextActions.map((act) => (
                        <div
                          key={act.id}
                          className="rounded-lg border border-zinc-800 bg-neutral-950 p-3.5 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-white">
                              #{act.priorityRank} — {act.action}
                            </span>
                            <span className="rounded border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-emerald-300">
                              {act.priority}
                            </span>
                          </div>
                          <p className="text-zinc-400">{act.reason}</p>
                          <div className="font-mono text-[11px] text-zinc-400 pt-1">
                            Owner: {act.owner || "Incoming Successor"} · Linked Claims:{" "}
                            {act.evidenceClaimIds.join(", ")}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="kh-surface p-5 space-y-3">
                    <h4 className="text-sm font-bold text-teal-300 uppercase tracking-wider font-mono">
                      Permitted Evidence-Linked Claims ({continuationPlan.claims.length})
                    </h4>
                    <div className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
                      {continuationPlan.claims.map((c) => (
                        <div
                          key={c.id}
                          className="rounded-lg border border-zinc-800 bg-neutral-950 p-3 text-xs space-y-1.5"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-emerald-400">
                                {c.claimId}
                              </span>
                              <EvidenceStatusBadge
                                status={c.status}
                                isAiGenerated={c.isAiGenerated}
                              />
                            </div>
                            <button
                              onClick={() => setInspectedClaim(c)}
                              className="rounded border border-zinc-700 bg-zinc-900 px-2 py-0.5 font-mono text-[10px] text-emerald-300 hover:border-emerald-500/40"
                            >
                              View Citations ({c.evidence.length})
                            </button>
                          </div>
                          <p className="text-zinc-200">{c.text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* All 13 Structured Sections (Readable Cards, Task Lists, Responsibilities, Risks & Dependencies) */}
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h4 className="text-base font-bold text-white">
                        Complete 13-Section Structured Handover Package
                      </h4>
                      <p className="text-xs text-zinc-400">
                        Organised for rapid engineering onboarding with task lists, ownership
                        responsibilities, dependencies, risks, and validated source citations.
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {Object.entries(continuationPlan.sections).map(([key, val]) => {
                      const meta = SECTION_META[key] || {
                        title: key.replace(/_/g, " ").toUpperCase(),
                        subtitle: "Structured handover continuity section.",
                      };
                      return (
                        <div key={key} className="kh-surface p-5 space-y-3">
                          <div className="border-b border-zinc-800/80 pb-2">
                            <h5 className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-400">
                              {meta.title}
                            </h5>
                            <p className="mt-0.5 text-[11px] text-zinc-400">{meta.subtitle}</p>
                          </div>
                          {renderContinuationSectionContent(key, val)}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* TAB 6: APPEND-ONLY AUDIT TRAIL (PROJECT_LEAD & REVIEWER_SME ONLY) */}
        {activeTab === "audit" && canViewAuditLogs && (
          <div className="kh-surface p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-bold text-white">
                  Immutable Governance & Security Audit Trail ({auditLogs.length} Events)
                </h3>
                <p className="text-xs text-zinc-400">
                  Every role switch, source ingestion, 3-agent reconstruction, claim review,
                  clarification answer, approval, and successor acknowledgement is logged with the
                  authenticated actor.
                </p>
              </div>
              <button
                onClick={handleLoadAuditLogs}
                disabled={loading}
                className="rounded-lg border border-emerald-500/40 bg-neutral-950 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-950/50"
              >
                Refresh Audit Trail
              </button>
            </div>
            <div className="space-y-2">
              {auditLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-neutral-950 px-4 py-2.5 text-xs font-mono"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 font-bold text-emerald-300">
                      {log.action}
                    </span>
                    <span className="text-zinc-300">
                      Actor: {log.actor_email || "system"} ({log.actor_role || "N/A"})
                    </span>
                    <span className="text-zinc-500">
                      Target: {log.target_type}:{log.target_id}
                    </span>
                  </div>
                  <span className="text-zinc-400">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <EvidenceInspectorModal
        isOpen={Boolean(inspectedClaim)}
        onClose={() => setInspectedClaim(null)}
        claimId={inspectedClaim?.claimId || ""}
        claimText={inspectedClaim?.text || ""}
        evidence={inspectedClaim?.evidence || []}
        conflicts={inspectedClaim?.conflicts || []}
        sources={sources}
      />
    </div>
  );
};
