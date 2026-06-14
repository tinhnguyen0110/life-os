import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const getWikiClusters = vi.fn();
const getWikiMocs = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiClusters: (...a: unknown[]) => getWikiClusters(...a),
    getWikiMocs: (...a: unknown[]) => getWikiMocs(...a),
  };
});
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a>,
}));

import WikiMocPage from "../page";
import { ApiError } from "@/lib/api";
import type { WikiClusterList, WikiMocList } from "@/lib/types";

function ok<T>(data: T) {
  return { success: true, data };
}
const CLUSTERS: WikiClusterList = {
  clusters: [
    { members: [{ id: 1, title: "Atomicity" }, { id: 2, title: "Linking" }, { id: 3, title: "Density" }], size: 3, density: 1.0, importance: 3.0, suggestedTitle: "PKM cluster" },
  ],
};
const MOCS: WikiMocList = {
  items: [
    { id: 4, title: "PKM Methodology MOC", status: "evergreen", created: "x", updated: "y", outboundLinks: 3 },
  ],
};

describe("W5 MOC / Synthesize", () => {
  it("renders MOC notes + cluster candidates from live shapes", async () => {
    getWikiClusters.mockResolvedValueOnce(ok(CLUSTERS));
    getWikiMocs.mockResolvedValueOnce(ok(MOCS));
    render(<WikiMocPage />);
    await waitFor(() => expect(screen.getByTestId("moc-screen")).toBeInTheDocument());
    expect(screen.getAllByTestId("moc-row").length).toBe(1);
    expect(screen.getByText("PKM Methodology MOC")).toBeInTheDocument();
    expect(screen.getAllByTestId("moc-cluster").length).toBe(1);
    // cluster meta shows size + density% + advisory importance
    expect(screen.getByTestId("moc-cluster-meta")).toHaveTextContent("3 note");
    expect(screen.getByTestId("moc-cluster-meta")).toHaveTextContent("100%");
    // members are deep-linkable
    expect(screen.getAllByTestId("moc-cluster-member").length).toBe(3);
  });

  it("HONEST: cluster card shows 'ask Claude Code to draft' hint, NOT a fabricated AI draft", async () => {
    getWikiClusters.mockResolvedValueOnce(ok(CLUSTERS));
    getWikiMocs.mockResolvedValueOnce(ok(MOCS));
    render(<WikiMocPage />);
    await waitFor(() => expect(screen.getByTestId("moc-screen")).toBeInTheDocument());
    const hint = screen.getByTestId("moc-cluster-hint");
    expect(hint).toHaveTextContent(/Claude Code/i);
    expect(hint).toHaveTextContent(/AI nháp, bạn duyệt/i);
  });

  it("honest empty: no MOCs → testid-scoped empty (not fabricated)", async () => {
    getWikiClusters.mockResolvedValueOnce(ok(CLUSTERS));
    getWikiMocs.mockResolvedValueOnce(ok({ items: [] }));
    render(<WikiMocPage />);
    await waitFor(() => expect(screen.getByTestId("moc-list-empty")).toBeInTheDocument());
    expect(screen.queryByTestId("moc-row")).toBeNull();
  });

  it("honest empty: no clusters → testid-scoped empty (graph community detection explained)", async () => {
    getWikiClusters.mockResolvedValueOnce(ok({ clusters: [] }));
    getWikiMocs.mockResolvedValueOnce(ok(MOCS));
    render(<WikiMocPage />);
    await waitFor(() => expect(screen.getByTestId("moc-clusters-empty")).toBeInTheDocument());
    expect(screen.queryByTestId("moc-cluster")).toBeNull();
  });

  it("FAIL-SOFT: clusters endpoint errors but MOCs render; clusters shows 'unavailable' (NOT honest-empty)", async () => {
    getWikiClusters.mockRejectedValueOnce(new ApiError(500, "clusters down"));
    getWikiMocs.mockResolvedValueOnce(ok(MOCS));
    render(<WikiMocPage />);
    await waitFor(() => expect(screen.getByTestId("moc-screen")).toBeInTheDocument());
    // mocs still rendered; clusters degraded to an UNAVAILABLE notice (distinct from
    // honest "no clusters" — a failure must NOT masquerade as "0 clusters").
    expect(screen.getAllByTestId("moc-row").length).toBe(1);
    expect(screen.getByTestId("moc-clusters-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("moc-clusters-empty")).toBeNull();
    expect(screen.queryByTestId("moc-screen-error")).toBeNull();
  });

  it("HANG-GUARD: a clusters endpoint that never resolves does NOT pin the screen on loading", async () => {
    // simulate a hung endpoint (never settles) — the per-call timeout in useWikiMoc
    // must degrade it to unavailable so MOCs still render. (Live W5b: /wiki/clusters hung.)
    // Uses the real 8s withTimeout; give the test room (≤10s wait below).
    getWikiClusters.mockReturnValueOnce(new Promise(() => {})); // never resolves
    getWikiMocs.mockResolvedValueOnce(ok(MOCS));
    render(<WikiMocPage />);
    await waitFor(() => expect(screen.getByTestId("moc-clusters-unavailable")).toBeInTheDocument(), { timeout: 9500 });
    expect(screen.getAllByTestId("moc-row").length).toBe(1);
  }, 11000);

  it("TOTAL failure (both endpoints down) → error screen", async () => {
    getWikiClusters.mockRejectedValueOnce(new ApiError(500, "clusters down"));
    getWikiMocs.mockRejectedValueOnce(new ApiError(500, "mocs down"));
    render(<WikiMocPage />);
    await waitFor(() => expect(screen.getByTestId("moc-screen-error")).toBeInTheDocument());
  });
});
