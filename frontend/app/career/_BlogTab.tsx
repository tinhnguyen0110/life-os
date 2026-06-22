"use client";
/* ============================================================
   Career · Blog tab (extracted from page.tsx, #138-P2 — pure MOVE, no logic change).
   Blog post manager (draft/published), CRUD metadata. blogFormToInput + the
   BlogForm type + EMPTY_BLOG live here (BlogTab is their only consumer).
   ============================================================ */
import { useMemo, useState } from "react";
import { useCareer } from "@/lib/useCareer";
import { Field, TextInput, Select } from "@/components/shared/Field";
import { Icon } from "@/lib/icons";
import { ApiError } from "@/lib/api";
import type { BlogPost, BlogInput } from "@/lib/types";

type BlogForm = {
  title: string; subtitle: string; dek: string; status: string;
  url: string; tags: string; publishedDate: string; readMinutes: string;
};
const EMPTY_BLOG: BlogForm = { title: "", subtitle: "", dek: "", status: "draft", url: "", tags: "", publishedDate: "", readMinutes: "" };

function blogFormToInput(f: BlogForm): BlogInput {
  return {
    title: f.title.trim(),
    subtitle: f.subtitle.trim(),
    dek: f.dek.trim(),
    status: (f.status as BlogInput["status"]),
    url: f.url.trim() || null,
    tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean),
    publishedDate: f.publishedDate.trim() || null,
    readMinutes: f.readMinutes.trim() ? Number(f.readMinutes) : null,
  };
}

