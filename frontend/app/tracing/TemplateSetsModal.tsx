"use client";
/* ============================================================
   TemplateSetsModal (#137-T2) — the template-SET modal. A "mẫu" = a saved LIST of rich
   activities (a reusable routine), NOT the rejected #109 1-word chips. The modal:
   • LIST view: all sets (name + member count + a member preview) · per-set Import (1-click)
     / Sửa (edit) / Xóa (delete) · "Tạo mẫu mới" · "Khôi phục mặc định" (reset).
   • EDIT view: rename + an editable member LIST (content + time HH:MM + reminder on/off +
     freq daily/weekdays + channel) + add/remove member → PUT (whole-set replace).
   1-click import → POST /import → the caller refetches GET /tracing (board updates) +
   a toast "đã thêm N việc". In-page (NO window.* — #72/#109 Chrome-MCP-safe). 422 → hint.
   Mirrors the FROZEN #137-T1 shape.
   ============================================================ */
import { useEffect, useState } from "react";
import {
  ApiError, getTemplateSets, createTemplateSet, updateTemplateSet, deleteTemplateSet,
  importTemplateSet, resetTemplateSets,
} from "@/lib/api";
import type { TemplateSet, TemplateMember, ReminderChannelOption, RemindRepeat, RemindChannel } from "@/lib/types";

function errText(e: unknown): string {
  if (e instanceof ApiError) return e.hint ? `${e.message} (${e.hint})` : e.message;
  return (e as Error).message;
}

/** a blank member (the add-member default). */
const BLANK_MEMBER: TemplateMember = { content: "", time: null, remindRepeat: "off", remindChannel: "in_app" };

type View = { kind: "list" } | { kind: "edit"; set: TemplateSet | null }; // set=null → create new

export function TemplateSetsModal({
  channels, onClose, onImported,
}: {
  channels: ReminderChannelOption[];
  onClose: () => void;
  /** called after a successful import with the created-count → the page refetches + toasts. */
  onImported: (created: number, skipped: string[]) => void;
}) {
  const [sets, setSets] = useState<TemplateSet[]>([]);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [errMsg, setErrMsg] = useState("");
  const [view, setView] = useState<View>({ kind: "list" });
  const [busy, setBusy] = useState<string | null>(null); // a set id, "__reset__", or "__save__"
  const [opErr, setOpErr] = useState("");

  async function load() {
    setStatus("loading"); setErrMsg("");
    try {
      const res = await getTemplateSets();
      setSets(res.data.sets ?? []);
      setStatus("ready");
    } catch (e) { setErrMsg(errText(e)); setStatus("error"); }
  }
  useEffect(() => { void load(); }, []);

  async function onImport(s: TemplateSet) {
    setOpErr(""); setBusy(s.id);
    try {
      const res = await importTemplateSet(s.id);
      onImported(res.data.created.length, res.data.skipped); // page refetches /tracing + toasts
    } catch (e) { setOpErr(errText(e)); } finally { setBusy(null); }
  }

  async function onDelete(s: TemplateSet) {
    setOpErr(""); setBusy(s.id);
    try { await deleteTemplateSet(s.id); await load(); } catch (e) { setOpErr(errText(e)); } finally { setBusy(null); }
  }

  async function onReset() {
    setOpErr(""); setBusy("__reset__");
    try { const res = await resetTemplateSets(); setSets(res.data.sets ?? []); setView({ kind: "list" }); }
    catch (e) { setOpErr(errText(e)); } finally { setBusy(null); }
  }

  // #137-T2 (UX) — click the BACKDROP (outside the box) closes; Escape closes too.
  // Only the LIST view closes on backdrop (the EDIT view stays so an in-progress edit
  // isn't lost by a stray click — Hủy/Đóng there are explicit).
  function onBackdrop(e: React.MouseEvent) {
    if (e.target === e.currentTarget && view.kind === "list") onClose();
  }
  useEffect(() => {
    function onKey(ev: KeyboardEvent) { if (ev.key === "Escape") { if (view.kind === "edit") setView({ kind: "list" }); else onClose(); } }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view.kind, onClose]);

  return (
    <div className="wex-move" data-testid="tpl-modal" role="dialog" aria-modal="true" aria-label="Mẫu hoạt động"
      onMouseDown={onBackdrop}>
      <div className="wex-move-box" style={{ minWidth: 420, maxWidth: 560, maxHeight: "80vh", overflow: "auto" }} onMouseDown={(e) => e.stopPropagation()}>
        {view.kind === "list" ? (
          <ListView
            sets={sets} status={status} errMsg={errMsg} busy={busy} opErr={opErr}
            onImport={onImport} onDelete={onDelete} onReset={onReset} onReload={load}
            onNew={() => setView({ kind: "edit", set: null })}
            onEdit={(s) => setView({ kind: "edit", set: s })}
            onClose={onClose}
          />
        ) : (
          <EditView
            initial={view.set} channels={channels}
            onCancel={() => setView({ kind: "list" })}
            onSaved={async () => { await load(); setView({ kind: "list" }); }}
            setBusy={setBusy} busy={busy}
          />
        )}
      </div>
    </div>
  );
}

