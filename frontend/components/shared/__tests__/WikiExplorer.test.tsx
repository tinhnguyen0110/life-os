import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within, act } from "@testing-library/react";

const getWikiTree = vi.fn();
const updateWikiNote = vi.fn();
const createWikiFolder = vi.fn();
const deleteWikiFolder = vi.fn();
const moveWikiFolder = vi.fn();
const importWiki = vi.fn();
const createWikiNote = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiTree: (...a: unknown[]) => getWikiTree(...a),
    updateWikiNote: (...a: unknown[]) => updateWikiNote(...a),
    // #127-W3 folder/file ops
    createWikiFolder: (...a: unknown[]) => createWikiFolder(...a),
    deleteWikiFolder: (...a: unknown[]) => deleteWikiFolder(...a),
    moveWikiFolder: (...a: unknown[]) => moveWikiFolder(...a),
    importWiki: (...a: unknown[]) => importWiki(...a),
    // #127-W3A — note-in-folder
    createWikiNote: (...a: unknown[]) => createWikiNote(...a),
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

  it("click a file → router.push(/wiki/[id]) on a NON-graph route (unchanged)", async () => {
    mockPath = "/wiki"; // default route
    getWikiTree.mockResolvedValueOnce(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-root-notes")).toBeInTheDocument());
    fireEvent.click(within(screen.getByTestId("wex-root-notes")).getByTestId("wex-file-open"));
    expect(mockPush).toHaveBeenCalledWith("/wiki/1");
  });

  it("GRAPH-FIX (Fix 1): on /wiki/graph → DISPATCHES wiki:graph-open-note (does NOT navigate away)", async () => {
    mockPath = "/wiki/graph";
    getWikiTree.mockResolvedValueOnce(ok(TREE));
    const events: number[] = [];
    const onEvt = (e: Event) => events.push((e as CustomEvent<{ id: number }>).detail.id);
    window.addEventListener("wiki:graph-open-note", onEvt);
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-root-notes")).toBeInTheDocument());
    fireEvent.click(within(screen.getByTestId("wex-root-notes")).getByTestId("wex-file-open"));
    window.removeEventListener("wiki:graph-open-note", onEvt);
    expect(events).toEqual([1]);          // dispatched the open-note event for id 1
    expect(mockPush).not.toHaveBeenCalled(); // and did NOT navigate away from the graph
  });

  it("GRAPH-FIX (Fix 1): on /wiki/[id] → still router.push (other routes NOT broken)", async () => {
    mockPath = "/wiki/47";
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

  // #108 — THE bug: a write to a NEW folder (no navigation) must refresh the Explorer
  // count WITHOUT a manual reload. The write-through bumps the wiki-tree bus → the
  // Explorer's useWikiTree refetches → the new folder + its count appear.
  it("a tree-mutating write (bus bump) refetches the tree → the new folder appears (no reload, no nav)", async () => {
    const TREE_BEFORE: WikiTree = { name: "", path: "", folders: [], notes: [{ id: 1, title: "Root note" }] };
    const TREE_AFTER: WikiTree = {
      name: "", path: "",
      folders: [{ name: "Projects", path: "Projects", folders: [], notes: [{ id: 9, title: "fulfill-app" }] }],
      notes: [{ id: 1, title: "Root note" }],
    };
    getWikiTree.mockResolvedValueOnce(ok(TREE_BEFORE));  // initial mount fetch
    getWikiTree.mockResolvedValueOnce(ok(TREE_AFTER));   // refetch after the write

    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wiki-explorer")).toBeInTheDocument());
    // before the write: no "Projects" folder
    expect(screen.queryAllByTestId("wex-folder").map((f) => f.getAttribute("data-folder"))).not.toContain("Projects");

    // a write elsewhere (create note into Projects/) bumps the bus — NO navigation.
    const { markWikiTreeStale } = await import("@/lib/wikiTreeBus");
    act(() => markWikiTreeStale());

    // the Explorer refetched + now shows the new folder (the BE-truth count) — live, no reload.
    await waitFor(() => expect(getWikiTree).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getAllByTestId("wex-folder").map((f) => f.getAttribute("data-folder"))).toContain("Projects")
    );
  });

  it("real write fns bump the bus → the Explorer refetches (createWikiNote path)", async () => {
    // prove the WIRING: calling the real createWikiNote (its inner apiPost mocked to resolve)
    // bumps the bus, which the mounted Explorer is subscribed to → a refetch fires.
    getWikiTree.mockResolvedValue(ok(TREE)); // any tree; we assert the refetch count
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wiki-explorer")).toBeInTheDocument());
    expect(getWikiTree).toHaveBeenCalledTimes(1);

    // directly bump via the bus (same effect createWikiNote.then(bumpTree) has on success)
    const { markWikiTreeStale } = await import("@/lib/wikiTreeBus");
    act(() => markWikiTreeStale());
    await waitFor(() => expect(getWikiTree).toHaveBeenCalledTimes(2));
  });
});

