import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HealthChip } from "../HealthChip";

describe("HealthChip", () => {
  it("renders the Vietnamese label + variant class for each health bucket", () => {
    const cases = [
      { health: "act", label: "healthy", cls: "sb-act" },
      { health: "slow", label: "chậm", cls: "sb-slow" },
      { health: "stall", label: "đứng", cls: "sb-stall" },
      { health: "dead", label: "chết", cls: "sb-dead" },
    ] as const;
    for (const c of cases) {
      const { unmount } = render(<HealthChip health={c.health} />);
      const chip = screen.getByTestId("health-chip");
      expect(chip).toHaveTextContent(c.label);
      expect(chip.className).toContain(c.cls);
      expect(chip).toHaveAttribute("data-health", c.health);
      unmount();
    }
  });

  it("falls back to dead styling for an unexpected value (defensive, no crash)", () => {
    // @ts-expect-error — deliberately passing an out-of-contract value
    render(<HealthChip health="bogus" />);
    const chip = screen.getByTestId("health-chip");
    expect(chip.className).toContain("sb-dead");
  });
});
