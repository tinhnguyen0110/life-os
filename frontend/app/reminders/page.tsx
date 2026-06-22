"use client";
/* ============================================================
   /reminders (#31 · GAP-4) — the user-facing reminder/agenda screen. The user
   SEES + manages reminders here (not just via API/Discord/brief). Closes GAP-4
   end-to-end ("what's on my plate this week").

   No reminders panel in the mock (post-mock module) → reuses the established
   journal/list+form tokens (port, NOT redesign): .view/.vtitle/.tabs/.panel/
   .field/.btn. RENDER-ONLY: the backend computes `overdue` (un-done AND
   past-due) → it drives the RED row, NOT an FE date-compare. Writes FAIL-CLOSED
   (a 422 surfaces visibly; no optimistic mutation).

   Filters: today/week/undone are SERVER filters; "Done" is a render-only client
   view (done_at != null over a fetched `all`) — there is no server `done` filter.
   Display order: overdue → today → week → later → done (de-emphasized).
   ============================================================ */
import { useMemo, useState } from "react";
import { useReminders, type ReminderTab } from "@/lib/useReminders";
import { LoadErrorShell } from "@/components/LoadErrorShell";
import { fmtDueAt, fmtDateTime, orDash } from "@/lib/format";
import { apiBase, ApiError } from "@/lib/api";
import type { Reminder, ReminderInput, ReminderRepeat } from "@/lib/types";

const TABS: { key: ReminderTab; label: string }[] = [
  { key: "undone", label: "Chưa xong" },
  { key: "today", label: "Hôm nay" },
  { key: "week", label: "Tuần này" },
  { key: "done", label: "Đã xong" },
  { key: "all", label: "Tất cả" },
];

type CreateForm = {
  title: string;
  note: string;
  due_at: string; // <input type="datetime-local"> value (local, no tz)
  repeat: ReminderRepeat;
  re_notify_every: string;
  max_times: string;
};

const EMPTY_CREATE: CreateForm = {
  title: "",
  note: "",
  due_at: "",
  repeat: "once",
  re_notify_every: "",
  max_times: "3",
};

/** Display order rank: overdue (0) → undone-soonest-by-due → done (last). Lower = higher. */
function sortKey(r: Reminder): [number, number] {
  if (r.done_at) return [2, Date.parse(r.done_at) || 0]; // done last
  if (r.overdue) return [0, Date.parse(r.due_at) || 0]; // overdue first
  return [1, Date.parse(r.due_at) || 0]; // upcoming, soonest first
}

