"use client";
/* ============================================================
   useMcpKeys — #88 MCP key scoping (MCPKEYS): list keys + create + delete.
   GET /mcp_keys (list) · POST /mcp_keys (create → returns the row WITH the key) ·
   DELETE /mcp_keys/{key}. Types mirror the FROZEN #86 CRUD schema.

   RENDER-ONLY: the backend owns the store + computes toolCount (the resolved union).
   Reads are gated on status (loading/error/ready + honest empty []). Writes are
   FAIL-CLOSED (throw → the caller surfaces) + refetch-after-write so the list reflects
   server truth. A `nonce` drives reload; an `alive` guard drops a stale list response.

   SEAM (#88): the scope-editor (per-domain + per-tool tick over GET /mcp_keys/catalog)
   drops in later — create/update already accept a full `scope`; this hook needs no
   change when the catalog lands (the page wires the editor into the create/edit forms).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getMcpKeys, createMcpKey, updateMcpKey, deleteMcpKey, ApiError } from "@/lib/api";
import type { McpKey, McpKeyCreate, McpKeyUpdate } from "@/lib/types";

export type McpKeysStatus = "loading" | "error" | "ready";

export interface UseMcpKeys {
  keys: McpKey[];
  status: McpKeysStatus;
  errMsg: string;
  reload: () => void;
  /** create a key; returns the new row (incl. the secret `key`). fail-closed. */
  create: (body: McpKeyCreate) => Promise<McpKey>;
  /** update a key's label/scope (partial). fail-closed. */
  update: (key: string, body: McpKeyUpdate) => Promise<McpKey>;
  /** delete a key by its token. fail-closed. */
  remove: (key: string) => Promise<void>;
}

export function useMcpKeys(): UseMcpKeys {
  const [keys, setKeys] = useState<McpKey[]>([]);
  const [status, setStatus] = useState<McpKeysStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getMcpKeys();
        if (!alive) return;
        const d = res?.data;
        if (!Array.isArray(d)) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setKeys(d);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [nonce]);

  const create = useCallback(async (body: McpKeyCreate) => {
    const res = await createMcpKey(body); // fail-closed: throws → caller surfaces
    reload();
    return res.data;
  }, [reload]);

  const update = useCallback(async (key: string, body: McpKeyUpdate) => {
    const res = await updateMcpKey(key, body); // fail-closed
    reload();
    return res.data;
  }, [reload]);

  const remove = useCallback(async (key: string) => {
    await deleteMcpKey(key); // fail-closed
    reload();
  }, [reload]);

  return { keys, status, errMsg, reload, create, update, remove };
}
