"use client";
/* ============================================================
   S3 — Project Detail. Ported from mock screens-projects.js SCREENS.project.
   RENDER-ONLY for metrics; the two write actions (refresh / abandon) POST to the
   backend and re-render from its response — we never mutate derived state locally.
   States: loading · 404 (not-found) · error · ready. Nulls → "—" / "chưa chạy".
   ============================================================ */
import { useEffect, useState } from "react";
import { useSafeRouter } from "@/lib/useNav";
import { getProject, apiPost, ApiError, apiBase } from "@/lib/api";
import type { ProjectStatus } from "@/lib/types";
import { HealthChip } from "@/components/shared/HealthChip";
import { ProgressBar } from "@/components/shared/ProgressBar";
import { KpiCard } from "@/components/shared/KpiCard";
import { relativeTime, idleDays, orDash } from "@/lib/format";
import { Icon } from "@/lib/icons";

export default function ProjectDetailPage({ params }: { params?: { id?: string } }) {
  const id = params?.id ?? "";
  const router = useSafeRouter();
  const [project, setProject] = useState<ProjectStatus | null>(null);
  const [status, setStatus] = useState<"loading" | "notfound" | "error" | "ready">("loading");
  const [errMsg, setErrMsg] = useState("");
  const [busy, setBusy] = useState<"" | "refresh" | "abandon">("");

  async function load() {
    setStatus("loading");
    try {
      const res = await getProject(id);
      setProject(res.data);
      setStatus("ready");
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setStatus("notfound");
      } else {
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    }
  }

  useEffect(() => {
    if (!id) {
      setStatus("notfound");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function onRefresh() {
    setBusy("refresh");
    try {
      const res = await apiPost<ProjectStatus>(`/projects/${encodeURIComponent(id)}/refresh`);
      setProject(res.data); // re-render from backend truth, never recompute
    } catch (e) {
      setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function onAbandon() {
    setBusy("abandon");
    try {
      await apiPost<ProjectStatus>(`/projects/${encodeURIComponent(id)}/abandon`, {
        reason: "Đưa vào nghĩa địa từ màn hình chi tiết",
      });
      router.push("/graveyard");
    } catch (e) {
      setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
      setBusy("");
    }
  }

  if (status === "loading") {
    return (
      <section className="view" data-screen="S3">
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="detail-loading">
          Đang tải dự án…
        </div>
      </section>
    );
  }

  if (status === "notfound") {
    return (
      <section className="view" data-screen="S3">
        <div className="empty-screen" data-testid="detail-notfound">
          <div className="es-icon">
            <Icon name="i-proj" />
          </div>
          <h1>Không tìm thấy dự án</h1>
          <span className="es-meta">Id “{id}” không có trong danh sách theo dõi.</span>
          <button className="btn" type="button" onClick={() => router.push("/projects")}>
            ← Về danh sách
          </button>
        </div>
      </section>
    );
  }

  if (status === "error" || !project) {
    return (
      <section className="view" data-screen="S3">
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="detail-error">
          Lỗi tải dự án: {errMsg}. Kiểm tra backend ({apiBase}).
          <button
            className="btn"
            type="button"
            style={{ marginLeft: 10 }}
            onClick={load}
          >
            Thử lại
          </button>
        </div>
      </section>
    );
  }

  const p = project;

  return (
    <section className="view" data-screen="S3" data-testid="detail-screen">
      <div className="detail-head" style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <button
          className="btn"
          type="button"
          onClick={() => router.push("/projects")}
          aria-label="Quay lại danh sách"
          data-testid="detail-back"
        >
          ←
        </button>
        <div style={{ flex: 1 }}>
          <h1 style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {p.name} <HealthChip health={p.health} />
          </h1>
          <div className="meta hint" style={{ display: "flex", gap: 14, marginTop: 6, flexWrap: "wrap" }}>
            <span>
              <Icon name="i-proj" /> {p.repo}
            </span>
            <span>{p.metrics.commits} commits</span>
            <span>{orDash(p.metrics.branch || null)}</span>
            <span>{orDash(p.metrics.lang)}</span>
            <span>cập nhật {relativeTime(p.last)}</span>
          </div>
        </div>
        <button
          className="btn accent"
          type="button"
          onClick={onRefresh}
          disabled={busy !== ""}
          data-testid="detail-refresh"
        >
          <Icon name="i-refresh" /> {busy === "refresh" ? "Đang chạy…" : "Chạy refresh"}
        </button>
        <button
          className="btn"
          type="button"
          onClick={onAbandon}
          disabled={busy !== ""}
          data-testid="detail-abandon"
        >
          <Icon name="i-grave" /> {busy === "abandon" ? "Đang chôn…" : "Đưa vào nghĩa địa"}
        </button>
      </div>

      {/* 4 core answers — what's the state, who uses it, what's next, how stale. */}
      <div className="grid g-4">
        <div className="stat" data-testid="detail-progress">
          <span className="sl">Tiến độ</span>
          <span className="sv acc">
            <ProgressBar value={p.progress} health={p.health} variant="block" />
          </span>
          <span className="sd faint">{orDash(p.desc)}</span>
        </div>
        <KpiCard
          label="Users thật"
          value={p.users}
          tone={p.users > 0 ? "pos" : "neg"}
          sub={p.users > 0 ? "đang dùng" : "chưa có ai dùng"}
        />
        <KpiCard label="Idle" value={idleDays(p.lastDays)} sub={`lần cuối ${relativeTime(p.last)}`} />
        <KpiCard label="Next" value={orDash(p.next)} sub="bước kế tiếp" />
      </div>

      {/* metrics row */}
      <div className="grid g-4">
        <KpiCard label="Commits" value={p.metrics.commits} />
        <KpiCard label="Branch" value={orDash(p.metrics.branch || null)} />
        <KpiCard label="Test pass" value={p.metrics.testPass != null ? `${p.metrics.testPass}%` : "—"} />
        <KpiCard label="Stars" value={p.metrics.stars != null ? p.metrics.stars : "—"} />
      </div>

      {/* routines + last automation */}
      <div className="panel">
        <div className="phead">
          <span className="kicker">Routine gắn với dự án</span>
          <span className="link" onClick={() => router.push("/routines")} style={{ marginLeft: "auto" }}>
            quản lý →
          </span>
        </div>
        <div style={{ padding: "12px 16px" }}>
          {p.routines.length > 0 ? (
            <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
              {p.routines.map((r) => (
                <span className="tagchip" key={r}>
                  {r}
                </span>
              ))}
            </div>
          ) : (
            <span className="hint">Chưa gắn routine nào.</span>
          )}
          <div className="hint" style={{ marginTop: 10 }} data-testid="detail-lastauto">
            Auto-refresh cuối: {p.lastAuto ? relativeTime(p.lastAuto) : "chưa chạy"}
          </div>
        </div>
      </div>
    </section>
  );
}