export default function RemindersPage() {
  const { data, status, errMsg, warning, tab, setTab, reload, create, tick, remove } =
    useReminders("undone");
  const [creating, setCreating] = useState<CreateForm | null>(null);
  const [busy, setBusy] = useState(false);
  const [actBusyId, setActBusyId] = useState<number | null>(null);
  const [formErr, setFormErr] = useState("");
  const [rowErr, setRowErr] = useState("");

  const reminders = data.reminders ?? [];

  // "Done" is a client-only view over the fetched `all`; the other tabs already
  // come server-filtered. The Done tab sorts done_at DESC (most-recently-completed
  // first → a "recently done" review view, team-lead refinement); the other tabs
  // keep the overdue→upcoming→done order (sortKey, ascending by due_at).
  const visible = useMemo(() => {
    if (tab === "done") {
      return reminders
        .filter((r) => r.done_at != null)
        .sort((a, b) => (Date.parse(b.done_at ?? "") || 0) - (Date.parse(a.done_at ?? "") || 0));
    }
    return [...reminders].sort((a, b) => {
      const [ra, sa] = sortKey(a);
      const [rb, sb] = sortKey(b);
      return ra !== rb ? ra - rb : sa - sb;
    });
  }, [reminders, tab]);

  const overdueCount = useMemo(() => reminders.filter((r) => r.overdue).length, [reminders]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!creating) return;
    setFormErr("");
    if (!creating.title.trim()) {
      setFormErr("Cần tiêu đề nhắc nhở.");
      return;
    }
    if (!creating.due_at.trim()) {
      setFormErr("Cần thời điểm tới hạn (due).");
      return;
    }
    const reNotify = creating.re_notify_every.trim() === "" ? null : Number(creating.re_notify_every);
    if (reNotify != null && (!Number.isInteger(reNotify) || reNotify < 1)) {
      setFormErr("Nhắc lại mỗi (phút) phải là số nguyên ≥ 1.");
      return;
    }
    const maxTimes = creating.max_times.trim() === "" ? null : Number(creating.max_times);
    if (maxTimes != null && (!Number.isInteger(maxTimes) || maxTimes < 1)) {
      setFormErr("Số lần báo tối đa phải là số nguyên ≥ 1.");
      return;
    }
    // datetime-local gives "2026-06-21T09:00" (no tz). Send as-is — backend assumes
    // UTC for a naive value (REMINDERS-1A). Round-trip echoes +00:00.
    const body: ReminderInput = {
      title: creating.title.trim(),
      note: creating.note.trim() || null,
      due_at: creating.due_at,
      repeat: creating.repeat,
      re_notify_every: reNotify,
      max_times: maxTimes,
    };
    setBusy(true);
    try {
      await create(body);
      setCreating(null);
    } catch (err) {
      setFormErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onTick(id: number) {
    setRowErr("");
    setActBusyId(id);
    try {
      await tick(id);
    } catch (err) {
      setRowErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setActBusyId(null);
    }
  }

  async function onDelete(id: number) {
    setRowErr("");
    setActBusyId(id);
    try {
      await remove(id);
    } catch (err) {
      setRowErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setActBusyId(null);
    }
  }

  return (
    <section className="view" data-screen="reminders" data-testid="reminders-screen">
      <div className="vtitle">
        <h1>Nhắc nhở</h1>
        <span className="sub">
          {data.undoneCount} chưa xong
          {overdueCount > 0 ? <span className="neg"> · {overdueCount} quá hạn</span> : null} · điều gì
          cần làm tuần này
        </span>
        <span className="sp" />
        <div className="tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`tab${tab === t.key ? " on" : ""}`}
              onClick={() => setTab(t.key)}
              data-testid={`tab-${t.key}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button
          className="btn accent"
          type="button"
          onClick={() => {
            setCreating({ ...EMPTY_CREATE });
            setFormErr("");
          }}
          data-testid="reminder-new"
        >
          + Nhắc nhở
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="reminders-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {/* Create form */}
      {creating && (
        <div className="panel" data-testid="reminder-create-form">
          <div className="phead">
            <span className="kicker">Nhắc nhở mới</span>
          </div>
          <form
            onSubmit={onCreate}
            style={{ padding: "12px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}
          >
            <div className="field" style={{ gridColumn: "1 / 3" }}>
              <span className="flabel">Tiêu đề</span>
              <input
                className="finput"
                placeholder="Vd: Nộp báo cáo thuế quý"
                value={creating.title}
                onChange={(e) => setCreating({ ...creating, title: e.target.value })}
                data-testid="c-title"
              />
            </div>
            <div className="field">
              <span className="flabel">Tới hạn (due)</span>
              <input
                className="finput"
                type="datetime-local"
                value={creating.due_at}
                onChange={(e) => setCreating({ ...creating, due_at: e.target.value })}
                data-testid="c-due"
              />
            </div>
            <div className="field">
              <span className="flabel">Lặp lại</span>
              <select
                className="finput"
                value={creating.repeat}
                onChange={(e) => setCreating({ ...creating, repeat: e.target.value as ReminderRepeat })}
                data-testid="c-repeat"
              >
                <option value="once">Một lần</option>
                <option value="daily">Hằng ngày</option>
                <option value="weekly">Hằng tuần</option>
              </select>
            </div>
            <div className="field">
              <span className="flabel">Nhắc lại mỗi (phút)</span>
              <input
                className="finput num"
                inputMode="numeric"
                placeholder="vd 30 (để trống = 1 lần)"
                value={creating.re_notify_every}
                onChange={(e) => setCreating({ ...creating, re_notify_every: e.target.value })}
                data-testid="c-renotify"
              />
            </div>
            <div className="field">
              <span className="flabel">Số lần báo tối đa</span>
              <input
                className="finput num"
                inputMode="numeric"
                placeholder="vd 3"
                value={creating.max_times}
                onChange={(e) => setCreating({ ...creating, max_times: e.target.value })}
                data-testid="c-maxtimes"
              />
            </div>
            <div className="field" style={{ gridColumn: "1 / 3" }}>
              <span className="flabel">Ghi chú (tùy chọn)</span>
              <input
                className="finput"
                placeholder="Chi tiết thêm…"
                value={creating.note}
                onChange={(e) => setCreating({ ...creating, note: e.target.value })}
                data-testid="c-note"
              />
            </div>
            {formErr && (
              <span className="hint neg" style={{ gridColumn: "1 / 3" }} data-testid="create-error">
                {formErr}
              </span>
            )}
            <div className="row" style={{ gap: 8, gridColumn: "1 / 3" }}>
              <button className="btn accent" type="submit" disabled={busy} data-testid="c-submit">
                {busy ? "Đang lưu…" : "Tạo nhắc nhở"}
              </button>
              <button className="btn" type="button" onClick={() => setCreating(null)} disabled={busy}>
                Hủy
              </button>
            </div>
          </form>
        </div>
      )}

      {/* #138-P1a-rollout — the inline loading/error hints → the shared <LoadErrorShell>
          WITHOUT a section wrapper (renders the bare hint div in-place, like the original
          two `&&` blocks). On "ready" it renders nothing (children=null); the body below
          stays gated on `status === "ready"`. Copy/testids preserved verbatim. */}
      <LoadErrorShell
        status={status}
        loadingTestid="reminders-loading"
        loadingLabel="Đang tải nhắc nhở…"
        errorTestid="reminders-error"
        errorLabel={<>Không tải được nhắc nhở: {errMsg}. Kiểm tra backend ({apiBase}).</>}
        reload={reload}
      >
        {null}
      </LoadErrorShell>

      {status === "ready" && (
        <div className="panel" style={{ overflow: "hidden" }} data-testid="reminders-list">
          <div className="phead">
            <span className="kicker">{TABS.find((t) => t.key === tab)?.label ?? "Nhắc nhở"}</span>
            <span className="hint" style={{ marginLeft: "auto" }}>
              {visible.length} mục
            </span>
          </div>

          {rowErr && (
            <div style={{ padding: "8px 16px" }}>
              <span className="hint neg" data-testid="row-error">
                ⚠ {rowErr}
              </span>
            </div>
          )}

          {visible.length === 0 ? (
            <div className="hint" style={{ padding: "22px 16px" }} data-testid="reminders-empty">
              {tab === "done" ? "Chưa có nhắc nhở nào hoàn thành." : "Không có nhắc nhở nào ở đây."}
            </div>
          ) : (
            visible.map((r) => {
              const done = r.done_at != null;
              const cls = `rem-row${r.overdue ? " overdue" : ""}${done ? " done" : ""}`;
              return (
                <div className={cls} key={r.id} data-testid={`rem-${r.id}`} data-overdue={r.overdue}>
                  <div className="rem-main">
                    <span className="rem-title" data-testid={`rem-title-${r.id}`}>
                      {r.title}
                    </span>
                    {r.note && <span className="rem-note">{r.note}</span>}
                    <div className="rem-meta">
                      <span className="rem-due" data-testid={`rem-due-${r.id}`} title={fmtDateTime(r.due_at)}>
                        {r.overdue ? "⚠ quá hạn " : "⏰ "}
                        {fmtDueAt(r.due_at)} · {fmtDateTime(r.due_at)}
                      </span>
                      {r.repeat !== "once" && (
                        <span className="tagchip">{r.repeat === "daily" ? "hằng ngày" : "hằng tuần"}</span>
                      )}
                      {/* #75: "from habit" badge ONLY when source="tracing". manual/absent
                          → NO badge (honest — don't badge a manual reminder). Defensive
                          against the not-yet-built BE field (undefined → no badge). */}
                      {r.source === "tracing" && (
                        <span className="tagchip acc" data-testid={`rem-source-${r.id}`} title={r.activity_id ? `Từ thói quen: ${r.activity_id}` : "Tự động từ một thói quen"}>
                          📿 từ thói quen
                        </span>
                      )}
                      {r.re_notify_every != null && (
                        <span className="faint">↻ {r.re_notify_every}′</span>
                      )}
                      {done && (
                        <span className="pos" data-testid={`rem-doneat-${r.id}`}>
                          ✓ xong {orDash(fmtDateTime(r.done_at))}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="rem-acts">
                    {!done ? (
                      <button
                        className="btn sm accent"
                        type="button"
                        disabled={actBusyId === r.id}
                        onClick={() => onTick(r.id)}
                        data-testid={`tick-${r.id}`}
                      >
                        {actBusyId === r.id ? "…" : "✓ Xong"}
                      </button>
                    ) : (
                      <span className="badge g" data-testid={`done-badge-${r.id}`}>
                        Hoàn thành
                      </span>
                    )}
                    <button
                      className="btn sm ghost"
                      type="button"
                      disabled={actBusyId === r.id}
                      onClick={() => onDelete(r.id)}
                      data-testid={`del-${r.id}`}
                      title="Xóa"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </section>
  );
}
