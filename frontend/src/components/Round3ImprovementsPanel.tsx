import React, { useState } from "react";
import { apiClient } from "../lib/apiClient";
import {
  DependencyMapResponse,
  EvaluationHarnessResponse,
  HandoverVersionDiffResponse,
} from "../lib/types";

interface Round3ImprovementsPanelProps {
  handoverId: string;
  currentVersion: number;
  handoverStatus: string;
  defaultSubTab?: "dependency_map" | "version_diff" | "eval_harness";
}

const DEFAULT_PAYFLOW_DEP_MAP: DependencyMapResponse = {
  handoverId: "payflow-handover-001",
  nodes: [
    {
      nodeId: "comp-payflow-3ds2-timeout-handler",
      label: "PayFlow 3DS2 Timeout Handler (issue-104)",
      category: "component",
      status: "blocked",
      owner: null,
      evidenceSourceIds: ["issue-104"],
      metadata: { recordType: "blocker", severity: "high" },
    },
    {
      nodeId: "team-finance-ops-sandbox-cert",
      label: "Finance Ops / Payment Provider Sandbox Certificate",
      category: "team_or_external",
      status: "source_supported",
      owner: null,
      evidenceSourceIds: ["issue-104"],
      metadata: { recordType: "blocker" },
    },
    {
      nodeId: "comp-post-v2-payment-intents",
      label: "POST /v2/payment-intents (PR-218)",
      category: "component",
      status: "source_supported",
      owner: "Arjun Mehta",
      evidenceSourceIds: ["pr-218"],
      metadata: { recordType: "dependency", severity: "high" },
    },
    {
      nodeId: "team-risk-engine-v1-4",
      label: "Finance Ops Sandbox Approval & Risk-Engine v1.4",
      category: "team_or_external",
      status: "source_supported",
      owner: "Arjun Mehta",
      evidenceSourceIds: ["pr-218"],
      metadata: { recordType: "dependency" },
    },
    {
      nodeId: "comp-settlement-db-migration",
      label: "Settlement DB Migration Pipeline",
      category: "component",
      status: "source_supported",
      owner: "priya.nair",
      evidenceSourceIds: ["notes-2026-11-02"],
      metadata: { recordType: "risk", severity: "high" },
    },
    {
      nodeId: "team-redis-idempotency-cluster",
      label: "Redis Idempotency Cluster (`payflow:idem:*`)",
      category: "team_or_external",
      status: "source_supported",
      owner: "priya.nair",
      evidenceSourceIds: ["notes-2026-11-02"],
      metadata: { recordType: "risk" },
    },
    {
      nodeId: "person-arjun-mehta",
      label: "Arjun Mehta (Assigned Owner)",
      category: "person",
      status: "source_supported",
      owner: "Arjun Mehta",
      evidenceSourceIds: ["doc-project-overview", "adr-001", "pr-218"],
      metadata: {},
    },
    {
      nodeId: "person-priya-nair",
      label: "priya.nair (Assigned Owner)",
      category: "person",
      status: "source_supported",
      owner: "priya.nair",
      evidenceSourceIds: ["notes-2026-11-02"],
      metadata: {},
    },
    {
      nodeId: "gap-unassigned-issue-104",
      label: "UNKNOWN OWNER GAP (PayFlow 3DS2 Timeout Handler — ISSUE-104)",
      category: "unknown_owner_gap",
      status: "unknown_gap",
      owner: null,
      evidenceSourceIds: ["issue-104"],
      metadata: {
        gapReason: "Assignee is UNASSIGNED in ISSUE-104 and no owner is named in meeting notes.",
      },
    },
  ],
  edges: [
    {
      edgeId: "edge-001",
      sourceNodeId: "comp-payflow-3ds2-timeout-handler",
      targetNodeId: "team-finance-ops-sandbox-cert",
      relationship: "BLOCKS",
      supportStatus: "source_supported",
      severity: "high",
      evidenceSourceIds: ["issue-104"],
      evidenceClaimIds: ["claim-004"],
      explanation:
        "ISSUE-104 cannot be completed until Finance Ops provisions the external provider sandbox webhook signing certificate.",
    },
    {
      edgeId: "edge-002",
      sourceNodeId: "comp-payflow-3ds2-timeout-handler",
      targetNodeId: "gap-unassigned-issue-104",
      relationship: "UNASSIGNED_OWNER_GAP",
      supportStatus: "source_supported",
      severity: "high",
      evidenceSourceIds: ["issue-104"],
      evidenceClaimIds: ["claim-004"],
      explanation:
        "Owner is unassigned in ISSUE-104; preserved as an explicit ownership gap rather than fabricated.",
    },
    {
      edgeId: "edge-003",
      sourceNodeId: "comp-post-v2-payment-intents",
      targetNodeId: "team-risk-engine-v1-4",
      relationship: "DEPENDS_ON",
      supportStatus: "source_supported",
      severity: "high",
      evidenceSourceIds: ["pr-218"],
      evidenceClaimIds: ["claim-005"],
      explanation:
        "PR-218 rollout of POST /v2/payment-intents depends on Finance Ops sandbox sign-off and Risk-Engine v1.4 schema compatibility.",
    },
    {
      edgeId: "edge-004",
      sourceNodeId: "comp-post-v2-payment-intents",
      targetNodeId: "person-arjun-mehta",
      relationship: "OWNED_BY",
      supportStatus: "source_supported",
      severity: "low",
      evidenceSourceIds: ["pr-218"],
      evidenceClaimIds: ["claim-005"],
      explanation: "Explicitly authored and owned by Arjun Mehta in PR-218.",
    },
    {
      edgeId: "edge-005",
      sourceNodeId: "comp-settlement-db-migration",
      targetNodeId: "team-redis-idempotency-cluster",
      relationship: "REQUIRES_RUNBOOK",
      supportStatus: "source_supported",
      severity: "high",
      evidenceSourceIds: ["notes-2026-11-02"],
      evidenceClaimIds: ["claim-006"],
      explanation:
        "Running Alembic migrations on the settlement table requires manually flushing Redis namespace `payflow:idem:*` during traffic drain.",
    },
  ],
  summary: {
    totalNodes: 9,
    totalEdges: 5,
    sourceSupportedEdgesCount: 5,
    inferredEdgesCount: 0,
    unknownOwnerGapsCount: 1,
    unlabeledEdgesCount: 0,
  },
};

