import { apiGet, apiPost, apiPut, apiDelete } from "./_client";
import type {
  ApiResponse,
  McpCatalog,
  McpKey,
  McpKeyCreate,
  McpKeyUpdate,
} from "@/lib/types";

/** GET /mcp_keys — list all keys (each row carries its scope + resolved toolCount). */
export function getMcpKeys(): Promise<ApiResponse<McpKey[]>> {
  return apiGet<McpKey[]>("/mcp_keys");
}
/** POST /mcp_keys — create a key. The response row INCLUDES the generated `key`
 *  token (the only time the full token appears in a row — surface it once). */
export function createMcpKey(body: McpKeyCreate): Promise<ApiResponse<McpKey>> {
  return apiPost<McpKey>("/mcp_keys", body);
}
/** PUT /mcp_keys/{key} — partial update (label and/or scope; undefined = unchanged). */
export function updateMcpKey(key: string, body: McpKeyUpdate): Promise<ApiResponse<McpKey>> {
  return apiPut<McpKey>(`/mcp_keys/${encodeURIComponent(key)}`, body);
}
/** DELETE /mcp_keys/{key} — remove a key. Returns `{deleted:<key>}`. */
export function deleteMcpKey(key: string): Promise<ApiResponse<{ deleted: string }>> {
  return apiDelete<{ deleted: string }>(`/mcp_keys/${encodeURIComponent(key)}`);
}
/** GET /mcp_keys/catalog — the whole tool catalog (audit + scope-editor source).
 *  ⚠️ #88: this REST route may NOT exist yet (list_tools_catalog is MCP-only). The
 *  scope-editor depends on it; flagged to expose it over REST. */
export function getMcpCatalog(): Promise<ApiResponse<McpCatalog>> {
  return apiGet<McpCatalog>("/mcp_keys/catalog");
}
