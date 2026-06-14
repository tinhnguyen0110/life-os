import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

const getWikiGraph = vi.fn();
const searchWiki = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiGraph: (...a: unknown[]) => getWikiGraph(...a),
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

describe("W4 Graph Explorer", () => {
  it("idle (no center chosen) → 'chọn note tâm' prompt, no graph fetch", async () => {
    mockNoteParam = null;
    render(<WikiGraphPage />);
    await waitFor(() => expect(screen.getByTestId("graph-idle")).toBeInTheDocument());
    expect(getWikiGraph).not.toHaveBeenCalled();
  });

  it("deep-link ?note=47 → fetches graph and renders SVG nodes/edges", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH));
    render(<WikiGraphPage />);
    await waitFor(() => expect(getWikiGraph).toHaveBeenCalledWith(47, 2));
    await screen.findByTestId("graph-svg");
    expect(screen.getAllByTestId("graph-node").length).toBe(3);
    expect(screen.getAllByTestId("graph-edge").length).toBe(1);
  });

  it("node click routes to /wiki/[id]", async () => {
    mockNoteParam = "47";
    getWikiGraph.mockResolvedValueOnce(ok(GRAPH));
    render(<WikiGraphPage />);
    const nodes = await screen.findAllByTestId("graph-node");
    const node88 = nodes.find((n) => n.getAttribute("data-node-id") === "88")!;
    fireEvent.click(node88);
    expect(mockPush).toHaveBeenCalledWith("/wiki/88");
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

  it("404 center note → error state, not a crash", async () => {
    mockNoteParam = "999";
    getWikiGraph.mockRejectedValueOnce(new Error("wiki note 999 not found"));
    render(<WikiGraphPage />);
    await waitFor(() => expect(screen.getByTestId("graph-error")).toBeInTheDocument());
    expect(screen.getByTestId("graph-error")).toHaveTextContent("not found");
  });

  it("center picker → choosing a hit sets center + updates URL", async () => {
    mockNoteParam = null;
    searchWiki.mockResolvedValue(ok([{ id: 88, title: "MOCs are workstations", status: "evergreen", snippet: "..." }]));
    getWikiGraph.mockResolvedValue(ok({ ...GRAPH, center: 88 }));
    render(<WikiGraphPage />);
    await waitFor(() => expect(screen.getByTestId("graph-idle")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("graph-search-input"), { target: { value: "MOC" } });
    const hit = await screen.findByTestId("graph-search-hit");
    fireEvent.click(hit);
    expect(mockReplace).toHaveBeenCalledWith("/wiki/graph?note=88");
    await waitFor(() => expect(getWikiGraph).toHaveBeenCalledWith(88, 2));
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
