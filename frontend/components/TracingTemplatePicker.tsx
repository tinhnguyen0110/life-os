"use client";
/* ============================================================
   TracingTemplatePicker (#109-FE) — a row of preset chips above the "Hoạt động mới"
   form. Click a template → onPick(it) PREFILLS the add form (id/name/goal/unit/emoji/
   color) so the user doesn't define a habit from scratch — they tweak + submit.

   Plus a LIGHT manage UI (toggle): edit (PUT) / add-new (PUT a new id) / delete (DELETE)
   a template · "Reset về mặc định" (POST reset, IN-PAGE confirm — NOT window.confirm,
   which blocks Chrome MCP) · bulk-select → bulk-delete (in-page confirm). source-tagged
   (seed vs user). render-safe: API error → honest empty + the add form still works.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getTracingTemplates, upsertTracingTemplate, deleteTracingTemplate,
  resetTracingTemplates, bulkDeleteTracingTemplates, ApiError,
} from "@/lib/api";
import type { TracingTemplate } from "@/lib/types";

type Status = "loading" | "error" | "ready";

/** what the picker hands back to prefill the add form. */
export interface TemplatePick {
  id: string; name: string; goal: string; unit: string; emoji: string; color: string;
}

const EMPTY_EDIT = { id: "", name: "", goal: "", unit: "", emoji: "", color: "#FF6A33" };

