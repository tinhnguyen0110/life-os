import { describe, it, expect } from "vitest";
import {
  toolsInDomain, isToolSelected, isDomainSelected, toggleDomain, toggleTool,
  resolvedTools, groupByDomain, EMPTY_SCOPE,
} from "../mcpScope";
import type { McpCatalogTool, McpScope } from "../types";

/* #88-part-2 — the scope-editor LOGIC (pure). The saved scope is {domains,tools}: a
   domain = "all its tools"; tools = explicit extras. These are the distinguishing
   cases the dispatch named: domain-tick selects all domain tools · per-tool toggle ·
   the union resolves correctly. */

const T = (name: string, server: string): McpCatalogTool => ({
  name, server, capability: "read", neutral: false, description: `${name} desc`,
  fullDescription: `${name} full desc`, params: [],
});
// 2 domains: "finance" (3 tools), "tracing" (2 tools)
const CATALOG: McpCatalogTool[] = [
  T("fin_a", "finance"), T("fin_b", "finance"), T("fin_c", "finance"),
  T("trc_a", "tracing"), T("trc_b", "tracing"),
];

describe("mcpScope — scope-editor logic (#88-part-2)", () => {
  it("toolsInDomain → exactly that domain's tool names", () => {
    expect(toolsInDomain(CATALOG, "finance").sort()).toEqual(["fin_a", "fin_b", "fin_c"]);
    expect(toolsInDomain(CATALOG, "tracing").sort()).toEqual(["trc_a", "trc_b"]);
    expect(toolsInDomain(CATALOG, "nope")).toEqual([]);
  });

  it("groupByDomain → one group per server with its tools", () => {
    const g = groupByDomain(CATALOG);
    expect(g.map((x) => x.domain).sort()).toEqual(["finance", "tracing"]);
    expect(g.find((x) => x.domain === "finance")!.tools.length).toBe(3);
  });

  // THE core case — ticking a DOMAIN selects ALL its tools.
  it("toggleDomain ON → domain in scope.domains; ALL its tools read as selected", () => {
    const s = toggleDomain(EMPTY_SCOPE, "finance", CATALOG);
    expect(s.domains).toEqual(["finance"]);
    expect(isDomainSelected(s, "finance")).toBe(true);
    // every finance tool is effectively selected (via the domain)
    for (const t of CATALOG.filter((x) => x.server === "finance")) {
      expect(isToolSelected(s, t)).toBe(true);
    }
    // tracing tools are NOT selected
    expect(isToolSelected(s, T("trc_a", "tracing"))).toBe(false);
    // resolved set = all 3 finance tools (no explicit needed)
    expect(resolvedTools(s, CATALOG).sort()).toEqual(["fin_a", "fin_b", "fin_c"]);
  });

  it("toggleDomain OFF → removes the domain (its tools no longer selected)", () => {
    let s = toggleDomain(EMPTY_SCOPE, "finance", CATALOG);
    s = toggleDomain(s, "finance", CATALOG);
    expect(s.domains).toEqual([]);
    expect(resolvedTools(s, CATALOG)).toEqual([]);
  });

  // per-tool toggle when the domain is NOT ticked → explicit tools[].
  it("toggleTool ON (domain not ticked) → tool goes in scope.tools, resolves to itself", () => {
    const s = toggleTool(EMPTY_SCOPE, T("fin_a", "finance"), CATALOG);
    expect(s.tools).toEqual(["fin_a"]);
    expect(s.domains).toEqual([]);
    expect(isToolSelected(s, T("fin_a", "finance"))).toBe(true);
    expect(isToolSelected(s, T("fin_b", "finance"))).toBe(false);
    expect(resolvedTools(s, CATALOG)).toEqual(["fin_a"]);
  });

  it("toggleTool OFF (explicit) → removes just that tool", () => {
    let s = toggleTool(EMPTY_SCOPE, T("fin_a", "finance"), CATALOG);
    s = toggleTool(s, T("fin_a", "finance"), CATALOG);
    expect(s.tools).toEqual([]);
  });

  // BOTH ticks together — domain + a stray tool of ANOTHER domain (the dispatch's case).
  it("domain + a stray individual tool → union resolves correctly", () => {
    let s = toggleDomain(EMPTY_SCOPE, "finance", CATALOG); // all finance
    s = toggleTool(s, T("trc_a", "tracing"), CATALOG);     // + one tracing tool
    expect(s.domains).toEqual(["finance"]);
    expect(s.tools).toEqual(["trc_a"]);
    // resolved = 3 finance + 1 tracing = 4
    expect(resolvedTools(s, CATALOG).sort()).toEqual(["fin_a", "fin_b", "fin_c", "trc_a"]);
    expect(isToolSelected(s, T("trc_a", "tracing"))).toBe(true);
    expect(isToolSelected(s, T("trc_b", "tracing"))).toBe(false);
  });

  // ticking a DOMAIN drops now-redundant explicit tools of that domain (kept clean).
  it("toggleDomain ON absorbs an already-explicit tool of that domain (no dup in tools)", () => {
    let s = toggleTool(EMPTY_SCOPE, T("fin_a", "finance"), CATALOG); // explicit fin_a
    s = toggleDomain(s, "finance", CATALOG);                          // now whole finance
    expect(s.domains).toEqual(["finance"]);
    expect(s.tools).toEqual([]); // fin_a absorbed — not duplicated
    expect(resolvedTools(s, CATALOG).sort()).toEqual(["fin_a", "fin_b", "fin_c"]);
  });

  // un-ticking ONE tool of a fully-ticked domain → domain expands to explicit MINUS that one.
  it("toggleTool OFF on a domain-ticked tool → un-tick exactly that one (keep the rest)", () => {
    let s = toggleDomain(EMPTY_SCOPE, "finance", CATALOG); // all 3 finance via domain
    s = toggleTool(s, T("fin_b", "finance"), CATALOG);     // un-tick fin_b
    expect(s.domains).toEqual([]); // domain no longer "all"
    expect(s.tools.sort()).toEqual(["fin_a", "fin_c"]); // the other two stay explicit
    expect(isToolSelected(s, T("fin_b", "finance"))).toBe(false);
    expect(resolvedTools(s, CATALOG).sort()).toEqual(["fin_a", "fin_c"]);
  });

  it("resolvedTools dedups overlap (domain + an explicit tool already in it)", () => {
    const s: McpScope = { domains: ["finance"], tools: ["fin_a"] }; // fin_a redundant
    expect(resolvedTools(s, CATALOG).sort()).toEqual(["fin_a", "fin_b", "fin_c"]);
  });
});
