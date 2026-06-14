import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { useWikiNote, useWikiInbox } from "../useWiki";
import type { WikiNote, WikiBacklinks, WikiInbox, WikiNoteUpdateInput } from "../types";

afterEach(() => vi.restoreAllMocks());

const NOTE: WikiNote = {
  id: 47,
  title: "Knowledge work accretes",
  aliases: ["accretion"],
  status: "evergreen",
  noteType: "concept",
  trustTier: "verified",
  author: "human",
  tags: ["pkm"],
  content: "Body with [[88|MOCs]].",
  created: "2026-04-02T00:00:00Z",
  updated: "2026-06-13T09:55:00Z",
  contentHash: "abc",
};
const BL: WikiBacklinks = {
  linked: [{ id: 88, title: "MOCs", snippet: "…[[47]]…", anchor: "^b3" }],
  unlinked: [],
  outbound: [{ id: 88, title: "MOCs", isResolved: true }],
};

/** Queue fetch responses in order (the hook GETs note then backlinks). */
function mockFetchSequence(responses: { body: unknown; ok?: boolean; status?: number }[]) {
  const fn = vi.fn();
  for (const r of responses) {
    fn.mockResolvedValueOnce({ ok: r.ok ?? true, status: r.status ?? 200, json: async () => r.body } as Response);
  }
  global.fetch = fn as unknown as typeof fetch;
  return fn;
}

function NoteProbe({ id }: { id: number }) {
  const { note, backlinks, status, errMsg } = useWikiNote(id);
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="title">{note?.title ?? ""}</span>
      <span data-testid="linked">{backlinks?.linked.length ?? -1}</span>
      <span data-testid="err">{errMsg}</span>
    </div>
  );
}

describe("useWikiNote", () => {
  it("loads note + backlinks on success", async () => {
    mockFetchSequence([
      { body: { success: true, data: NOTE } },
      { body: { success: true, data: BL } },
    ]);
    render(<NoteProbe id={47} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("title")).toHaveTextContent("Knowledge work accretes");
    expect(screen.getByTestId("linked")).toHaveTextContent("1");
  });

  it("errors when the note GET 404s (fail-closed, not silent)", async () => {
    mockFetchSequence([{ body: { detail: "not found" }, ok: false, status: 404 }]);
    render(<NoteProbe id={999} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("error"));
    expect(screen.getByTestId("err").textContent).not.toBe("");
  });

  it("fail-soft backlinks: note still renders if backlinks GET fails", async () => {
    mockFetchSequence([
      { body: { success: true, data: NOTE } },
      { body: { detail: "boom" }, ok: false, status: 500 },
    ]);
    render(<NoteProbe id={47} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("title")).toHaveTextContent("Knowledge work accretes");
    expect(screen.getByTestId("linked")).toHaveTextContent("0"); // empty, not crash
  });
});

const INBOX: WikiInbox = {
  items: [
    { id: 47, title: null, status: "fleeting", rawContent: "dump…", captured: "08:12", captureSource: "command_bar", linkCount: 0, aiSuggest: null },
  ],
};

function InboxProbe({ onReady }: { onReady?: (refine: (id: number, i: WikiNoteUpdateInput) => Promise<string | null>) => void }) {
  const { items, status, refine } = useWikiInbox();
  if (status === "ready" && onReady) onReady(refine);
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="count">{items.length}</span>
    </div>
  );
}

describe("useWikiInbox + refine gate", () => {
  it("loads the fleeting list", async () => {
    mockFetchSequence([{ body: { success: true, data: INBOX } }]);
    render(<InboxProbe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("count")).toHaveTextContent("1");
  });

  it("refine THROWS ApiError(422) when the ≥1-link gate fails (fail-closed surface)", async () => {
    const fn = mockFetchSequence([{ body: { success: true, data: INBOX } }]);
    let refineFn: ((id: number, i: WikiNoteUpdateInput) => Promise<string | null>) | null = null;
    render(<InboxProbe onReady={(r) => (refineFn = r)} />);
    await waitFor(() => expect(refineFn).not.toBeNull());

    // next fetch = the refine POST → 422
    fn.mockResolvedValueOnce({ ok: false, status: 422, json: async () => ({ detail: "refine requires ≥1 link" }) } as Response);
    await expect(
      act(async () => {
        await refineFn!(47, { title: "T", content: "no links", status: "developing" });
      }),
    ).rejects.toMatchObject({ status: 422 });
  });

  it("refine returns the cold-start warning on success (200 + warning)", async () => {
    const fn = mockFetchSequence([{ body: { success: true, data: INBOX } }]);
    let refineFn: ((id: number, i: WikiNoteUpdateInput) => Promise<string | null>) | null = null;
    render(<InboxProbe onReady={(r) => (refineFn = r)} />);
    await waitFor(() => expect(refineFn).not.toBeNull());

    fn.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ success: true, data: NOTE, warning: "vault too small to link" }) } as Response);
    // the post-refine reload also fetches the inbox again
    fn.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ success: true, data: INBOX }) } as Response);
    let warn: string | null = "x";
    await act(async () => {
      warn = await refineFn!(47, { content: "c", status: "developing" });
    });
    expect(warn).toContain("vault too small");
  });
});
