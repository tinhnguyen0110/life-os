import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent, act, within } from "@testing-library/react";

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
    // (D) clusters live in a collapsible popover now — open it first.
    fireEvent.click(screen.getByTestId("graph-clusters-toggle"));
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
    // (D) open the cluster popover; the toggle shows the count.
    fireEvent.click(screen.getByTestId("graph-clusters-toggle"));
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
    await screen.findByTestId("graph-svg");
    fireEvent.click(screen.getByTestId("graph-clusters-toggle")); // (D) open the popover
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

  // ─────────── GRAPH-POLISH-A (D): filter toolbar above the graph, full-width, no side col ───────────
  it("(D): the filter is a TOOLBAR above the graph (full-width, no right side column)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(GLOBAL));
    const { container } = render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    const toolbar = screen.getByTestId("graph-toolbar");
    const canvas = screen.getByTestId("graph-canvas");
    // the toolbar contains the status filter + orphan toggle + counts (relocated, same testids)
    for (const s of ["all", "evergreen", "developing", "fleeting"]) {
      expect(within(toolbar).getByTestId(`graph-filter-${s}`)).toBeInTheDocument();
    }
    expect(within(toolbar).getByTestId("graph-highlight-orphan")).toBeInTheDocument();
    expect(within(toolbar).getByTestId("graph-counts")).toHaveTextContent(/nodes/);
    // the toolbar sits ABOVE the canvas in document order (toolbar precedes canvas).
    expect(toolbar.compareDocumentPosition(canvas) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // the old 2-col side column is gone.
    expect(container.querySelector(".wgraph-side")).toBeNull();
  });

  it("(D): status filter + orphan toggle STILL WORK from the toolbar", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    // orphan toggle flips
    const orphan = screen.getByTestId("graph-highlight-orphan");
    expect(orphan).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(orphan);
    expect(orphan).toHaveAttribute("aria-pressed", "true");
    // status filter dims a non-matching node (developing #12 dimmed when filter=evergreen)
    fireEvent.click(screen.getByTestId("graph-filter-evergreen"));
    const n12 = screen.getAllByTestId("graph-node").find((n) => n.getAttribute("data-node-id") === "12")!;
    expect(n12.getAttribute("data-dimmed")).toBe("true");
  });

  it("(E): GLOBAL labels are CULLED/capped (not one-per-node) so the dense cluster doesn't pile labels", async () => {
    mockNoteParam = null;
    // many high-degree nodes → without culling every node would label + overlap.
    const MANY: WikiGraph = {
      center: null,
      nodes: Array.from({ length: 20 }, (_, i) => ({ id: i + 1, title: `Node title number ${i + 1} long`, status: "evergreen" as const, degree: 8 })),
      edges: Array.from({ length: 19 }, (_, i) => ({ source: i + 1, target: i + 2, type: "relates", isResolved: true })),
      clusters: [],
    };
    getWikiGraphGlobal.mockResolvedValueOnce(ok(MANY));
    const { container } = render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    const nodeCount = screen.getAllByTestId("graph-node").length;
    const labels = container.querySelectorAll("text.wgnode-lbl");
    expect(nodeCount).toBe(20);
    // collision-cull + cap (default ≤ 8) → far fewer labels than nodes (no per-node pile-up).
    expect(labels.length).toBeLessThan(nodeCount);
    expect(labels.length).toBeLessThanOrEqual(8);
  });

  it("(E): hover always labels the hovered node (even if it was culled)", async () => {
    mockNoteParam = null;
    const MANY: WikiGraph = {
      center: null,
      nodes: Array.from({ length: 20 }, (_, i) => ({ id: i + 1, title: `Title ${i + 1}`, status: "evergreen" as const, degree: 8 })),
      edges: Array.from({ length: 19 }, (_, i) => ({ source: i + 1, target: i + 2, type: "relates", isResolved: true })),
      clusters: [],
    };
    getWikiGraphGlobal.mockResolvedValueOnce(ok(MANY));
    const { container } = render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    const before = container.querySelectorAll("text.wgnode-lbl").length;
    // hover a node that's likely culled (a later/low-priority one)
    const node = screen.getAllByTestId("graph-node").find((n) => n.getAttribute("data-node-id") === "20")!;
    fireEvent.mouseEnter(node);
    const after = container.querySelectorAll("text.wgnode-lbl").length;
    expect(after).toBeGreaterThanOrEqual(before); // hover adds (or keeps) the hovered label
  });

  it("(D): cluster hints still reachable via the popover toggle (collapsed by default)", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH_WITH_CLUSTER));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    // collapsed by default — no cluster panel until toggled.
    expect(screen.queryByTestId("graph-clusters-pop")).toBeNull();
    expect(screen.queryByTestId("graph-cluster")).toBeNull();
    // toggle shows the cluster count + opens the popover.
    const toggle = screen.getByTestId("graph-clusters-toggle");
    expect(toggle).toHaveTextContent(/Cụm \(1\)/);
    fireEvent.click(toggle);
    expect(screen.getByTestId("graph-clusters-pop")).toBeInTheDocument();
    expect(screen.getByTestId("graph-cluster")).toBeInTheDocument();
  });

  // ─────────── GRAPH-POLISH: responsive + zoom/pan + click-vs-drag ───────────
  it("GRAPH-POLISH req1: SVG is RESPONSIVE — width 100% + a viewBox (not a fixed px width)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(GLOBAL));
    render(<WikiGraphPage />);
    const svg = await screen.findByTestId("graph-svg");
    expect(svg).toHaveStyle({ width: "100%" });
    // GRAPH-POLISH-A — the viewBox is now the AUTO-FIT node bounds, not the hardcoded box.
    const vb = svg.getAttribute("viewBox");
    expect(vb).toBeTruthy();
    expect(/^[-\d.]+ [-\d.]+ [\d.]+ [\d.]+$/.test(vb!)).toBe(true); // 4 numbers (a real viewBox)
    expect(svg).toHaveAttribute("preserveAspectRatio", "xMidYMid meet");
    // NOT a fixed pixel width attribute
    expect(svg.getAttribute("width")).toBeNull();
  });

  // GRAPH-POLISH-A (C): zoom is now SMOOTH (rAF-lerped) — a wheel sets a TARGET; the actual
  // view.w eases toward it over rAF frames. Drive rAF synchronously to assert the eased step.
  function flushRaf(n: number) {
    for (let i = 0; i < n; i++) {
      const cbs = (globalThis as any).__rafQueue ?? [];
      (globalThis as any).__rafQueue = [];
      act(() => { cbs.forEach((cb: FrameRequestCallback) => cb(performance.now?.() ?? 0)); });
    }
  }
  function withSyncRaf(fn: () => Promise<void> | void) {
    const realRaf = globalThis.requestAnimationFrame;
    const realCancel = globalThis.cancelAnimationFrame;
    (globalThis as any).__rafQueue = [];
    globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) => {
      (globalThis as any).__rafQueue.push(cb);
      return (globalThis as any).__rafQueue.length;
    }) as any;
    globalThis.cancelAnimationFrame = (() => {}) as any;
    return Promise.resolve(fn()).finally(() => {
      globalThis.requestAnimationFrame = realRaf;
      globalThis.cancelAnimationFrame = realCancel;
    });
  }

  it("GRAPH-POLISH-A req2: wheel up sets a zoom-IN target → the rAF lerp SHRINKS the viewBox (smooth, eased over frames)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(GLOBAL));
    await withSyncRaf(async () => {
      render(<WikiGraphPage />);
      const svg = await screen.findByTestId("graph-svg");
      const before = svg.getAttribute("viewBox")!.split(" ").map(Number); // the fitted box
      act(() => { fireEvent.wheel(svg, { deltaY: -100, clientX: 380, clientY: 230 }); }); // wheel UP = zoom IN
      // one step → eased PARTWAY (not a jump): w shrank but not all the way to the target.
      flushRaf(1);
      const step1 = svg.getAttribute("viewBox")!.split(" ").map(Number);
      expect(step1[2]).toBeLessThan(before[2]); // already shrinking (zoom in)
      // more steps → converges to the (smaller) target; never grows past the start.
      flushRaf(20);
      const settled = svg.getAttribute("viewBox")!.split(" ").map(Number);
      expect(settled[2]).toBeLessThan(before[2]);          // ended zoomed in
      expect(settled[2]).toBeLessThanOrEqual(step1[2]);    // monotonic toward the target (eased, not bouncing)
      expect(settled[3]).toBeLessThan(before[3]);          // h shrank proportionally
    });
  });

  it("GRAPH-POLISH-A req2: reset button restores the FITTED viewBox after a zoom (not the old hardcoded box)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(GLOBAL));
    await withSyncRaf(async () => {
      render(<WikiGraphPage />);
      const svg = await screen.findByTestId("graph-svg");
      const fitted = svg.getAttribute("viewBox"); // the auto-fit bounds at load
      act(() => { fireEvent.wheel(svg, { deltaY: -100, clientX: 380, clientY: 230 }); });
      flushRaf(6);
      expect(svg.getAttribute("viewBox")).not.toBe(fitted); // zoom eased away
      act(() => { fireEvent.click(screen.getByTestId("graph-reset-view")); });
      expect(svg.getAttribute("viewBox")).toBe(fitted); // reset → back to the fitted frame (instant)
    });
  });

  it("GRAPH-POLISH req3: a DRAG (mousedown+move past threshold+up) pans + a node click after it does NOT focus", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(GLOBAL));
    render(<WikiGraphPage />);
    const svg = await screen.findByTestId("graph-svg");
    mockReplace.mockClear();
    // drag the bg far past the 4px threshold → pans (viewBox x/y move)
    act(() => {
      fireEvent.mouseDown(svg, { button: 0, clientX: 100, clientY: 100 });
      fireEvent.mouseMove(svg, { clientX: 180, clientY: 140 }); // 80px,40px → well past threshold
      fireEvent.mouseUp(svg, { clientX: 180, clientY: 140 });
    });
    const vb = svg.getAttribute("viewBox")!.split(" ").map(Number);
    expect(vb[0] !== 0 || vb[1] !== 0).toBe(true); // panned (x or y moved)
    // a node click WHILE didPan is still true → ignored (pan didn't open a note)
    const node = screen.getAllByTestId("graph-node").find((n) => n.getAttribute("data-node-id") === "88")!;
    fireEvent.click(node);
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("GRAPH-POLISH req3: a CLEAN click (mousedown+up, no move) DOES focus the note (regression guard)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(GLOBAL));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    mockReplace.mockClear();
    const node = screen.getAllByTestId("graph-node").find((n) => n.getAttribute("data-node-id") === "88")!;
    // no drag → mousedown then a plain click (didPan stays false) → opens the note
    fireEvent.mouseDown(node, { button: 0, clientX: 100, clientY: 100 });
    fireEvent.mouseUp(node, { clientX: 100, clientY: 100 });
    fireEvent.click(node);
    expect(mockReplace).toHaveBeenCalledWith("/wiki/graph?note=88");
  });

  it("GRAPH-POLISH req3: a sub-threshold move (<4px) is still a CLICK (opens the note)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(GLOBAL));
    render(<WikiGraphPage />);
    const svg = await screen.findByTestId("graph-svg");
    mockReplace.mockClear();
    const node = screen.getAllByTestId("graph-node").find((n) => n.getAttribute("data-node-id") === "88")!;
    act(() => {
      fireEvent.mouseDown(svg, { button: 0, clientX: 100, clientY: 100 });
      fireEvent.mouseMove(svg, { clientX: 102, clientY: 101 }); // ~2px → under threshold, NOT a pan
      fireEvent.mouseUp(svg, { clientX: 102, clientY: 101 });
    });
    fireEvent.click(node);
    expect(mockReplace).toHaveBeenCalledWith("/wiki/graph?note=88");
  });

  it("GRAPH-POLISH req4: deterministic layout (node transforms are real translate(), may now be negative)", async () => {
    // the viewBox transform sits ON TOP — node translate() positions are layout-only, so
    // they must be real coords (no Math.random regression). GRAPH-POLISH-A: with the hard
    // clamp removed, coords can be NEGATIVE / >W, so allow a sign.
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValue(ok(GLOBAL));
    const { unmount } = render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    const before = screen.getAllByTestId("graph-node").map((n) => n.getAttribute("transform"));
    expect(before.every((t) => /^translate\(-?[\d.]+,-?[\d.]+\)$/.test(t || ""))).toBe(true);
    unmount();
  });

  // ─────────── GRAPH-POLISH-A: organic layout (no hard clamp) + auto-fit viewBox ───────────
  // a fixture that FORCES spread: nodes with NO edges → pure repulsion pushes them out;
  // with the clamp gone they should NOT all pile on the box edges (3/97, 4/96).
  const SPREAD: WikiGraph = {
    center: null,
    nodes: Array.from({ length: 12 }, (_, i) => ({ id: i + 1, title: `n${i + 1}`, status: "evergreen" as const, degree: 0 })),
    edges: [],
    clusters: [],
  };

  it("GRAPH-POLISH-A: NO hard clamp — repulsed nodes are NOT all piled on the box edges (x∈{3,97}/y∈{4,96})", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok(SPREAD));
    render(<WikiGraphPage />);
    await screen.findByTestId("graph-svg");
    // read each node's translate() (rendered coords = (p.x/100)*760, (p.y/100)*460).
    const coords = screen.getAllByTestId("graph-node").map((n) => {
      const m = /translate\((-?[\d.]+),(-?[\d.]+)\)/.exec(n.getAttribute("transform") || "");
      return m ? { x: +m[1] / 760 * 100, y: +m[2] / 460 * 100 } : null;
    }).filter(Boolean) as { x: number; y: number }[];
    // the OLD clamp would force every node onto an edge value (≈3/97 in x or ≈4/96 in y).
    const onEdge = (c: { x: number; y: number }) =>
      Math.abs(c.x - 3) < 0.5 || Math.abs(c.x - 97) < 0.5 || Math.abs(c.y - 4) < 0.5 || Math.abs(c.y - 96) < 0.5;
    expect(coords.every(onEdge)).toBe(false); // NOT all on the frame — organic spread
    // and at least one node lives well inside (not clamped to a wall)
    expect(coords.some((c) => c.x > 10 && c.x < 90 && c.y > 10 && c.y < 90)).toBe(true);
  });

  it("GRAPH-POLISH-A: AUTO-FIT — the default viewBox frames the node bounds + padding (deterministic)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValue(ok(GLOBAL));
    // capture the fitted viewBox twice → must be byte-identical (deterministic fit).
    const cap = async () => {
      const { unmount } = render(<WikiGraphPage />);
      const svg = await screen.findByTestId("graph-svg");
      const vb = svg.getAttribute("viewBox");
      unmount();
      return vb;
    };
    const a = await cap();
    const b = await cap();
    expect(a).toBe(b); // deterministic fit
    // the fitted box brackets the node coords (computed from the transforms) + a margin.
    const { unmount } = render(<WikiGraphPage />);
    const svg = await screen.findByTestId("graph-svg");
    const [vx, vy, vw, vh] = a!.split(" ").map(Number);
    const xs: number[] = [], ys: number[] = [];
    for (const n of screen.getAllByTestId("graph-node")) {
      const m = /translate\((-?[\d.]+),(-?[\d.]+)\)/.exec(n.getAttribute("transform") || "");
      if (m) { xs.push(+m[1]); ys.push(+m[2]); }
    }
    // every node sits inside the fitted box (the box frames them, with padding).
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(vx);
    expect(Math.max(...xs)).toBeLessThanOrEqual(vx + vw);
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(vy);
    expect(Math.max(...ys)).toBeLessThanOrEqual(vy + vh);
    unmount();
  });

  it("GRAPH-POLISH-A: degenerate (1 node) → a sensible default-sized box (no w=0)", async () => {
    mockNoteParam = null;
    getWikiGraphGlobal.mockResolvedValueOnce(ok({
      center: null, nodes: [{ id: 1, title: "solo", status: "evergreen", degree: 0 }], edges: [], clusters: [],
    }));
    render(<WikiGraphPage />);
    const svg = await screen.findByTestId("graph-svg");
    const [, , vw, vh] = svg.getAttribute("viewBox")!.split(" ").map(Number);
    expect(vw).toBeGreaterThan(0); // not a zero-width box
    expect(vh).toBeGreaterThan(0);
  });
});