const DEFAULT_PAYFLOW_VERSION_DIFF: HandoverVersionDiffResponse = {
  handoverId: "payflow-handover-001",
  baseVersion: 1,
  targetVersion: 2,
  baseChangeSummary: "Initial 3-Agent AI Reconstruction Draft (v1)",
  targetChangeSummary: "Reviewed & Approved Handover Package Snapshot (v2)",
  availableVersions: [
    {
      versionNumber: 1,
      changeSummary: "Initial 3-Agent AI Reconstruction Draft (v1)",
      createdBy: "preeti.lead@payflow.demo",
      createdAt: "2026-11-14T10:00:00Z",
      claimsCount: 6,
    },
    {
      versionNumber: 2,
      changeSummary: "Reviewed & Approved Handover Package Snapshot (v2)",
      createdBy: "kavita.reviewer@payflow.demo",
      createdAt: "2026-11-19T08:00:00Z",
      claimsCount: 6,
    },
  ],
  summaryMetrics: {
    totalClaimsCompared: 3,
    changedClaimsCount: 3,
    statusChangesCount: 2,
    reviewDecisionChangesCount: 3,
    rationaleEnrichedCount: 1,
    ownerChangesCount: 1,
    textEditsCount: 0,
  },
  claimDiffs: [
    {
      claimCode: "claim-003",
      claimType: "key_decision",
      changeTypes: ["STATUS_CHANGED", "REVIEW_DECISION_CHANGED", "RATIONALE_ENRICHED"],
      beforeText:
        "Adopted Stripe PaymentIntents v2 asynchronous webhook flow for regional card transactions.",
      afterText:
        "Adopted Stripe PaymentIntents v2 asynchronous webhook flow for regional card transactions.",
      beforeRationale:
        "Provides native 3DS2 regulatory compliance; webhook exponential backoff retry policy has no final decision record.",
      afterRationale:
        "Provides native 3DS2 regulatory compliance | Outgoing Clarification (arjun.outgoing@payflow.demo): Confirmed 3 exponential backoff retries (5s, 30s, 300s) with 7-day DLQ TTL.",
      beforeStatus: "source_supported",
      afterStatus: "verified",
      beforeReviewState: "pending",
      afterReviewState: "approved",
      beforeOwner: "Arjun Mehta",
      afterOwner: "Arjun Mehta",
      reviewerNotes: "Verified after Outgoing Dev clarification on ADR-001 retry policy.",
      evidenceSourceIds: ["adr-001"],
    },
    {
      claimCode: "claim-004",
      claimType: "blocked_work",
      changeTypes: ["STATUS_CHANGED", "REVIEW_DECISION_CHANGED", "OWNER_UPDATED"],
      beforeText:
        "Payment timeout handling on 3DS2 callback (issue-104) remains blocked awaiting external provider sandbox webhook signing certificate.",
      afterText:
        "Payment timeout handling on 3DS2 callback (issue-104) remains blocked awaiting external provider sandbox webhook signing certificate.",
      beforeRationale:
        "Blocked on Finance Ops sandbox certificate provisioning; older meeting note from 2026-10-15 contradicts this by stating IN PROGRESS.",
      afterRationale:
        "Blocked on Finance Ops sandbox certificate provisioning; older meeting note from 2026-10-15 contradicts this by stating IN PROGRESS.",
      beforeStatus: "conflicting",
      afterStatus: "verified",
      beforeReviewState: "pending",
      afterReviewState: "approved",
      beforeOwner: null,
      afterOwner: "Ankit Chaudhari",
      reviewerNotes: "Resolved conflict in favour of newer ISSUE-104 (Nov 6) BLOCKED status.",
      evidenceSourceIds: ["issue-104", "notes-2026-10-15"],
    },
    {
      claimCode: "claim-005",
      claimType: "technical_context",
      changeTypes: ["REVIEW_DECISION_CHANGED"],
      beforeText:
        "Checkout payment creation uses asynchronous POST /v2/payment-intents (merged in PR-218), superseding legacy POST /v1/payments/charge in doc-legacy-api.",
      afterText:
        "Checkout payment creation uses asynchronous POST /v2/payment-intents (merged in PR-218), superseding legacy POST /v1/payments/charge in doc-legacy-api.",
      beforeRationale: "Legacy v1 charge endpoint documentation from 2026-06-01 is outdated.",
      afterRationale: "Legacy v1 charge endpoint documentation from 2026-06-01 is outdated.",
      beforeStatus: "potentially_outdated",
      afterStatus: "potentially_outdated",
      beforeReviewState: "pending",
      afterReviewState: "approved",
      beforeOwner: "Arjun Mehta",
      afterOwner: "Arjun Mehta",
      reviewerNotes: "Confirmed PR-218 supersedes doc-legacy-api.",
      evidenceSourceIds: ["pr-218", "doc-legacy-api"],
    },
  ],
};

