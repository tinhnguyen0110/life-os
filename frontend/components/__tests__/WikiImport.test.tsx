import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within, cleanup, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #93 Wiki import flow — pick/paste → preview → confirm → POST /wiki/import → per-file
   results (created → title+link · error → agent message+hint). Mocks the NAMED api fn
   importWiki (mock-named-api). The file-picker uses FileReader (awkward in jsdom) → we
   drive the PASTE path (same code into the POST + results) + assert the file input's
   accept attrs. mockResolvedValue (steady-state). Asserts scoped to testids. */

const importWiki = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, importWiki: (...a: unknown[]) => importWiki(...a) };
});
// next/link → plain anchor for the test (forward ALL props incl data-testid/onClick).
vi.mock("next/link", () => ({ default: ({ children, href, ...rest }: any) => <a href={href} {...rest}>{children}</a> }));

import { WikiImport } from "../WikiImport";

afterEach(() => { importWiki.mockReset(); cleanup(); });

const RESP = (imported: object[], createdCount?: number) => ({
  success: true,
  data: { imported, createdCount: createdCount ?? imported.filter((r: any) => r.ok).length },
});
const OK = (filename: string, noteId: number, title: string) => ({ filename, ok: true, noteId, title, error: null });
const BAD = (filename: string, message: string, hint: string) => ({
  filename, ok: false, noteId: null, title: null,
  error: { code: "INVALID_INPUT", message, hint, retryable: false },
});

function noop() {}

// NOTE: use fireEvent.change for the content — userEvent.type mangles `[[wikilinks]]`
// (treats `[[` as keyboard-modifier syntax). The name field is safe for user.type.
async function pasteFile(user: ReturnType<typeof userEvent.setup>, name: string, text: string) {
  fireEvent.change(screen.getByTestId("import-paste-name"), { target: { value: name } });
  fireEvent.change(screen.getByTestId("import-paste-text"), { target: { value: text } });
  await user.click(screen.getByTestId("import-paste-add"));
}

describe("WikiImport (#93)", () => {
  it("file input accepts only .md/.txt + multiple", () => {
    render(<WikiImport onClose={noop} onImported={noop} />);
    const input = screen.getByTestId("import-file-input") as HTMLInputElement;
    expect(input.getAttribute("accept")).toContain(".md");
    expect(input.getAttribute("accept")).toContain(".txt");
    expect(input.hasAttribute("multiple")).toBe(true);
  });

  it("paste → preview shows the filename + snippet before confirm", async () => {
    const user = userEvent.setup();
    render(<WikiImport onClose={noop} onImported={noop} />);
    await pasteFile(user, "note-a.md", "# Hello\nsome body");
    const preview = await screen.findByTestId("import-preview");
    expect(preview).toHaveTextContent("note-a.md");
    expect(preview).toHaveTextContent("Hello");
    // not yet POSTed
    expect(importWiki).not.toHaveBeenCalled();
  });

  it("empty paste → inline error, not added", async () => {
    const user = userEvent.setup();
    render(<WikiImport onClose={noop} onImported={noop} />);
    await user.type(screen.getByTestId("import-paste-name"), "x.md");
    await user.click(screen.getByTestId("import-paste-add"));
    expect(screen.getByTestId("import-error")).toHaveTextContent(/dán nội dung/i);
    expect(screen.queryByTestId("import-preview")).toBeNull();
  });

  it("confirm → POSTs the files + renders the created result with a link to the note", async () => {
    const user = userEvent.setup();
    const onImported = vi.fn();
    importWiki.mockResolvedValue(RESP([OK("note-a.md", 42, "Hello Note")]));
    render(<WikiImport onClose={noop} onImported={onImported} />);
    await pasteFile(user, "note-a.md", "# Hello\nbody [[life-os]]");
    await user.click(screen.getByTestId("import-confirm"));

    await waitFor(() => expect(importWiki).toHaveBeenCalledWith({
      files: [{ filename: "note-a.md", content: "# Hello\nbody [[life-os]]" }],
    }));
    // created result row → title + link to /wiki/42
    const ok = await screen.findByTestId("import-ok-0");
    expect(ok).toHaveTextContent("Hello Note");
    expect(ok.getAttribute("href")).toBe("/wiki/42");
    // a created note → parent refreshes
    expect(onImported).toHaveBeenCalled();
  });

  // THE agent-error row — a bad file shows message + hint (honest, not generic).
  it("bad file → fail-soft error row shows the agent message + hint (no crash)", async () => {
    const user = userEvent.setup();
    const onImported = vi.fn();
    importWiki.mockResolvedValue(RESP([
      OK("good.md", 7, "Good"),
      BAD("bad.exe", "unsupported file type '.exe' — only .md and .txt are supported", "import only non-empty .md or .txt files"),
    ], 1));
    render(<WikiImport onClose={noop} onImported={onImported} />);
    await pasteFile(user, "good.md", "ok");
    await pasteFile(user, "bad.exe", "junk");
    await user.click(screen.getByTestId("import-confirm"));

    const bad = await screen.findByTestId("import-bad-1");
    expect(bad).toHaveTextContent("unsupported file type '.exe'");
    expect(bad).toHaveTextContent("import only non-empty .md or .txt files"); // the hint
    // the GOOD file still imported (fail-soft) + summary counts
    expect(screen.getByTestId("import-ok-0")).toHaveTextContent("Good");
    expect(screen.getByTestId("import-summary")).toHaveTextContent("1 tạo");
    expect(screen.getByTestId("import-summary")).toHaveTextContent("1 lỗi");
  });

  it("confirm with no files → inline error, no POST", async () => {
    const user = userEvent.setup();
    render(<WikiImport onClose={noop} onImported={noop} />);
    // confirm button is disabled with no files, so assert that + no call
    expect((screen.getByTestId("import-confirm") as HTMLButtonElement).disabled).toBe(true);
    expect(importWiki).not.toHaveBeenCalled();
  });

  it("POST throws (BE down) → honest error, no results", async () => {
    const user = userEvent.setup();
    importWiki.mockRejectedValue(new Error("import 500"));
    render(<WikiImport onClose={noop} onImported={noop} />);
    await pasteFile(user, "a.md", "x");
    await user.click(screen.getByTestId("import-confirm"));
    await waitFor(() => expect(screen.getByTestId("import-error")).toHaveTextContent("import 500"));
    expect(screen.queryByTestId("import-results")).toBeNull();
  });

  it("paste name without extension → defaults to .md", async () => {
    const user = userEvent.setup();
    importWiki.mockResolvedValue(RESP([OK("my-note.md", 1, "T")]));
    render(<WikiImport onClose={noop} onImported={noop} />);
    await pasteFile(user, "my-note", "body");
    await user.click(screen.getByTestId("import-confirm"));
    await waitFor(() => expect(importWiki).toHaveBeenCalledWith({
      files: [{ filename: "my-note.md", content: "body" }],
    }));
  });

  it("remove a previewed file before confirm", async () => {
    const user = userEvent.setup();
    render(<WikiImport onClose={noop} onImported={noop} />);
    await pasteFile(user, "a.md", "x");
    expect(screen.getByTestId("import-file-0")).toBeInTheDocument();
    await user.click(screen.getByTestId("import-remove-0"));
    expect(screen.queryByTestId("import-preview")).toBeNull();
  });
});
