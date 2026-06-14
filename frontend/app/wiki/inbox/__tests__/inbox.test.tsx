import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** Set a textarea value directly — userEvent.type treats `[`/`{` as special keys,
 *  which mangles a literal `[[id|title]]` wikilink. fireEvent.change is verbatim. */
function setBody(el: HTMLElement, value: string) {
  const ta = within(el).getByTestId("wedit-textarea") as HTMLTextAreaElement;
  fireEvent.change(ta, { target: { value } });
  return ta;
}

const getWikiInbox = vi.fn();
const refineWikiNote = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiInbox: (...a: unknown[]) => getWikiInbox(...a),
    refineWikiNote: (...a: unknown[]) => refineWikiNote(...a),
  };
});
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import WikiInboxPage from "../page";
import { ApiError } from "@/lib/api";
import type { WikiInbox, WikiNote } from "@/lib/types";

const INBOX: WikiInbox = {
  items: [
    { id: 47, title: null, status: "fleeting", rawContent: "tri thức bồi đắp qua kết nối nhỏ", captured: "08:12", captureSource: "command_bar", linkCount: 0, aiSuggest: null },
    { id: 201, title: null, status: "fleeting", rawContent: "dry powder = slack", captured: "07:48", captureSource: "daily_note", linkCount: 0, aiSuggest: null },
  ],
};
const REFINED: WikiNote = {
  id: 47, title: "Knowledge work accretes", aliases: [], status: "developing", noteType: "concept",
  trustTier: "verified", author: "human", tags: [], content: "atomic [[88|MOC]]", created: "x", updated: "y", contentHash: "h",
};
function ok<T>(data: T, warning?: string) {
  return { success: true, data, ...(warning ? { warning } : {}) };
}

describe("W3 Inbox / Refine", () => {
  it("renders the fleeting list + progress count", async () => {
    getWikiInbox.mockResolvedValueOnce(ok(INBOX));
    render(<WikiInboxPage />);
    await waitFor(() => expect(screen.getByTestId("inbox-screen")).toBeInTheDocument());
    expect(screen.getAllByTestId("inbox-row").length).toBe(2);
    expect(screen.getByTestId("inbox-progress")).toHaveTextContent("2");
  });

  it("opens the refine panel for the first item + shows raw capture + AI empty-state", async () => {
    getWikiInbox.mockResolvedValueOnce(ok(INBOX));
    render(<WikiInboxPage />);
    await waitFor(() => expect(screen.getByTestId("refine-panel")).toBeInTheDocument());
    expect(screen.getByTestId("refine-raw")).toHaveTextContent("tri thức bồi đắp");
    expect(screen.getByTestId("refine-ai-empty")).toHaveTextContent("Claude Code");
  });

  it("gate shows BLOCKED with no link, OK once a [[link]] is in the body", async () => {
    getWikiInbox.mockResolvedValueOnce(ok(INBOX));
    render(<WikiInboxPage />);
    await waitFor(() => expect(screen.getByTestId("refine-gate")).toBeInTheDocument());
    expect(screen.getByTestId("refine-gate")).toHaveAttribute("data-gate", "blocked");

    // put a wikilink into the body → gate flips to ok (advisory)
    setBody(screen.getByTestId("refine-body"), "atomic prose [[88|MOC]]");
    await waitFor(() => expect(screen.getByTestId("refine-gate")).toHaveAttribute("data-gate", "ok"));
  });

  it("refine success → POSTs refine then refetches (note left fleeting)", async () => {
    getWikiInbox.mockResolvedValueOnce(ok(INBOX)); // initial
    refineWikiNote.mockResolvedValueOnce(ok(REFINED));
    getWikiInbox.mockResolvedValueOnce(ok({ items: [INBOX.items[1]] })); // refetch: 1 left
    render(<WikiInboxPage />);
    await waitFor(() => expect(screen.getByTestId("refine-panel")).toBeInTheDocument());

    setBody(screen.getByTestId("refine-body"), "atomic prose [[88|MOC]]");
    await userEvent.click(screen.getByTestId("refine-done"));

    await waitFor(() => expect(refineWikiNote).toHaveBeenCalled());
    const [id, body] = refineWikiNote.mock.calls[0];
    expect(id).toBe(47);
    expect(body.status).toBe("developing");
    // refetched list shrank to 1
    await waitFor(() => expect(screen.getByTestId("inbox-progress")).toHaveTextContent("1"));
  });

  it("TEETH: 0-link non-cold-start → 422 surfaces VISIBLY, note NOT refined (fail-closed)", async () => {
    getWikiInbox.mockResolvedValueOnce(ok(INBOX));
    refineWikiNote.mockRejectedValueOnce(new ApiError(422, "refine requires ≥1 link"));
    render(<WikiInboxPage />);
    await waitFor(() => expect(screen.getByTestId("refine-panel")).toBeInTheDocument());

    // no link in body → click Done (button is intentionally enabled so the server
    // gate fires and the 422 surfaces — FE does NOT pre-block)
    await userEvent.click(screen.getByTestId("refine-done"));

    await waitFor(() => expect(screen.getByTestId("refine-error")).toBeInTheDocument());
    expect(screen.getByTestId("refine-error")).toHaveTextContent("≥1 link");
    // panel still open (not refined away)
    expect(screen.getByTestId("refine-panel")).toBeInTheDocument();
  });

  it("cold-start: 200 + warning shown as a warning (NOT an error)", async () => {
    getWikiInbox.mockResolvedValueOnce(ok(INBOX));
    refineWikiNote.mockResolvedValueOnce(ok(REFINED, "vault quá nhỏ để link — refine anyway"));
    getWikiInbox.mockResolvedValueOnce(ok({ items: [INBOX.items[1]] }));
    render(<WikiInboxPage />);
    await waitFor(() => expect(screen.getByTestId("refine-panel")).toBeInTheDocument());

    await userEvent.click(screen.getByTestId("refine-done"));
    await waitFor(() => expect(screen.getByTestId("refine-warning")).toBeInTheDocument());
    expect(screen.getByTestId("refine-warning")).toHaveTextContent("vault quá nhỏ");
    expect(screen.queryByTestId("refine-error")).not.toBeInTheDocument();
  });

  it("empty inbox → friendly empty state (no crash, no refine panel)", async () => {
    getWikiInbox.mockResolvedValueOnce(ok({ items: [] }));
    render(<WikiInboxPage />);
    await waitFor(() => expect(screen.getByTestId("inbox-empty")).toBeInTheDocument());
    expect(screen.queryByTestId("refine-panel")).not.toBeInTheDocument();
  });

  it("inbox GET error → error state (not a crash)", async () => {
    getWikiInbox.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<WikiInboxPage />);
    await waitFor(() => expect(screen.getByTestId("inbox-error")).toBeInTheDocument());
  });
});
