import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, within, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #137-T2 TemplateSetsModal — a "mẫu" = a saved LIST of rich activities. The modal:
   list sets · per-set import(1-click)/edit/delete · create · edit (rename + member list
   with content/time/reminder, add/remove member) · reset-to-default. Mocks the NAMED api
   fns (mock-named-api). Steady-state mockResolvedValue (unhandled-errors-not-green). */
const getTemplateSets = vi.fn();
const createTemplateSet = vi.fn();
const updateTemplateSet = vi.fn();
const deleteTemplateSet = vi.fn();
const importTemplateSet = vi.fn();
const resetTemplateSets = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getTemplateSets: (...a: unknown[]) => getTemplateSets(...a),
    createTemplateSet: (...a: unknown[]) => createTemplateSet(...a),
    updateTemplateSet: (...a: unknown[]) => updateTemplateSet(...a),
    deleteTemplateSet: (...a: unknown[]) => deleteTemplateSet(...a),
    importTemplateSet: (...a: unknown[]) => importTemplateSet(...a),
    resetTemplateSets: (...a: unknown[]) => resetTemplateSets(...a),
  };
});

import { TemplateSetsModal } from "../TemplateSetsModal";
import { ApiError } from "@/lib/api";

const CHANNELS = [
  { id: "in_app", label: "In-app", available: true },
  { id: "email", label: "Email", available: true },
  { id: "discord", label: "Discord", available: true },
] as const;

const MEMBER = (over = {}) => ({ content: "Uống nước", time: "07:00", remindRepeat: "daily", remindChannel: "discord", ...over });
const SET = (over = {}) => ({ id: "buoi-sang", name: "Buổi sáng", activities: [MEMBER(), { content: "Đọc sách", time: null, remindRepeat: "off", remindChannel: "in_app" }], ...over });
const ok = <T,>(data: T) => ({ success: true, data });

const onClose = vi.fn();
const onImported = vi.fn();
function renderModal() {
  return render(<TemplateSetsModal channels={CHANNELS as any} onClose={onClose} onImported={onImported} />);
}

beforeEach(() => { getTemplateSets.mockResolvedValue(ok({ sets: [SET()] })); });
afterEach(() => {
  getTemplateSets.mockReset(); createTemplateSet.mockReset(); updateTemplateSet.mockReset();
  deleteTemplateSet.mockReset(); importTemplateSet.mockReset(); resetTemplateSets.mockReset();
  onClose.mockReset(); onImported.mockReset(); cleanup();
});

describe("#137 TemplateSetsModal — list view", () => {
  it("🔴 D2 — lists each set's members as ROWS (time · content · remind-chip), like the /tracing timeline", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-buoi-sang")).toBeInTheDocument());
    expect(screen.getByTestId("tpl-set-name-buoi-sang")).toHaveTextContent("Buổi sáng");
    expect(screen.getByTestId("tpl-set-count-buoi-sang")).toHaveTextContent("2 việc");
    // each member is its OWN row (NOT a single joined string) — proving the list render
    const m0 = screen.getByTestId("tpl-set-member-buoi-sang-0");
    expect(within(m0).getByTestId("tpl-set-member-time-buoi-sang-0")).toHaveTextContent("07:00");
    expect(within(m0).getByTestId("tpl-set-member-content-buoi-sang-0")).toHaveTextContent("Uống nước");
    // member 0 has a daily reminder → a remind chip (🔔 time · freq · channel)
    expect(within(m0).getByTestId("tpl-set-member-remind-buoi-sang-0")).toHaveTextContent("07:00");
    expect(within(m0).getByTestId("tpl-set-member-remind-buoi-sang-0")).toHaveTextContent("hằng ngày");
    expect(within(m0).getByTestId("tpl-set-member-remind-buoi-sang-0")).toHaveTextContent("Discord");
    // member 1 (Đọc sách): no time, no reminder → its own row, no chip
    const m1 = screen.getByTestId("tpl-set-member-buoi-sang-1");
    expect(within(m1).getByTestId("tpl-set-member-content-buoi-sang-1")).toHaveTextContent("Đọc sách");
    expect(within(m1).getByTestId("tpl-set-member-time-buoi-sang-1")).toHaveTextContent("–"); // no time
    expect(within(m1).queryByTestId("tpl-set-member-remind-buoi-sang-1")).toBeNull(); // remindRepeat off → no chip
  });

  it("no sets → honest empty state", async () => {
    getTemplateSets.mockResolvedValue(ok({ sets: [] }));
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-empty")).toBeInTheDocument());
  });

  it("load error → honest error + retry", async () => {
    getTemplateSets.mockRejectedValue(new Error("sets down"));
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-error")).toHaveTextContent("sets down"));
  });
});

