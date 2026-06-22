"use client";
/* ============================================================
   Career · Demo tab (extracted from page.tsx, #138-P2 — pure MOVE, no logic change).
   Live-demo / flagship showcase, CRUD. demoFormToInput + the DemoForm type +
   EMPTY_DEMO + DEMO_STATUS_CLS live here (DemoTab is their only consumer).
   ============================================================ */
import { useState } from "react";
import { useCareer } from "@/lib/useCareer";
import { Field, TextInput, Select } from "@/components/shared/Field";
import { Icon } from "@/lib/icons";
import { ApiError } from "@/lib/api";
import type { DemoItem, DemoInput } from "@/lib/types";

type DemoForm = {
  name: string; tagline: string; desc: string; status: string;
  url: string; repo: string; tags: string; loc: string;
};
const EMPTY_DEMO: DemoForm = { name: "", tagline: "", desc: "", status: "live", url: "", repo: "", tags: "", loc: "" };

function demoFormToInput(f: DemoForm): DemoInput {
  return {
    name: f.name.trim(),
    tagline: f.tagline.trim(),
    desc: f.desc.trim(),
    status: (f.status as DemoInput["status"]),
    url: f.url.trim() || null,
    repo: f.repo.trim() || null,
    tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean),
    loc: f.loc.trim() ? Number(f.loc) : null,
  };
}

const DEMO_STATUS_CLS: Record<string, string> = { live: "g", wip: "a", offline: "r" };

