import React from "react";
import { EvidenceStatus } from "../lib/types";

const STATUS_STYLES: Record<
  EvidenceStatus,
  { label: string; className: string; description: string }
> = {
  source_supported: {
    label: "Source-supported",
    className: "bg-teal-500/15 text-teal-300 border-teal-500/35",
    description: "Linked to an authorised source; awaits human reviewer sign-off.",
  },
  verified: {
    label: "Verified (Human)",
    className: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    description: "Checked and accepted by an authorised human reviewer.",
  },
  conflicting: {
    label: "Conflicting",
    className: "bg-rose-500/15 text-rose-300 border-rose-500/40",
    description: "Two or more source records disagree; both shown side by side.",
  },
  potentially_outdated: {
    label: "Potentially outdated",
    className: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    description: "Source is older or superseded by a newer pull request/record.",
  },
  inferred: {
    label: "Inferred",
    className: "bg-emerald-900/30 text-teal-200 border-teal-600/40",
    description: "Relationship or interpretation suggested but not directly stated.",
  },
  unknown: {
    label: "Unknown / unsupported",
    className: "bg-zinc-800/80 text-zinc-300 border-zinc-700",
    description: "No adequate supporting evidence found; system abstains or requests clarification.",
  },
};

export const EvidenceStatusBadge: React.FC<{
  status: EvidenceStatus;
  isAiGenerated?: boolean;
}> = ({ status, isAiGenerated = true }) => {
  const cfg = STATUS_STYLES[status] || STATUS_STYLES.unknown;
  return (
    <div className="inline-flex items-center gap-1.5" title={cfg.description}>
      <span
        className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold tracking-tight ${cfg.className}`}
      >
        {cfg.label}
      </span>
      <span
        className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${
          status === "verified"
            ? "bg-emerald-950/90 text-emerald-300 border border-emerald-700/60"
            : "bg-zinc-900 text-zinc-400 border border-zinc-700/80"
        }`}
      >
        {status === "verified" ? "Human-Reviewed" : isAiGenerated ? "AI-Generated Draft" : "Human-Edited"}
      </span>
    </div>
  );
};
