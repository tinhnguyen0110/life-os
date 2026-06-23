import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #88 MCP Keys screen — full (part-1 CRUD + part-2 scope-editor). list/create-with-
   scope/edit-scope/delete/connect-hint(X-MCP-Key)/key-once/catalog-audit/empty/skeleton.
   Mocks the NAMED api fns (mock-named-api) — NOT apiGet. mockResolvedValue (steady-state,
   refetch-after-write won't exhaust → no unhandled rejection per unhandled-errors-not-
   green). Asserts scoped to testids. The scope-editor LOGIC is unit-tested separately
   in lib/__tests__/mcpScope.test.ts; here we test the wiring (catalog → ticks → save). */

const getMcpKeys = vi.fn();
const createMcpKey = vi.fn();
const updateMcpKey = vi.fn();
const deleteMcpKey = vi.fn();
const getMcpCatalog = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getMcpKeys: (...a: unknown[]) => getMcpKeys(...a),
    createMcpKey: (...a: unknown[]) => createMcpKey(...a),
    updateMcpKey: (...a: unknown[]) => updateMcpKey(...a),
    deleteMcpKey: (...a: unknown[]) => deleteMcpKey(...a),
    getMcpCatalog: (...a: unknown[]) => getMcpCatalog(...a),
  };
});

import McpKeysPage from "../page";

const CATALOG = () => ({
  success: true,
  data: {
    tools: [
      // fin_a HAS params (the #129 params-table test); fin_b is a no-arg tool ("không tham số").
      { name: "fin_a", server: "finance", capability: "read", neutral: false, description: "finance a",
        fullDescription: "finance a — the full docstring with details.",
        params: [{ name: "channel", type: "str", required: true }, { name: "days", type: "int", required: false, default: 90 }] },
      { name: "fin_b", server: "finance", capability: "read", neutral: false, description: "finance b",
        fullDescription: "finance b — full docstring, no args.", params: [] },
      { name: "trc_a", server: "tracing", capability: "read", neutral: false, description: "tracing a",
        fullDescription: "tracing a full", params: [] },
      { name: "wri_a", server: "write", capability: "propose", neutral: false, description: "write a",
        fullDescription: "write a full", params: [] },
    ],
    counts: { read: 3, write: 1, total: 4, byMount: { finance: 2, tracing: 1, write: 1 }, allMounts: 4, note: "x" },
    capabilityBoundary: { read: "reads only", write: "enqueue only" },
  },
});