/* ---- the LIST view ---- */
function ListView({
  sets, status, errMsg, busy, opErr, onImport, onDelete, onReset, onReload, onNew, onEdit, onClose,
}: {
  sets: TemplateSet[]; status: "loading" | "error" | "ready"; errMsg: string; busy: string | null; opErr: string;
  onImport: (s: TemplateSet) => void; onDelete: (s: TemplateSet) => void; onReset: () => void; onReload: () => void;
  onNew: () => void; onEdit: (s: TemplateSet) => void; onClose: () => void;
}) {
  return (
    <>
      <div className="row" style={{ alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span className="kicker">Mẫu hoạt động (bộ việc lưu sẵn)</span>
        <span className="sp" style={{ flex: 1 }} />
        <button className="btn sm accent" type="button" onClick={onNew} data-testid="tpl-set-new">+ Tạo mẫu</button>
      </div>

      {status === "loading" && <div className="hint faint" data-testid="tpl-set-loading">Đang tải mẫu…</div>}
      {status === "error" && (
        <div className="hint neg" data-testid="tpl-set-error">Không tải được mẫu: {errMsg}.
          <button className="btn sm" type="button" style={{ marginLeft: 8 }} onClick={onReload}>Thử lại</button>
        </div>
      )}
      {opErr && <div className="hint neg" style={{ marginBottom: 6 }} data-testid="tpl-set-op-error">⚠ {opErr}</div>}

      {status === "ready" && (
        sets.length === 0 ? (
          <div className="hint faint" data-testid="tpl-set-empty" style={{ padding: "16px 0" }}>
            Chưa có mẫu nào. Tạo một bộ việc lưu sẵn để nhập nhanh mỗi ngày.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }} data-testid="tpl-set-list">
            {sets.map((s) => (
              <div className="panel" key={s.id} style={{ padding: "10px 12px" }} data-testid={`tpl-set-${s.id}`}>
                <div className="row" style={{ alignItems: "center", gap: 8 }}>
                  <b data-testid={`tpl-set-name-${s.id}`}>{s.name}</b>
                  <span className="tagchip" data-testid={`tpl-set-count-${s.id}`}>{s.activities.length} việc</span>
                  <span className="sp" style={{ flex: 1 }} />
                  <button className="btn sm accent" type="button" disabled={busy === s.id} onClick={() => onImport(s)} data-testid={`tpl-set-import-${s.id}`}>
                    {busy === s.id ? "…" : "Nhập vào hôm nay"}
                  </button>
                  <button className="btn sm" type="button" onClick={() => onEdit(s)} data-testid={`tpl-set-edit-${s.id}`}>Sửa</button>
                  <button className="btn sm ghost" type="button" disabled={busy === s.id} onClick={() => onDelete(s)} data-testid={`tpl-set-delete-${s.id}`} title="Xóa mẫu">✕</button>
                </div>
                {/* member preview (the rich list — content + time, honest) */}
                <div className="hint faint" style={{ marginTop: 4, fontFamily: "var(--mono)", fontSize: 10.5 }} data-testid={`tpl-set-preview-${s.id}`}>
                  {s.activities.length === 0 ? "(trống)" : s.activities.map((m) => `${m.time ? m.time + " " : ""}${m.content}`).join(" · ")}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      <div className="row" style={{ gap: 7, justifyContent: "space-between", marginTop: 12 }}>
        <button className="btn sm" type="button" disabled={busy === "__reset__"} onClick={onReset} data-testid="tpl-set-reset">
          {busy === "__reset__" ? "…" : "↺ Khôi phục mặc định"}
        </button>
        <button className="btn sm ghost" type="button" onClick={onClose} data-testid="tpl-modal-close">Đóng</button>
      </div>
    </>
  );
}

/* ---- the EDIT view (create / rename + member list) ---- */
function EditView({
  initial, channels, onCancel, onSaved, setBusy, busy,
}: {
  initial: TemplateSet | null; channels: ReminderChannelOption[];
  onCancel: () => void; onSaved: () => void; setBusy: (v: string | null) => void; busy: string | null;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [members, setMembers] = useState<TemplateMember[]>(initial ? initial.activities.map((m) => ({ ...m })) : [{ ...BLANK_MEMBER }]);
  const [err, setErr] = useState("");
  const saving = busy === "__save__";

  function setMember(i: number, patch: Partial<TemplateMember>) {
    setMembers((ms) => ms.map((m, idx) => (idx === i ? { ...m, ...patch } : m)));
  }
  function addMember() { setMembers((ms) => [...ms, { ...BLANK_MEMBER }]); }
  function removeMember(i: number) { setMembers((ms) => ms.filter((_, idx) => idx !== i)); }

  async function save() {
    setErr("");
    if (!name.trim()) { setErr("Nhập tên mẫu."); return; }
    const cleaned = members.filter((m) => m.content.trim()).map((m) => ({ ...m, content: m.content.trim() }));
    if (cleaned.length === 0) { setErr("Mẫu cần ít nhất 1 việc."); return; }
    const body = { name: name.trim(), activities: cleaned };
    setBusy("__save__");
    try {
      if (initial) await updateTemplateSet(initial.id, body); else await createTemplateSet(body);
      onSaved();
    } catch (e) { setErr(errText(e)); } finally { setBusy(null); }
  }

  return (
    <div data-testid="tpl-edit">
      <div className="kicker" style={{ marginBottom: 8 }}>{initial ? `Sửa mẫu "${initial.name}"` : "Tạo mẫu mới"}</div>
      <input className="wex-move-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên mẫu (vd: Buổi sáng)"
        data-testid="tpl-edit-name" style={{ marginBottom: 10 }} maxLength={80} autoFocus />

      <div className="kicker faint" style={{ fontSize: 10, marginBottom: 4 }}>Các việc trong mẫu</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }} data-testid="tpl-edit-members">
        {members.map((m, i) => (
          <div className="panel" key={i} style={{ padding: "8px 10px", background: "var(--bg-2)" }} data-testid={`tpl-member-${i}`}>
            <div className="row" style={{ gap: 6, alignItems: "center" }}>
              <input className="finput" style={{ flex: 1 }} value={m.content} onChange={(e) => setMember(i, { content: e.target.value })}
                placeholder="Tên việc (vd: Uống nước)" data-testid={`tpl-member-content-${i}`} maxLength={120} />
              <input className="finput num" type="time" style={{ width: 110 }} value={m.time ?? ""}
                onChange={(e) => setMember(i, { time: e.target.value || null })} data-testid={`tpl-member-time-${i}`} aria-label="Giờ" />
              <button type="button" className="btn sm ghost" onClick={() => removeMember(i)} data-testid={`tpl-member-remove-${i}`} title="Bỏ việc này">✕</button>
            </div>
            {/* the member's reminder: on/off + freq + channel (reuses the daily/weekdays + channel model) */}
            <div className="row" style={{ gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 6 }}>
              <button type="button" className={`tab${m.remindRepeat !== "off" ? " on" : ""}`}
                onClick={() => setMember(i, { remindRepeat: m.remindRepeat === "off" ? "daily" : "off" })}
                data-testid={`tpl-member-remind-toggle-${i}`} aria-pressed={m.remindRepeat !== "off"}>
                🔔 {m.remindRepeat !== "off" ? "Bật" : "Nhắc"}
              </button>
              {m.remindRepeat !== "off" && (
                <>
                  <select className="finput" style={{ width: 140 }} value={m.remindRepeat}
                    onChange={(e) => setMember(i, { remindRepeat: e.target.value as RemindRepeat })} data-testid={`tpl-member-freq-${i}`} aria-label="Lặp lại">
                    <option value="daily">Hằng ngày</option>
                    <option value="weekdays">Ngày thường (T2–T6)</option>
                  </select>
                  <select className="finput" style={{ width: 130 }} value={m.remindChannel}
                    onChange={(e) => setMember(i, { remindChannel: e.target.value as RemindChannel })} data-testid={`tpl-member-channel-${i}`} aria-label="Kênh">
                    {channels.map((c) => (
                      <option key={c.id} value={c.id} disabled={!c.available}>{c.label}{c.available ? "" : " (chưa cấu hình)"}</option>
                    ))}
                  </select>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
      <button type="button" className="btn sm" onClick={addMember} data-testid="tpl-member-add" style={{ marginTop: 8 }}>+ Thêm việc</button>

      {err && <div className="hint neg" style={{ marginTop: 8 }} data-testid="tpl-edit-error">⚠ {err}</div>}
      <div className="row" style={{ gap: 7, justifyContent: "flex-end", marginTop: 12 }}>
        <button type="button" className="btn sm ghost" onClick={onCancel} disabled={saving}>Hủy</button>
        <button type="button" className="btn sm accent" onClick={save} disabled={saving} data-testid="tpl-edit-save">
          {saving ? "Đang lưu…" : "Lưu mẫu"}
        </button>
      </div>
    </div>
  );
}
