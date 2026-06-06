"use client";
/* ============================================================
   S2 — Projects List. Ported from mock screens-projects.js SCREENS.projects.
   RENDER-ONLY: health/progress/summary come computed from the backend
   (GET /projects) — we never recompute a derived metric. Client-fetch on mount
   (BE base = NEXT_PUBLIC_API_BASE), tab filter is pure client-side over the rows.
   States: loading · error · empty · data (playbook: every data view).
   ============================================================ */
import { useEffect, useMemo, useState } from "react";
import { useSafeRouter } from "@/lib/useNav";
import { getProjects, ApiError, apiBase } from "@/lib/api";
import type { ProjectStatus, ProjectsSummary } from "@/lib/types";
import { HealthChip } from "@/components/shared/HealthChip";
import { ProgressBar } from "@/components/shared/ProgressBar";
import { KpiCard } from "@/components/shared/KpiCard";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { relativeTime, orDash } from "@/lib/format";
import { Icon } from "@/lib/icons";

type Filter = "all" | "act" | "slow" | "stall";

const TABS: { key: Filter; label: string }[] = [
  { key: "all", label: "Tất cả" },
  { key: "act", label: "Active" },
  { key: "slow", label: "Chậm" },
  { key: "stall", label: "Đứng" },
];

const EMPTY_SUMMARY: ProjectsSummary = { act: 0, slow: 0, stall: 0, dead: 0, total: 0 };

export default function ProjectsPage() {
  const router = useSafeRouter();
  const [projects, setProjects] = useState<ProjectStatus[]>([]);
  const [summary, setSummary] = useState<ProjectsSummary>(EMPTY_SUMMARY);
  const [warning, setWarning] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [errMsg, setErrMsg] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getProjects();
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
    return () => {
      alive = false;
    };
  }, []);

  const rows = useMemo(
    () => (filter === "all" ? projects : projects.filter((p) => p.health === filter)),
    [projects, filter],
  );

  const columns: Column<ProjectStatus>[] = useMemo(
    () => [
      { key: "name", header: "Dự án", className: "pn", cell: (p) => p.name },
      {
        key: "desc",
        header: "Mô tả",
        className: "mut",
        cell: (p) => orDash(p.desc),
      },
      { key: "health", header: "Sức khỏe", cell: (p) => <HealthChip health={p.health} /> },
      {
        key: "progress",
        header: "Tiến độ",
        cell: (p) => <ProgressBar value={p.progress} health={p.health} />,
      },
      {
        key: "users",
        header: "Users",
        className: undefined,
        cell: (p) => <span className={p.users > 0 ? "pos" : "faint"}>{p.users}</span>,
      },
      { key: "last", header: "Lần cuối", className: "faint", cell: (p) => relativeTime(p.last) },
      {
        key: "routines",
        header: "Routine",
        className: "faint",
        cell: (p) => p.routines.length,
      },
      { key: "next", header: "Next", className: "mut", cell: (p) => orDash(p.next) },
    ],
    [],
  );

  return (
    <section className="view" data-screen="S2" data-testid="projects-screen">
      <div className="vtitle">
        <h1>Dự án</h1>
        <span className="sub">{summary.total} đang theo dõi</span>
        <span className="sp" />
        <div className="tabs">
          {TABS.map((t) => (
            <span
              key={t.key}
              className={`tab${filter === t.key ? " on" : ""}`}
              onClick={() => setFilter(t.key)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") setFilter(t.key);
              }}
              data-tab={t.key}
            >
              {t.label}
            </span>
          ))}
        </div>
        <button className="btn accent" type="button" data-testid="new-project" title="Đăng ký dự án (sắp có)">
          <Icon name="i-proj" /> Dự án mới
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="projects-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {/* Summary KPI bar — values come straight from backend summary (render-only). */}
      <div className="grid g-4">
        <KpiCard label="Tổng dự án" value={summary.total} sub="đang theo dõi" />
        <KpiCard label="Active" value={summary.act} tone="pos" sub="commit gần đây" />
        <KpiCard
          label="Cần chú ý"
          value={summary.slow + summary.stall}
          tone="mid"
          sub={`${summary.stall} đứng · ${summary.slow} chậm`}
        />
        <KpiCard
          label="Đã chôn"
          value={summary.dead}
          tone={summary.dead > 0 ? "neg" : "default"}
          sub="nghĩa địa"
        />
      </div>

      <div className="panel" style={{ overflow: "hidden" }}>
        <div className="phead">
          <span className="kicker">Tất cả dự án</span>
          <span className="hint" style={{ marginLeft: "auto" }}>
            sắp theo idle ↓
          </span>
        </div>

        {status === "loading" && (
          <div className="hint" style={{ padding: "18px 16px" }} data-testid="projects-loading">
            Đang tải dự án…
          </div>
        )}

        {status === "error" && (
          <div className="hint neg" style={{ padding: "18px 16px" }} data-testid="projects-error">
            Không tải được dự án: {errMsg}. Kiểm tra backend ({apiBase}) rồi thử lại.
          </div>
        )}

        {status === "ready" && (
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(p) => p.id}
            onRowClick={(p) => router.push(`/projects/${p.id}`)}
            emptyLabel={
              filter === "all"
                ? "Chưa có dự án nào được theo dõi."
                : "Không có dự án nào ở trạng thái này."
            }
          />
        )}
      </div>
    </section>
  );
}
