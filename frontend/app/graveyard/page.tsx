"use client";
/* ============================================================
   /graveyard (#114) — REDIRECT to /projects?tab=graveyard. The S4 graveyard is now an
   in-page sub-tab of the unified Projects screen (gộp 3→2). The old /graveyard URL
   keeps working (deep-links, bookmarks) by redirecting here. The actual UI lives in
   <GraveyardView> rendered inside app/projects/page.tsx.
   ============================================================ */
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function GraveyardRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/projects?tab=graveyard");
  }, [router]);
  return (
    <div className="hint faint" style={{ padding: "24px 4px" }} data-testid="graveyard-redirect">
      Đang chuyển tới Dự án › Nghĩa địa…
    </div>
  );
}
