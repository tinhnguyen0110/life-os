import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #109-FE Tracing template picker — preset chips that prefill the add form + a light
   manage UI (edit/delete/reset/bulk). Mocks the NAMED api fns. mockResolvedValue (steady-
   state; refetch-after-write won't exhaust). Asserts scoped to testids. */

const getTracingTemplates = vi.fn();
const upsertTracingTemplate = vi.fn();
const deleteTracingTemplate = vi.fn();
const resetTracingTemplates = vi.fn();
const bulkDeleteTracingTemplates = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getTracingTemplates: (...a: unknown[]) => getTracingTemplates(...a),
    upsertTracingTemplate: (...a: unknown[]) => upsertTracingTemplate(...a),
    deleteTracingTemplate: (...a: unknown[]) => deleteTracingTemplate(...a),
    resetTracingTemplates: (...a: unknown[]) => resetTracingTemplates(...a),
    bulkDeleteTracingTemplates: (...a: unknown[]) => bulkDeleteTracingTemplates(...a),
  };
});

import { TracingTemplatePicker } from "../TracingTemplatePicker";

afterEach(() => {
  getTracingTemplates.mockReset(); upsertTracingTemplate.mockReset();
  deleteTracingTemplate.mockReset(); resetTracingTemplates.mockReset();
  bulkDeleteTracingTemplates.mockReset(); cleanup();
});

const TPL = (id: string, name: string, over = {}) => ({
  id, name, goal: 8, unit: "ly", emoji: "💧", icon: "", color: "#38bdf8", source: "seed", ...over,
});
const LIST = (items: object[]) => ({ success: true, data: { templates: items } });

describe("TracingTemplatePicker (#109-FE)", () => {
  it("renders the template chips from GET", async () => {
    getTracingTemplates.mockResolvedValue(LIST([TPL("uong-nuoc", "Uống nước"), TPL("ngu", "Ngủ", { emoji: "😴" })]));
    render(<TracingTemplatePicker onPick={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("tpl-chips")).toBeInTheDocument());
    expect(screen.getByTestId("tpl-pick-uong-nuoc")).toHaveTextContent("Uống nước");
    expect(screen.getByTestId("tpl-pick-ngu")).toHaveTextContent("Ngủ");
  });

  // THE core value — picking a template PREFILLS (via onPick) the add form fields.
  it("clicking a chip → onPick(prefill) with id/name/goal/unit/emoji/color", async () => {
    const onPick = vi.fn();
    getTracingTemplates.mockResolvedValue(LIST([TPL("uong-nuoc", "Uống nước", { goal: 8, unit: "ly", emoji: "💧", color: "#38bdf8" })]));
    render(<TracingTemplatePicker onPick={onPick} />);
    await waitFor(() => expect(screen.getByTestId("tpl-pick-uong-nuoc")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-pick-uong-nuoc"));
    expect(onPick).toHaveBeenCalledWith({ id: "uong-nuoc", name: "Uống nước", goal: "8", unit: "ly", emoji: "💧", color: "#38bdf8" });
  });

  it("user templates are tagged distinct from seed (★)", async () => {
    getTracingTemplates.mockResolvedValue(LIST([TPL("custom", "Mine", { source: "user" }), TPL("ngu", "Ngủ", { source: "seed" })]));
    render(<TracingTemplatePicker onPick={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("tpl-src-custom")).toHaveTextContent("★"));
    expect(screen.getByTestId("tpl-src-ngu")).toHaveTextContent(""); // seed → no star
  });

  it("API error → honest note, the add form below still usable (render-safe)", async () => {
    getTracingTemplates.mockRejectedValue(new Error("templates 500"));
    render(<TracingTemplatePicker onPick={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("tpl-error")).toHaveTextContent("templates 500"));
    expect(screen.getByTestId("tpl-error")).toHaveTextContent(/vẫn có thể tạo thủ công/);
  });

  it("empty list → honest empty-state (not blank)", async () => {
    getTracingTemplates.mockResolvedValue(LIST([]));
    render(<TracingTemplatePicker onPick={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("tpl-empty")).toBeInTheDocument());
  });

  // manage: edit → PUT
  it("manage → edit a template → upsertTracingTemplate(PUT) with the new values", async () => {
    getTracingTemplates.mockResolvedValue(LIST([TPL("ngu", "Ngủ", { goal: 8 })]));
    upsertTracingTemplate.mockResolvedValue({ success: true, data: TPL("ngu", "Ngủ đủ", { goal: 9, source: "user" }) });
    render(<TracingTemplatePicker onPick={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("tpl-manage-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-manage-toggle"));
    await user.click(screen.getByTestId("tpl-edit-ngu"));
    const goal = screen.getByTestId("tpl-f-goal");
    await user.clear(goal);
    await user.type(goal, "9");
    await user.click(screen.getByTestId("tpl-f-save"));
    await waitFor(() => expect(upsertTracingTemplate).toHaveBeenCalledWith("ngu", expect.objectContaining({ goal: 9 })));
  });

  // manage: delete → DELETE
  it("manage → delete a template → deleteTracingTemplate(DELETE)", async () => {
    getTracingTemplates.mockResolvedValue(LIST([TPL("ngu", "Ngủ")]));
    deleteTracingTemplate.mockResolvedValue({ success: true, data: { deleted: "ngu", changed: true } });
    render(<TracingTemplatePicker onPick={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("tpl-manage-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-manage-toggle"));
    await user.click(screen.getByTestId("tpl-del-ngu"));
    await waitFor(() => expect(deleteTracingTemplate).toHaveBeenCalledWith("ngu"));
  });

  // reset uses an IN-PAGE confirm (NOT window.confirm)
  it("reset → IN-PAGE confirm (not window.confirm) → POST reset", async () => {
    getTracingTemplates.mockResolvedValue(LIST([TPL("ngu", "Ngủ")]));
    resetTracingTemplates.mockResolvedValue({ success: true, data: { reset: true, count: 0 } });
    const confirmSpy = vi.spyOn(window, "confirm");
    render(<TracingTemplatePicker onPick={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("tpl-manage-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-manage-toggle"));
    await user.click(screen.getByTestId("tpl-reset"));
    expect(screen.getByTestId("tpl-reset-confirm")).toBeInTheDocument(); // in-page
    expect(confirmSpy).not.toHaveBeenCalled();
    await user.click(screen.getByTestId("tpl-reset-yes"));
    await waitFor(() => expect(resetTracingTemplates).toHaveBeenCalled());
    confirmSpy.mockRestore();
  });

  // bulk-select → bulk-delete (in-page confirm)
  it("bulk-select 2 → bulk-delete (in-page confirm) → POST bulk-delete with the ids", async () => {
    getTracingTemplates.mockResolvedValue(LIST([TPL("a", "A"), TPL("b", "B"), TPL("c", "C")]));
    bulkDeleteTracingTemplates.mockResolvedValue({ success: true, data: { deleted: 2 } });
    render(<TracingTemplatePicker onPick={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("tpl-manage-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tpl-manage-toggle"));
    await user.click(screen.getByTestId("tpl-sel-a"));
    await user.click(screen.getByTestId("tpl-sel-b"));
    await user.click(screen.getByTestId("tpl-bulk-del"));
    expect(screen.getByTestId("tpl-bulk-confirm")).toBeInTheDocument();
    await user.click(screen.getByTestId("tpl-bulk-yes"));
    await waitFor(() => expect(bulkDeleteTracingTemplates).toHaveBeenCalledWith(["a", "b"]));
  });
});
