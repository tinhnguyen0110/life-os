/** What a key can see. A key with `{domains:[],tools:[]}` (the default) sees NOTHING. */
export interface McpScope {
  /** mount labels (= catalog `server` values, e.g. "read","finance") the key sees IN FULL. */
  domains: string[];
  /** explicit tool names the key sees (on top of its domains). */
  tools: string[];
}
/** A key row (GET /mcp_keys list item + POST /mcp_keys response). The POST response
 *  is the ONLY place the full `key` token appears in a row — surface it once on create. */
export interface McpKey {
  /** the secret key token. */
  key: string;
  label: string;
  scope: McpScope;
  /** the RESOLVED count of tools this scope sees (domain tools ∪ explicit, deduped) —
   *  computed by the backend, render-only. */
  toolCount: number;
  createdAt: string;
}
/** POST /mcp_keys body — label (1-80) + optional scope (defaults to sees-nothing). */
export interface McpKeyCreate {
  label: string;
  scope?: McpScope;
}
/** PUT /mcp_keys/{key} body — partial; a field left undefined is unchanged. */
export interface McpKeyUpdate {
  label?: string;
  scope?: McpScope;
}
/** One tool in the catalog (the audit surface). From `list_tools_catalog`. */
export interface McpCatalogTool {
  name: string;
  /** the mount/domain this tool belongs to (e.g. "read","finance","wiki-read"). */
  server: string;
  /** "read" (safe) or "propose" (write-proposing). */
  capability: string;
  /** whether the tool is neutral (no side-class). */
  neutral: boolean;
  /** the 1-line summary (the collapsed label). */
  description: string;
  /** #129 — the full tool docstring (shown when a tool row is expanded). */
  fullDescription: string;
  /** #129 — the tool's call-params (name/type/required/default). [] = a no-arg tool
   *  ("không tham số"). Mirrors the FROZEN #129-BE catalog shape. */
  params: McpToolParam[];
}
/** #129 — one call-parameter of a tool (the expanded params table row). `default` is
 *  present only when the param HAS a default (omitted for required/no-default params). */
export interface McpToolParam {
  name: string;
  type: string;
  required: boolean;
  default?: unknown;
}
/** Catalog counts — BE-computed (render-only). byMount = the per-DOMAIN tool count
 *  (the audit numbers + the domains the scope ticks). `note` honestly explains the
 *  cross-domain overlap (some domains reference-import shared fns). */
export interface McpCatalogCounts {
  /** distinct read-capability tools. */
  read: number;
  /** distinct write(propose)-capability tools. */
  write: number;
  total: number;
  /** per-mount/domain listing counts (the scope-editor domains + audit counts). */
  byMount: Record<string, number>;
  /** total listing length across mounts (with overlaps). */
  allMounts: number;
  note: string;
}
/** GET /mcp_keys/catalog → the whole tool catalog (audit + scope-editor source).
 *  Live as of #87. byte-identical to the `list_tools_catalog` MCP payload. */
export interface McpCatalog {
  tools: McpCatalogTool[];
  counts: McpCatalogCounts;
  /** honest per-capability safety boundary text (read/write/apply/...). Shown in the
   *  audit view so the user understands what each capability class can/can't do. */
  capabilityBoundary: Record<string, string>;
}
