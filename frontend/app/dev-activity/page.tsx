"use client";
/* ============================================================
   /dev-activity (#120) — REDIRECT to /projects?tab=dev. The DEVACT git-contribution
   view is now an in-page sub-tab of the unified Projects screen (user-CHỐT: fold Dev
   Activity into the Projects tab). The old /dev-activity URL keeps working (deep-links,
   bookmarks) by redirecting here. The actual UI lives in <DevActivityView> rendered
   inside app/projects/page.tsx.
   ============================================================ */
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DevActivityRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/projects?tab=dev");
  }, [router]);
  return (
    <div className="hint faint" style={{ padding: "24px 4px" }} data-testid="dev-activity-redirect">
      Đang chuyển tới Dự án › Dev Activity…
    </div>
  );
}