describe("#137 TemplateSetsModal — import (the headline 1-click)", () => {
  it("🔴 Import a set → importTemplateSet(id) → onImported(createdCount, skipped, archivedCount)", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-import-buoi-sang")).toBeInTheDocument());
    // D3 — import is a REPLACE: BE returns archivedCount (old activities soft-deleted, recoverable)
    importTemplateSet.mockResolvedValue(ok({ created: [{ id: "uong-nuoc" }, { id: "doc-sach" }], skipped: [], archivedCount: 4 }));
    await userEvent.setup().click(screen.getByTestId("tpl-set-import-buoi-sang"));
    await waitFor(() => expect(importTemplateSet).toHaveBeenCalledWith("buoi-sang"));
    await waitFor(() => expect(onImported).toHaveBeenCalledWith(2, [], 4));
  });

  it("import surfaces skipped (already-present, honest) + archivedCount", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-import-buoi-sang")).toBeInTheDocument());
    importTemplateSet.mockResolvedValue(ok({ created: [{ id: "uong-nuoc" }], skipped: ["Đọc sách"], archivedCount: 2 }));
    await userEvent.setup().click(screen.getByTestId("tpl-set-import-buoi-sang"));
    await waitFor(() => expect(onImported).toHaveBeenCalledWith(1, ["Đọc sách"], 2));
  });

  it("D3 — archivedCount absent on an older BE → defaults to 0 (additive, no crash)", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-import-buoi-sang")).toBeInTheDocument());
    importTemplateSet.mockResolvedValue(ok({ created: [{ id: "uong-nuoc" }], skipped: [] })); // no archivedCount
    await userEvent.setup().click(screen.getByTestId("tpl-set-import-buoi-sang"));
    await waitFor(() => expect(onImported).toHaveBeenCalledWith(1, [], 0));
  });
});

describe("#137 TemplateSetsModal — delete / reset", () => {
  it("delete a set → deleteTemplateSet(id) + reload", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-delete-buoi-sang")).toBeInTheDocument());
    deleteTemplateSet.mockResolvedValue(ok({ deleted: "buoi-sang" }));
    await userEvent.setup().click(screen.getByTestId("tpl-set-delete-buoi-sang"));
    await waitFor(() => expect(deleteTemplateSet).toHaveBeenCalledWith("buoi-sang"));
    await waitFor(() => expect(getTemplateSets).toHaveBeenCalledTimes(2)); // reload
  });

  it("reset → resetTemplateSets() → shows the returned default set", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-reset")).toBeInTheDocument());
    resetTemplateSets.mockResolvedValue(ok({ sets: [SET({ name: "Buổi sáng" })] }));
    await userEvent.setup().click(screen.getByTestId("tpl-set-reset"));
    await waitFor(() => expect(resetTemplateSets).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("tpl-set-name-buoi-sang")).toHaveTextContent("Buổi sáng"));
  });

  it("Đóng → onClose", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-modal-close")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("tpl-modal-close"));
    expect(onClose).toHaveBeenCalled();
  });

  it("🔴 #137-T2 UX — clicking the BACKDROP (outside the box) closes the modal", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-modal")).toBeInTheDocument());
    // mousedown on the backdrop overlay itself (not the box) → close
    fireEvent.mouseDown(screen.getByTestId("tpl-modal"));
    expect(onClose).toHaveBeenCalled();
  });

  it("clicking INSIDE the box does NOT close (stopPropagation)", async () => {
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-buoi-sang")).toBeInTheDocument());
    fireEvent.mouseDown(screen.getByTestId("tpl-set-buoi-sang")); // a click inside the box
    expect(onClose).not.toHaveBeenCalled();
  });

  it("🔴 #137-T2 UX — the EDIT view does NOT close on backdrop (an in-progress edit isn't lost)", async () => {
    getTemplateSets.mockResolvedValue(ok({ sets: [] }));
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-new")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("tpl-set-new"));
    await waitFor(() => expect(screen.getByTestId("tpl-edit")).toBeInTheDocument());
    fireEvent.mouseDown(screen.getByTestId("tpl-modal")); // backdrop click while editing
    expect(onClose).not.toHaveBeenCalled(); // edit view stays — explicit Hủy/Đóng only
    expect(screen.getByTestId("tpl-edit")).toBeInTheDocument();
  });
});

