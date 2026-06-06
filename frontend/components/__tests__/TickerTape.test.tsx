import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { TickerTape } from "../TickerTape";
import { TICKER_MOCK } from "@/lib/ticker-mock";

describe("TickerTape", () => {
  it("renders the doubled track (mock loop) for the default feed", () => {
    render(<TickerTape />);
    const tape = screen.getByTestId("ticker");
    // each item doubled → BTC appears twice
    expect(within(tape).getAllByText("BTC")).toHaveLength(2);
  });

  it("shows green/red direction class per item", () => {
    const { container } = render(<TickerTape items={[{ sym: "VNINDEX", px: "1,284", chg: "-0.6%", dir: "neg" }]} />);
    const neg = container.querySelector(".ti .neg");
    expect(neg).toHaveTextContent("-0.6%");
  });

  it("empty data renders an empty tape (no crash)", () => {
    render(<TickerTape items={[]} />);
    const tape = screen.getByTestId("ticker");
    expect(tape.querySelector(".tk")?.children.length).toBe(0);
  });

  it("covers all 9 mock symbols", () => {
    render(<TickerTape />);
    const tape = screen.getByTestId("ticker");
    for (const t of TICKER_MOCK) {
      expect(within(tape).getAllByText(t.sym).length).toBeGreaterThan(0);
    }
    expect(TICKER_MOCK).toHaveLength(9);
  });
});