afterEach(() => {
  getMcpKeys.mockReset();
  createMcpKey.mockReset();
  updateMcpKey.mockReset();
  deleteMcpKey.mockReset();
  getMcpCatalog.mockReset();
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

describe("S MCPKEYS — MCP Keys manager (#88 full: CRUD + scope-editor)", () => {
  // default the catalog so the create-form's scope-editor renders in every test.
  beforeEach(() => { getMcpCatalog.mockResolvedValue(CATALOG()); });

  it("connect-hint shows the MCP endpoint + the X-MCP-Key header mechanism (#87)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("connect-hint")).toBeInTheDocument());
    // #160 — the connect body is collapsed (reference info); open it to see the endpoint/header.
    const user = userEvent.setup();
    await user.click(screen.getByTestId("connect-toggle"));
    expect(screen.getByTestId("mcp-endpoint")).toHaveTextContent("/mcp/");
    // #87 chose the X-MCP-Key HEADER (not ?key=)
    expect(screen.getByTestId("key-header")).toHaveTextContent("X-MCP-Key");
    expect(screen.getByTestId("mcp-json-snippet")).toHaveTextContent("X-MCP-Key");
  });

  it("no keys → honest empty-state (not a blank hang)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-empty")).toBeInTheDocument());
    expect(screen.getByTestId("keys-empty")).toHaveTextContent("Chưa có key");
    // #160 — the inviting empty-state CTA opens the create form
    const user = userEvent.setup();
    await user.click(screen.getByTestId("keys-empty-cta"));
    expect(screen.getByTestId("key-create-form")).toBeInTheDocument();
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

  it("#162 aperture bar — granted count computed FE-side from the REAL catalog scope", async () => {
    // ROW scope = {domains:["finance"], tools:["reminders_list"]} over the CATALOG (fin_a,
    // fin_b in finance; trc_a tracing; wri_a write). resolvedTools = fin_a+fin_b (finance
    // domain) + reminders_list (loose) = 3 granted; catalog total = 4 tools.
    getMcpKeys.mockResolvedValue(LIST([ROW()]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-list")).toBeInTheDocument());
    const ap = await screen.findByTestId("key-aperture-Kkey_abc123def456");
    expect(within(ap).getByTestId("aperture-granted-Kkey_abc123def456")).toHaveTextContent("3");
    expect(ap).toHaveTextContent("/ 4 tool"); // total from catalog.tools.length
    // the bar has segments (signature) — finance(on) + tracing/write(off)
    expect(ap.querySelectorAll(".seg").length).toBeGreaterThan(0);
  });

  it("create requires a label (empty → inline error, no API call)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    // #160 — open the (collapsed) create form first
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle"));
    await waitFor(() => expect(screen.getByTestId("key-create-btn")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-create-btn"));
    expect(screen.getByTestId("create-error")).toHaveTextContent("Nhập nhãn");
    expect(createMcpKey).not.toHaveBeenCalled();
  });

  it("create → calls API with the label + scope, surfaces the generated key ONCE", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    createMcpKey.mockResolvedValue(CREATED({ key: "Knew_secret_TOKEN_999", label: "agent-x" }));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    // #160 — open the (collapsed) create form first
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle"));
    await waitFor(() => expect(screen.getByTestId("key-create-btn")).toBeInTheDocument());

    await user.type(screen.getByTestId("key-label-input"), "agent-x");
    await user.click(screen.getByTestId("key-create-btn"));

    // now sends {label, scope} (scope = empty by default → sees-nothing, honest)
    await waitFor(() => expect(createMcpKey).toHaveBeenCalledWith({ label: "agent-x", scope: { domains: [], tools: [] } }));
    // #128 — the token is shown ONCE but MASKED by default (the full secret is NOT on screen)
    const once = await screen.findByTestId("key-once");
    expect(within(once).getByTestId("key-once-token")).not.toHaveTextContent("Knew_secret_TOKEN_999");
    expect(within(once).getByTestId("key-once-token").textContent).toMatch(/•/); // masked dots
    // reveal-on-demand → the full token appears
    await user.click(within(once).getByTestId("key-once-reveal"));
    expect(within(once).getByTestId("key-once-token")).toHaveTextContent("Knew_secret_TOKEN_999");
    // dismissing hides it (the token won't reappear)
    await user.click(screen.getByTestId("key-once-dismiss"));
    expect(screen.queryByTestId("key-once")).toBeNull();
  });

  // part-2 — the scope editor: tick a DOMAIN → create sends that domain in scope.
  it("scope-editor: ticking a DOMAIN → create sends it in scope.domains", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    createMcpKey.mockResolvedValue(CREATED());
    render(<McpKeysPage />);
    const user = userEvent.setup();
    // #160 — open the (collapsed) create form first
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle"));
    await waitFor(() => expect(screen.getByTestId("scope-editor")).toBeInTheDocument());
    await user.type(screen.getByTestId("key-label-input"), "fin-agent");
    // tick the whole "finance" domain
    await user.click(screen.getByTestId("domain-check-finance"));
    // the selected-count reflects finance's 2 tools
    await waitFor(() => expect(screen.getByTestId("scope-selected-count")).toHaveTextContent("2"));
    await user.click(screen.getByTestId("key-create-btn"));
    await waitFor(() => expect(createMcpKey).toHaveBeenCalledWith({ label: "fin-agent", scope: { domains: ["finance"], tools: [] } }));
  });

  // part-2 — tick a stray individual tool of another domain → goes in scope.tools.
  it("scope-editor: DOMAIN + a stray TOOL → create sends the union {domains, tools}", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    createMcpKey.mockResolvedValue(CREATED());
    render(<McpKeysPage />);
    const user = userEvent.setup();
    // #160 — open the (collapsed) create form first
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle"));
    await waitFor(() => expect(screen.getByTestId("scope-editor")).toBeInTheDocument());
    await user.type(screen.getByTestId("key-label-input"), "mix");
    await user.click(screen.getByTestId("domain-check-finance"));   // whole finance
    await user.click(screen.getByTestId("tool-check-trc_a"));       // + one tracing tool
    await waitFor(() => expect(screen.getByTestId("scope-selected-count")).toHaveTextContent("3"));
    await user.click(screen.getByTestId("key-create-btn"));
    await waitFor(() => expect(createMcpKey).toHaveBeenCalledWith({ label: "mix", scope: { domains: ["finance"], tools: ["trc_a"] } }));
  });

  // part-2 — edit a key's scope → PUT with the new scope.
  it("edit scope → updateMcpKey called with the changed scope", async () => {
    getMcpKeys.mockResolvedValue(LIST([ROW({ scope: { domains: [], tools: [] }, toolCount: 0 })]));
    updateMcpKey.mockResolvedValue(CREATED());
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("keys-list")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("key-edit-Kkey_abc123def456"));
    const editBox = await screen.findByTestId("edit-scope-Kkey_abc123def456");
    // tick finance in the EDIT editor (scope the query — the create form has one too)
    await user.click(within(editBox).getByTestId("domain-check-finance"));
    await user.click(screen.getByTestId("edit-save-Kkey_abc123def456"));
    await waitFor(() => expect(updateMcpKey).toHaveBeenCalledWith("Kkey_abc123def456", { scope: { domains: ["finance"], tools: [] } }));
  });

  // part-2 — the catalog AUDIT view lists all tools + descriptions + the boundary.
  it("catalog audit → lists all tools with descriptions + capability boundary", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    await waitFor(() => expect(screen.getByTestId("audit-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("audit-toggle"));
    const audit = await screen.findByTestId("catalog-audit");
    expect(within(audit).getByTestId("audit-tool-fin_a")).toHaveTextContent("finance a");
    expect(within(audit).getByTestId("boundary-read")).toHaveTextContent("reads only");
    expect(within(audit).getByTestId("audit-domain-finance")).toBeInTheDocument();
  });

  it("create failure → inline error, no key-once banner", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    createMcpKey.mockRejectedValue(new Error("label taken"));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    // #160 — open the (collapsed) create form first
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle"));
    await waitFor(() => expect(screen.getByTestId("key-create-btn")).toBeInTheDocument());
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

  // part-2 — the scope editor renders in the create form (the seam is now the real editor).
  it("scope-editor renders in the create form with all catalog domains", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle")); // #160 open the create form
    await waitFor(() => expect(screen.getByTestId("scope-editor")).toBeInTheDocument());
    expect(screen.getByTestId("scope-domain-finance")).toBeInTheDocument();
    expect(screen.getByTestId("scope-domain-tracing")).toBeInTheDocument();
    expect(screen.getByTestId("scope-domain-write")).toBeInTheDocument();
    expect(screen.getByTestId("tool-row-fin_a")).toBeInTheDocument();
  });

  // catalog fetch fails → the scope-editor area shows an honest error (not a blank form).
  it("catalog fetch fails → scope-editor shows an honest error (not a blank form)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    getMcpCatalog.mockRejectedValue(new Error("catalog 500"));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle")); // #160 open the create form
    await waitFor(() => expect(screen.getByTestId("scope-cat-error")).toHaveTextContent("catalog 500"));
    // the create form itself still renders (label input present — create still possible)
    expect(screen.getByTestId("key-label-input")).toBeInTheDocument();
  });
});

