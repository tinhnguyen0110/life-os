"use client";
/* ============================================================
   S2 — Projects (unified, #114). gộp 3→2: ONE "Dự án" screen with a [Đang chạy |
   Nghĩa địa] sub-tab. Đang chạy = the S2 list (health-filterable table); Nghĩa địa =
   <GraveyardView> in-page (the old S4). /graveyard redirects here; ?tab=graveyard
   deep-links. RENDER-ONLY: health/progress/summary/source/hidden/dev-stat all from the
   backend — never recomputed.

   #114 per-row: source badge (auto/config/registered) · hide/unhide (soft, ≠ abandon,
   in-page) · dev-stat strip (GET /projects/{id}/dev-activity, found:false → honest
   "chưa track git", NOT fake 0s).
   ============================================================ */
import { useEffect, useMemo, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useSafeRouter } from "@/lib/useNav";
import { getProjects, hideProject, unhideProject, ApiError, apiBase } from "@/lib/api";
import type { ProjectStatus, ProjectsSummary, ProjectSource } from "@/lib/types";
import { HealthChip } from "@/components/shared/HealthChip";
import { ProgressBar } from "@/components/shared/ProgressBar";
import { KpiCard } from "@/components/shared/KpiCard";
import { GraveyardView } from "@/components/GraveyardView";
import { ProjectDevStat } from "@/components/ProjectDevStat";
import { relativeTime, orDash } from "@/lib/format";
import { Icon } from "@/lib/icons";

type Filter = "all" | "act" | "slow" | "stall";
type SubTab = "running" | "graveyard";

const HEALTH_TABS: { key: Filter; label: string }[] = [
  { key: "all", label: "Tất cả" },
  { key: "act", label: "Active" },
  { key: "slow", label: "Chậm" },
  { key: "stall", label: "Đứng" },
];

/** source badge label + tone (render-only, from #113 ProjectStatus.source). */
const SOURCE_META: Record<ProjectSource, { label: string; cls: string }> = {
  auto: { label: "tự động", cls: "mid" },
  config: { label: "cấu hình", cls: "acc" },
  registered: { label: "đã đăng ký", cls: "pos" },
};

const EMPTY_SUMMARY: ProjectsSummary = { act: 0, slow: 0, stall: 0, dead: 0, total: 0 };

