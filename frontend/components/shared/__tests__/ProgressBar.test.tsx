import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgressBar } from "../ProgressBar";

describe("ProgressBar", () => {
  it("renders the percent label and fill width for a known value", () => {
    render(<ProgressBar value={41} health="stall" />);
    const bar = screen.getByTestId("progress-bar");
    expect(bar).toHaveAttribute("data-value", "41");
    expect(bar).toHaveTextContent("41%");
    const fill = bar.querySelector("i") as HTMLElement;
    expect(fill.style.width).toBe("41%");
  });

  it("renders ONLY an em-dash and NO track for null progress (honest unknown, not fake 0%)", () => {
    render(<ProgressBar value={null} />);
    const bar = screen.getByTestId("progress-bar");
    expect(bar).toHaveAttribute("data-value", "none");
    expect(bar).toHaveTextContent("—");
    // unknown must NOT render an empty bar track — that would masquerade as a real 0%
    expect(bar.querySelector("i")).toBeNull();
    expect(bar.querySelector(".bar, .barc")).toBeNull();
  });

  it("clamps out-of-range values to [0,100]", () => {
    render(<ProgressBar value={150} />);
    const fill = screen.getByTestId("progress-bar").querySelector("i") as HTMLElement;
    expect(fill.style.width).toBe("100%");
  });

  it("treats NaN as unknown (no track, em-dash label)", () => {
    render(<ProgressBar value={NaN} />);
    const bar = screen.getByTestId("progress-bar");
    expect(bar).toHaveTextContent("—");
    expect(bar).toHaveAttribute("data-value", "none");
    expect(bar.querySelector("i")).toBeNull();
  });

  it("uses health-driven fill color", () => {
    render(<ProgressBar value={80} health="act" />);
    const fill = screen.getByTestId("progress-bar").querySelector("i") as HTMLElement;
    expect(fill.style.background).toContain("--green");
  });

  it("can hide the label", () => {
    render(<ProgressBar value={50} showLabel={false} />);
    expect(screen.getByTestId("progress-bar")).not.toHaveTextContent("50%");
  });
});