export function TracingTemplatePicker({ onPick }: { onPick: (t: TemplatePick) => void }) {
  const [templates, setTemplates] = useState<TracingTemplate[]>([]);
  const [status, setStatus] = useState<Status>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const [manage, setManage] = useState(false);
  const [editing, setEditing] = useState<typeof EMPTY_EDIT | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmBulk, setConfirmBulk] = useState(false);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getTracingTemplates();
        if (!alive) return;
        const list = res?.data?.templates;
        if (!Array.isArray(list)) { setErrMsg("phản hồi không hợp lệ"); setStatus("error"); return; }
        setTemplates(list);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [nonce]);

  function pick(t: TracingTemplate) {
    onPick({ id: t.id, name: t.name, goal: String(t.goal), unit: t.unit, emoji: t.emoji, color: t.color });
  }

  function startEdit(t: TracingTemplate) {
    setEditing({ id: t.id, name: t.name, goal: String(t.goal), unit: t.unit, emoji: t.emoji, color: t.color });
    setActionErr("");
  }
  function startNew() {
    setEditing({ ...EMPTY_EDIT });
    setActionErr("");
  }

  async function saveEdit() {
    if (!editing) return;
    const id = editing.id.trim();
    const goal = Number(editing.goal);
    if (!id || !editing.name.trim()) { setActionErr("Cần ID + Tên"); return; }
    if (!Number.isFinite(goal) || goal <= 0) { setActionErr("Mục tiêu phải > 0"); return; }
    setBusy(true); setActionErr("");
    try {
      await upsertTracingTemplate(id, { name: editing.name.trim(), goal, unit: editing.unit.trim(), emoji: editing.emoji.trim(), color: editing.color });
      setEditing(null);
      reload();
    } catch (e) {
      setActionErr(e instanceof ApiError ? (e.hint ? `${e.message} (${e.hint})` : e.message) : (e as Error).message);
    } finally { setBusy(false); }
  }

  async function removeOne(id: string) {
    setBusy(true); setActionErr("");
    try { await deleteTracingTemplate(id); reload(); }
    catch (e) { setActionErr(e instanceof ApiError ? e.message : (e as Error).message); }
    finally { setBusy(false); }
  }

  async function doReset() {
    setBusy(true); setActionErr("");
    try { await resetTracingTemplates(); setConfirmReset(false); setSelected(new Set()); reload(); }
    catch (e) { setActionErr(e instanceof ApiError ? e.message : (e as Error).message); }
    finally { setBusy(false); }
  }

  async function doBulkDelete() {
    if (selected.size === 0) return;
    setBusy(true); setActionErr("");
    try { await bulkDeleteTracingTemplates([...selected]); setConfirmBulk(false); setSelected(new Set()); reload(); }
    catch (e) { setActionErr(e instanceof ApiError ? e.message : (e as Error).message); }
    finally { setBusy(false); }
  }

  function toggleSel(id: string) {
    setSelected((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  // render-safe: an error never blocks the add form — show a tiny note + nothing else.
  if (status === "error") {
    return (
      <div className="hint faint" style={{ padding: "6px 2px" }} data-testid="tpl-error">
        Không tải được mẫu hoạt động ({errMsg}) — bạn vẫn có thể tạo thủ công bên dưới.
      </div>
    );
  }

  return (
    <div className="tpl-picker" data-testid="tpl-picker">
      <div className="row" style={{ alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span className="kicker">Mẫu có sẵn — bấm để điền nhanh</span>
        <span className="sp" style={{ flex: 1 }} />
        <button type="button" className="tab" onClick={() => setManage((m) => !m)} data-testid="tpl-manage-toggle">
          {manage ? "Xong" : "Quản lý"}
        </button>
      </div>

      {status === "loading" ? (
        <div className="hint faint" data-testid="tpl-loading">Đang tải mẫu…</div>
      ) : templates.length === 0 ? (
        <div className="hint faint" data-testid="tpl-empty">Chưa có mẫu nào — tạo thủ công bên dưới.</div>
      ) : (
        <div className="tpl-chips" data-testid="tpl-chips">
          {templates.map((t) => (
            <div className="tpl-chip-wrap" key={t.id} data-testid={`tpl-${t.id}`}>
              {manage && (
                <input type="checkbox" checked={selected.has(t.id)} onChange={() => toggleSel(t.id)} data-testid={`tpl-sel-${t.id}`} />
              )}
              <button
                type="button"
                className="tpl-chip"
                style={{ borderColor: t.color }}
                onClick={() => pick(t)}
                data-testid={`tpl-pick-${t.id}`}
                title={`${t.name} · ${t.goal} ${t.unit}`}
              >
                <span>{t.emoji}</span> {t.name}
                <span className="tpl-src" data-testid={`tpl-src-${t.id}`}>{t.source === "user" ? "★" : ""}</span>
              </button>
              {manage && (
                <>
                  <button type="button" className="tab sm" onClick={() => startEdit(t)} data-testid={`tpl-edit-${t.id}`}>✎</button>
                  <button type="button" className="tab sm" onClick={() => removeOne(t.id)} disabled={busy} data-testid={`tpl-del-${t.id}`}>✕</button>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {/* manage bar */}
      {manage && (
        <div className="tpl-manage" data-testid="tpl-manage" style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button type="button" className="tab" onClick={startNew} data-testid="tpl-new">+ Mẫu mới</button>

          {/* bulk delete (in-page confirm) */}
          {confirmBulk ? (
            <span className="row" style={{ gap: 6, alignItems: "center" }} data-testid="tpl-bulk-confirm">
              <span className="hint neg">Xóa {selected.size} mẫu?</span>
              <button type="button" className="tab sm" disabled={busy} onClick={doBulkDelete} data-testid="tpl-bulk-yes">Xác nhận</button>
              <button type="button" className="tab sm" onClick={() => setConfirmBulk(false)} data-testid="tpl-bulk-no">Hủy</button>
            </span>
          ) : (
            <button type="button" className="tab" disabled={selected.size === 0} onClick={() => setConfirmBulk(true)} data-testid="tpl-bulk-del">Xóa đã chọn ({selected.size})</button>
          )}

          {/* reset (in-page confirm) */}
          {confirmReset ? (
            <span className="row" style={{ gap: 6, alignItems: "center" }} data-testid="tpl-reset-confirm">
              <span className="hint neg">Về 8 mẫu mặc định?</span>
              <button type="button" className="tab sm" disabled={busy} onClick={doReset} data-testid="tpl-reset-yes">Xác nhận</button>
              <button type="button" className="tab sm" onClick={() => setConfirmReset(false)} data-testid="tpl-reset-no">Hủy</button>
            </span>
          ) : (
            <button type="button" className="tab" onClick={() => { setActionErr(""); setConfirmReset(true); }} data-testid="tpl-reset">Reset về mặc định</button>
          )}
        </div>
      )}

      {actionErr && <div className="hint neg" style={{ marginTop: 4 }} data-testid="tpl-action-err">⚠ {actionErr}</div>}

      {/* edit/new template mini-form */}
      {editing && (
        <div className="panel" style={{ padding: "10px 12px", marginTop: 8 }} data-testid="tpl-edit-form">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <input className="finput" placeholder="id" value={editing.id} onChange={(e) => setEditing({ ...editing, id: e.target.value })} data-testid="tpl-f-id" style={{ width: 100 }} />
            <input className="finput" placeholder="Tên" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} data-testid="tpl-f-name" />
            <input className="finput num" placeholder="mục tiêu" inputMode="decimal" value={editing.goal} onChange={(e) => setEditing({ ...editing, goal: e.target.value })} data-testid="tpl-f-goal" style={{ width: 80 }} />
            <input className="finput" placeholder="đơn vị" value={editing.unit} onChange={(e) => setEditing({ ...editing, unit: e.target.value })} data-testid="tpl-f-unit" style={{ width: 80 }} />
            <input className="finput" placeholder="emoji" value={editing.emoji} onChange={(e) => setEditing({ ...editing, emoji: e.target.value })} data-testid="tpl-f-emoji" style={{ width: 60 }} />
            <input className="finput" type="color" value={editing.color} onChange={(e) => setEditing({ ...editing, color: e.target.value })} data-testid="tpl-f-color" />
            <button type="button" className="btn sm acc" disabled={busy} onClick={saveEdit} data-testid="tpl-f-save">Lưu</button>
            <button type="button" className="btn sm" onClick={() => setEditing(null)} data-testid="tpl-f-cancel">Hủy</button>
          </div>
        </div>
      )}
    </div>
  );
}
