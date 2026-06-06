import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiCard } from "../KpiCard";

describe("KpiCard", () => {
  it("renders label, value and sub", () => {
    render(<KpiCard label="Tổng dự án" value={4} sub="1 trong nghĩa địa" />);
    const card = screen.getByTestId("kpi-card");
    expect(card).toHaveTextContent("Tổng dự án");
    expect(screen.getByTestId("kpi-value")).toHaveTextContent("4");
    expect(card).toHaveTextContent("1 trong nghĩa địa");
  });

  it("omits the sub line when not provided", () => {
    const { container } = render(<KpiCard label="Active" value={2} />);
    expect(container.querySelector(".sd")).toBeNull();
  });

  it("applies the tone class to the value", () => {
    render(<KpiCard label="Active" value={2} tone="pos" />);
    expect(screen.getByTestId("kpi-value").className).toContain("pos");
  });

  it("renders a ReactNode value (e.g. a pre-formatted string)", () => {
    render(<KpiCard label="Auto cuối" value={<span>2 phút trước</span>} />);
    expect(screen.getByTestId("kpi-value")).toHaveTextContent("2 phút trước");
  });
});
