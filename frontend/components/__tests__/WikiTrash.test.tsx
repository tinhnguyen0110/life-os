import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #94 Wiki trash/restore — list soft-deleted notes + restore (the "xoá nhầm" rollback).
   Mocks the NAMED api fns (getWikiTrash/restoreWikiNote). mockResolvedValue (steady-
   state; refetch-after-restore won't exhaust). Asserts scoped to testids. */

const getWikiTrash = vi.fn();
const restoreWikiNote = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiTrash: (...a: unknown[]) => getWikiTrash(...a),
    restoreWikiNote: (...a: unknown[]) => restoreWikiNote(...a),
  };
});

import { WikiTrash } from "../WikiTrash";

afterEach(() => { getWikiTrash.mockReset(); restoreWikiNote.mockReset(); cleanup(); });

const TRASH = (items: object[]) => ({ success: true, data: { trash: items, count: items.length } });
const ITEM = (id: number, title: string) => ({ id, title, deletedAt: "2026-06-21T10:00:00+00:00", folder: "" });
function noop() {}

describe("WikiTrash (#94)", () => {
  it("empty trash → honest empty-state (not blank)", async () => {
    getWikiTrash.mockResolvedValue(TRASH([]));
    render(<WikiTrash onClose={noop} onRestored={noop} />);
    await waitFor(() => expect(screen.getByTestId("trash-empty")).toBeInTheDocument());
    expect(screen.getByTestId("trash-empty")).toHaveTextContent(/trống/);
  });

  it("lists soft-deleted notes with title + when-deleted + a Restore button", async () => {
    getWikiTrash.mockResolvedValue(TRASH([ITEM(42, "Deleted Note A"), ITEM(43, "Deleted Note B")]));
    render(<WikiTrash onClose={noop} onRestored={noop} />);
    await waitFor(() => expect(screen.getByTestId("trash-list")).toBeInTheDocument());
    const row = screen.getByTestId("trash-row-42");
    expect(row).toHaveTextContent("Deleted Note A");
    expect(within(row).getByTestId("trash-when-42")).toHaveTextContent(/xoá/);
    expect(within(row).getByTestId("trash-restore-42")).toBeInTheDocument();
  });

  it("restore → calls restoreWikiNote + tells the parent to refresh the tree", async () => {
    const onRestored = vi.fn();
    getWikiTrash.mockResolvedValue(TRASH([ITEM(42, "Recover Me")]));
    restoreWikiNote.mockResolvedValue({ success: true, data: { id: 42, title: "Recover Me" } });
    render(<WikiTrash onClose={noop} onRestored={onRestored} />);
    await waitFor(() => expect(screen.getByTestId("trash-restore-42")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("trash-restore-42"));
    await waitFor(() => expect(restoreWikiNote).toHaveBeenCalledWith(42));
    expect(onRestored).toHaveBeenCalled(); // the vault tree refresh
  });

  it("restore failure → row error shown, no crash", async () => {
    getWikiTrash.mockResolvedValue(TRASH([ITEM(42, "X")]));
    restoreWikiNote.mockRejectedValue(new Error("restore 500"));
    render(<WikiTrash onClose={noop} onRestored={noop} />);
    await waitFor(() => expect(screen.getByTestId("trash-restore-42")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("trash-restore-42"));
    await waitFor(() => expect(screen.getByTestId("trash-row-err-42")).toHaveTextContent("restore 500"));
  });

  it("BE down → honest error state with retry (not a blank hang)", async () => {
    getWikiTrash.mockRejectedValue(new Error("trash 500"));
    render(<WikiTrash onClose={noop} onRestored={noop} />);
    await waitFor(() => expect(screen.getByTestId("trash-error")).toHaveTextContent("trash 500"));
  });

  it("malformed body → honest error (not a crash)", async () => {
    getWikiTrash.mockResolvedValue({ success: true, data: { trash: null } });
    render(<WikiTrash onClose={noop} onRestored={noop} />);
    await waitFor(() => expect(screen.getByTestId("trash-error")).toHaveTextContent(/không hợp lệ/));
  });

  it("a trash item with no title → '(không có tiêu đề)' (honest, not blank)", async () => {
    getWikiTrash.mockResolvedValue(TRASH([ITEM(50, "")]));
    render(<WikiTrash onClose={noop} onRestored={noop} />);
    await waitFor(() => expect(screen.getByTestId("trash-row-50")).toHaveTextContent("(không có tiêu đề)"));
  });
});
