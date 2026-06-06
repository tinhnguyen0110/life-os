"use client";
/* ============================================================
   S10 — Ghi chú (Notes). Ported from mock screens-system.js SCREENS.notes.
   First WRITE screen: create / edit / delete / pin via useNotes (refetch-after-
   write, FAIL-CLOSED — a failed mutation surfaces an error, never silently loses
   the note or shows it as saved). Client-side search + multi-tag filter over the
   fetched list (render-only display; pinned/updatedAt are backend values).
   ⚠️ Consumes loose placeholder types from useNotes — swapped for the frozen
   notes/schema.py mirror when it lands. States: loading · error · empty · data.
   ============================================================ */
import { useMemo, useState } from "react";
import { useNotes, type Note, type Attach, type AttachType } from "@/lib/useNotes";
import { NoteCard } from "@/components/shared/NoteCard";
import { apiBase, ApiError } from "@/lib/api";
import { Icon } from "@/lib/icons";

/** Form state always has title/body/tags/pinned defined (the inputs are controlled);
 *  NoteInput's optional body/tags are filled here, so the form never deals with undefined. */
type FormInput = { title: string; body: string; tags: string[]; pinned: boolean; attach: Attach };
type Editing = { id: string | null; input: FormInput } | null;

const EMPTY_INPUT: FormInput = { title: "", body: "", tags: [], pinned: false, attach: { type: "none", ref: null } };