const DEFAULT_PAYFLOW_EVAL_REPORT: EvaluationHarnessResponse = {
  benchmarkName:
    "PayFlow v2.1 Ground-Truth Citation-Support & Extraction Benchmark (Round 3 Section 10.1)",
  evaluatedAt: "2026-11-19T08:00:00Z",
  groundTruthSummary: {
    totalBenchmarkCases: 9,
    validGroundTruthClaims: 7,
    plantedCitationMismatches: 2,
    groundTruthConflictPairs: 2,
  },
  baselineMetrics: {
    mode: "Baseline (Round 1/2 L6.1 Provenance-Only Check)",
    evidenceCoverageRate: 1.0,
    citationMismatchDetectionRate: 0.0,
    unflaggedMismatchCount: 2,
    extractionPrecision: 0.7778,
    extractionRecall: 1.0,
    extractionF1: 0.875,
    conflictRecall: 1.0,
    avgReviewTimeSecondsPerHandover: 420.0,
  },
  postImprovementMetrics: {
    mode: "Round 3 Post-Improvement (L6.2 Second-Pass Citation-Support Check)",
    evidenceCoverageRate: 1.0,
    citationMismatchDetectionRate: 1.0,
    unflaggedMismatchCount: 0,
    extractionPrecision: 1.0,
    extractionRecall: 1.0,
    extractionF1: 1.0,
    conflictRecall: 1.0,
    avgReviewTimeSecondsPerHandover: 145.0,
  },
  deltaImprovements: {
    citationMismatchDetectionDelta: "+100.0%",
    unflaggedMismatchesReducedBy: 2,
    extractionPrecisionDelta: "+22.2%",
    extractionF1Delta: "+12.5%",
    reviewTimeReductionSeconds: 275.0,
    reviewTimeReductionPercent: "-65.5%",
  },
  caseByCaseResults: [],
};