export function DemoTab({ career }: { career: ReturnType<typeof useCareer> }) {
  const { demo, createDemo, updateDemo, deleteDemo } = career;
  const [editingId, setEditingId] = useState<string | null | undefined>(undefined);
  const [form, setForm] = useState<DemoForm>(EMPTY_DEMO);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");

  function openNew() { setFormErr(""); setForm(EMPTY_DEMO); setEditingId(null); }
  function openEdit(d: DemoItem) {
    setFormErr("");
    setForm({
      name: d.name, tagline: d.tagline, desc: d.desc, status: d.status,
      url: d.url ?? "", repo: d.repo ?? "", tags: d.tags.join(", "),
      loc: d.loc != null ? String(d.loc) : "",
    });
    setEditingId(d.id);
  }

  async function onSubmit() {
    if (!form.name.trim()) { setFormErr("Cần tên demo."); return; }
    setFormErr(""); setBusy(true);
    try {
      const input = demoFormToInput(form);
      if (editingId) await updateDemo(editingId, input);
      else await createDemo(input);
      setEditingId(undefined);
    } catch (e) {
      setFormErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally { setBusy(false); }
  }

  async function onDelete(d: DemoItem) {
    setFormErr("");
    try { await deleteDemo(d.id); }
    catch (e) { setFormErr(`Xóa thất bại: ${e instanceof ApiError ? e.message : (e as Error).message}`); }
  }

  return (
    <div data-testid="demo-tab">
      <div className="row" style={{ alignItems: "center", marginBottom: 10 }}>
        <span className="hint mid">{demo.length} demo · {demo.filter((d) => d.status === "live").length} live</span>
        <span className="sp" />
        <button className="btn accent" type="button" onClick={openNew} data-testid="demo-new"><Icon name="i-plus" /> Demo mới</button>
      </div>

      {formErr && editingId === undefined && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="demo-write-error">
          <span className="hint neg">⚠ {formErr}</span>
          <span className="link" style={{ marginLeft: 10 }} onClick={() => setFormErr("")}>đóng</span>
        </div>
      )}

      {editingId !== undefined && (
        <div className="panel" data-testid="demo-form">
          <div className="phead"><span className="kicker">{editingId ? "Sửa demo" : "Demo mới"}</span></div>
          <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
            <Field label="Tên" testId="demo-f-name"><TextInput value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="demo-i-name" /></Field>
            <Field label="Tagline" testId="demo-f-tagline"><TextInput value={form.tagline} onChange={(v) => setForm({ ...form, tagline: v })} testId="demo-i-tagline" /></Field>
            <Field label="Mô tả" testId="demo-f-desc">
              <textarea className="finput" style={{ minHeight: 80, resize: "vertical" }} value={form.desc} onChange={(e) => setForm({ ...form, desc: e.target.value })} data-testid="demo-i-desc" />
            </Field>
            <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
              <Field label="Trạng thái" testId="demo-f-status">
                <Select value={form.status} onChange={(v) => setForm({ ...form, status: v })} options={[{ value: "live", label: "Live" }, { value: "wip", label: "WIP" }, { value: "offline", label: "Offline" }]} testId="demo-i-status" />
              </Field>
              <Field label="LOC (xấp xỉ)" testId="demo-f-loc"><TextInput value={form.loc} onChange={(v) => setForm({ ...form, loc: v })} testId="demo-i-loc" /></Field>
            </div>
            <Field label="URL demo" testId="demo-f-url"><TextInput value={form.url} onChange={(v) => setForm({ ...form, url: v })} placeholder="https://demo.tinhdev.com/…" testId="demo-i-url" /></Field>
            <Field label="Repo (tùy chọn)" testId="demo-f-repo"><TextInput value={form.repo} onChange={(v) => setForm({ ...form, repo: v })} testId="demo-i-repo" /></Field>
            <Field label="Tags (phân cách dấu phẩy)" testId="demo-f-tags"><TextInput value={form.tags} onChange={(v) => setForm({ ...form, tags: v })} testId="demo-i-tags" /></Field>
            {formErr && <span className="hint neg" data-testid="demo-form-error">{formErr}</span>}
            <div className="row" style={{ gap: 8 }}>
              <button className="btn accent" type="button" onClick={onSubmit} disabled={busy} data-testid="demo-submit">{busy ? "Đang lưu…" : editingId ? "Lưu" : "Tạo"}</button>
              <button className="btn" type="button" onClick={() => { setEditingId(undefined); setFormErr(""); }} disabled={busy}>Hủy</button>
            </div>
          </div>
        </div>
      )}

      {demo.length === 0 ? (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="demo-empty">Chưa có demo nào.</div>
      ) : (
        <div className="grid g-2" style={{ alignItems: "start", marginTop: 12 }} data-testid="demo-list">
          {demo.map((d) => (
            <div className="panel" key={d.id} data-testid={`demo-card-${d.id}`}>
              <div style={{ padding: "12px 16px" }}>
                <div className="row" style={{ alignItems: "center", gap: 8 }}>
                  <span className={`chip ${DEMO_STATUS_CLS[d.status] ?? "a"}`} data-testid={`demo-status-${d.id}`}>{d.status}</span>
                  {d.loc != null && <span className="hint faint">~{(d.loc / 1000).toFixed(0)}k LOC</span>}
                </div>
                <h3 style={{ margin: "8px 0 2px" }}>{d.name}</h3>
                {d.tagline && <div className="hint mid">{d.tagline}</div>}
                {d.desc && <p className="hint" style={{ marginTop: 6 }}>{d.desc}</p>}
                {d.tags.length > 0 && (
                  <div className="row" style={{ gap: 4, flexWrap: "wrap", marginTop: 8 }}>
                    {d.tags.map((t) => <span key={t} className="pill">{t}</span>)}
                  </div>
                )}
                <div className="row" style={{ gap: 8, marginTop: 10 }}>
                  {d.url && <a className="btn" href={d.url} target="_blank" rel="noreferrer" data-testid={`demo-open-${d.id}`}><Icon name="i-link" /> Mở demo</a>}
                  {d.repo && <a className="btn" href={d.repo} target="_blank" rel="noreferrer" data-testid={`demo-repo-${d.id}`}>Repo</a>}
                  <span className="sp" />
                  <button className="btn" type="button" onClick={() => openEdit(d)} data-testid={`demo-edit-${d.id}`}><Icon name="i-note" /> Sửa</button>
                  <button className="btn" type="button" onClick={() => onDelete(d)} data-testid={`demo-del-${d.id}`}><Icon name="i-x" /> Xóa</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
