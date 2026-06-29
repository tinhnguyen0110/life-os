"use client";
/* ============================================================
   /wiki/inbox (WIKI-AIFIRST) — REDIRECT to /wiki. The standalone Inbox/triage
   screen was REMOVED (AI-first: writes land directly, fleeting notes refine in
   place at /wiki/{id}). This route file exists ONLY to keep old bookmarks /
   deep-links alive — it is NOT a nav item and links to /wiki, never to itself.
   (Without it, /wiki/inbox falls into /wiki/[id] and renders a confusing
   "Note id không hợp lệ" error.) Matches the /graveyard + /dev-activity redirect
   convention.
   ============================================================ */
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function WikiInboxRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/wiki");
  }, [router]);
  return (
    <div className="hint faint" style={{ padding: "24px 4px" }} data-testid="wiki-inbox-redirect">
      Đang chuyển tới Vault…
    </div>
  );
}
