import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/useNav", () => ({ useSafeRouter: () => ({ push: vi.fn() }) }));

const getBrief = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getBrief: () => getBrief() };
});

import { HomeBriefTile } from "../HomeBriefTile";

afterEach(() => { getBrief.mockReset(); });

const PR = (over = {}) => ({ n: 1, text: "crewly đứng 69 ngày", source: "projects", severity: "warn", ...over });
const BRIEF = (priorities: unknown[]) => ({ success: true, data: {
  generatedAt: "2026-06-06T15:32:30Z", asOf: "2026-04-17", source: "template",
  summary: { netWorth: 63121, projectsActive: 3, claudePct: 18.9, alertsToday: 2 },
  priorities, stale: true, warnings: [],
} });

describe("HomeBriefTile — top-N priorities (per-tile fail-open)", () => {
  it("shows numbered priorities + 'template' header (not opus)", async () => {
    getBrief.mockResolvedValueOnce(BRIEF([PR()]));
    render(<HomeBriefTile />);
    await waitFor(() => expect(screen.getByTestId("home-brief-pr-1")).toBeInTheDocument());
    expect(screen.getByTestId("home-brief-pr-1")).toHaveTextContent("crewly đứng 69 ngày");
    expect(screen.getByTestId("home-brief-tile")).toHaveTextContent("template");
    expect(screen.getByTestId("home-brief-tile")).not.toHaveTextContent(/opus/i);
  });

  it("caps at top 3 priorities", async () => {
    getBrief.mockResolvedValueOnce(BRIEF([PR({ n: 1 }), PR({ n: 2 }), PR({ n: 3 }), PR({ n: 4 })]));
    render(<HomeBriefTile />);
    await waitFor(() => expect(screen.getByTestId("home-brief-pr-3")).toBeInTheDocument());
    expect(screen.queryByTestId("home-brief-pr-4")).toBeNull(); // 4th dropped
  });

  it("HONEST-EMPTY: priorities=[] → calm 'Ổn định' (no fake priorities)", async () => {
    getBrief.mockResolvedValueOnce(BRIEF([]));
    render(<HomeBriefTile />);
    await waitFor(() => expect(screen.getByTestId("home-brief-calm")).toBeInTheDocument());
    expect(screen.getByTestId("home-brief-calm")).toHaveTextContent(/Ổn định/);
  });

  it("FAIL-OPEN: brief down → tile shows its own error (no blank, no throw)", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getBrief.mockRejectedValueOnce(new (ApiError as any)(500, "boom"));
    render(<HomeBriefTile />);
    await waitFor(() => expect(screen.getByTestId("home-brief-error")).toBeInTheDocument());
    expect(screen.getByTestId("home-brief-error")).toHaveTextContent("boom");
  });
});