describe("#129 MCP Keys — tool-detail expand (fullDescription + params table)", () => {
  beforeEach(() => { getMcpCatalog.mockResolvedValue(CATALOG()); });

  it("a tool row EXPANDS → its fullDescription + a params TABLE (name/type/required/default)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle")); // #160 open the create form (scope editor)
    await waitFor(() => expect(screen.getByTestId("tool-row-fin_a")).toBeInTheDocument());
    // collapsed by default — no detail
    expect(screen.queryByTestId("tool-detail-fin_a")).toBeNull();
    await user.click(screen.getByTestId("tool-expand-fin_a"));
    // expanded: full description + the params table
    expect(screen.getByTestId("tool-fulldesc-fin_a")).toHaveTextContent("the full docstring with details");
    const table = screen.getByTestId("tool-params-fin_a");
    expect(within(table).getByTestId("tool-param-fin_a-channel")).toHaveTextContent("channel");
    expect(within(table).getByTestId("tool-param-fin_a-channel")).toHaveTextContent("str");
    expect(within(table).getByTestId("tool-param-fin_a-channel")).toHaveTextContent("có"); // required
    // a param WITH a default shows it; required-no-default shows "—"
    expect(within(table).getByTestId("tool-param-fin_a-days")).toHaveTextContent("90");
  });

  it("🔴 a NO-ARG tool → 'không tham số' (honest-empty, not a fabricated row)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle")); // #160 open the create form (scope editor)
    await waitFor(() => expect(screen.getByTestId("tool-row-fin_b")).toBeInTheDocument());
    await user.click(screen.getByTestId("tool-expand-fin_b"));
    expect(screen.getByTestId("tool-noparams-fin_b")).toHaveTextContent("không tham số");
    expect(screen.queryByTestId("tool-params-fin_b")).toBeNull(); // no params table
  });

  it("expanding a tool does NOT toggle its scope checkbox (the ⓘ stops propagation)", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle")); // #160 open the create form (scope editor)
    await waitFor(() => expect(screen.getByTestId("tool-check-fin_a")).toBeInTheDocument());
    const check = screen.getByTestId("tool-check-fin_a") as HTMLInputElement;
    expect(check.checked).toBe(false);
    await user.click(screen.getByTestId("tool-expand-fin_a"));
    expect(check.checked).toBe(false); // still unchecked — expand ≠ tick
    expect(screen.getByTestId("tool-detail-fin_a")).toBeInTheDocument();
  });
});

