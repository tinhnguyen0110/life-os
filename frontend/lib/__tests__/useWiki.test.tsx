import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { useWikiNote } from "../useWiki";
import type { WikiNote, WikiBacklinks } from "../types";

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
