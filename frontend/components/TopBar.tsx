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
import { getHealth, getRoutines, ApiError } from "@/lib/api";
import { usePrivacy } from "@/lib/usePrivacy";
import { PrivacyRevealModal } from "./PrivacyRevealModal";

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
  const { privacy, locked, setPrivacy, unlock } = usePrivacy();
  const [revealOpen, setRevealOpen] = useState(false);
  const [api, setApi] = useState<ApiState>("checking");
  const [spinning, setSpinning] = useState(false);
  // Live "routine active" count (S13 badge) — null until loaded / on failure.
  const [activeRoutines, setActiveRoutines] = useState<number | null>(null);
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
    // Fetch the live active-routine count for the badge (fail-soft: null on error,
    // so the pill just hides the number — never blocks the TopBar).
    getRoutines()
      .then((res) => setActiveRoutines(res?.data?.activeCount ?? null))
      .catch(() => setActiveRoutines(null));
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
      <div className="pill" data-testid="routine-active-pill">
        <span className="dot g" />
        {activeRoutines != null ? activeRoutines : "—"} routine <b>active</b>
      </div>
      <div className="pill">
        Sync <b>2 phút trước</b>
      </div>
      {/* #74 change 3+5 — privacy toggle (moved here from the sidebar). Same usePrivacy
          hook (CustomEvent broadcast keeps the body[data-privacy] mask in sync). Behavior:
          OFF → turn ON (money HIDDEN/locked); ON+locked → open the pass modal to reveal;
          ON+unlocked → turn OFF (back to normal). 👁 off / 🙈 on, accent when on. */}
      <button
        type="button"
        className={`icbtn${privacy ? " on" : ""}`}
        onClick={() => {
          if (!privacy) setPrivacy(true);          // OFF → lock money
          else if (locked) setRevealOpen(true);    // ON+locked → ask for pass
          else setPrivacy(false);                  // ON+unlocked → back to normal
        }}
        title={
          !privacy ? "Bật chế độ riêng tư (ẩn số tiền)"
            : locked ? "Mở khóa để hiện số tiền" : "Tắt chế độ riêng tư (hiện số tiền)"
        }
        aria-label="Chế độ riêng tư"
        aria-pressed={privacy}
        data-testid="tb-privacy-toggle"
        data-privacy-on={privacy ? "1" : "0"}
        data-privacy-locked={privacy && locked ? "1" : "0"}
      >
        <span aria-hidden style={{ fontSize: 15, lineHeight: 1 }}>{privacy ? "🙈" : "👁"}</span>
      </button>
      <PrivacyRevealModal open={revealOpen} onClose={() => setRevealOpen(false)} onSubmit={unlock} />
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