export function BlogTab({ career }: { career: ReturnType<typeof useCareer> }) {
  const { blog, createBlog, updateBlog, deleteBlog } = career;
  const [editingId, setEditingId] = useState<string | null | undefined>(undefined); // undefined=closed, null=new
  const [form, setForm] = useState<BlogForm>(EMPTY_BLOG);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");

  const counts = useMemo(() => ({
    published: blog.filter((b) => b.status === "published").length,
    draft: blog.filter((b) => b.status === "draft").length,
  }), [blog]);

  function openNew() { setFormErr(""); setForm(EMPTY_BLOG); setEditingId(null); }
  function openEdit(b: BlogPost) {
    setFormErr("");
    setForm({
      title: b.title, subtitle: b.subtitle, dek: b.dek, status: b.status,
      url: b.url ?? "", tags: b.tags.join(", "),
      publishedDate: b.publishedDate ?? "", readMinutes: b.readMinutes != null ? String(b.readMinutes) : "",
    });
    setEditingId(b.id);
  }

  async function onSubmit() {
    if (!form.title.trim()) { setFormErr("Cần tiêu đề bài viết."); return; }
    setFormErr(""); setBusy(true);
    try {
      const input = blogFormToInput(form);
      if (editingId) await updateBlog(editingId, input);
      else await createBlog(input);
      setEditingId(undefined);
    } catch (e) {
      setFormErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally { setBusy(false); }
  }

  async function onDelete(b: BlogPost) {
    setFormErr("");
    try { await deleteBlog(b.id); }
    catch (e) { setFormErr(`Xóa thất bại: ${e instanceof ApiError ? e.message : (e as Error).message}`); }
  }

  return (
    <div data-testid="blog-tab">
      <div className="row" style={{ alignItems: "center", marginBottom: 10 }}>
        <span className="hint mid">{blog.length} bài · {counts.published} published · {counts.draft} draft</span>
        <span className="sp" />
        <button className="btn accent" type="button" onClick={openNew} data-testid="blog-new"><Icon name="i-plus" /> Bài mới</button>
      </div>

      {formErr && editingId === undefined && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="blog-write-error">
          <span className="hint neg">⚠ {formErr}</span>
          <span className="link" style={{ marginLeft: 10 }} onClick={() => setFormErr("")}>đóng</span>
        </div>
      )}

      {editingId !== undefined && (
        <div className="panel" data-testid="blog-form">
          <div className="phead"><span className="kicker">{editingId ? "Sửa bài" : "Bài mới"}</span></div>
          <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
            <Field label="Tiêu đề" testId="blog-f-title"><TextInput value={form.title} onChange={(v) => setForm({ ...form, title: v })} testId="blog-i-title" /></Field>
            <Field label="Phụ đề" testId="blog-f-subtitle"><TextInput value={form.subtitle} onChange={(v) => setForm({ ...form, subtitle: v })} testId="blog-i-subtitle" /></Field>
            <Field label="Mô tả (dek)" testId="blog-f-dek">
              <textarea className="finput" style={{ minHeight: 70, resize: "vertical" }} value={form.dek} onChange={(e) => setForm({ ...form, dek: e.target.value })} data-testid="blog-i-dek" />
            </Field>
            <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
              <Field label="Trạng thái" testId="blog-f-status">
                <Select value={form.status} onChange={(v) => setForm({ ...form, status: v })} options={[{ value: "draft", label: "Draft" }, { value: "published", label: "Published" }]} testId="blog-i-status" />
              </Field>
              <Field label="Read (phút)" testId="blog-f-read"><TextInput value={form.readMinutes} onChange={(v) => setForm({ ...form, readMinutes: v })} testId="blog-i-read" /></Field>
              <Field label="Ngày publish" testId="blog-f-date"><TextInput value={form.publishedDate} onChange={(v) => setForm({ ...form, publishedDate: v })} placeholder="2026-06-14" testId="blog-i-date" /></Field>
            </div>
            <Field label="URL công khai" testId="blog-f-url"><TextInput value={form.url} onChange={(v) => setForm({ ...form, url: v })} placeholder="https://blog.tinhdev.com/…" testId="blog-i-url" /></Field>
            <Field label="Tags (phân cách dấu phẩy)" testId="blog-f-tags"><TextInput value={form.tags} onChange={(v) => setForm({ ...form, tags: v })} testId="blog-i-tags" /></Field>
            {formErr && <span className="hint neg" data-testid="blog-form-error">{formErr}</span>}
            <div className="row" style={{ gap: 8 }}>
              <button className="btn accent" type="button" onClick={onSubmit} disabled={busy} data-testid="blog-submit">{busy ? "Đang lưu…" : editingId ? "Lưu" : "Tạo"}</button>
              <button className="btn" type="button" onClick={() => { setEditingId(undefined); setFormErr(""); }} disabled={busy}>Hủy</button>
            </div>
          </div>
        </div>
      )}

      {blog.length === 0 ? (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="blog-empty">Chưa có bài viết nào.</div>
      ) : (
        <div className="grid g-2" style={{ alignItems: "start", marginTop: 12 }} data-testid="blog-list">
          {blog.map((b) => (
            <div className="panel" key={b.id} data-testid={`blog-card-${b.id}`}>
              <div style={{ padding: "12px 16px" }}>
                <div className="row" style={{ alignItems: "center", gap: 8 }}>
                  <span className={`chip ${b.status === "published" ? "g" : "a"}`} data-testid={`blog-status-${b.id}`}>{b.status}</span>
                  {b.readMinutes != null && <span className="hint faint">{b.readMinutes} phút đọc</span>}
                  {b.publishedDate && <span className="hint faint">· {b.publishedDate}</span>}
                </div>
                <h3 style={{ margin: "8px 0 2px" }}>{b.title}</h3>
                {b.subtitle && <div className="hint mid">{b.subtitle}</div>}
                {b.dek && <p className="hint" style={{ marginTop: 6 }}>{b.dek}</p>}
                {b.tags.length > 0 && (
                  <div className="row" style={{ gap: 4, flexWrap: "wrap", marginTop: 8 }}>
                    {b.tags.map((t) => <span key={t} className="pill">{t}</span>)}
                  </div>
                )}
                <div className="row" style={{ gap: 8, marginTop: 10 }}>
                  {b.url && <a className="btn" href={b.url} target="_blank" rel="noreferrer" data-testid={`blog-open-${b.id}`}><Icon name="i-link" /> Mở</a>}
                  <span className="sp" />
                  <button className="btn" type="button" onClick={() => openEdit(b)} data-testid={`blog-edit-${b.id}`}><Icon name="i-note" /> Sửa</button>
                  <button className="btn" type="button" onClick={() => onDelete(b)} data-testid={`blog-del-${b.id}`}><Icon name="i-x" /> Xóa</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
