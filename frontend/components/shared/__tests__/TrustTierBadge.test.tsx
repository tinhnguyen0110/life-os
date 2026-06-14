import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusPill, TrustTierBadge, TypeBadge, CandidateWarning } from "../TrustTierBadge";

describe("StatusPill", () => {
  it("renders each status with its label + data-status + class", () => {
    for (const s of ["fleeting", "developing", "evergreen"] as const) {
      const { unmount } = render(<StatusPill status={s} testId="pill" />);
      const pill = screen.getByTestId("pill");
      expect(pill).toHaveTextContent(s);
      expect(pill).toHaveAttribute("data-status", s);
      expect(pill.className).toContain(s);
      unmount();
    }
  });
});

describe("TrustTierBadge", () => {
  it("renders verified with a check (human-confirmed)", () => {
    render(<TrustTierBadge tier="verified" testId="tt" />);
    const b = screen.getByTestId("tt");
    expect(b).toHaveTextContent("verified");
    expect(b).toHaveAttribute("data-tier", "verified");
    expect(b.className).toContain("ver");
  });

  it("renders candidate distinctly (agent-proposed, NOT verified)", () => {
    render(<TrustTierBadge tier="candidate" testId="tt" />);
    const b = screen.getByTestId("tt");
    expect(b).toHaveTextContent("candidate");
    expect(b).toHaveAttribute("data-tier", "candidate");
    expect(b.className).toContain("cand");
  });
});

describe("TypeBadge", () => {
  it("labels concept and literature distinctly", () => {
    const { unmount } = render(<TypeBadge type="concept" testId="tb" />);
    expect(screen.getByTestId("tb")).toHaveTextContent("concept");
    expect(screen.getByTestId("tb")).toHaveAttribute("data-type", "concept");
    unmount();
    render(<TypeBadge type="literature" testId="tb" />);
    expect(screen.getByTestId("tb")).toHaveTextContent("literature");
  });
});

describe("CandidateWarning", () => {
  it("renders the candidate ratify banner", () => {
    render(<CandidateWarning testId="warn" />);
    const w = screen.getByTestId("warn");
    expect(w).toHaveTextContent("candidate");
    expect(w).toHaveTextContent("Ratify");
  });
});
