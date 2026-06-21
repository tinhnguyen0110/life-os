"use client";
/* ============================================================
   useMcpCatalog — #88-part-2: the whole MCP tool catalog (audit + scope-editor source).
   GET /mcp_keys/catalog (live as of #87) → {tools, counts:{byMount,...}, capabilityBoundary}.
   RENDER-ONLY: the backend lists + counts; the FE displays + lets the user TICK a scope.
   One-shot load on mount (the catalog is static within a session) + reload. alive-guard.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getMcpCatalog, ApiError } from "@/lib/api";
import type { McpCatalog } from "@/lib/types";

export type CatalogStatus = "loading" | "error" | "ready";

export interface UseMcpCatalog {
  catalog: McpCatalog | null;
  status: CatalogStatus;
  errMsg: string;
  reload: () => void;
}

export function useMcpCatalog(): UseMcpCatalog {
  const [catalog, setCatalog] = useState<McpCatalog | null>(null);
  const [status, setStatus] = useState<CatalogStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getMcpCatalog();
        if (!alive) return;
        const d = res?.data;
        if (d == null || !Array.isArray(d.tools) || d.counts == null) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setCatalog(d);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [nonce]);

  return { catalog, status, errMsg, reload };
}
