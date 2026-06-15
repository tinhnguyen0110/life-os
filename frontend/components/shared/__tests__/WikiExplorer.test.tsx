import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";

const getWikiTree = vi.fn();
const updateWikiNote = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiTree: (...a: unknown[]) => getWikiTree(...a),
    updateWikiNote: (...a: unknown[]) => updateWikiNote(...a),
  };
});
const mockPush = vi.fn();
let mockPath = "/wiki";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockPath,
}));

import { WikiExplorer } from "../WikiExplorer";
import { ApiError } from "@/lib/api";
import type { WikiTree } from "@/lib/types";

function ok<T>(data: T) { return { success: true, data }; }
// Frozen WEXP-BE shape: a recursive nested node {name, path, folders[], notes[]}.
const TREE: WikiTree = {
  name: "", path: "",
  folders: [
    {
      name: "pkm", path: "pkm",
      folders: [{ name: "zettel", path: "pkm/zettel", folders: [], notes: [{ id: 3, title: "Slip box" }] }],
      notes: [{ id: 2, title: "Atomicity" }],
    },
  ],
  notes: [{ id: 1, title: "Root note" }],
};

describe("WikiExplorer (WEXP tree pane)", () => {
  beforeEach(() => { mockPush.mockReset(); updateWikiNote.mockReset(); mockPath = "/wiki"; });

  it("renders nested folders from flat groups + root notes", async () => {
    getWikiTree.mockResolvedValueOnce(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wiki-explorer")).toBeInTheDocument());
    // top-level folder "pkm" + root note present
    const folders = screen.getAllByTestId("wex-folder").map((f) => f.getAttribute("data-folder"));
    expect(folders).toContain("pkm");
    expect(screen.getByTestId("wex-root-notes")).toHaveTextContent("Root note");
  });

  it("expand a folder reveals its notes + nested subfolder", async () => {
    getWikiTree.mockResolvedValueOnce(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wiki-explorer")).toBeInTheDocument());
    const pkm = screen.getAllByTestId("wex-folder").find((f) => f.getAttribute("data-folder") === "pkm")!;
    fireEvent.click(within(pkm).getAllByTestId("wex-folder-toggle")[0]);
    await waitFor(() => expect(within(pkm).getByText("Atomicity")).toBeInTheDocument());
    // nested subfolder pkm/zettel appears
    expect(screen.getAllByTestId("wex-folder").map((f) => f.getAttribute("data-folder"))).toContain("pkm/zettel");
  });

  it("click a file → router.push(/wiki/[id])", async () => {
    getWikiTree.mockResolvedValueOnce(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-root-notes")).toBeInTheDocument());
    fireEvent.click(within(screen.getByTestId("wex-root-notes")).getByTestId("wex-file-open"));
    expect(mockPush).toHaveBeenCalledWith("/wiki/1");
  });

  it("move a note → updateWikiNote(id, {folder}) + refetch", async () => {
    getWikiTree.mockResolvedValueOnce(ok(TREE)).mockResolvedValueOnce(ok(TREE));
    updateWikiNote.mockResolvedValueOnce(ok({}));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-root-notes")).toBeInTheDocument());
    fireEvent.click(within(screen.getByTestId("wex-root-notes")).getByTestId("wex-file-move"));
    await waitFor(() => expect(screen.getByTestId("wex-move-modal")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("wex-move-input"), { target: { value: "pkm" } });
    fireEvent.click(screen.getByTestId("wex-move-submit"));
    await waitFor(() => expect(updateWikiNote).toHaveBeenCalledWith(1, { folder: "pkm" }));
    await waitFor(() => expect(getWikiTree).toHaveBeenCalledTimes(2));
  });

  it("FAIL-CLOSED: move error → surfaced in modal, not swallowed", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    updateWikiNote.mockRejectedValueOnce(new ApiError(404, "note gone"));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-root-notes")).toBeInTheDocument());
    fireEvent.click(within(screen.getByTestId("wex-root-notes")).getByTestId("wex-file-move"));
    await waitFor(() => expect(screen.getByTestId("wex-move-modal")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("wex-move-input"), { target: { value: "x" } });
    fireEvent.click(screen.getByTestId("wex-move-submit"));
    await waitFor(() => expect(screen.getByTestId("wex-move-error")).toHaveTextContent("note gone"));
  });

  it("empty vault → honest empty (not a crash)", async () => {
    getWikiTree.mockResolvedValueOnce(ok({ name: "", path: "", folders: [], notes: [] }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-empty")).toBeInTheDocument());
  });

  it("tree error → inline error w/ retry (fail-soft, pane not blanked)", async () => {
    getWikiTree.mockRejectedValueOnce(new ApiError(500, "tree down"));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-error")).toBeInTheDocument());
    expect(screen.getByTestId("wiki-explorer")).toBeInTheDocument(); // pane still there
  });

  // Regression: the explorer must REFETCH the tree when the route changes, so a note
  // deleted from the note page (which routes back to /wiki) disappears from the tree
  // without a manual refresh. Previously the tree was fetched once on mount only.
  it("refetches the tree when the pathname changes (e.g. after a delete routes to /wiki)", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    mockPath = "/wiki/3";
    const { rerender } = render(<WikiExplorer />);
    await waitFor(() => expect(getWikiTree).toHaveBeenCalledTimes(1));
    // simulate navigation (note deleted → routed to /wiki): pathname changes
    mockPath = "/wiki";
    rerender(<WikiExplorer />);
    await waitFor(() => expect(getWikiTree).toHaveBeenCalledTimes(2));
  });
});
