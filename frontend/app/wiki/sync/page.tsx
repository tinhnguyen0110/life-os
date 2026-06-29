"use client";
/* ============================================================
   /wiki/sync (WIKI-TRIM) — REDIRECT to /wiki. The Sync & Integrity (conflict-
   resolution) screen was REMOVED — it solves a MULTI-USER problem (concurrent
   edits / conflicts) that doesn't exist in a 1-user AI-first app. The BE endpoints
   (conflicts/resolve) stay for MCP/agent. This route file exists ONLY so old
   bookmarks/deep-links redirect cleanly instead of falling into /wiki/[id]
   ("Note id không hợp lệ"). Matches the inbox-redirect convention. NOT a nav item;
   links to /wiki, never to itself.
   ============================================================ */
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function WikiSyncRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/wiki");
  }, [router]);
  return (
    <div className="hint faint" style={{ padding: "24px 4px" }} data-testid="wiki-sync-redirect">
      Đang chuyển tới Vault…
    </div>
  );
}
