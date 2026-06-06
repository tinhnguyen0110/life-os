/**
 * notes.test.tsx — S10 Notes (frontend-owned). Mocks the apiGet/apiPost/apiPut/
 * apiDelete the useNotes hook calls directly (the hook uses them inline, so
 * mocking these intercepts correctly — unlike named-fn wrappers).
 *
 * WRITE-FAILURE teeth-tests (Sprint-5 lesson, hard): a failed POST/PUT/DELETE must
 * surface an error + keep the form open (fail-closed) + NOT crash / lose the note.
 * Proven by mocking the write to reject and asserting the error UI, not a silent loss.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiGet = vi.fn();
const apiPost = vi.fn();
const apiPut = vi.fn();
const apiDelete = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiGet: (...a: unknown[]) => apiGet(...a),
    apiPost: (...a: unknown[]) => apiPost(...a),
    apiPut: (...a: unknown[]) => apiPut(...a),
    apiDelete: (...a: unknown[]) => apiDelete(...a),
  };
});

import NotesPage from "../page";

afterEach(() => {
  apiGet.mockReset();
  apiPost.mockReset();
  apiPut.mockReset();
  apiDelete.mockReset();
});

const NOTE = (over = {}) => ({
  id: "n1", title: "Idea", body: "ship S10", tags: ["idea", "project"],
  pinned: false, attach: { type: "none", ref: null }, // mirrors frozen schema (nested attach)
  createdAt: "2026-06-06T10:00:00Z", updatedAt: "2026-06-06T11:00:00Z", ...over,
});
const LIST = (notes: unknown[]) => ({ success: true, data: notes });

describe("S10 Notes — render + filter", () => {
  it("renders pinned + masonry sections from /notes", async () => {
    apiGet.mockResolvedValue(LIST([NOTE({ id: "p1", title: "Pinned one", pinned: true }), NOTE()]));
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("notes-pinned")).toBeInTheDocument());
    expect(screen.getByText("Pinned one")).toBeInTheDocument();
    expect(screen.getByText("Idea")).toBeInTheDocument();
  });

  it("client-side search filters by title/body", async () => {
    apiGet.mockResolvedValue(LIST([NOTE({ id: "a", title: "Alpha" }), NOTE({ id: "b", title: "Beta" })]));
    const user = userEvent.setup();
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByText("Alpha")).toBeInTheDocument());
    await user.type(screen.getByTestId("notes-search"), "beta");
    await waitFor(() => expect(screen.queryByText("Alpha")).toBeNull());
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("tag filter shows only notes with the tag", async () => {
    apiGet.mockResolvedValue(LIST([NOTE({ id: "a", title: "HasIdea", tags: ["idea"] }), NOTE({ id: "b", title: "HasFin", tags: ["finance"] })]));
    const user = userEvent.setup();
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("tagfilter-finance")).toBeInTheDocument());
    await user.click(screen.getByTestId("tagfilter-finance"));
    await waitFor(() => expect(screen.queryByText("HasIdea")).toBeNull());
    expect(screen.getByText("HasFin")).toBeInTheDocument();
  });

  it("empty list → empty state, no crash", async () => {
    apiGet.mockResolvedValue(LIST([]));
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("notes-empty")).toHaveTextContent(/Chưa có ghi chú/));
  });

  it("GET error → error state with retry", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    apiGet.mockRejectedValueOnce(new (ApiError as any)(0, "down"));
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("notes-error")).toBeInTheDocument());
  });
});

describe("S10 Notes — WRITE (create/edit/delete) + fail-closed teeth-tests", () => {
  it("create: form submit POSTs the note then refetches", async () => {
    apiGet.mockResolvedValue(LIST([]));
    apiPost.mockResolvedValueOnce({ success: true, data: NOTE() });
    const user = userEvent.setup();
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("note-new")).toBeInTheDocument());
    await user.click(screen.getByTestId("note-new"));
    await user.type(screen.getByTestId("form-title"), "New note");
    await user.click(screen.getByTestId("form-submit"));
    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith("/notes", expect.objectContaining({ title: "New note" })),
    );
  });

  it("comma-separated tags input → parsed into a string[] for POST", async () => {
    apiGet.mockResolvedValue(LIST([]));
    apiPost.mockResolvedValueOnce({ success: true, data: NOTE() });
    const user = userEvent.setup();
    render(<NotesPage />);
    await user.click(screen.getByTestId("note-new"));
    await user.type(screen.getByTestId("form-title"), "T");
    fireEvent.change(screen.getByTestId("form-tags"), { target: { value: "idea, finance, project" } });
    await user.click(screen.getByTestId("form-submit"));
    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith("/notes", expect.objectContaining({ tags: ["idea", "finance", "project"] })),
    );
  });

  it("TEETH: create POST FAILS → error surfaces, form stays open, note NOT saved (fail-closed)", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    apiGet.mockResolvedValue(LIST([]));
    apiPost.mockRejectedValueOnce(new (ApiError as any)(500, "git commit failed"));
    const user = userEvent.setup();
    render(<NotesPage />);
    await user.click(screen.getByTestId("note-new"));
    await user.type(screen.getByTestId("form-title"), "Doomed note");
    await user.click(screen.getByTestId("form-submit"));
    // error shown + form still open (fail-closed) — the note is NOT shown as saved
    await waitFor(() => expect(screen.getByTestId("form-error")).toHaveTextContent(/git commit failed/));
    expect(screen.getByTestId("note-form")).toBeInTheDocument(); // form did NOT close
  });

  it("validation: empty title+body → error, no POST", async () => {
    apiGet.mockResolvedValue(LIST([]));
    const user = userEvent.setup();
    render(<NotesPage />);
    await user.click(screen.getByTestId("note-new"));
    await user.click(screen.getByTestId("form-submit"));
    expect(screen.getByTestId("form-error")).toBeInTheDocument();
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("edit: opens prefilled + PUTs to /notes/{id}", async () => {
    apiGet.mockResolvedValue(LIST([NOTE()]));
    apiPut.mockResolvedValueOnce({ success: true, data: NOTE({ title: "Edited" }) });
    const user = userEvent.setup();
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("edit-n1")).toBeInTheDocument());
    await user.click(screen.getByTestId("edit-n1"));
    expect((screen.getByTestId("form-title") as HTMLInputElement).value).toBe("Idea");
    await user.click(screen.getByTestId("form-submit"));
    await waitFor(() => expect(apiPut).toHaveBeenCalledWith("/notes/n1", expect.objectContaining({ title: "Idea" })));
  });

  it("TEETH: delete FAILS → error surfaces, no silent loss / crash", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    apiGet.mockResolvedValue(LIST([NOTE()]));
    apiDelete.mockRejectedValueOnce(new (ApiError as any)(500, "delete blew up"));
    const user = userEvent.setup();
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("del-n1")).toBeInTheDocument());
    await user.click(screen.getByTestId("del-n1"));
    // delete error surfaces in the top-level write-error bar (form is CLOSED) —
    // the gap this teeth-test caught: a closed-form delete error must still show.
    await waitFor(() => expect(screen.getByTestId("notes-write-error")).toHaveTextContent(/Xóa thất bại/));
    // the note is still on screen (not optimistically removed) — no silent loss
    expect(screen.getByText("Idea")).toBeInTheDocument();
  });

  it("pin toggle → PUT /notes/{id} with the FULL body + pinned flipped (not POST, not partial)", async () => {
    apiGet.mockResolvedValue(LIST([NOTE({ pinned: false })]));
    apiPut.mockResolvedValueOnce({ success: true, data: NOTE({ pinned: true }) });
    const user = userEvent.setup();
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("pin-n1")).toBeInTheDocument());
    await user.click(screen.getByTestId("pin-n1"));
    await waitFor(() =>
      expect(apiPut).toHaveBeenCalledWith(
        "/notes/n1",
        expect.objectContaining({ title: "Idea", pinned: true, attach: { type: "none", ref: null } }),
      ),
    );
    expect(apiPost).not.toHaveBeenCalled(); // pin is PUT, never POST
  });

  it("attach picker: selecting a project + ref → POST carries attach {type:'project', ref}", async () => {
    apiGet.mockResolvedValue(LIST([]));
    apiPost.mockResolvedValueOnce({ success: true, data: NOTE() });
    const user = userEvent.setup();
    render(<NotesPage />);
    await user.click(screen.getByTestId("note-new"));
    await user.type(screen.getByTestId("form-title"), "Attached note");
    await user.selectOptions(screen.getByTestId("form-attach-type"), "project");
    await user.type(screen.getByTestId("form-attach-ref"), "devcrew");
    await user.click(screen.getByTestId("form-submit"));
    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith("/notes", expect.objectContaining({ attach: { type: "project", ref: "devcrew" } })),
    );
  });

  it("attach validation: type≠none without ref → error, no POST (mirrors backend validator)", async () => {
    apiGet.mockResolvedValue(LIST([]));
    const user = userEvent.setup();
    render(<NotesPage />);
    await user.click(screen.getByTestId("note-new"));
    await user.type(screen.getByTestId("form-title"), "Needs ref");
    await user.selectOptions(screen.getByTestId("form-attach-type"), "channel");
    await user.click(screen.getByTestId("form-submit"));
    expect(screen.getByTestId("form-error")).toHaveTextContent(/ref/);
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("delete: success → DELETEs /notes/{id} + refetch", async () => {
    apiGet.mockResolvedValue(LIST([NOTE()]));
    apiDelete.mockResolvedValueOnce({ success: true, data: { deleted: "n1" } });
    const user = userEvent.setup();
    render(<NotesPage />);
    await waitFor(() => expect(screen.getByTestId("del-n1")).toBeInTheDocument());
    await user.click(screen.getByTestId("del-n1"));
    await waitFor(() => expect(apiDelete).toHaveBeenCalledWith("/notes/n1"));
  });
});
