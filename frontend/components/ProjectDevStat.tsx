"use client";
/* ============================================================
   ProjectDevStat (#114 · #112) — a compact per-project git dev-stat for the projects
   table: commits + a mini bar + lastActive over 90 days. Calls GET /projects/{id}/
   dev-activity?days=90 (lazy, on mount). RENDER-ONLY.

   🔴 honest-mirror: found:false → "chưa track git" (the repo isn't in the dev_activity
   scan) — NEVER a fake "0 commits" presented as real. The BE distinguishes "0 commits in
   a tracked repo" (found:true, commits:0) from "untracked" (found:false); we mirror that.
   ============================================================ */
import { useEffect, useState } from "react";
import { getProjectDevActivity, ApiError } from "@/lib/api";
import { fmtTokens, relativeTime } from "@/lib/format";
import type { ProjectDevActivity } from "@/lib/types";

type State = "loading" | "error" | "ready";

export function ProjectDevStat({ id, days = 90 }: { id: string; days?: number }) {
  const [data, setData] = useState<ProjectDevActivity | null>(null);
  const [state, setState] = useState<State>("loading");

  useEffect(() => {
    let alive = true;
    setState("loading");
    (async () => {
      try {
        const res = await getProjectDevActivity(id, days);
        if (!alive) return;
        setData(res.data);
        setState("ready");
      } catch {
        if (!alive) return;
        setState("error"); // a fetch error is non-fatal for the row — show a faint dash
      }
    })();
    return () => { alive = false; };
  }, [id, days]);

  if (state === "loading") return <span className="hint faint" data-testid={`devstat-loading-${id}`}>…</span>;
  if (state === "error" || !data) return <span className="hint faint" data-testid={`devstat-err-${id}`}>—</span>;

  // honest untracked — found:false → not in the scan, NOT a real 0.
  if (!data.found) {
    return (
      <span className="hint faint" data-testid={`devstat-untracked-${id}`} title={data.reason ?? "chưa track git"}>
        chưa track git
      </span>
    );
  }

  // found:true — real stats (commits:0 here means a tracked repo with no commits in
  // the window, which IS honest to show as 0).
  const net = data.locNet;
  return (
    <span className="devstat" data-testid={`devstat-${id}`} title={`${data.activeDays} ngày active · net ${net >= 0 ? "+" : "−"}${fmtTokens(Math.abs(net))} LOC`}>
      <b className="acc" data-testid={`devstat-commits-${id}`}>{data.commits}</b> commit
      {" · "}
      <span className="faint" data-testid={`devstat-last-${id}`}>{data.lastActiveDay ? relativeTime(data.lastActiveDay + "T00:00:00Z") : "—"}</span>
    </span>
  );
}