export default function NotesPage() {
  const { notes, status, errMsg, warning, reload, createNote, updateNote, deleteNote, togglePin } =
    useNotes();

  const [search, setSearch] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [formErr, setFormErr] = useState(""); // fail-closed: write errors surface here

  const allTags = useMemo(() => {
    const s = new Set<string>();
    notes.forEach((n) => (n.tags ?? []).forEach((t) => s.add(t)));
    return [...s].sort();
  }, [notes]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return notes.filter((n) => {
      const matchesQ =
        !q || n.title.toLowerCase().includes(q) || n.body.toLowerCase().includes(q);
      const matchesTag = !activeTag || (n.tags ?? []).includes(activeTag);
      return matchesQ && matchesTag;
    });
  }, [notes, search, activeTag]);

  const pinned = filtered.filter((n) => n.pinned);
  const rest = filtered.filter((n) => !n.pinned);

  function openNew() {
    setFormErr("");
    setEditing({ id: null, input: { ...EMPTY_INPUT } });
  }
  function openEdit(n: Note) {
    setFormErr("");
    setEditing({
      id: n.id,
      input: { title: n.title, body: n.body, tags: n.tags ?? [], pinned: n.pinned, attach: n.attach ?? { type: "none", ref: null } },
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setFormErr("");
    if (!editing.input.title.trim() && !editing.input.body.trim()) {
      setFormErr("Cần ít nhất tiêu đề hoặc nội dung.");
      return;
    }
    // mirror backend validator: ref required when attach.type != none.
    if (editing.input.attach.type !== "none" && !(editing.input.attach.ref ?? "").trim()) {
      setFormErr("Cần nhập ref khi gắn với dự án/kênh.");
      return;
    }
    setFormBusy(true);
    try {
      if (editing.id) await updateNote(editing.id, editing.input);
      else await createNote(editing.input);
      setEditing(null); // close only on SUCCESS (fail-closed)
    } catch (err) {
      // fail-closed: keep the form open + show the error; the note is NOT saved.
      setFormErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setFormBusy(false);
    }
  }

  async function onDelete(n: Note) {
    setFormErr("");
    try {
      await deleteNote(n.id);
    } catch (err) {
      setFormErr(`Xóa thất bại: ${err instanceof ApiError ? err.message : (err as Error).message}`);
    }
  }

  return (
    <section className="view" data-screen="S10" data-testid="notes-screen">
      <div className="vtitle">
        <h1>Ghi chú</h1>
        <span className="sub">
          {notes.length} note · {notes.filter((n) => n.pinned).length} ghim
        </span>
        <span className="sp" />
        <div className="pill" style={{ cursor: "text" }}>
          <Icon name="i-note" />
          <input
            style={{ background: "transparent", border: 0, color: "inherit", fontFamily: "var(--mono)", outline: "none", width: 140 }}
            placeholder="tìm note…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="notes-search"
          />
        </div>
        <button className="btn accent" type="button" onClick={openNew} data-testid="note-new">
          <Icon name="i-note" /> Note mới
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="notes-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {/* Write-error bar — surfaces delete/write failures even when the form is
          CLOSED (fail-closed: an error must never be invisible). The form shows
          its own copy when open; this catches errors from row-level actions. */}
      {formErr && !editing && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="notes-write-error">
          <span className="hint neg">⚠ {formErr}</span>
          <span className="link" style={{ marginLeft: 10 }} onClick={() => setFormErr("")}>đóng</span>
        </div>
      )}

      {allTags.length > 0 && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }} data-testid="notes-tagfilter">
          <span
            className={`tab${activeTag === null ? " on" : ""}`}
            onClick={() => setActiveTag(null)}
            role="button"
            tabIndex={0}
          >
            Tất cả
          </span>
          {allTags.map((t) => (
            <span
              key={t}
              className={`tab${activeTag === t ? " on" : ""}`}
              onClick={() => setActiveTag(activeTag === t ? null : t)}
              role="button"
              tabIndex={0}
              data-testid={`tagfilter-${t}`}
            >
              {t}
            </span>
          ))}
        </div>
      )}

      {editing && (
        <div className="panel" data-testid="note-form">
          <div className="phead">
            <span className="kicker">{editing.id ? "Sửa note" : "Note mới"}</span>
          </div>
          <form onSubmit={onSubmit} style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
            <input
              className="tab"
              style={{ fontFamily: "var(--sans)" }}
              placeholder="Tiêu đề"
              value={editing.input.title}
              onChange={(e) => setEditing({ ...editing, input: { ...editing.input, title: e.target.value } })}
              data-testid="form-title"
            />
            <textarea
              className="tab"
              style={{ fontFamily: "var(--sans)", minHeight: 80, resize: "vertical" }}
              placeholder="Nội dung"
              value={editing.input.body}
              onChange={(e) => setEditing({ ...editing, input: { ...editing.input, body: e.target.value } })}
              data-testid="form-body"
            />
            <input
              className="tab"
              style={{ fontFamily: "var(--mono)" }}
              placeholder="Tags (phân cách bởi dấu phẩy)"
              value={editing.input.tags.join(", ")}
              onChange={(e) =>
                setEditing({
                  ...editing,
                  input: { ...editing.input, tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) },
                })
              }
              data-testid="form-tags"
            />
            <label className="hint" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="checkbox"
                checked={!!editing.input.pinned}
                onChange={(e) => setEditing({ ...editing, input: { ...editing.input, pinned: e.target.checked } })}
                data-testid="form-pinned"
              />
              Ghim note này
            </label>
            {/* Attach picker: project | channel | none (+ ref). ref required when type≠none. */}
            <div className="row" style={{ gap: 8, alignItems: "center" }}>
              <span className="hint" style={{ minWidth: 56 }}>Gắn với</span>
              <select
                className="tab"
                value={editing.input.attach.type}
                onChange={(e) => {
                  const type = e.target.value as AttachType;
                  setEditing({
                    ...editing,
                    input: { ...editing.input, attach: { type, ref: type === "none" ? null : editing.input.attach.ref ?? "" } },
                  });
                }}
                data-testid="form-attach-type"
              >
                <option value="none">— không —</option>
                <option value="project">Dự án</option>
                <option value="channel">Kênh TC</option>
              </select>
              {editing.input.attach.type !== "none" && (
                <input
                  className="tab"
                  style={{ flex: 1, fontFamily: "var(--mono)" }}
                  placeholder={editing.input.attach.type === "project" ? "project id" : "channel (crypto/etf/vn)"}
                  value={editing.input.attach.ref ?? ""}
                  onChange={(e) =>
                    setEditing({ ...editing, input: { ...editing.input, attach: { ...editing.input.attach, ref: e.target.value } } })
                  }
                  data-testid="form-attach-ref"
                />
              )}
            </div>
            {formErr && <span className="hint neg" data-testid="form-error">{formErr}</span>}
            <div className="row" style={{ gap: 8 }}>
              <button className="btn accent" type="submit" disabled={formBusy} data-testid="form-submit">
                {formBusy ? "Đang lưu…" : editing.id ? "Lưu" : "Tạo"}
              </button>
              <button className="btn" type="button" onClick={() => setEditing(null)} disabled={formBusy}>
                Hủy
              </button>
            </div>
          </form>
        </div>
      )}

      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="notes-loading">
          Đang tải ghi chú…
        </div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="notes-error">
          Không tải được ghi chú: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>
            Thử lại
          </button>
        </div>
      )}

      {status === "ready" && (
        <>
          {filtered.length === 0 && (
            <div className="hint" style={{ padding: "24px 4px" }} data-testid="notes-empty">
              {notes.length === 0 ? "Chưa có ghi chú nào." : "Không có note khớp bộ lọc."}
            </div>
          )}

          {pinned.length > 0 && (
            <div>
              <div className="kicker" style={{ marginBottom: 10 }}>📌 Đã ghim</div>
              <div className="grid g-2" style={{ alignItems: "start" }} data-testid="notes-pinned">
                {pinned.map((n) => (
                  <NoteCard key={n.id} note={n} onEdit={openEdit} onDelete={onDelete} onTogglePin={togglePin} />
                ))}
              </div>
            </div>
          )}

          {rest.length > 0 && (
            <div>
              <div className="kicker" style={{ margin: "6px 0 10px" }}>Tất cả</div>
              <div style={{ columns: 3, columnGap: 14 }} data-testid="notes-all">
                {rest.map((n) => (
                  <div key={n.id} style={{ marginBottom: 14, breakInside: "avoid" }}>
                    <NoteCard note={n} onEdit={openEdit} onDelete={onDelete} onTogglePin={togglePin} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
