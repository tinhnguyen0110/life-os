"use client";
/* ============================================================
   TopBar — breadcrumb · API live pill · routine-active · Sync · Refresh · alert bell.
   Ported from mock shell.js topbar markup. DEVIATION (ARCH §11): "Hỏi AI" button DROPPED.
   API pill polls /health (C4) → green=live, amber=checking, red=down.
   Refresh button spins (visual) + re-probes health. Bell → /market.
   ============================================================ */
import { useEffect, useState } from "react";
import { useSafeRouter, useSafePathname } from "@/lib/useNav";
import { CRUMB } from "@/lib/nav";
import { Icon } from "@/lib/icons";
import { getHealth, ApiError } from "@/lib/api";

type ApiState = "checking" | "live" | "down";

function crumbFor(pathname: string): string {
  if (CRUMB[pathname]) return CRUMB[pathname];
  // detail routes: /projects/foo → parent crumb
  const parent = "/" + (pathname.split("/").filter(Boolean)[0] ?? "");
  return CRUMB[parent] ?? "Home";
}

export function TopBar({ route }: { route?: string } = {}) {
  const router = useSafeRouter();
  const pathname = useSafePathname();
  const [api, setApi] = useState<ApiState>("checking");
  const [spinning, setSpinning] = useState(false);
  // Mount gate: the safe-pathname fallback can differ from the SSR value during
  // hydration, which would log a "Text content did not match" breadcrumb warning.
  // Render a stable crumb on the server/first paint, then the real path crumb.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  async function probe() {
    setApi("checking");
    try {
      const res = await getHealth();
      setApi(res.success ? "live" : "down");
    } catch (e) {
      // Backend not up yet in Sprint 0 dev is expected — fail to "down", no crash.
      if (e instanceof ApiError || e instanceof Error) setApi("down");
      else setApi("down");
    }
  }

  useEffect(() => {
    probe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onRefresh() {
    setSpinning(true);
    probe().finally(() => setTimeout(() => setSpinning(false), 800));
  }

  const dotCls = api === "live" ? "g" : api === "checking" ? "a" : "r";
  const apiLabel = api === "live" ? "live" : api === "checking" ? "…" : "down";

  return (
    <div className="topbar">
      <div className="crumb">
        <span className="c0">Life OS</span>
        <span className="sep">/</span>
        <span className="c1" data-testid="crumb">
          {route ?? (mounted ? crumbFor(pathname) : crumbFor("/"))}
        </span>
      </div>
      <div className="sp" />
      <div className="pill" data-testid="api-pill" data-api-status={api}>
        <span className={`dot ${dotCls}`} />
        API <b>{apiLabel}</b>
      </div>
      <div className="pill">
        <span className="dot g" />5 routine <b>active</b>
      </div>
      <div className="pill">
        Sync <b>2 phút trước</b>
      </div>
      <button
        type="button"
        className={`icbtn${spinning ? " spinning" : ""}`}
        onClick={onRefresh}
        title="Refresh data"
        aria-label="Refresh data"
      >
        <Icon name="i-refresh" />
      </button>
      <button
        type="button"
        className="icbtn"
        onClick={() => router.push("/market")}
        title="Cảnh báo"
        aria-label="Cảnh báo"
      >
        <Icon name="i-bell" />
        <span className="bdg">2</span>
      </button>
    </div>
  );
}
