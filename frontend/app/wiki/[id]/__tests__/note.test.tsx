import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the named api fns the useWikiNote hook calls (module-closure refs).
const getWikiNote = vi.fn();
const getWikiBacklinks = vi.fn();
const updateWikiNote = vi.fn();
const deleteWikiNote = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiNote: (...a: unknown[]) => getWikiNote(...a),
    getWikiBacklinks: (...a: unknown[]) => getWikiBacklinks(...a),
    updateWikiNote: (...a: unknown[]) => updateWikiNote(...a),
    deleteWikiNote: (...a: unknown[]) => deleteWikiNote(...a),
  };
});
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
// Router mock — the delete flow calls router.push("/wiki") on success.
const routerPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush }),
}));

import WikiNotePage from "../page";
import { ApiError } from "@/lib/api";
import type { WikiNote, WikiBacklinks } from "@/lib/types";

const NOTE: WikiNote = {
  id: 47,
  title: "Knowledge work accretes",
  aliases: ["accretion model"],
  status: "evergreen",
  noteType: "concept",
  trustTier: "verified",
  author: "human",
  tags: ["learning", "pkm"],
  content: "Tri thức **bồi đắp** qua [[88|MOCs are workstations]] và [[Atomicity principle]].",
  created: "2026-04-02",
  updated: "2026-06-13 · 09:55",
  contentHash: "h",
};
const BL: WikiBacklinks = {
  linked: [{ id: 88, title: "MOCs are workstations", snippet: "…<b>[[47]]</b>…", anchor: "^b3" }],
  unlinked: [{ id: 102, title: "Evergreen notes compound", snippet: "…accretes…" }],
  outbound: [
    { id: 88, title: "MOCs are workstations", isResolved: true },
    { ghost: "Atomicity principle", isResolved: false },
  ],
};

function ok<T>(data: T, warning?: string) {
  return { success: true, data, ...(warning ? { warning } : {}) };
}

