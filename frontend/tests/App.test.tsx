import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EvidenceStatusBadge } from "../src/components/EvidenceStatusBadge";
import App from "../src/App";

describe("Knowledge Handover Frontend Suite", () => {
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

  it("renders the main landing workflow overview and navigation", () => {
    render(<App />);
    expect(
      screen.getByText(/Prevent Critical Project Knowledge From Leaving With People/i)
    ).toBeDefined();
    expect(screen.getByText("01 CONNECT")).toBeDefined();
    expect(screen.getByText("02 RECONSTRUCT")).toBeDefined();
    expect(screen.getByText("03 CLARIFY")).toBeDefined();
    expect(screen.getByText("04 VERIFY & REVIEW")).toBeDefined();
    expect(screen.getByText("05 HANDOVER")).toBeDefined();
  });
});