describe("#128 MCP Keys — polish: key value masked (reveal-on-demand)", () => {
  beforeEach(() => { getMcpCatalog.mockResolvedValue(CATALOG()); });

  it("a freshly-created key is MASKED by default; reveal shows it, toggle re-masks", async () => {
    getMcpKeys.mockResolvedValue(LIST([]));
    createMcpKey.mockResolvedValue(CREATED({ key: "Ksecret_LONG_value_42", label: "z" }));
    render(<McpKeysPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("key-new-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("key-new-toggle")); // #160 open the create form
    await waitFor(() => expect(screen.getByTestId("key-create-btn")).toBeInTheDocument());
    await user.type(screen.getByTestId("key-label-input"), "z");
    await user.click(screen.getByTestId("key-create-btn"));
    const token = await screen.findByTestId("key-once-token");
    // masked: the raw secret is NOT on screen
    expect(token).not.toHaveTextContent("Ksecret_LONG_value_42");
    expect(token.textContent).toMatch(/•/);
    // the copy button is still offered (copies the real key — the #88 wiring is unchanged)
    expect(screen.getByTestId("key-once-copy")).toBeInTheDocument();
    // reveal → full key visible; toggle again → masked
    await user.click(screen.getByTestId("key-once-reveal"));
    expect(screen.getByTestId("key-once-token")).toHaveTextContent("Ksecret_LONG_value_42");
    await user.click(screen.getByTestId("key-once-reveal"));
    expect(screen.getByTestId("key-once-token")).not.toHaveTextContent("Ksecret_LONG_value_42");
  });
});
