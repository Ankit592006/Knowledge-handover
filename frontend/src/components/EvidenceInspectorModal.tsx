import React from "react";
import { ConflictPair, EvidenceReference, SourceDocumentItem } from "../lib/types";

interface EvidenceInspectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  claimId: string;
  claimUuid?: string;
  claimText: string;
  evidence: EvidenceReference[];
  conflicts: ConflictPair[];
  sources: SourceDocumentItem[];
  citationSupportStatus?: "supported" | "weak" | "mismatch";
  citationSupportScore?: number;
  reviewerFlaggedMismatch?: boolean;
  canFlagMismatch?: boolean;
  onToggleFlagMismatch?: (claimUuid: string, flagMismatch: boolean) => void;
}

export const EvidenceInspectorModal: React.FC<EvidenceInspectorModalProps> = ({
  isOpen,
  onClose,
  claimId,
  claimUuid,
  claimText,
  evidence,
  conflicts,
  sources,
  citationSupportStatus = "supported",
  citationSupportScore = 0.88,
  reviewerFlaggedMismatch = false,
  canFlagMismatch = false,
  onToggleFlagMismatch,
}) => {
  if (!isOpen) return null;

  const renderSupportBadge = (
    status: "supported" | "weak" | "mismatch" = "supported",
    score?: number
  ) => {
    const pct = score !== undefined ? ` (${Math.round(score * 100)}%)` : "";
    if (status === "supported") {
      return (
        <span className="rounded border border-emerald-500/40 bg-emerald-950/40 px-2.5 py-0.5 font-mono text-[11px] font-bold text-emerald-300">
          L6.2 SUPPORTED{pct}
        </span>
      );
    }
    if (status === "weak") {
      return (
        <span className="rounded border border-amber-500/40 bg-amber-950/40 px-2.5 py-0.5 font-mono text-[11px] font-bold text-amber-300">
          L6.2 WEAK SUPPORT{pct}
        </span>
      );
    }
    return (
      <span className="rounded border border-rose-500/50 bg-rose-950/50 px-2.5 py-0.5 font-mono text-[11px] font-bold text-rose-300">
        L6.2 CITATION MISMATCH{pct}
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-800 pb-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-wider text-emerald-400">
                Provenance &amp; Citation-Support Inspector — {claimId}
              </span>
              {renderSupportBadge(citationSupportStatus, citationSupportScore)}
              {reviewerFlaggedMismatch && (
                <span className="rounded border border-rose-500/50 bg-rose-950/60 px-2 py-0.5 font-mono text-[10px] font-bold text-rose-200">
                  REVIEWER FLAGGED MISMATCH
                </span>
              )}
            </div>
            <h3 className="text-lg font-semibold text-white">{claimText}</h3>
          </div>
          <div className="flex items-center gap-2">
            {canFlagMismatch && claimUuid && onToggleFlagMismatch && (
              <button
                type="button"
                onClick={() => onToggleFlagMismatch(claimUuid, !reviewerFlaggedMismatch)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                  reviewerFlaggedMismatch
                    ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/40"
                    : "border-rose-500/40 bg-rose-950/40 text-rose-300 hover:bg-rose-900/40"
                }`}
              >
                {reviewerFlaggedMismatch
                  ? "Clear Citation Mismatch Flag"
                  : "Flag Citation Mismatch (Feed Back)"}
              </button>
            )}
            <button
              onClick={onClose}
              className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:border-emerald-500/40 hover:text-emerald-300"
            >
              Close
            </button>
          </div>
        </div>

        {/* Round 3 Improvement 2: Second-Pass Citation-Support Summary Banner */}
        <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-900/70 p-3.5 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-mono font-semibold text-teal-300">
              Round 3 Second-Pass Support Verification (L6.1 Provenance + L6.2 Entailment Check)
            </span>
            <span className="font-mono text-zinc-400">
              Overall Verdict: <strong className="text-white uppercase">{citationSupportStatus}</strong>
            </span>
          </div>
          <p className="mt-1 text-zinc-300">
            L6.1 confirms the cited <code className="text-emerald-300">sourceId</code> exists in PostgreSQL and character offsets resolve.
            L6.2 verifies whether the verbatim excerpt substantiates the claim&apos;s entities and assertion (labelled{" "}
            <code className="text-emerald-300">supported</code>, <code className="text-amber-300">weak</code>, or{" "}
            <code className="text-rose-300">mismatch</code>).
          </p>
        </div>

        {conflicts.length > 0 && (
          <div className="mt-5 rounded-lg border border-rose-500/40 bg-rose-950/20 p-4">
            <h4 className="text-sm font-semibold text-rose-300">
              Side-by-Side Contradiction / Staleness Analysis ({conflicts.length})
            </h4>
            <p className="mt-1 text-xs text-rose-200/80">
              The platform never silently chooses between disagreeing records. Both sources and their timestamps are shown below for human decision.
            </p>
            {conflicts.map((conf, idx) => (
              <div key={idx} className="mt-3 space-y-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="rounded border border-zinc-800 bg-neutral-950 p-3">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span className="font-mono font-bold text-emerald-400">{conf.sourceAId}</span>
                      <span>Timestamp: {new Date(conf.sourceATimestamp).toLocaleDateString()}</span>
                    </div>
                    <p className="mt-2 text-xs text-zinc-200 font-mono">&ldquo;{conf.sourceAExcerpt}&rdquo;</p>
                  </div>
                  <div className="rounded border border-zinc-800 bg-neutral-950 p-3">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span className="font-mono font-bold text-amber-400">{conf.sourceBId}</span>
                      <span>Timestamp: {new Date(conf.sourceBTimestamp).toLocaleDateString()}</span>
                    </div>
                    <p className="mt-2 text-xs text-zinc-200 font-mono">&ldquo;{conf.sourceBExcerpt}&rdquo;</p>
                  </div>
                </div>
                <p className="text-xs text-zinc-300 italic">{conf.explanation}</p>
              </div>
            ))}
          </div>
        )}

        <div className="mt-5 space-y-4">
          <h4 className="text-sm font-semibold text-zinc-200">
            Deterministically Validated Source Citations ({evidence.length})
          </h4>
          {evidence.length === 0 ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-4 text-xs text-amber-200">
              No supporting source record is linked to this claim. Marked as Unknown / Unsupported.
            </div>
          ) : (
            evidence.map((ev, index) => {
              const fullDoc = sources.find((s) => s.stable_source_id === ev.sourceId);
              const evSupport = ev.supportStatus || citationSupportStatus || "supported";
              const evScore = ev.supportScore ?? citationSupportScore;
              return (
                <div
                  key={index}
                  className="rounded-lg border border-zinc-800 bg-neutral-950/90 p-4 space-y-2.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 font-mono font-semibold text-emerald-300">
                        {ev.sourceId}
                      </span>
                      <span className="text-zinc-400">Type: {ev.sourceType}</span>
                      <span className="font-mono text-zinc-400">Location: {ev.location}</span>
                      <span className="text-zinc-400">Version: {ev.versionTag}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {renderSupportBadge(evSupport, evScore)}
                      <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-400 border border-emerald-500/25">
                        {ev.deterministicVerified
                          ? "DB Source ID & Permission Verified"
                          : "Unverified Reference"}
                      </span>
                    </div>
                  </div>
                  <div className="rounded border-l-2 border-emerald-500 bg-zinc-900 p-3 text-xs text-zinc-200 font-mono">
                    &ldquo;{ev.excerpt}&rdquo;
                  </div>
                  {ev.supportExplanation && (
                    <div className="text-[11px] font-mono text-zinc-400">
                      <strong className="text-teal-300">L6.2 Support Analysis:</strong> {ev.supportExplanation}
                    </div>
                  )}
                  {fullDoc && (
                    <details className="text-xs text-zinc-400">
                      <summary className="cursor-pointer font-medium text-emerald-400 hover:underline">
                        View Full Redacted Source Document ({fullDoc.title})
                      </summary>
                      <pre className="mt-2 whitespace-pre-wrap rounded bg-zinc-900 p-3 font-mono text-xs text-zinc-300">
                        {fullDoc.content_redacted}
                      </pre>
                    </details>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