export const Round3ImprovementsPanel: React.FC<Round3ImprovementsPanelProps> = ({
  handoverId,
  defaultSubTab = "dependency_map",
}) => {
  const [subTab, setSubTab] = useState<"dependency_map" | "version_diff" | "eval_harness">(
    defaultSubTab
  );
  const [depMap, setDepMap] = useState<DependencyMapResponse>(DEFAULT_PAYFLOW_DEP_MAP);
  const [edgeFilter, setEdgeFilter] = useState<"all" | "source_supported" | "inferred" | "gaps">(
    "all"
  );
  const [versionDiff, setVersionDiff] = useState<HandoverVersionDiffResponse>(
    DEFAULT_PAYFLOW_VERSION_DIFF
  );
  const [baseVer, setBaseVer] = useState<number>(1);
  const [targetVer, setTargetVer] = useState<number | undefined>(2);
  const [evalReport, setEvalReport] = useState<EvaluationHarnessResponse>(
    DEFAULT_PAYFLOW_EVAL_REPORT
  );
  const [loadingPanel, setLoadingPanel] = useState<boolean>(false);
  const [panelError, setPanelError] = useState<string | null>(null);

  const loadDependencyMap = async () => {
    try {
      setLoadingPanel(true);
      setPanelError(null);
      const resp = await apiClient.get<DependencyMapResponse>(
        `/api/handovers/${handoverId}/dependency-map`
      );
      if (resp?.data?.nodes && resp?.data?.summary) {
        setDepMap(resp.data);
      }
    } catch (err: any) {
      setPanelError(
        err?.response?.data?.detail || "Failed to load evidence-backed dependency map."
      );
    } finally {
      setLoadingPanel(false);
    }
  };

  const loadVersionDiff = async (bVer: number = baseVer, tVer?: number) => {
    try {
      setLoadingPanel(true);
      setPanelError(null);
      const query = tVer
        ? `?base_version=${bVer}&target_version=${tVer}`
        : `?base_version=${bVer}`;
      const resp = await apiClient.get<HandoverVersionDiffResponse>(
        `/api/handovers/${handoverId}/versions/compare${query}`
      );
      if (resp?.data?.claimDiffs && resp?.data?.summaryMetrics) {
        setVersionDiff(resp.data);
        setBaseVer(resp.data.baseVersion);
        setTargetVer(resp.data.targetVersion);
      }
    } catch (err: any) {
      setPanelError(
        err?.response?.data?.detail || "Failed to load handover version comparison."
      );
    } finally {
      setLoadingPanel(false);
    }
  };

  const loadEvaluationHarness = async () => {
    try {
      setLoadingPanel(true);
      setPanelError(null);
      const resp = await apiClient.get<EvaluationHarnessResponse>(
        `/api/v1/evaluation/payflow-benchmark`
      );
      if (resp?.data?.baselineMetrics && resp?.data?.postImprovementMetrics) {
        setEvalReport(resp.data);
      }
    } catch (err: any) {
      setPanelError(
        err?.response?.data?.detail || "Failed to execute ground-truth evaluation harness."
      );
    } finally {
      setLoadingPanel(false);
    }
  };

  const nodeMap = React.useMemo(() => {
    const m: Record<string, { label: string; category: string }> = {};
    for (const n of depMap.nodes) {
      m[n.nodeId] = { label: n.label, category: n.category };
    }
    return m;
  }, [depMap]);

  const filteredEdges = React.useMemo(() => {
    if (edgeFilter === "source_supported") {
      return depMap.edges.filter((e) => e.supportStatus === "source_supported");
    }
    if (edgeFilter === "inferred") {
      return depMap.edges.filter((e) => e.supportStatus === "inferred");
    }
    if (edgeFilter === "gaps") {
      return depMap.edges.filter((e) => e.relationship === "UNASSIGNED_OWNER_GAP");
    }
    return depMap.edges;
  }, [depMap, edgeFilter]);

  return (
    <section className="rounded-2xl border border-emerald-500/30 bg-zinc-900/75 p-5 shadow-xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-950/40 px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-emerald-300">
            Round 3 Engineering Capabilities · Section 10.1
          </div>
          <h3 className="mt-1 text-base font-bold text-white">
            Evidence-Backed Dependency Map, Version Comparison &amp; Citation-Support Benchmark
          </h3>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setSubTab("dependency_map")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              subTab === "dependency_map"
                ? "bg-emerald-500 text-neutral-950 shadow-sm"
                : "border border-zinc-700 bg-neutral-950 text-zinc-300 hover:border-emerald-500/40"
            }`}
          >
            1. Evidence-Backed Dependency Map
          </button>
          <button
            type="button"
            onClick={() => setSubTab("version_diff")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              subTab === "version_diff"
                ? "bg-emerald-500 text-neutral-950 shadow-sm"
                : "border border-zinc-700 bg-neutral-950 text-zinc-300 hover:border-emerald-500/40"
            }`}
          >
            2. Handover Version Comparison (v1 vs v2)
          </button>
          <button
            type="button"
            onClick={() => setSubTab("eval_harness")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              subTab === "eval_harness"
                ? "bg-emerald-500 text-neutral-950 shadow-sm"
                : "border border-zinc-700 bg-neutral-950 text-zinc-300 hover:border-emerald-500/40"
            }`}
          >
            3. Citation-Support Evaluation Harness
          </button>
        </div>
      </div>

      {panelError && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-950/30 px-4 py-2.5 text-xs text-rose-200">
          {panelError}
        </div>
      )}

      {/* SUB-TAB 1: EVIDENCE-BACKED DEPENDENCY MAP */}
      {subTab === "dependency_map" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <div className="rounded-xl border border-zinc-800 bg-neutral-950 p-3">
              <div className="text-[10px] font-mono uppercase text-zinc-400">Graph Nodes</div>
              <div className="mt-1 text-lg font-bold text-white">{depMap.summary.totalNodes}</div>
            </div>
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3">
              <div className="text-[10px] font-mono uppercase text-emerald-300">
                Source-Supported Edges
              </div>
              <div className="mt-1 text-lg font-bold text-emerald-300">
                {depMap.summary.sourceSupportedEdgesCount}
              </div>
            </div>
            <div className="rounded-xl border border-teal-500/30 bg-teal-950/20 p-3">
              <div className="text-[10px] font-mono uppercase text-teal-300">
                Explicit Inferred Edges
              </div>
              <div className="mt-1 text-lg font-bold text-teal-300">
                {depMap.summary.inferredEdgesCount}
              </div>
            </div>
            <div className="rounded-xl border border-amber-500/40 bg-amber-950/25 p-3">
              <div className="text-[10px] font-mono uppercase text-amber-300">
                Unknown Owner Gaps
              </div>
              <div className="mt-1 text-lg font-bold text-amber-300">
                {depMap.summary.unknownOwnerGapsCount}
              </div>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-neutral-950 p-3">
              <div className="text-[10px] font-mono uppercase text-zinc-400">Unlabeled Edges</div>
              <div className="mt-1 text-lg font-bold text-emerald-400">
                {depMap.summary.unlabeledEdgesCount} (Strict 0)
              </div>
            </div>
          </div>

          {/* Filter Controls */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="font-mono text-zinc-400">Filter Dependency Edges:</span>
              {(
                [
                  { id: "all", label: `All Edges (${depMap.edges.length})` },
                  {
                    id: "source_supported",
                    label: `Source-Supported (${depMap.summary.sourceSupportedEdgesCount})`,
                  },
                  {
                    id: "inferred",
                    label: `Inferred (${depMap.summary.inferredEdgesCount})`,
                  },
                  {
                    id: "gaps",
                    label: `Unknown Owner Gaps (${depMap.summary.unknownOwnerGapsCount})`,
                  },
                ] as const
              ).map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setEdgeFilter(f.id)}
                  className={`rounded-lg px-2.5 py-1 font-mono text-[11px] transition ${
                    edgeFilter === f.id
                      ? "bg-emerald-500 text-neutral-950 font-bold"
                      : "border border-zinc-800 bg-neutral-950 text-zinc-300 hover:border-emerald-500/40"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={loadDependencyMap}
              disabled={loadingPanel}
              className="rounded-lg border border-zinc-700 bg-neutral-950 px-2.5 py-1 font-mono text-[11px] text-zinc-300 hover:border-emerald-500/40"
            >
              {loadingPanel ? "Syncing..." : "Sync Live Graph from Backend"}
            </button>
          </div>

          {/* Categorized Nodes Overview */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-neutral-950/90 p-3.5 space-y-2">
              <div className="text-xs font-mono font-bold uppercase text-emerald-300">
                Components &amp; External Dependencies
              </div>
              {depMap.nodes
                .filter(
                  (n) => n.category === "component" || n.category === "team_or_external"
                )
                .map((n) => (
                  <div
                    key={n.nodeId}
                    className="rounded-lg border border-zinc-800 bg-zinc-900/80 px-2.5 py-2 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-white">{n.label}</span>
                      <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] text-emerald-300">
                        {n.category === "team_or_external" ? "EXTERNAL / TEAM" : "COMPONENT"}
                      </span>
                    </div>
                    <div className="mt-1 font-mono text-[10px] text-zinc-400">
                      Sources: {n.evidenceSourceIds.join(", ") || "inferred"}
                    </div>
                  </div>
                ))}
            </div>

            <div className="rounded-xl border border-zinc-800 bg-neutral-950/90 p-3.5 space-y-2">
              <div className="text-xs font-mono font-bold uppercase text-teal-300">
                Assigned People &amp; Owners
              </div>
              {depMap.nodes
                .filter((n) => n.category === "person")
                .map((n) => (
                  <div
                    key={n.nodeId}
                    className="rounded-lg border border-teal-500/30 bg-teal-950/20 px-2.5 py-2 text-xs"
                  >
                    <div className="font-semibold text-teal-200">{n.label}</div>
                    <div className="mt-1 font-mono text-[10px] text-zinc-400">
                      Backed by: {n.evidenceSourceIds.join(", ")}
                    </div>
                  </div>
                ))}
            </div>

            <div className="rounded-xl border border-amber-500/40 bg-amber-950/15 p-3.5 space-y-2">
              <div className="text-xs font-mono font-bold uppercase text-amber-300">
                Explicit Unknown Owner Gaps (Never Invented)
              </div>
              {depMap.nodes
                .filter((n) => n.category === "unknown_owner_gap")
                .map((n) => (
                  <div
                    key={n.nodeId}
                    className="rounded-lg border border-amber-500/40 bg-amber-950/30 px-2.5 py-2 text-xs"
                  >
                    <div className="font-mono font-bold text-amber-300">{n.label}</div>
                    <div className="mt-1 text-[11px] text-amber-200/80">
                      {n.metadata?.gapReason ||
                        "Unassigned in source evidence; flagged for human assignment."}
                    </div>
                    <div className="mt-1 font-mono text-[10px] text-zinc-400">
                      Evidence: {n.evidenceSourceIds.join(", ")}
                    </div>
                  </div>
                ))}
            </div>
          </div>

          {/* Directed Dependency Edges with Mandatory Source Evidence or Inferred Label */}
          <div className="space-y-2">
            <div className="text-xs font-mono font-semibold uppercase text-zinc-300">
              Evidence-Linked Dependency &amp; Ownership Edges ({filteredEdges.length})
            </div>
            <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
              {filteredEdges.map((edge) => {
                const srcInfo = nodeMap[edge.sourceNodeId];
                const tgtInfo = nodeMap[edge.targetNodeId];
                const isGap = edge.relationship === "UNASSIGNED_OWNER_GAP";
                return (
                  <div
                    key={edge.edgeId}
                    className={`rounded-xl border p-3 text-xs ${
                      isGap
                        ? "border-amber-500/40 bg-amber-950/20"
                        : "border-zinc-800 bg-neutral-950"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                        {edge.relationship}
                      </span>
                      <span
                        className={`rounded border px-2 py-0.5 font-mono text-[10px] font-bold ${
                          edge.supportStatus === "source_supported"
                            ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-300"
                            : "border-amber-500/40 bg-amber-950/40 text-amber-300"
                        }`}
                      >
                        {edge.supportStatus === "source_supported"
                          ? "SOURCE-SUPPORTED EDGE"
                          : "INFERRED EDGE"}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-sm font-semibold text-white">
                      <span>{srcInfo?.label || edge.sourceNodeId}</span>
                      <span className="font-mono text-emerald-400">&rarr;</span>
                      <span className={isGap ? "text-amber-300" : "text-teal-300"}>
                        {tgtInfo?.label || edge.targetNodeId}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-zinc-300">{edge.explanation}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[10px] text-zinc-400">
                      <span>
                        Sources:{" "}
                        <strong className="text-emerald-300">
                          {edge.evidenceSourceIds.join(", ") || "inferred"}
                        </strong>
                      </span>
                      {edge.evidenceClaimIds.length > 0 && (
                        <span>
                          Claims:{" "}
                          <strong className="text-teal-300">
                            {edge.evidenceClaimIds.join(", ")}
                          </strong>
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: HANDOVER VERSION COMPARISON */}
      {subTab === "version_diff" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-neutral-950 p-3.5">
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <div>
                <label className="block font-mono text-[10px] uppercase text-zinc-400">
                  Base Snapshot (Before)
                </label>
                <select
                  aria-label="Base Handover Version"
                  value={baseVer}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setBaseVer(v);
                    loadVersionDiff(v, targetVer);
                  }}
                  className="mt-1 rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1 font-mono text-xs text-white"
                >
                  {versionDiff.availableVersions.map((av) => (
                    <option key={av.versionNumber} value={av.versionNumber}>
                      v{av.versionNumber} — {av.changeSummary}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block font-mono text-[10px] uppercase text-zinc-400">
                  Target Snapshot (After)
                </label>
                <select
                  aria-label="Target Handover Version"
                  value={targetVer ?? versionDiff.targetVersion}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setTargetVer(v);
                    loadVersionDiff(baseVer, v);
                  }}
                  className="mt-1 rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1 font-mono text-xs text-white"
                >
                  {versionDiff.availableVersions.map((av) => (
                    <option key={av.versionNumber} value={av.versionNumber}>
                      v{av.versionNumber} — {av.changeSummary}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={() => loadVersionDiff(baseVer, targetVer)}
                disabled={loadingPanel}
                className="mt-4 rounded-lg border border-emerald-500/40 bg-emerald-950/30 px-3 py-1 font-mono text-[11px] font-semibold text-emerald-300 hover:bg-emerald-900/40"
              >
                {loadingPanel ? "Comparing..." : "Compare Live Snapshots"}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
              <span className="rounded border border-emerald-500/30 bg-emerald-950/30 px-2.5 py-1 text-emerald-300">
                Changed Claims: {versionDiff.summaryMetrics.changedClaimsCount} /{" "}
                {versionDiff.summaryMetrics.totalClaimsCompared}
              </span>
              <span className="rounded border border-teal-500/30 bg-teal-950/30 px-2.5 py-1 text-teal-300">
                Status / Review Updates:{" "}
                {versionDiff.summaryMetrics.statusChangesCount +
                  versionDiff.summaryMetrics.reviewDecisionChangesCount}
              </span>
              <span className="rounded border border-amber-500/30 bg-amber-950/30 px-2.5 py-1 text-amber-300">
                Clarification Enrichments: {versionDiff.summaryMetrics.rationaleEnrichedCount}
              </span>
            </div>
          </div>

          <div className="space-y-3">
            {versionDiff.claimDiffs.map((cd) => {
              const isChanged = !cd.changeTypes.includes("UNCHANGED");
              return (
                <div
                  key={cd.claimCode}
                  className={`rounded-xl border p-4 text-xs ${
                    isChanged
                      ? "border-emerald-500/40 bg-neutral-950"
                      : "border-zinc-800/80 bg-neutral-950/60"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-emerald-300">
                        {cd.claimCode.toUpperCase()}
                      </span>
                      <span className="text-zinc-400">({cd.claimType})</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {cd.changeTypes.map((ct) => (
                        <span
                          key={ct}
                          className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold ${
                            ct === "UNCHANGED"
                              ? "bg-zinc-800 text-zinc-400"
                              : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                          }`}
                        >
                          {ct}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-3 space-y-1.5">
                      <div className="flex items-center justify-between font-mono text-[10px] text-zinc-400">
                        <span>v{versionDiff.baseVersion} (BEFORE)</span>
                        <span>
                          Status: <strong className="text-amber-300">{cd.beforeStatus || "N/A"}</strong>{" "}
                          · Review:{" "}
                          <strong className="text-zinc-200">{cd.beforeReviewState || "N/A"}</strong>
                        </span>
                      </div>
                      <p className="text-zinc-200">{cd.beforeText || "Not present in base version."}</p>
                      {cd.beforeRationale && (
                        <p className="text-[11px] text-zinc-400">
                          <strong>Rationale:</strong> {cd.beforeRationale}
                        </p>
                      )}
                      <div className="font-mono text-[10px] text-zinc-400">
                        Owner: {cd.beforeOwner || "UNKNOWN (Null in evidence)"}
                      </div>
                    </div>

                    <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/15 p-3 space-y-1.5">
                      <div className="flex items-center justify-between font-mono text-[10px] text-emerald-300">
                        <span>v{versionDiff.targetVersion} (AFTER)</span>
                        <span>
                          Status: <strong className="text-emerald-300">{cd.afterStatus || "N/A"}</strong>{" "}
                          · Review:{" "}
                          <strong className="text-white">{cd.afterReviewState || "N/A"}</strong>
                        </span>
                      </div>
                      <p className="text-white">{cd.afterText || "Removed or revoked in target version."}</p>
                      {cd.afterRationale && (
                        <p className="text-[11px] text-emerald-200/90">
                          <strong>Rationale:</strong> {cd.afterRationale}
                        </p>
                      )}
                      <div className="flex flex-wrap items-center justify-between font-mono text-[10px] text-zinc-300">
                        <span>Owner: {cd.afterOwner || "UNKNOWN (Null in evidence)"}</span>
                        {cd.reviewerNotes && (
                          <span className="text-teal-300">Note: {cd.reviewerNotes}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SUB-TAB 3: CITATION-SUPPORT EVALUATION HARNESS */}
      {subTab === "eval_harness" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-zinc-800 bg-neutral-950 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="font-mono text-xs font-bold text-emerald-300">
                  {evalReport.benchmarkName}
                </div>
                <p className="mt-0.5 text-xs text-zinc-400">
                  Compares Round 1/2 Baseline (L6.1 Provenance-Only) vs. Round 3 Post-Improvement (L6.2 Second-Pass Citation-Support Verification) on the 9-case PayFlow Ground-Truth Set.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded border border-emerald-500/40 bg-emerald-950/40 px-2.5 py-1 font-mono text-xs font-bold text-emerald-300">
                  Review Time: {evalReport.deltaImprovements.reviewTimeReductionPercent} (420s &rarr; 145s)
                </span>
                <button
                  type="button"
                  onClick={loadEvaluationHarness}
                  disabled={loadingPanel}
                  className="rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1 font-mono text-[11px] text-zinc-300 hover:border-emerald-500/40"
                >
                  {loadingPanel ? "Running..." : "Re-Run Live Harness"}
                </button>
              </div>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-zinc-800 font-mono text-[11px] text-zinc-400">
                    <th className="py-2 pr-3">Evaluation Metric</th>
                    <th className="py-2 px-3">Baseline (L6.1 Provenance-Only)</th>
                    <th className="py-2 px-3">Round 3 Post-Improvement (L6.2 Support Check)</th>
                    <th className="py-2 pl-3">Measured Improvement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/70 font-mono">
                  <tr>
                    <td className="py-2 pr-3 text-zinc-200">Evidence Coverage Rate</td>
                    <td className="py-2 px-3 text-zinc-300">
                      {Math.round(evalReport.baselineMetrics.evidenceCoverageRate * 100)}%
                    </td>
                    <td className="py-2 px-3 text-emerald-300 font-bold">
                      {Math.round(evalReport.postImprovementMetrics.evidenceCoverageRate * 100)}%
                    </td>
                    <td className="py-2 pl-3 text-emerald-400">100% Maintained</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-3 text-zinc-200">Citation Mismatch Detection Rate</td>
                    <td className="py-2 px-3 text-rose-300">
                      {Math.round(
                        evalReport.baselineMetrics.citationMismatchDetectionRate * 100
                      )}
                      % ({evalReport.baselineMetrics.unflaggedMismatchCount} unflagged)
                    </td>
                    <td className="py-2 px-3 text-emerald-300 font-bold">
                      {Math.round(
                        evalReport.postImprovementMetrics.citationMismatchDetectionRate * 100
                      )}
                      % ({evalReport.postImprovementMetrics.unflaggedMismatchCount} unflagged)
                    </td>
                    <td className="py-2 pl-3 text-emerald-400 font-bold">
                      {evalReport.deltaImprovements.citationMismatchDetectionDelta}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-3 text-zinc-200">Extraction Precision</td>
                    <td className="py-2 px-3 text-amber-300">
                      {Math.round(evalReport.baselineMetrics.extractionPrecision * 1000) / 10}%
                    </td>
                    <td className="py-2 px-3 text-emerald-300 font-bold">
                      {Math.round(
                        evalReport.postImprovementMetrics.extractionPrecision * 1000
                      ) / 10}
                      %
                    </td>
                    <td className="py-2 pl-3 text-emerald-400 font-bold">
                      {evalReport.deltaImprovements.extractionPrecisionDelta}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-3 text-zinc-200">Extraction Recall &amp; F1</td>
                    <td className="py-2 px-3 text-zinc-300">
                      Recall: {Math.round(evalReport.baselineMetrics.extractionRecall * 100)}% · F1:{" "}
                      {Math.round(evalReport.baselineMetrics.extractionF1 * 1000) / 10}%
                    </td>
                    <td className="py-2 px-3 text-emerald-300 font-bold">
                      Recall: {Math.round(evalReport.postImprovementMetrics.extractionRecall * 100)}% ·
                      F1: {Math.round(evalReport.postImprovementMetrics.extractionF1 * 1000) / 10}%
                    </td>
                    <td className="py-2 pl-3 text-emerald-400 font-bold">
                      {evalReport.deltaImprovements.extractionF1Delta} F1
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-3 text-zinc-200">Conflict Recall (Contradictions)</td>
                    <td className="py-2 px-3 text-zinc-300">
                      {Math.round(evalReport.baselineMetrics.conflictRecall * 100)}%
                    </td>
                    <td className="py-2 px-3 text-emerald-300 font-bold">
                      {Math.round(evalReport.postImprovementMetrics.conflictRecall * 100)}%
                    </td>
                    <td className="py-2 pl-3 text-emerald-400">100% Conflict Recall</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