describe("#127-W3 WikiExplorer — folder + file ops menu", () => {
  beforeEach(() => {
    mockPush.mockReset(); mockPath = "/wiki";
    createWikiFolder.mockReset(); deleteWikiFolder.mockReset();
    moveWikiFolder.mockReset(); importWiki.mockReset(); getWikiTree.mockReset();
  });

  it("🔴 NESTED create: a folder's ⋯ → 'Thư mục con mới' → createWikiFolder({path: parent+'/'+name})", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    createWikiFolder.mockResolvedValue(ok({ path: "pkm/zettel2", desc: "", created: true }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    // open the pkm folder's ops menu → new-sub
    fireEvent.click(screen.getByTestId("wex-ops-toggle-pkm"));
    fireEvent.click(screen.getByTestId("wex-op-newsub-pkm"));
    // type the CHILD name + submit → POST with the NESTED path
    fireEvent.change(screen.getByTestId("wex-op-input"), { target: { value: "zettel2" } });
    fireEvent.click(screen.getByTestId("wex-op-submit"));
    await waitFor(() => expect(createWikiFolder).toHaveBeenCalledWith({ path: "pkm/zettel2" }));
  });

  it("new ROOT folder: the toolbar ＋ → createWikiFolder({path: name})", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    createWikiFolder.mockResolvedValue(ok({ path: "newroot", desc: "", created: true }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-new-folder")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-new-folder"));
    fireEvent.change(screen.getByTestId("wex-op-input"), { target: { value: "newroot" } });
    fireEvent.click(screen.getByTestId("wex-op-submit"));
    await waitFor(() => expect(createWikiFolder).toHaveBeenCalledWith({ path: "newroot" }));
  });

  it("🔴 DELETE: ⋯ → 'Xóa' → an IN-PAGE confirm (NOT window.confirm) → deleteWikiFolder + tree refetch", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    getWikiTree.mockResolvedValue(ok(TREE));
    deleteWikiFolder.mockResolvedValue(ok({ folder: "pkm", deletedNotes: [2, 3], removedMeta: ["pkm"], warnings: [] }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    expect(getWikiTree).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId("wex-ops-toggle-pkm"));
    fireEvent.click(screen.getByTestId("wex-op-delete-pkm"));
    // an in-page confirm dialog appears (NOT a native window.confirm)
    expect(screen.getByTestId("wex-delete-confirm")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("wex-delete-confirm-yes"));
    await waitFor(() => expect(deleteWikiFolder).toHaveBeenCalledWith("pkm"));
    // 🔴 the gotcha: "gone" is observed via a REFETCHED tree (reload), not get_note
    await waitFor(() => expect(getWikiTree).toHaveBeenCalledTimes(2));
    expect(confirmSpy).not.toHaveBeenCalled(); // never the blocking native confirm
    confirmSpy.mockRestore();
  });

  it("delete can be CANCELLED in-page (no DELETE fired)", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-ops-toggle-pkm"));
    fireEvent.click(screen.getByTestId("wex-op-delete-pkm"));
    fireEvent.click(screen.getByTestId("wex-delete-cancel"));
    expect(screen.queryByTestId("wex-delete-confirm")).toBeNull();
    expect(deleteWikiFolder).not.toHaveBeenCalled();
  });

  it("RENAME / MOVE: ⋯ → 'Đổi tên / Chuyển' → moveWikiFolder(path, to)", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    moveWikiFolder.mockResolvedValue(ok({ from: "pkm", to: "knowledge", movedNotes: [2], movedMeta: 1, warnings: [] }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-ops-toggle-pkm"));
    fireEvent.click(screen.getByTestId("wex-op-rename-pkm"));
    // prefilled with the current path; change to the new one
    fireEvent.change(screen.getByTestId("wex-op-input"), { target: { value: "knowledge" } });
    fireEvent.click(screen.getByTestId("wex-op-submit"));
    await waitFor(() => expect(moveWikiFolder).toHaveBeenCalledWith("pkm", "knowledge"));
  });

  it("a folder-op ERROR (e.g. dup → 409) is surfaced honestly (agent-error msg+hint)", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    createWikiFolder.mockRejectedValue(new ApiError(409, "folder exists", { hint: "pick another name" }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-new-folder")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-new-folder"));
    fireEvent.change(screen.getByTestId("wex-op-input"), { target: { value: "pkm" } });
    fireEvent.click(screen.getByTestId("wex-op-submit"));
    await waitFor(() => expect(screen.getByTestId("wex-op-error")).toHaveTextContent("folder exists"));
    expect(screen.getByTestId("wex-op-error")).toHaveTextContent("pick another name"); // hint
  });

  it("IMPORT paste .md → importWiki({files:[{filename,content}]}) + result shown", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    importWiki.mockResolvedValue(ok({ imported: [{ filename: "note.md", ok: true, noteId: 50, title: "note", error: null }], createdCount: 1 }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-import-open")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-import-open"));
    fireEvent.change(screen.getByTestId("wex-import-paste-name"), { target: { value: "note.md" } });
    fireEvent.change(screen.getByTestId("wex-import-paste-body"), { target: { value: "# hi\nbody" } });
    fireEvent.click(screen.getByTestId("wex-import-paste-submit"));
    await waitFor(() => expect(importWiki).toHaveBeenCalledWith({ files: [{ filename: "note.md", content: "# hi\nbody" }] }));
    await waitFor(() => expect(screen.getByTestId("wex-import-result-0")).toHaveTextContent("note.md"));
  });

  it("🔴 IMPORT a .pdf (paste) → client-side REJECT (.md/.txt only), no POST", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-import-open")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-import-open"));
    fireEvent.change(screen.getByTestId("wex-import-paste-name"), { target: { value: "x.pdf" } });
    fireEvent.change(screen.getByTestId("wex-import-paste-body"), { target: { value: "x" } });
    fireEvent.click(screen.getByTestId("wex-import-paste-submit"));
    await waitFor(() => expect(screen.getByTestId("wex-import-error")).toHaveTextContent(/\.md|\.txt/));
    expect(importWiki).not.toHaveBeenCalled(); // rejected before the POST
  });

  it("IMPORT surfaces the BE per-file rejection honestly (a .pdf the BE rejected)", async () => {
    // even if a bad file reaches the BE (e.g. via the file picker), the per-file error shows.
    getWikiTree.mockResolvedValue(ok(TREE));
    importWiki.mockResolvedValue(ok({ imported: [{ filename: "x.pdf", ok: false, noteId: null, title: null, error: { code: "INVALID_INPUT", message: "unsupported file type '.pdf'", hint: "only .md/.txt", retryable: false } }], createdCount: 0 }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-import-open")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-import-open"));
    // a valid-named paste that the BE still rejects (simulating the per-file path)
    fireEvent.change(screen.getByTestId("wex-import-paste-name"), { target: { value: "note.md" } });
    fireEvent.change(screen.getByTestId("wex-import-paste-body"), { target: { value: "x" } });
    fireEvent.click(screen.getByTestId("wex-import-paste-submit"));
    await waitFor(() => expect(screen.getByTestId("wex-import-rejected-0")).toHaveTextContent("unsupported file type"));
  });

  it("mock-diff: the #108 features are KEPT (tree browse, note open, move-note) alongside the ops", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    // #108 still present: folders, files, the per-note move button
    expect(screen.getAllByTestId("wex-folder").length).toBeGreaterThan(0);
    expect(screen.getByTestId("wex-refresh")).toBeInTheDocument();
    // and the NEW ops toolbar
    expect(screen.getByTestId("wex-new-folder")).toBeInTheDocument();
    expect(screen.getByTestId("wex-import-open")).toBeInTheDocument();
  });
});