describe("#137 TemplateSetsModal — create / edit a set (member list)", () => {
  it("🔴 create a NEW set with 2 members (1 timed+reminded, 1 bare) → createTemplateSet({name, activities})", async () => {
    getTemplateSets.mockResolvedValue(ok({ sets: [] }));
    createTemplateSet.mockResolvedValue(ok(SET({ id: "new" })));
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-new")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-set-new"));
    await waitFor(() => expect(screen.getByTestId("tpl-edit")).toBeInTheDocument());
    await user.type(screen.getByTestId("tpl-edit-name"), "Buổi tối");
    // member 0 (present by default): a timed + reminded one
    fireEvent.change(screen.getByTestId("tpl-member-content-0"), { target: { value: "Thiền" } });
    fireEvent.change(screen.getByTestId("tpl-member-time-0"), { target: { value: "21:00" } });
    await user.click(screen.getByTestId("tpl-member-remind-toggle-0"));
    await waitFor(() => expect(screen.getByTestId("tpl-member-channel-0")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("tpl-member-channel-0"), { target: { value: "discord" } });
    // add member 1: a bare one (no time, no reminder)
    await user.click(screen.getByTestId("tpl-member-add"));
    fireEvent.change(screen.getByTestId("tpl-member-content-1"), { target: { value: "Viết nhật ký" } });
    await user.click(screen.getByTestId("tpl-edit-save"));
    await waitFor(() => expect(createTemplateSet).toHaveBeenCalled());
    const body = createTemplateSet.mock.calls[0][0];
    expect(body.name).toBe("Buổi tối");
    expect(body.activities).toHaveLength(2);
    expect(body.activities[0]).toMatchObject({ content: "Thiền", time: "21:00", remindRepeat: "daily", remindChannel: "discord" });
    expect(body.activities[1]).toMatchObject({ content: "Viết nhật ký", time: null, remindRepeat: "off" });
  });

  it("edit an existing set (rename) → updateTemplateSet(id, {...})", async () => {
    updateTemplateSet.mockResolvedValue(ok(SET()));
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-edit-buoi-sang")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-set-edit-buoi-sang"));
    await waitFor(() => expect(screen.getByTestId("tpl-edit-name")).toBeInTheDocument());
    // the existing members prefill
    expect(screen.getByTestId("tpl-member-content-0")).toHaveValue("Uống nước");
    await user.clear(screen.getByTestId("tpl-edit-name"));
    await user.type(screen.getByTestId("tpl-edit-name"), "Buổi sáng 2");
    await user.click(screen.getByTestId("tpl-edit-save"));
    await waitFor(() => expect(updateTemplateSet).toHaveBeenCalledWith("buoi-sang", expect.objectContaining({ name: "Buổi sáng 2" })));
  });

  it("remove a member → the saved set has one fewer", async () => {
    updateTemplateSet.mockResolvedValue(ok(SET()));
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-edit-buoi-sang")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-set-edit-buoi-sang"));
    await waitFor(() => expect(screen.getByTestId("tpl-member-0")).toBeInTheDocument());
    await user.click(screen.getByTestId("tpl-member-remove-1")); // drop "Đọc sách"
    await user.click(screen.getByTestId("tpl-edit-save"));
    await waitFor(() => expect(updateTemplateSet).toHaveBeenCalled());
    expect(updateTemplateSet.mock.calls[0][1].activities).toHaveLength(1);
  });

  it("blank name → validation error, no POST", async () => {
    getTemplateSets.mockResolvedValue(ok({ sets: [] }));
    renderModal();
    await waitFor(() => expect(screen.getByTestId("tpl-set-new")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-set-new"));
    fireEvent.change(screen.getByTestId("tpl-member-content-0"), { target: { value: "X" } });
    await user.click(screen.getByTestId("tpl-edit-save")); // name blank
    await waitFor(() => expect(screen.getByTestId("tpl-edit-error")).toHaveTextContent(/tên/));
    expect(createTemplateSet).not.toHaveBeenCalled();
  });

  it("🔴 a 422 from the BE surfaces the agent-error hint honestly", async () => {
    getTemplateSets.mockResolvedValue(ok({ sets: [] }));
    createTemplateSet.mockRejectedValue(new (ApiError as any)(422, "bad time", { hint: "time must be HH:MM" }));
    renderModal();
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("tpl-set-new")).toBeInTheDocument());
    await user.click(screen.getByTestId("tpl-set-new"));
    await user.type(screen.getByTestId("tpl-edit-name"), "X");
    fireEvent.change(screen.getByTestId("tpl-member-content-0"), { target: { value: "Y" } });
    await user.click(screen.getByTestId("tpl-edit-save"));
    await waitFor(() => expect(screen.getByTestId("tpl-edit-error")).toHaveTextContent("bad time"));
    expect(screen.getByTestId("tpl-edit-error")).toHaveTextContent("time must be HH:MM"); // the hint
  });
});