describe("W2 Note view/edit", () => {
  it("renders a real note: header id/status/type/trust + title + body wikilinks", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    render(<WikiNotePage params={{ id: "47" }} />);
    await waitFor(() => expect(screen.getByTestId("wiki-note-screen")).toBeInTheDocument());
    expect(screen.getByTestId("wiki-id")).toHaveTextContent("#47");
    expect(screen.getByTestId("wiki-status")).toHaveTextContent("evergreen");
    expect(screen.getByTestId("wiki-type")).toHaveTextContent("concept");
    expect(screen.getByTestId("wiki-trust")).toHaveTextContent("verified");
    expect(screen.getByTestId("wiki-title")).toHaveTextContent("Knowledge work accretes");
    // body rendered the resolved wikilink + bold — scope to the body (the title
    // "MOCs are workstations" ALSO appears in backlinks/outbound panels).
    const body = within(screen.getByTestId("wiki-body"));
    expect(body.getByText("MOCs are workstations")).toHaveAttribute("href", "/wiki/88");
    // WEXP: body now renders via WikiMarkdown (react-markdown) — **bold** → <strong>
    // (semantic standard) instead of the old hand-rolled <b>. Wikilinks still preserved.
    expect(body.getByText("bồi đắp").tagName).toBe("STRONG");
    // ghost link in body is NOT a link
    const bodyGhost = body.getByText("Atomicity principle");
    expect(bodyGhost.tagName).toBe("SPAN");
    expect(bodyGhost.className).toContain("ghost");
  });

  it("renders backlinks (linked clickable + unlinked) + outbound (resolved + ghost)", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    render(<WikiNotePage params={{ id: "47" }} />);
    await waitFor(() => expect(screen.getByTestId("wiki-note-screen")).toBeInTheDocument());
    expect(screen.getByTestId("linked-row")).toHaveAttribute("href", "/wiki/88");
    expect(screen.getByTestId("unlinked-row")).toHaveTextContent("Evergreen notes compound");
    expect(screen.getByTestId("outbound-resolved")).toHaveAttribute("href", "/wiki/88");
    expect(screen.getByTestId("outbound-ghost")).toHaveTextContent("Atomicity principle");
  });

  it("AI link-suggestions panel shows the EMPTY state (M1, NOT fabricated)", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    render(<WikiNotePage params={{ id: "47" }} />);
    await waitFor(() => expect(screen.getByTestId("wiki-note-screen")).toBeInTheDocument());
    expect(screen.getByTestId("wiki-suggestions-empty")).toBeInTheDocument();
    expect(screen.getByTestId("wiki-suggestions-empty")).toHaveTextContent("Claude Code");
  });

  it("candidate note shows the trust badge + ratify warning banner", async () => {
    getWikiNote.mockResolvedValueOnce(ok({ ...NOTE, trustTier: "candidate", author: "agent:claude-code" }));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    render(<WikiNotePage params={{ id: "47" }} />);
    await waitFor(() => expect(screen.getByTestId("wiki-note-screen")).toBeInTheDocument());
    expect(screen.getByTestId("wiki-trust")).toHaveTextContent("candidate");
    expect(screen.getByTestId("wiki-candidate-warn")).toHaveTextContent("Ratify");
  });

  it("edit → save: PUTs the edit then refetches (server-truth, not optimistic)", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE)); // initial
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    updateWikiNote.mockResolvedValueOnce(ok({ ...NOTE, title: "Renamed", status: "developing" }));
    getWikiNote.mockResolvedValueOnce(ok({ ...NOTE, title: "Renamed", status: "developing" })); // refetch
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));

    render(<WikiNotePage params={{ id: "47" }} />);
    await waitFor(() => expect(screen.getByTestId("wiki-note-screen")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("wiki-edit-btn"));

    const titleInput = screen.getByTestId("wiki-edit-title") as HTMLInputElement;
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Renamed");
    await userEvent.click(screen.getByTestId("wiki-edit-save"));

    await waitFor(() => expect(updateWikiNote).toHaveBeenCalled());
    const [calledId, body] = updateWikiNote.mock.calls[0];
    expect(calledId).toBe(47);
    expect(body.title).toBe("Renamed");
    // after refetch, the new title shows + edit mode closed (view title visible)
    await waitFor(() => expect(screen.getByTestId("wiki-title")).toHaveTextContent("Renamed"));
  });

  it("TEETH: save FAILS (422) → error surfaces, edit mode STAYS open (fail-closed)", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    updateWikiNote.mockRejectedValueOnce(new ApiError(422, "title: too long"));

    render(<WikiNotePage params={{ id: "47" }} />);
    await waitFor(() => expect(screen.getByTestId("wiki-note-screen")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("wiki-edit-btn"));
    await userEvent.click(screen.getByTestId("wiki-edit-save"));

    await waitFor(() => expect(screen.getByTestId("wiki-edit-error")).toBeInTheDocument());
    expect(screen.getByTestId("wiki-edit-error")).toHaveTextContent("too long");
    // still in edit mode (save button present) — NOT closed/saved
    expect(screen.getByTestId("wiki-edit-save")).toBeInTheDocument();
  });

  it("404 → error state (not a crash)", async () => {
    getWikiNote.mockRejectedValueOnce(new ApiError(404, "note 999 not found"));
    render(<WikiNotePage params={{ id: "999" }} />);
    await waitFor(() => expect(screen.getByTestId("wiki-error")).toBeInTheDocument());
  });

  it("non-numeric id → error state (no NaN fetch)", async () => {
    render(<WikiNotePage params={{ id: "abc" }} />);
    await waitFor(() => expect(screen.getByTestId("wiki-error")).toBeInTheDocument());
    expect(getWikiNote).not.toHaveBeenCalled();
  });

  // --- delete control (gap closed: the note page now exposes delete) ---
  it("delete is a TWO-CLICK confirm: first click arms it, does NOT delete yet", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    render(<WikiNotePage params={{ id: "47" }} />);
    await screen.findByTestId("wiki-id");

    // first click: arms — confirm button appears, delete NOT called (no 1-click loss)
    await userEvent.click(screen.getByTestId("wiki-delete-btn"));
    expect(screen.getByTestId("wiki-delete-confirm")).toBeInTheDocument();
    expect(deleteWikiNote).not.toHaveBeenCalled();
    expect(routerPush).not.toHaveBeenCalled();
  });

  // #94 — delete is now SOFT (recoverable): navigates to /wiki?trashed=<id> so the vault
  // shows the "moved to trash · restore" toast (NOT a scary permanent delete).
  it("confirm → SOFT-deletes the note then navigates to /wiki?trashed=<id> (recoverable)", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    deleteWikiNote.mockResolvedValueOnce(ok({ deleted: 47, deletedAt: "2026-06-21T10:00:00Z" }));
    render(<WikiNotePage params={{ id: "47" }} />);
    await screen.findByTestId("wiki-id");

    await userEvent.click(screen.getByTestId("wiki-delete-btn"));      // arm
    // the confirm copy reflects soft-delete ("thùng rác"), not a scary "xoá"
    expect(screen.getByTestId("wiki-delete-confirm")).toHaveTextContent(/thùng rác/i);
    await userEvent.click(screen.getByTestId("wiki-delete-confirm"));  // confirm
    await waitFor(() => expect(deleteWikiNote).toHaveBeenCalledWith(47));
    await waitFor(() => expect(routerPush).toHaveBeenCalledWith("/wiki?trashed=47"));
  });

  it("cancel disarms the delete (note NOT deleted)", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    render(<WikiNotePage params={{ id: "47" }} />);
    await screen.findByTestId("wiki-id");

    await userEvent.click(screen.getByTestId("wiki-delete-btn"));     // arm
    await userEvent.click(screen.getByTestId("wiki-delete-cancel"));  // cancel
    // back to the un-armed delete button; nothing deleted/navigated
    expect(screen.getByTestId("wiki-delete-btn")).toBeInTheDocument();
    expect(screen.queryByTestId("wiki-delete-confirm")).toBeNull();
    expect(deleteWikiNote).not.toHaveBeenCalled();
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("TEETH: delete FAILS → error surfaces, no navigation, note stays (fail-closed)", async () => {
    getWikiNote.mockResolvedValueOnce(ok(NOTE));
    getWikiBacklinks.mockResolvedValueOnce(ok(BL));
    deleteWikiNote.mockRejectedValueOnce(new ApiError(500, "delete failed"));
    render(<WikiNotePage params={{ id: "47" }} />);
    await screen.findByTestId("wiki-id");

    await userEvent.click(screen.getByTestId("wiki-delete-btn"));      // arm
    await userEvent.click(screen.getByTestId("wiki-delete-confirm"));  // confirm → rejects
    await waitFor(() => expect(screen.getByTestId("wiki-delete-err")).toBeInTheDocument());
    expect(routerPush).not.toHaveBeenCalled(); // did NOT navigate
  });
});
