"use client";
/* ============================================================
   /wiki/moc (WIKI-TRIM) — REDIRECT to /wiki. The MOC / Synthesize screen was
   REMOVED (over-engineered cluster-detector for a 1-user AI-first app). MOC notes
   (kind=moc) are NORMAL notes — they still live in the Vault + Graph; only the
   standalone screen is gone. The BE endpoints (clusters/mocs) stay for MCP/agent.
   This route file exists ONLY so old bookmarks/deep-links redirect cleanly instead
   of falling into /wiki/[id] ("Note id không hợp lệ"). Matches the inbox-redirect
   convention. NOT a nav item; links to /wiki, never to itself.
   ============================================================ */
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function WikiMocRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/wiki");
  }, [router]);
  return (
    <div className="hint faint" style={{ padding: "24px 4px" }} data-testid="wiki-moc-redirect">
      Đang chuyển tới Vault…
    </div>
  );
}