function ProjectsInner() {
  const router = useSafeRouter();
  const params = useSearchParams();
  const subTab: SubTab = params?.get("tab") === "graveyard" ? "graveyard" : "running";

  const [projects, setProjects] = useState<ProjectStatus[]>([]);
  const [summary, setSummary] = useState<ProjectsSummary>(EMPTY_SUMMARY);
  const [warning, setWarning] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [errMsg, setErrMsg] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  // #114 hide/unhide
  const [includeHidden, setIncludeHidden] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState("");
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getProjects(includeHidden);
        if (!alive) return;
        setProjects(res.data.projects ?? []);
        setSummary(res.data.summary ?? EMPTY_SUMMARY);
        setWarning(res.warning ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [includeHidden, nonce]);

  const rows = useMemo(
    () => (filter === "all" ? projects : projects.filter((p) => p.health === filter)),
    [projects, filter],
  );

  function setTab(t: SubTab) {
    router.push(t === "graveyard" ? "/projects?tab=graveyard" : "/projects");
  }

  async function onHide(p: ProjectStatus) {
    setActionErr(""); setBusyId(p.id);
    try {
      if (p.hidden) await unhideProject(p.id); else await hideProject(p.id);
      setNonce((n) => n + 1); // refetch (the row leaves/joins per the current includeHidden)
    } catch (e) {
      setActionErr(`${p.hidden ? "Bỏ ẩn" : "Ẩn"} "${p.name}" thất bại: ${e instanceof ApiError ? e.message : (e as Error).message}`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="view" data-screen="S2" data-testid="projects-screen">
      <div className="vtitle">
        <h1>Dự án</h1>
        <span className="sub">{summary.total} đang theo dõi · {summary.dead} đã chôn</span>
        <span className="sp" />
        <button className="btn accent" type="button" data-testid="new-project" title="Đăng ký dự án (sắp có)">
          <Icon name="i-proj" /> Dự án mới
        </button>
      </div>

      {/* #114 sub-tab: Đang chạy | Nghĩa địa */}
      <div className="seg" data-testid="project-subtab" role="tablist" style={{ marginBottom: 12 }}>
        <button type="button" role="tab" aria-selected={subTab === "running"} className={subTab === "running" ? "on" : ""} onClick={() => setTab("running")} data-testid="subtab-running">
          Đang chạy
        </button>
        <button type="button" role="tab" aria-selected={subTab === "graveyard"} className={subTab === "graveyard" ? "on" : ""} onClick={() => setTab("graveyard")} data-testid="subtab-graveyard">
          Nghĩa địa{summary.dead > 0 ? ` (${summary.dead})` : ""}
        </button>
      </div>

      {subTab === "graveyard" ? (
        <GraveyardView showExportHeader />
      ) : (
        <>
          {warning && (
            <div className="panel" style={{ padding: "10px 14px" }} data-testid="projects-warning">
              <span className="hint mid">⚠ {warning}</span>
            </div>
          )}
          {actionErr && (
            <div className="panel" style={{ padding: "10px 14px" }} data-testid="projects-action-error">
              <span className="hint neg">⚠ {actionErr}</span>
              <span className="link" style={{ marginLeft: 10 }} onClick={() => setActionErr("")}>đóng</span>
            </div>
          )}

          {/* Summary KPI bar (render-only) */}
          <div className="grid g-4">
            <KpiCard label="Tổng dự án" value={summary.total} sub="đang theo dõi" />
            <KpiCard label="Active" value={summary.act} tone="pos" sub="commit gần đây" />
            <KpiCard label="Cần chú ý" value={summary.slow + summary.stall} tone="mid" sub={`${summary.stall} đứng · ${summary.slow} chậm`} />
            <KpiCard label="Đã chôn" value={summary.dead} tone={summary.dead > 0 ? "neg" : "default"} sub="nghĩa địa" />
          </div>

          {/* health filter + hidden toggle */}
          <div className="row" style={{ alignItems: "center", gap: 8, margin: "10px 0 6px", flexWrap: "wrap" }}>
            <div className="tabs">
              {HEALTH_TABS.map((t) => (
                <span key={t.key} className={`tab${filter === t.key ? " on" : ""}`} onClick={() => setFilter(t.key)} role="button" tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setFilter(t.key); }} data-tab={t.key}>
                  {t.label}
                </span>
              ))}
            </div>
            <span className="sp" style={{ flex: 1 }} />
            <button type="button" className={`tab${includeHidden ? " on" : ""}`} onClick={() => setIncludeHidden((h) => !h)} data-testid="toggle-hidden" aria-pressed={includeHidden}>
              {includeHidden ? "Đang hiện cả ẩn" : "Hiện cả đã ẩn"}
            </button>
          </div>

          <div className="panel" style={{ overflow: "hidden" }}>
            <div className="phead"><span className="kicker">Dự án</span><span className="hint" style={{ marginLeft: "auto" }}>{rows.length} dự án</span></div>

            {status === "loading" && <div className="hint" style={{ padding: "18px 16px" }} data-testid="projects-loading">Đang tải dự án…</div>}
            {status === "error" && <div className="hint neg" style={{ padding: "18px 16px" }} data-testid="projects-error">Không tải được dự án: {errMsg}. Kiểm tra backend ({apiBase}) rồi thử lại.</div>}

            {status === "ready" && (
              rows.length === 0 ? (
                <div className="hint" style={{ padding: "18px 16px" }} data-testid="projects-empty">
                  {filter === "all" ? "Chưa có dự án nào được theo dõi." : "Không có dự án nào ở trạng thái này."}
                </div>
              ) : (
                <table className="proj-table" data-testid="projects-table">
                  <thead>
                    <tr>
                      <th>Dự án</th><th>Nguồn</th><th>Sức khỏe</th><th>Tiến độ</th>
                      <th className="num-col">Git (90n)</th><th className="num-col">Lần cuối</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((p) => (
                      <tr key={p.id} data-testid={`proj-row-${p.id}`} className={p.hidden ? "proj-hidden" : ""}>
                        <td className="pn clickable" onClick={() => router.push(`/projects/${p.id}`)}>
                          {p.name}
                          {p.hidden && <span className="tagchip" style={{ marginLeft: 6 }} data-testid={`hidden-tag-${p.id}`}>đã ẩn</span>}
                          <div className="mut" style={{ fontSize: 11 }}>{orDash(p.desc)}</div>
                        </td>
                        <td>
                          <span className={`tagchip ${SOURCE_META[p.source]?.cls ?? ""}`} data-testid={`source-${p.id}`} title={`nguồn: ${p.source}`}>
                            {SOURCE_META[p.source]?.label ?? p.source}
                          </span>
                        </td>
                        <td><HealthChip health={p.health} /></td>
                        <td style={{ minWidth: 110 }}><ProgressBar value={p.progress} health={p.health} /></td>
                        <td className="num-col"><ProjectDevStat id={p.id} /></td>
                        <td className="num-col faint">{relativeTime(p.last)}</td>
                        <td className="num-col">
                          <button type="button" className="btn sm" disabled={busyId === p.id} onClick={() => onHide(p)} data-testid={`hide-${p.id}`} title={p.hidden ? "Bỏ ẩn" : "Ẩn khỏi danh sách"}>
                            {busyId === p.id ? "…" : p.hidden ? "Bỏ ẩn" : "Ẩn"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default function ProjectsPage() {
  // useSearchParams requires a Suspense boundary in the app router.
  return (
    <Suspense fallback={<div className="hint" style={{ padding: "18px 16px" }}>Đang tải…</div>}>
      <ProjectsInner />
    </Suspense>
  );
}
