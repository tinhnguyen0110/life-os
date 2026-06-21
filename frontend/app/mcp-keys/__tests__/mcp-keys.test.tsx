import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #88 MCP Keys screen — the unblocked CRUD half (list/create/delete/connect-hint/
   key-shown-once/empty-state/skeleton). The scope-editor + catalog audit land later
   (GET /mcp_keys/catalog seam). Mocks the NAMED api fns (mock-named-api) — NOT apiGet.
   mockResolvedValue (steady-state, refetch-after-write won't exhaust → no unhandled
   rejection per unhandled-errors-not-green). Asserts scoped to testids. */

const getMcpKeys = vi.fn();
const createMcpKey = vi.fn();
const deleteMcpKey = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getMcpKeys: (...a: unknown[]) => getMcpKeys(...a),
    createMcpKey: (...a: unknown[]) => createMcpKey(...a),
    deleteMcpKey: (...a: unknown[]) => deleteMcpKey(...a),
  };
});

import McpKeysPage from "../page";

afterEach(() => {
  getMcpKeys.mockReset();
  createMcpKey.mockReset();
  deleteMcpKey.mockReset();
});

const ROW = (over = {}) => ({
  key: "Kkey_abc123def456",
  label: "finance-agent",
  scope: { domains: ["finance"], tools: ["reminders_list"] },
  toolCount: 16,
  createdAt: "2026-06-21T09:00:00+00:00",
  ...over,
});
const LIST = (rows: object[] = []) => ({ success: true, data: rows });
const CREATED = (over = {}) => ({ success: true, data: ROW(over) });

describe("S MCPKEYS — MCP Keys manager (#88, CRUD half)", () => {
  it("connect-hint shows the MCP endpoint + key-passing placeholder (mechanism TBD)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("connect-hint")).toBeInTheDocument());
    expect(screen.getByTestId("mcp-endpoint")).toHaveTextContent("/mcp/");
    // honest: the key-passing mechanism is a placeholder until #87 lands
    expect(screen.getByTestId("connect-hint")).toHaveTextContent(/query vs header|đang chốt/);
  });

  it("no keys → honest empty-state (not a blank hang)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-empty")).toBeInTheDocument());
    expect(screen.getByTestId("keys-empty")).toHaveTextContent("Chưa có key");
  });

  it("renders key rows with label + BE toolCount + scope summary (render-only)", async () => {
    getMcpKeys.mockResolvedValue(LIST([ROW()]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-list")).toBeInTheDocument());
    const row = screen.getByTestId("key-row-Kkey_abc123def456");
    expect(within(row).getByTestId("key-label-Kkey_abc123def456")).toHaveTextContent("finance-agent");
    // toolCount is the BE-resolved union — rendered, not recomputed
    expect(within(row).getByTestId("key-toolcount-Kkey_abc123def456")).toHaveTextContent("16 tool");
    expect(within(row).getByTestId("key-scope-Kkey_abc123def456")).toHaveTextContent("finance");
    expect(within(row).getByTestId("key-scope-Kkey_abc123def456")).toHaveTextContent("reminders_list");
  });

  it("create requires a label (empty → inline error, no API call)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("key-create-btn")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("key-create-btn"));
    expect(screen.getByTestId("create-error")).toHaveTextContent("Nhập nhãn");
    expect(createMcpKey).not.toHaveBeenCalled();
  });

  it("create → calls API with the label + surfaces the generated key ONCE", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    createMcpKey.mockResolvedValue(CREATED({ key: "Knew_secret_TOKEN_999", label: "agent-x" }));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("key-create-btn")).toBeInTheDocument());

    const user = userEvent.setup();
    await user.type(screen.getByTestId("key-label-input"), "agent-x");
    await user.click(screen.getByTestId("key-create-btn"));

    await waitFor(() => expect(createMcpKey).toHaveBeenCalledWith({ label: "agent-x" }));
    // the full token is shown ONCE
    const once = await screen.findByTestId("key-once");
    expect(within(once).getByTestId("key-once-token")).toHaveTextContent("Knew_secret_TOKEN_999");
    // dismissing hides it (the token won't reappear)
    await user.click(screen.getByTestId("key-once-dismiss"));
    expect(screen.queryByTestId("key-once")).toBeNull();
  });

  it("create failure → inline error, no key-once banner", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    createMcpKey.mockRejectedValue(new Error("label taken"));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("key-create-btn")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("key-label-input"), "dup");
    await user.click(screen.getByTestId("key-create-btn"));
    await waitFor(() => expect(screen.getByTestId("create-error")).toHaveTextContent("label taken"));
    expect(screen.queryByTestId("key-once")).toBeNull();
  });

  // in-page confirm — NOT a JS confirm() dialog (that blocks the browser extension).
  it("delete uses an IN-PAGE confirm (yes calls deleteMcpKey, not window.confirm)", async () => {
    getMcpKeys.mockResolvedValue(LIST([ROW()]));
    deleteMcpKey.mockResolvedValue({ success: true, data: { deleted: "Kkey_abc123def456" } });
    const confirmSpy = vi.spyOn(window, "confirm");
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-list")).toBeInTheDocument());

    const user = userEvent.setup();
    // first click reveals the in-page confirm (no native dialog)
    await user.click(screen.getByTestId("key-del-Kkey_abc123def456"));
    expect(screen.getByTestId("confirm-del-Kkey_abc123def456")).toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();
    // confirming calls the API
    await user.click(screen.getByTestId("confirm-yes-Kkey_abc123def456"));
    await waitFor(() => expect(deleteMcpKey).toHaveBeenCalledWith("Kkey_abc123def456"));
    confirmSpy.mockRestore();
  });

  it("delete confirm can be cancelled (no API call)", async () => {
    getMcpKeys.mockResolvedValue(LIST([ROW()]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-list")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("key-del-Kkey_abc123def456"));
    await user.click(screen.getByTestId("confirm-no-Kkey_abc123def456"));
    expect(screen.queryByTestId("confirm-del-Kkey_abc123def456")).toBeNull();
    expect(deleteMcpKey).not.toHaveBeenCalled();
  });

  it("BE down → honest error state with retry (not a blank hang)", async () => {
    getMcpKeys.mockRejectedValue(new Error("keys 500"));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-error")).toHaveTextContent("keys 500"));
  });

  it("malformed list body → honest error (not a crash)", async () => {
    getMcpKeys.mockResolvedValue({ success: true, data: null });
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-error")).toHaveTextContent("không hợp lệ"));
  });

  // the scope-editor SEAM is present + honest about the deferred scope.
  it("scope-editor seam present + honest 'scope added later' note (sees-nothing default)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("scope-seam")).toBeInTheDocument());
    expect(screen.getByTestId("scope-seam")).toHaveTextContent(/không thấy tool nào|phạm vi/i);
  });
});
