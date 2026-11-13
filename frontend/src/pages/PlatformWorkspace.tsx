import React, { useState } from "react";
import { EvidenceStatusBadge } from "../components/EvidenceStatusBadge";
import { EvidenceInspectorModal } from "../components/EvidenceInspectorModal";
import { useAuth } from "../hooks/useAuth";
import { apiClient } from "../lib/apiClient";
import {
  ClaimReviewState,
  EvidenceStatus,
  HandoverClaim,
  HandoverPackage,
  ProjectRole,
  SourceDocumentItem,
} from "../lib/types";

export const PlatformWorkspace: React.FC = () => {
  const {
    user,
    isAuthenticated,
    login,
    register,
    logout,
    effectiveRole,
    setActiveRoleOverride,
  } = useAuth();

  const [activeTab, setActiveTab] = useState<
    | "landing"
    | "auth"
    | "dashboard"
    | "projects"
    | "sources"
    | "wizard"
    | "review"
    | "successor"
    | "audit"
    | "settings"
  >("landing");

  const [authMode, setAuthMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("preeti.lead@payflow.demo");
  const [password, setPassword] = useState("StrongPassword!123");
  const [fullName, setFullName] = useState("Preeti Satish Mittal");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const [handover, setHandover] = useState<HandoverPackage | null>(null);
  const [continuationPlan, setContinuationPlan] = useState<Record<string, any> | null>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [selectedClaimForModal, setSelectedClaimForModal] = useState<HandoverClaim | null>(null);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});

  // Custom source upload form state
  const [newSourceId, setNewSourceId] = useState("note-custom-01");
  const [newSourceTitle, setNewSourceTitle] = useState("Custom Handover Technical Note");
  const [newSourceType, setNewSourceType] = useState("technical_doc");
  const [newSourceAccess, setNewSourceAccess] = useState("INTERNAL");
  const [newSourceContent, setNewSourceContent] = useState(
    "Settlement reconciliation worker runs every night at 02:00 UTC. Contact @priya.nair if dead-letter queue exceeds 50 messages."
  );

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsLoading(true);
    try {
      if (authMode === "register") {
        await register(email, password, fullName);
        setStatusMessage("Account registered and authenticated with Argon2id + JWT.");
      } else {
        await login(email, password);
        setStatusMessage("Logged in successfully.");
      }
      setActiveTab("dashboard");
    } catch (err: any) {
      // If account already exists on register, auto-fallback to login for smooth demo UX
      if (authMode === "register" && err?.response?.status === 409) {
        try {
          await login(email, password);
          setStatusMessage("Existing demo account logged in.");
          setActiveTab("dashboard");
        } catch (loginErr: any) {
          setErrorMessage(loginErr?.response?.data?.detail || "Authentication failed.");
        }
      } else {
        setErrorMessage(err?.response?.data?.detail || "Authentication failed.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleBootstrapPayFlowDemo = async () => {
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const resp = await apiClient.post("/api/v1/demo/bootstrap-payflow");
      setHandover(resp.data);
      setStatusMessage(
        "PayFlow synthetic dataset seeded, secrets redacted, and 3-Agent LangGraph reconstruction completed!"
      );
      setActiveTab("review");
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Failed to bootstrap PayFlow demo.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleUploadCustomSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!handover) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await apiClient.post(`/api/v1/projects/${handover.projectId}/sources/upload`, {
        stable_source_id: newSourceId,
        source_type: newSourceType,
        title: newSourceTitle,
        content: newSourceContent,
        access_level: newSourceAccess,
        version_tag: "v1",
      });
      await apiClient.post(`/api/handovers/${handover.handoverId}/sources/import`, {
        source_ids: [],
        seed_payflow_if_empty: false,
      });
      const recon = await apiClient.post(`/api/handovers/${handover.handoverId}/reconstruct`);
      setHandover(recon.data);
      setStatusMessage(`Uploaded source '${newSourceId}' (secrets scanned) and re-ran 3-agent reconstruction.`);
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Upload failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateClaimStatus = async (
    claimId: string,
    newStatus: EvidenceStatus,
    reviewState: ClaimReviewState,
    notes?: string
  ) => {
    if (!handover) return;
    setErrorMessage(null);
    try {
      await apiClient.patch(`/api/claims/${claimId}`, {
        status: newStatus,
        review_state: reviewState,
        reviewer_notes: notes || `Updated to ${newStatus} by ${effectiveRole}`,
      });
      const refreshed = await apiClient.get(`/api/handovers/${handover.handoverId}/draft`);
      setHandover(refreshed.data);
      setStatusMessage(`Claim updated to '${newStatus}' (${reviewState}). Audit event recorded.`);
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Failed to update claim.");
    }
  };

  const handleAnswerClarification = async (questionId: string) => {
    if (!handover) return;
    const answerText = clarificationAnswers[questionId];
    if (!answerText || answerText.trim().length < 2) return;
    setErrorMessage(null);
    try {
      await apiClient.post(
        `/api/handovers/${handover.handoverId}/clarifications/${questionId}`,
        {
          answer_text: answerText,
          mark_resolved: true,
        }
      );
      const refreshed = await apiClient.get(`/api/handovers/${handover.handoverId}/draft`);
      setHandover(refreshed.data);
      setStatusMessage("Clarification recorded and linked to claim rationale.");
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Failed to submit clarification.");
    }
  };

  const handleApproveHandover = async () => {
    if (!handover) return;
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const resp = await apiClient.post(`/api/handovers/${handover.handoverId}/approve`, {
        approval_notes: "Human review completed; evidence links and conflicts verified.",
      });
      setHandover(resp.data);
      const succResp = await apiClient.get(
        `/api/handovers/${handover.handoverId}/successor-view`
      );
      setContinuationPlan(succResp.data);
      setStatusMessage(
        `Handover ${handover.handoverId} approved (v${resp.data.currentVersion})! Successor continuation plan unlocked.`
      );
      setActiveTab("successor");
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Approval failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const isGuestDemo = !isAuthenticated || effectiveRole === "GUEST_DEMO";

  const handleLoadSuccessorPlan = async () => {
    if (!handover) return;
    setErrorMessage(null);
    try {
      const succResp = await apiClient.get(
        `/api/handovers/${handover.handoverId}/successor-view`
      );
      setContinuationPlan(succResp.data);
      setActiveTab("successor");
    } catch (err: any) {
      const backendDetail = err?.response?.data?.detail;
      setErrorMessage(
        isGuestDemo
          ? `${backendDetail || "Successor view is protected until human approval."} Sign in as a Reviewer or Project Lead to verify claims and approve the handover package.`
          : backendDetail ||
              "Successor view blocked: Handover must be approved by a human reviewer before sharing."
      );
    }
  };

  const handleAcknowledgeReceipt = async () => {
    if (!handover || isGuestDemo) return;
    setErrorMessage(null);
    try {
      const resp = await apiClient.post(`/api/handovers/${handover.handoverId}/acknowledge`, {
        acknowledgement_notes:
          "Successor reviewed all 13 sections, blocked tasks, and prioritised next actions.",
      });
      setHandover(resp.data);
      const succResp = await apiClient.get(
        `/api/handovers/${handover.handoverId}/successor-view`
      );
      setContinuationPlan(succResp.data);
      setStatusMessage("Successor receipt acknowledged and recorded in the immutable audit log.");
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Acknowledgement failed.");
    }
  };

  const handleLoadAuditLogs = async () => {
    if (!handover) return;
    setErrorMessage(null);
    if (isGuestDemo) {
      setErrorMessage(
        "Audit Trail requires an authenticated Project Lead or Reviewer session. Please sign in to inspect immutable audit logs."
      );
      return;
    }
    try {
      const resp = await apiClient.get(
        `/api/v1/handovers/${handover.handoverId}/audit-logs`
      );
      setAuditLogs(resp.data);
      setActiveTab("audit");
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Failed to load audit trail.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navigation & Judge Role Switcher Bar */}
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-900/95 backdrop-blur px-6 py-3">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/20 border border-teal-500/40 font-bold text-teal-300">
              KH
            </div>
            <div>
              <span className="font-bold tracking-tight text-white">
                Knowledge Handover
              </span>
              <span className="ml-2 rounded bg-slate-800 px-2 py-0.5 text-[11px] text-teal-400 border border-slate-700">
                LangGraph 3-Agent + pgvector
              </span>
            </div>
          </div>

          <nav className="flex flex-wrap items-center gap-1.5 text-xs font-medium">
            <button
              onClick={() => setActiveTab("landing")}
              className={`rounded-md px-3 py-1.5 ${
                activeTab === "landing"
                  ? "bg-teal-600 text-white"
                  : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              Overview
            </button>
            {(isAuthenticated || Boolean(handover)) && (
              <>
                <button
                  onClick={() => setActiveTab("dashboard")}
                  className={`rounded-md px-3 py-1.5 ${
                    activeTab === "dashboard"
                      ? "bg-teal-600 text-white"
                      : "text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  Dashboard
                </button>
                <button
                  onClick={() => setActiveTab("sources")}
                  className={`rounded-md px-3 py-1.5 ${
                    activeTab === "sources"
                      ? "bg-teal-600 text-white"
                      : "text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  Sources & Redaction ({handover?.scopedSources?.length || 0})
                </button>
                <button
                  onClick={() => setActiveTab("review")}
                  className={`rounded-md px-3 py-1.5 ${
                    activeTab === "review"
                      ? "bg-teal-600 text-white"
                      : "text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  Review Workspace ({handover?.claims?.length || 0})
                </button>
                <button
                  onClick={handleLoadSuccessorPlan}
                  className={`rounded-md px-3 py-1.5 ${
                    activeTab === "successor"
                      ? "bg-teal-600 text-white"
                      : "text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  Successor Plan
                </button>
              </>
            )}
            {isAuthenticated && (
              <button
                onClick={handleLoadAuditLogs}
                className={`rounded-md px-3 py-1.5 ${
                  activeTab === "audit"
                    ? "bg-teal-600 text-white"
                    : "text-slate-300 hover:bg-slate-800"
                }`}
              >
                Audit Trail
              </button>
            )}
          </nav>

          {isAuthenticated ? (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400">Perspective:</span>
              <select
                aria-label="Role Perspective Switcher"
                value={effectiveRole}
                onChange={(e) => setActiveRoleOverride(e.target.value as ProjectRole)}
                className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-teal-300"
              >
                <option value="PROJECT_LEAD">Project Lead</option>
                <option value="OUTGOING_DEV">Outgoing Developer</option>
                <option value="REVIEWER_SME">Reviewer / SME</option>
                <option value="SUCCESSOR">Successor (Incoming Dev)</option>
              </select>
              <button
                onClick={logout}
                className="rounded border border-slate-700 px-2.5 py-1 text-slate-400 hover:bg-slate-800"
              >
                Logout
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs">
              <span
                data-testid="guest-demo-badge"
                className="rounded border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 font-semibold text-amber-300"
              >
                GUEST_DEMO (Read-Only)
              </span>
              <button
                onClick={() => setActiveTab("auth")}
                className="rounded-md bg-teal-600 px-3 py-1.5 font-medium text-white hover:bg-teal-500"
              >
                Login / Register
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Status & Error Banners */}
      <div className="mx-auto w-full max-w-7xl px-6 pt-4">
        {statusMessage && (
          <div className="mb-3 flex items-center justify-between rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-4 py-2.5 text-xs text-emerald-200">
            <span>{statusMessage}</span>
            <button onClick={() => setStatusMessage(null)} className="text-emerald-400 font-bold">
              ✕
            </button>
          </div>
        )}
        {errorMessage && (
          <div className="mb-3 flex items-center justify-between rounded-lg border border-rose-500/40 bg-rose-950/40 px-4 py-2.5 text-xs text-rose-200">
            <span>{errorMessage}</span>
            <button onClick={() => setErrorMessage(null)} className="text-rose-400 font-bold">
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <main className="mx-auto w-full max-w-7xl flex-1 p-6">
        {/* 1. LANDING PAGE */}
        {activeTab === "landing" && (
          <div className="space-y-8">
            <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-teal-950/30 p-8 shadow-2xl">
              <span className="inline-flex items-center rounded-full bg-teal-500/10 px-3 py-1 text-xs font-semibold text-teal-400 ring-1 ring-inset ring-teal-500/30">
                Core Paradigm: Evidence Before Assertion • Uncertainty Shown, Never Hidden • Human Approval Gate
              </span>
              <h1 className="mt-4 text-4xl font-extrabold tracking-tight text-white">
                Prevent Critical Project Knowledge From Leaving With People
              </h1>
              <p className="mt-3 max-w-3xl text-base text-slate-300">
                Knowledge Handover converts scattered software artefacts (issues, pull requests, ADRs, meeting notes, and technical docs) into an evidence-linked, conflict-aware, human-approved handover package and prioritised continuation plan.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                {!isAuthenticated && (
                  <button
                    onClick={handleBootstrapPayFlowDemo}
                    disabled={isLoading}
                    className="rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-teal-500 disabled:opacity-50"
                  >
                    {isLoading
                      ? "Bootstrapping PayFlow Demo..."
                      : "Try Instant PayFlow Demo (Read-Only)"}
                  </button>
                )}
                <button
                  onClick={() => setActiveTab(isAuthenticated ? "dashboard" : "auth")}
                  className={`rounded-lg px-5 py-2.5 text-sm font-semibold shadow ${
                    isAuthenticated
                      ? "bg-teal-600 text-white hover:bg-teal-500"
                      : "border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700"
                  }`}
                >
                  {isAuthenticated ? "Open Handover Workspace" : "Get Started — Login / Register"}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
              {[
                { step: "01 CONNECT", desc: "Scope project & ingest authorised sources with automatic secret redaction." },
                { step: "02 RECONSTRUCT", desc: "LangGraph orchestrates Knowledge Extraction & Risk/Dependency agents." },
                { step: "03 CLARIFY", desc: "Turn missing rationale & unknown owners into targeted outgoing dev questions." },
                { step: "04 VERIFY & REVIEW", desc: "Side-by-side conflict & staleness inspection; human approval gate." },
                { step: "05 HANDOVER", desc: "Role-filtered 13-section Continuation Plan with receipt acknowledgement." },
              ].map((item) => (
                <div
                  key={item.step}
                  className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
                >
                  <div className="text-xs font-bold text-teal-400">{item.step}</div>
                  <p className="mt-2 text-xs text-slate-300">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 2. AUTHENTICATION PAGE (LOGIN / REGISTER) */}
        {activeTab === "auth" && (
          <div className="mx-auto max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <div className="flex gap-2 border-b border-slate-800 pb-3">
              <button
                type="button"
                onClick={() => setAuthMode("register")}
                className={`flex-1 rounded py-1.5 text-xs font-semibold ${
                  authMode === "register" ? "bg-teal-600 text-white" : "text-slate-400"
                }`}
              >
                Register Demo Account
              </button>
              <button
                type="button"
                onClick={() => setAuthMode("login")}
                className={`flex-1 rounded py-1.5 text-xs font-semibold ${
                  authMode === "login" ? "bg-teal-600 text-white" : "text-slate-400"
                }`}
              >
                Sign In
              </button>
            </div>
            <form onSubmit={handleAuthSubmit} className="mt-4 space-y-4">
              {authMode === "register" && (
                <div>
                  <label className="block text-xs font-medium text-slate-300">Full Name</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                  />
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-slate-300">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300">
                  Password (min 8 chars, Argon2id hashed)
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                />
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-lg bg-teal-600 py-2.5 text-sm font-semibold text-white hover:bg-teal-500 disabled:opacity-50"
              >
                {isLoading
                  ? "Authenticating..."
                  : authMode === "register"
                  ? "Register & Continue"
                  : "Sign In"}
              </button>
            </form>
          </div>
        )}

        {/* 3. DASHBOARD & ONE-CLICK PAYFLOW DEMO INITIALIZER */}
        {activeTab === "dashboard" && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900 p-6">
              <div>
                <h2 className="text-xl font-bold text-white">
                  Welcome, {user?.full_name || "Engineer"} ({effectiveRole})
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  Launch the synthetic PayFlow Payment Gateway handover scenario (with seeded conflicts, stale API docs, unassigned blockers, and secret redaction).
                </p>
              </div>
              <button
                onClick={handleBootstrapPayFlowDemo}
                disabled={isLoading}
                className="rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-teal-500 disabled:opacity-50"
              >
                {isLoading
                  ? "Running 3-Agent LangGraph Reconstruction..."
                  : "Seed PayFlow Dataset & Run 3-Agent Reconstruction"}
              </button>
            </div>

            {handover && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                  <div className="text-xs text-slate-400">Active Handover Package</div>
                  <div className="mt-1 text-lg font-bold text-white">{handover.handoverId}</div>
                  <div className="mt-1 text-xs text-teal-400">
                    Status: {handover.status} (v{handover.currentVersion})
                  </div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                  <div className="text-xs text-slate-400">Extracted Claims</div>
                  <div className="mt-1 text-2xl font-bold text-white">
                    {handover.claims.length}
                  </div>
                  <div className="mt-1 text-xs text-rose-400">
                    Conflicts / Stale:{" "}
                    {
                      handover.claims.filter(
                        (c) =>
                          c.status === "conflicting" || c.status === "potentially_outdated"
                      ).length
                    }
                  </div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                  <div className="text-xs text-slate-400">Blockers, Risks & Dependencies</div>
                  <div className="mt-1 text-2xl font-bold text-white">
                    {handover.risksAndDependencies.length}
                  </div>
                  <div className="mt-1 text-xs text-amber-400">
                    Open Questions: {handover.openQuestions.length}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                  <div className="text-xs text-slate-400">Human Approval Gate</div>
                  <div className="mt-1 text-lg font-bold uppercase text-white">
                    {handover.approval.status}
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    Reviewer: {handover.approval.reviewer || "Pending sign-off"}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 4. SOURCE MANAGEMENT & SECRET REDACTION VIEW */}
        {activeTab === "sources" && handover && (
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="text-lg font-bold text-white">
                Scoped Project Sources & Secret Redaction Inventory
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                Scope clearance applied: {handover.scopedSources.length} authorised records. Any RESTRICTED records outside handover clearance are excluded before RAG retrieval.
              </p>
              <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                {handover.scopedSources.map((src: SourceDocumentItem) => (
                  <div
                    key={src.id}
                    className="rounded-lg border border-slate-800 bg-slate-950 p-4 space-y-2"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-bold text-teal-400">
                        {src.stable_source_id}
                      </span>
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300">
                        {src.source_type} • {src.access_level}
                      </span>
                    </div>
                    <div className="text-sm font-semibold text-white">{src.title}</div>
                    <p className="text-xs text-slate-400 line-clamp-3 font-mono">
                      {src.content_redacted}
                    </p>
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>Updated: {new Date(src.source_updated_at).toLocaleDateString()}</span>
                      <span>Version: {src.version_tag}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {isGuestDemo ? (
              <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-5 text-xs text-amber-200 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <strong>Read-Only Guest Demo Scope (PUBLIC & INTERNAL):</strong> Custom source upload and RESTRICTED records (e.g., <code className="font-mono">restricted-vendor-note</code>) are protected. Sign in to upload sources or manage clearances.
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("auth")}
                  className="rounded-md bg-teal-600 px-3 py-1.5 font-semibold text-white hover:bg-teal-500"
                >
                  Login / Register
                </button>
              </div>
            ) : (
              <form
                onSubmit={handleUploadCustomSource}
                className="rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4"
              >
                <h3 className="text-sm font-bold text-white">
                  Ingest Additional Project Record (Automatic Secret Scanning & Chunking)
                </h3>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <input
                    type="text"
                    value={newSourceId}
                    onChange={(e) => setNewSourceId(e.target.value)}
                    placeholder="stable_source_id"
                    className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                  />
                  <input
                    type="text"
                    value={newSourceTitle}
                    onChange={(e) => setNewSourceTitle(e.target.value)}
                    placeholder="Source Title"
                    className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                  />
                  <select
                    value={newSourceType}
                    onChange={(e) => setNewSourceType(e.target.value)}
                    className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                  >
                    <option value="technical_doc">Technical Document</option>
                    <option value="synthetic_issue">Issue</option>
                    <option value="pull_request">Pull Request</option>
                    <option value="adr">ADR</option>
                    <option value="meeting_note">Meeting Note</option>
                  </select>
                </div>
                <textarea
                  rows={3}
                  value={newSourceContent}
                  onChange={(e) => setNewSourceContent(e.target.value)}
                  className="w-full rounded border border-slate-700 bg-slate-950 p-3 text-xs text-white font-mono"
                />
                <button
                  type="submit"
                  disabled={isLoading}
                  className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-500"
                >
                  Ingest Source & Re-Run Reconstruction
                </button>
              </form>
            )}
          </div>
        )}

        {/* 5. HUMAN REVIEW WORKSPACE, CONFLICT RESOLUTION & CLARIFICATION LOOP */}
        {activeTab === "review" && handover && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900 p-6">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-teal-400">{handover.handoverId}</span>
                  <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                    Version {handover.currentVersion}
                  </span>
                </div>
                <h2 className="mt-1 text-xl font-bold text-white">{handover.title}</h2>
                <p className="mt-1 text-xs text-slate-300">{handover.summary.text}</p>
              </div>
              <div className="flex items-center gap-3">
                {!isGuestDemo &&
                (effectiveRole === "PROJECT_LEAD" || effectiveRole === "REVIEWER_SME") ? (
                  <button
                    onClick={handleApproveHandover}
                    disabled={isLoading}
                    className="rounded-lg bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white shadow hover:bg-emerald-500"
                  >
                    Approve Handover Package & Unlock Successor View
                  </button>
                ) : isGuestDemo ? (
                  <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-950/20 px-3.5 py-2 text-xs text-amber-200">
                    <span>Read-Only Guest Demo — Sign in to verify claims & approve package</span>
                    <button
                      type="button"
                      onClick={() => setActiveTab("auth")}
                      className="rounded bg-teal-600 px-2.5 py-1 font-semibold text-white hover:bg-teal-500"
                    >
                      Sign In
                    </button>
                  </div>
                ) : null}
              </div>
            </div>

            {/* Claims Review List */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                Extracted Claims & Evidence Status ({handover.claims.length})
              </h3>
              {handover.claims.map((claim) => (
                <div
                  key={claim.id}
                  className="rounded-xl border border-slate-800 bg-slate-900/90 p-5 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-teal-400">
                        {claim.claimId}
                      </span>
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                        {claim.type}
                      </span>
                      <EvidenceStatusBadge
                        status={claim.status}
                        isAiGenerated={claim.isAiGenerated}
                      />
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-400">
                        Owner:{" "}
                        <strong className="text-white">
                          {claim.owner || "UNKNOWN (Unassigned in evidence)"}
                        </strong>
                      </span>
                      <button
                        onClick={() => setSelectedClaimForModal(claim)}
                        className="rounded border border-teal-500/40 bg-teal-500/10 px-3 py-1 text-xs font-semibold text-teal-300 hover:bg-teal-500/20"
                      >
                        Inspect Citations ({claim.evidence.length})
                        {claim.conflicts.length > 0
                          ? ` & Conflicts (${claim.conflicts.length})`
                          : ""}
                      </button>
                    </div>
                  </div>

                  <p className="text-sm font-medium text-white">{claim.text}</p>
                  {claim.rationale && (
                    <p className="text-xs text-slate-400">
                      <strong>Rationale / Context:</strong> {claim.rationale}
                    </p>
                  )}

                  {claim.conflicts.length > 0 && (
                    <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-200">
                      <strong>Contradiction / Staleness Surfaced:</strong>{" "}
                      {claim.conflicts[0].explanation}
                    </div>
                  )}

                  {/* Reviewer Controls */}
                  {!isGuestDemo &&
                    (effectiveRole === "PROJECT_LEAD" ||
                      effectiveRole === "REVIEWER_SME" ||
                      effectiveRole === "OUTGOING_DEV") && (
                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-3 text-xs">
                      <span className="text-slate-400">
                        Review State: <strong className="text-slate-200">{claim.reviewState}</strong>
                        {claim.reviewerNotes ? ` — "${claim.reviewerNotes}"` : ""}
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {(effectiveRole === "PROJECT_LEAD" ||
                          effectiveRole === "REVIEWER_SME") && (
                          <button
                            onClick={() =>
                              handleUpdateClaimStatus(
                                claim.id,
                                "verified",
                                "approved",
                                "Human reviewer verified source support."
                              )
                            }
                            className="rounded bg-emerald-600/20 border border-emerald-500/40 px-2.5 py-1 text-emerald-300 hover:bg-emerald-600/30"
                          >
                            Mark Verified
                          </button>
                        )}
                        <button
                          onClick={() =>
                            handleUpdateClaimStatus(
                              claim.id,
                              claim.status,
                              "clarification_requested",
                              "Needs outgoing developer clarification."
                            )
                          }
                          className="rounded bg-amber-600/20 border border-amber-500/40 px-2.5 py-1 text-amber-300 hover:bg-amber-600/30"
                        >
                          Flag Unresolved
                        </button>
                        <button
                          onClick={() =>
                            handleUpdateClaimStatus(
                              claim.id,
                              "unknown",
                              "rejected",
                              "Rejected during human review."
                            )
                          }
                          className="rounded bg-rose-600/20 border border-rose-500/40 px-2.5 py-1 text-rose-300 hover:bg-rose-600/30"
                        >
                          Reject Claim
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Clarification Loop for Outgoing Developer */}
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4">
              <h3 className="text-sm font-bold text-white">
                Outgoing Developer Clarification Loop ({handover.openQuestions.length} Open Questions)
              </h3>
              {handover.openQuestions.map((q) => (
                <div
                  key={q.id}
                  className="rounded-lg border border-slate-800 bg-slate-950 p-4 space-y-2"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-amber-300">{q.question}</span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] uppercase text-slate-300">
                      Status: {q.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Reason: {q.reason}</p>
                  {q.answerText ? (
                    <div className="rounded border border-emerald-500/30 bg-emerald-950/20 p-2.5 text-xs text-emerald-200">
                      <strong>Recorded Clarification:</strong> {q.answerText}
                    </div>
                  ) : isGuestDemo ? (
                    <div className="pt-1 text-xs text-slate-400 italic">
                      Read-only in Guest Demo mode. Sign in as Outgoing Developer or Project Lead to submit clarification answers.
                    </div>
                  ) : (
                    <div className="flex gap-2 pt-1">
                      <input
                        type="text"
                        placeholder="Provide outgoing developer context or decision rationale..."
                        value={clarificationAnswers[q.id] || ""}
                        onChange={(e) =>
                          setClarificationAnswers({
                            ...clarificationAnswers,
                            [q.id]: e.target.value,
                          })
                        }
                        className="flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-white"
                      />
                      <button
                        onClick={() => handleAnswerClarification(q.id)}
                        className="rounded bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-500"
                      >
                        Submit Answer
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 6. SUCCESSOR 13-SECTION CONTINUATION PLAN & ACKNOWLEDGEMENT */}
        {activeTab === "successor" && continuationPlan && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-teal-500/30 bg-slate-900 p-6">
              <div>
                <span className="rounded bg-emerald-500/20 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">
                  Human-Approved Continuation Package • Scope:{" "}
                  {continuationPlan.accessScopeApplied.join(", ")} (
                  {continuationPlan.restrictedSourcesFilteredOut} Restricted Source Excluded)
                </span>
                <h2 className="mt-2 text-2xl font-bold text-white">
                  {continuationPlan.title} — Successor Continuation Plan
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  Approved by: {continuationPlan.approval.reviewer} • Status:{" "}
                  {continuationPlan.approval.status.toUpperCase()}
                </p>
              </div>
              {!isGuestDemo && (
                <button
                  onClick={handleAcknowledgeReceipt}
                  disabled={continuationPlan.approval.status === "acknowledged"}
                  className="rounded-lg bg-teal-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-teal-500 disabled:bg-slate-700"
                >
                  {continuationPlan.approval.status === "acknowledged"
                    ? "Receipt Acknowledged ✓"
                    : "Acknowledge Handover Receipt"}
                </button>
              )}
            </div>

            {/* Prioritised Next Actions */}
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-teal-400">
                Prioritised Next Actions for Incoming Developer
              </h3>
              {continuationPlan.nextActions.map((act: any) => (
                <div
                  key={act.id}
                  className="flex items-start justify-between gap-4 rounded-lg border border-slate-800 bg-slate-950 p-4"
                >
                  <div>
                    <span className="rounded bg-teal-500/20 px-2 py-0.5 font-mono text-xs font-bold text-teal-300">
                      #{act.priorityRank} [{act.priority.toUpperCase()}]
                    </span>
                    <p className="mt-1.5 text-sm font-semibold text-white">{act.action}</p>
                    <p className="mt-1 text-xs text-slate-400">Reason: {act.reason}</p>
                  </div>
                  <div className="text-right text-xs text-slate-400">
                    <div>Suggested Owner: {act.owner || "Unassigned"}</div>
                    <div className="font-mono text-teal-400">
                      Linked: {act.evidenceClaimIds.join(", ")}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Risks, Blockers & Dependencies */}
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-amber-400">
                Blockers, Operational Risks & Evidence-Backed Dependencies
              </h3>
              {continuationPlan.risksAndDependencies.map((item: any) => (
                <div
                  key={item.id}
                  className="rounded-lg border border-slate-800 bg-slate-950 p-4 space-y-1"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold uppercase text-amber-300">
                      [{item.recordType}] {item.title}
                    </span>
                    <span className="font-mono text-slate-400">
                      Sources: {item.evidenceSourceIds.join(", ")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">{item.description}</p>
                  {item.workaround && (
                    <p className="text-xs text-teal-300">Workaround: {item.workaround}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 7. APPEND-ONLY AUDIT TRAIL */}
        {activeTab === "audit" && (
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4">
            <h2 className="text-lg font-bold text-white">
              Immutable Append-Only Audit Log ({auditLogs.length} Events)
            </h2>
            <div className="space-y-2">
              {auditLogs.map((ev) => (
                <div
                  key={ev.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-800 bg-slate-950 px-4 py-2.5 text-xs"
                >
                  <div>
                    <span className="font-mono font-bold text-teal-400">{ev.action}</span>
                    <span className="ml-2 text-slate-300">
                      Target: {ev.target_type} ({ev.target_id})
                    </span>
                    <span className="ml-2 text-slate-400">
                      Actor: {ev.actor_email || "System"} ({ev.actor_role})
                    </span>
                  </div>
                  <span className="font-mono text-slate-500">
                    {new Date(ev.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Evidence & Conflict Inspector Modal */}
      {selectedClaimForModal && handover && (
        <EvidenceInspectorModal
          isOpen={Boolean(selectedClaimForModal)}
          onClose={() => setSelectedClaimForModal(null)}
          claimId={selectedClaimForModal.claimId}
          claimText={selectedClaimForModal.text}
          evidence={selectedClaimForModal.evidence}
          conflicts={selectedClaimForModal.conflicts}
          sources={handover.scopedSources}
        />
      )}
    </div>
  );
};
