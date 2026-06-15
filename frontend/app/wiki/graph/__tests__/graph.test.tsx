import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

const getWikiGraph = vi.fn();
const getWikiGraphGlobal = vi.fn();
const searchWiki = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiGraph: (...a: unknown[]) => getWikiGraph(...a),
    getWikiGraphGlobal: (...a: unknown[]) => getWikiGraphGlobal(...a),
    searchWiki: (...a: unknown[]) => searchWiki(...a),
  };
});
const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockNoteParam: string | null = null;
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => ({ get: (k: string) => (k === "note" ? mockNoteParam : null) }),
}));

import WikiGraphPage from "../page";
import type { WikiGraph } from "@/lib/types";

function ok<T>(data: T, warning?: string) {
  return { success: true, data, ...(warning ? { warning } : {}) };
}

const GRAPH: WikiGraph = {
  center: 47,
  nodes: [
    { id: 47, title: "Knowledge work accretes", status: "evergreen", degree: 3 },
    { id: 88, title: "MOCs are workstations", status: "evergreen", degree: 2 },
    { id: 12, title: "Spaced repetition", status: "developing", degree: 0 },
  ],
  edges: [{ source: 47, target: 88, type: "relates", isResolved: true }],
  clusters: [],
};

// Bug #1 regression fixture: a graph WITH a populated cluster, in the SHAPE the
// backend actually emits (reader.detect_clusters → {members:[{id,title}], size,
// density, importance, suggestedTitle}). The page crashed here because it read the
// stale {label, noteIds} shape — `c.noteIds.map` on undefined. This fixture exercises
// the cluster-render path so that regression can't ship green again.
const GRAPH_WITH_CLUSTER: WikiGraph = {
  ...GRAPH,
  clusters: [
    {
      members: [
        { id: 47, title: "Knowledge work accretes" },
        { id: 88, title: "MOCs are workstations" },
      ],
      size: 2,
      density: 0.6,
      importance: 1.2,
      suggestedTitle: "Knowledge work accretes",
    },
  ],
};

// global fixture: center:null, whole-vault nodes/edges.
const GLOBAL: WikiGraph = { center: null, nodes: GRAPH.nodes, edges: GRAPH.edges, clusters: [] };