describe("#127-W3A WikiExplorer — import INTO a folder + new note IN a folder", () => {
  beforeEach(() => {
    mockPush.mockReset(); mockPath = "/wiki";
    createWikiFolder.mockReset(); deleteWikiFolder.mockReset(); moveWikiFolder.mockReset();
    importWiki.mockReset(); createWikiNote.mockReset(); updateWikiNote.mockReset(); getWikiTree.mockReset();
  });

  it("🔴 import a .md INTO a folder (modal picker) → import→root then PUT {folder} (the 2-step)", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    importWiki.mockResolvedValue(ok({ imported: [{ filename: "note.md", ok: true, noteId: 50, title: "note", error: null }], createdCount: 1 }));
    updateWikiNote.mockResolvedValue(ok({}));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-import-open")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-import-open"));
    // pick the target folder (the picker has root + the existing folders)
    fireEvent.change(screen.getByTestId("wex-import-folder"), { target: { value: "pkm" } });
    fireEvent.change(screen.getByTestId("wex-import-paste-name"), { target: { value: "note.md" } });
    fireEvent.change(screen.getByTestId("wex-import-paste-body"), { target: { value: "# hi" } });
    fireEvent.click(screen.getByTestId("wex-import-paste-submit"));
    // step 1: import lands at root
    await waitFor(() => expect(importWiki).toHaveBeenCalledWith({ files: [{ filename: "note.md", content: "# hi" }] }));
    // step 2: the created note is MOVED into the target folder (the 2-step)
    await waitFor(() => expect(updateWikiNote).toHaveBeenCalledWith(50, { folder: "pkm" }));
  });

  it("import to ROOT (default target) → NO move (the note stays at root)", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    importWiki.mockResolvedValue(ok({ imported: [{ filename: "r.md", ok: true, noteId: 60, title: "r", error: null }], createdCount: 1 }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-import-open")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-import-open")); // toolbar import → target = root ("")
    fireEvent.change(screen.getByTestId("wex-import-paste-name"), { target: { value: "r.md" } });
    fireEvent.change(screen.getByTestId("wex-import-paste-body"), { target: { value: "x" } });
    fireEvent.click(screen.getByTestId("wex-import-paste-submit"));
    await waitFor(() => expect(importWiki).toHaveBeenCalled());
    // root target → no PUT move
    expect(updateWikiNote).not.toHaveBeenCalled();
  });

  it("🔴 '📥 Import vào đây' on a folder → opens the import modal PRE-TARGETED to that folder", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-ops-toggle-pkm"));
    fireEvent.click(screen.getByTestId("wex-op-importhere-pkm"));
    // the import modal opens, the folder picker pre-selected to "pkm"
    expect(screen.getByTestId("wex-import-modal")).toBeInTheDocument();
    expect((screen.getByTestId("wex-import-folder") as HTMLSelectElement).value).toBe("pkm");
  });

  it("🔴 '＋ Note mới' on a folder → in-page title input → createWikiNote({title, folder})", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    createWikiNote.mockResolvedValue(ok({ id: 70, title: "Ý tưởng" }));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-ops-toggle-pkm"));
    fireEvent.click(screen.getByTestId("wex-op-newnote-pkm"));
    // an in-page title input (NOT window.prompt)
    fireEvent.change(screen.getByTestId("wex-op-input"), { target: { value: "Ý tưởng" } });
    fireEvent.click(screen.getByTestId("wex-op-submit"));
    await waitFor(() => expect(createWikiNote).toHaveBeenCalledWith({ title: "Ý tưởng", content: "", folder: "pkm" }));
    // opens the new note
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/wiki/70"));
  });

  it("'＋ Note mới' with a blank title → validation error, no create", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-ops-toggle-pkm"));
    fireEvent.click(screen.getByTestId("wex-op-newnote-pkm"));
    fireEvent.click(screen.getByTestId("wex-op-submit")); // blank title
    await waitFor(() => expect(screen.getByTestId("wex-op-error")).toHaveTextContent(/tiêu đề/));
    expect(createWikiNote).not.toHaveBeenCalled();
  });

  it("the folder ⋯ menu now has BOTH the W3 ops AND the W3A import/note ops (mock-diff)", async () => {
    getWikiTree.mockResolvedValue(ok(TREE));
    render(<WikiExplorer />);
    await waitFor(() => expect(screen.getByTestId("wex-tree")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("wex-ops-toggle-pkm"));
    // W3A added
    expect(screen.getByTestId("wex-op-newnote-pkm")).toBeInTheDocument();
    expect(screen.getByTestId("wex-op-importhere-pkm")).toBeInTheDocument();
    // W3 KEPT
    expect(screen.getByTestId("wex-op-newsub-pkm")).toBeInTheDocument();
    expect(screen.getByTestId("wex-op-rename-pkm")).toBeInTheDocument();
    expect(screen.getByTestId("wex-op-delete-pkm")).toBeInTheDocument();
  });
});
