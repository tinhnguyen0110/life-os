/* ============================================================
   #88-part-2 — MCP scope editor logic (PURE, testable). The saved scope is
   `{domains, tools}`: a DOMAIN means "all tools in that mount"; `tools` are explicit
   extras on top. The "resolved set" a key sees = (∪ tools of each domain) ∪ tools.

   Editor model — both ticks, per the spec:
   - tick a whole DOMAIN → it goes in `domains` (the key sees ALL its tools)
   - tick an INDIVIDUAL tool → it goes in `tools` (unless its domain is already ticked,
     in which case it's redundant and we keep `tools` clean by not adding it)

   These helpers are display/derivation ONLY — the backend resolves toolCount + enforces
   the scope. Keep them pure so the editor logic is unit-tested without a DOM.
   ============================================================ */
import type { McpScope, McpCatalogTool } from "@/lib/types";

/** All tool names belonging to a domain (mount = `server`). */
export function toolsInDomain(tools: McpCatalogTool[], domain: string): string[] {
  return tools.filter((t) => t.server === domain).map((t) => t.name);
}

/** Is a single tool effectively SELECTED by a scope? (its domain is fully ticked OR
 *  it's an explicit tool). This drives the per-tool checkbox state in the editor. */
export function isToolSelected(scope: McpScope, tool: McpCatalogTool): boolean {
  return scope.domains.includes(tool.server) || scope.tools.includes(tool.name);
}

/** Is a whole DOMAIN ticked? */
export function isDomainSelected(scope: McpScope, domain: string): boolean {
  return scope.domains.includes(domain);
}

/** Toggle a whole DOMAIN. On → add to `domains` AND drop any now-redundant explicit
 *  tools of that domain (kept clean). Off → remove from `domains` (its tools are no
 *  longer seen unless re-ticked individually). */
export function toggleDomain(scope: McpScope, domain: string, allTools: McpCatalogTool[]): McpScope {
  if (scope.domains.includes(domain)) {
    return { domains: scope.domains.filter((d) => d !== domain), tools: scope.tools };
  }
  const domainToolNames = new Set(toolsInDomain(allTools, domain));
  return {
    domains: [...scope.domains, domain],
    // drop explicit tools now covered by the domain (no redundant entries)
    tools: scope.tools.filter((t) => !domainToolNames.has(t)),
  };
}

/** Toggle an INDIVIDUAL tool. If its domain is fully ticked, toggling the tool OFF
 *  means: un-tick the domain but keep the OTHER domain tools as explicit `tools` (so
 *  the user removes exactly one). Toggling ON when domain not ticked → add to `tools`. */
export function toggleTool(scope: McpScope, tool: McpCatalogTool, allTools: McpCatalogTool[]): McpScope {
  const domain = tool.server;
  const domainTicked = scope.domains.includes(domain);

  if (domainTicked) {
    // expand the domain into explicit tools MINUS this one (un-tick exactly one tool).
    const others = toolsInDomain(allTools, domain).filter((n) => n !== tool.name);
    const merged = new Set([...scope.tools.filter((t) => !toolsInDomain(allTools, domain).includes(t)), ...others]);
    return {
      domains: scope.domains.filter((d) => d !== domain),
      tools: Array.from(merged),
    };
  }

  // domain not ticked → simple toggle of the explicit tool
  if (scope.tools.includes(tool.name)) {
    return { domains: scope.domains, tools: scope.tools.filter((t) => t !== tool.name) };
  }
  return { domains: scope.domains, tools: [...scope.tools, tool.name] };
}

/** The RESOLVED set of tool names a scope grants (domain tools ∪ explicit), deduped.
 *  Display-only — the BE computes the authoritative toolCount on the row. */
export function resolvedTools(scope: McpScope, allTools: McpCatalogTool[]): string[] {
  const set = new Set<string>();
  for (const d of scope.domains) for (const n of toolsInDomain(allTools, d)) set.add(n);
  for (const t of scope.tools) set.add(t);
  return Array.from(set);
}

/** A clean empty scope (sees nothing). */
export const EMPTY_SCOPE: McpScope = { domains: [], tools: [] };

/** Group the catalog tools by domain (`server`), in a stable order. */
export function groupByDomain(tools: McpCatalogTool[]): { domain: string; tools: McpCatalogTool[] }[] {
  const map = new Map<string, McpCatalogTool[]>();
  for (const t of tools) {
    const arr = map.get(t.server) ?? [];
    arr.push(t);
    map.set(t.server, arr);
  }
  return Array.from(map.entries()).map(([domain, ts]) => ({ domain, tools: ts }));
}