describe("W4 Graph Explorer", () => {
  it("GLOBAL-GRAPH: default view (no ?note=) fetches the global graph + renders nodes (NOT idle)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(GLOBAL));
    render(<WikiGraphPage />);
    await waitFor(() => expect(getWikiGraphGlobal).toHaveBeenCalled());
    await screen.findByTestId("graph-svg");
    expect(screen.getAllByTestId("graph-node").length).toBe(3);
    // global mode active; ego endpoint NOT called for the default view
    expect(screen.getByTestId("graph-mode-global")).toHaveClass("on");
    expect(getWikiGraph).not.toHaveBeenCalled();
  });

  it("GLOBAL-GRAPH: layout is DETERMINISTIC (same vault → identical node positions, no Math.random)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValue(ok(GLOBAL));
    // render twice; capture each node's transform (x,y) — must be byte-identical.
    const capture = async (): Promise<Record<string, string | null>> => {
      const { unmount } = render(<WikiGraphPage />);
      await screen.findByTestId("graph-svg");
      const map: Record<string, string | null> = {};
      for (const n of screen.getAllByTestId("graph-node")) {
        map[n.getAttribute("data-node-id") ?? ""] = n.getAttribute("transform");
      }
      unmount();
      return map;
    };
    const a = await capture();
    const b = await capture();
    expect(a).toEqual(b); // deterministic — reload gives the same positions
    // and positions are real (not all 0,0)
    expect(Object.values(a).every((t) => /translate\([\d.]+,[\d.]+\)/.test(t || ""))).toBe(true);
  });

  it("GLOBAL-GRAPH: empty vault → friendly empty (NOT a blank that looks broken)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok({ center: null, nodes: [], edges: [], clusters: [] }));
    render(<WikiGraphPage />);
    await waitFor(() => expect(screen.getByTestId("graph-empty-global")).toBeInTheDocument());
  });

  it("deep-link ?note=47 → fetches EGO graph and renders SVG nodes/edges", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH));
    render(<WikiGraphPage />);
    await waitFor(() => expect(getWikiGraph).toHaveBeenCalledWith(47, 2));
    await screen.findByTestId("graph-svg");
    expect(screen.getAllByTestId("graph-node").length).toBe(3);
    expect(screen.getAllByTestId("graph-edge").length).toBe(1);
  });

  it("node click → focuses the note (local mode, URL ?note=id)", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH));
    render(<WikiGraphPage />);
    const nodes = await screen.findAllByTestId("graph-node");
    const node88 = nodes.find((n) => n.getAttribute("data-node-id") === "88")!;
    fireEvent.click(node88);
    expect(mockReplace).toHaveBeenCalledWith("/wiki/graph?note=88");
  });

  it("Global toggle from local → goes back to global (URL /wiki/graph)", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValue(ok(GRAPH));
    getWikiGraphGlobal.mockResolvedValue(ok(GLOBAL));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    fireEvent.click(screen.getByTestId("graph-mode-global"));
    expect(mockReplace).toHaveBeenCalledWith("/wiki/graph");
  });

  it("depth toggle re-fetches at the new depth", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValue(ok(GRAPH));
    render(<WikiGraphPage />);
    await waitFor(() => expect(getWikiGraph).toHaveBeenCalledWith(47, 2));
    fireEvent.click(screen.getByTestId("graph-depth-1"));
    await waitFor(() => expect(getWikiGraph).toHaveBeenCalledWith(47, 1));
  });

  it("HONEST: empty clusters → cluster-hint empty state (no fabricated MOC suggestion)", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    const empty = screen.getByTestId("graph-cluster-empty");
    expect(empty).toBeInTheDocument();
    expect(empty.textContent).toMatch(/Claude Code/i);
    expect(screen.queryByTestId("graph-cluster")).toBeNull();
  });

  // --- Bug #1 regression: a graph WITH a cluster must render the cluster + its member
  //     chips WITHOUT crashing. The page used to read the stale {label, noteIds} shape
  //     → `c.noteIds.map` on undefined → white-screen TypeError. This renders the real
  //     {members, suggestedTitle} shape end-to-end.
  it("graph WITH a cluster renders the cluster + member chips (no crash)", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH_WITH_CLUSTER));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    // the cluster block renders (not the empty-state)
    const cluster = await screen.findByTestId("graph-cluster");
    expect(cluster).toBeInTheDocument();
    expect(screen.queryByTestId("graph-cluster-empty")).toBeNull();
    // suggestedTitle is shown
    expect(cluster.textContent).toMatch(/Knowledge work accretes/);
    // each member renders as a chip with its id (the c.members.map path)
    expect(cluster.textContent).toMatch(/#47/);
    expect(cluster.textContent).toMatch(/#88/);
  });

  it("cluster member chip click routes to /wiki/[id]", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH_WITH_CLUSTER));
    render(<WikiGraphPage />);
    const cluster = await screen.findByTestId("graph-cluster");
    const chip88 = [...cluster.querySelectorAll(".tagchip")].find((c) => /#88/.test(c.textContent || ""));
    expect(chip88).toBeTruthy();
    fireEvent.click(chip88 as Element);
    expect(mockReplace).toHaveBeenCalledWith("/wiki/graph?note=88");
  });

  it("404 center note → error state, not a crash", async () => {
    mockNoteParam = "999";
    getWikiGraph.mockRejectedValueOnce(new Error("wiki note 999 not found"));
    render(<WikiGraphPage />);
    await waitFor(() => expect(screen.getByTestId("graph-error")).toBeInTheDocument());
    expect(screen.getByTestId("graph-error")).toHaveTextContent("not found");
  });

  it("center picker → choosing a hit focuses that note (URL ?note=88)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValue(ok(GLOBAL));
    searchWiki.mockResolvedValue(ok([{ id: 88, title: "MOCs are workstations", status: "evergreen", snippet: "..." }]));
    getWikiGraph.mockResolvedValue(ok({ ...GRAPH, center: 88 }));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg"); // global renders first
    fireEvent.change(screen.getByTestId("graph-search-input"), { target: { value: "MOC" } });
    const hit = await screen.findByTestId("graph-search-hit");
    fireEvent.click(hit);
    expect(mockReplace).toHaveBeenCalledWith("/wiki/graph?note=88");
  });

  it("center with no neighbors (degree 0, single node) → 'chưa có hàng xóm' empty", async () => {
    mockNoteParam = "12";
    getWikiGraph.mockResolvedValueOnce(ok({ center: 12, nodes: [], edges: [], clusters: [] }));
    render(<WikiGraphPage />);
    await waitFor(() => expect(screen.getByTestId("graph-empty")).toBeInTheDocument());
  });

  it("A1c polish: status filter dims non-matching nodes (developing #12 dimmed when filter=evergreen)", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    fireEvent.click(screen.getByTestId("graph-filter-evergreen"));
    const nodes = screen.getAllByTestId("graph-node");
    const dev12 = nodes.find((n) => n.getAttribute("data-node-id") === "12")!; // developing
    const ever88 = nodes.find((n) => n.getAttribute("data-node-id") === "88")!; // evergreen
    expect(dev12).toHaveAttribute("data-dimmed", "true");
    expect(ever88).not.toHaveAttribute("data-dimmed");
  });

  it("A1c polish: orphan-highlight toggle flips on", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    const toggle = screen.getByTestId("graph-highlight-orphan");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });
});
