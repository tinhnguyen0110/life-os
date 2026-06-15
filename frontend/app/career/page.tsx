"use client";
/* ============================================================
   Career cockpit · /career (CAR-1) — the user's career/personal-brand command
   center, three tabs:
     CV    — the living CV: sections + proof chips, raw export/copy, edit.
     Blog  — blog post manager (draft/published), CRUD metadata.
     Demo  — live-demo / flagship showcase, CRUD.
   Dark command-center aesthetic (shared tokens). All writes fail-closed
   (refetch-after-write; a failed mutation surfaces an error, never silent).
   States: loading · error · empty · data.
   ============================================================ */
import { useMemo, useState } from "react";
import { useCareer } from "@/lib/useCareer";
import { WikiMarkdown } from "@/components/shared";
import { Field, TextInput, Select } from "@/components/shared/Field";
import { Icon, type IconKey } from "@/lib/icons";
import { apiBase, ApiError } from "@/lib/api";
import type { BlogPost, BlogInput, DemoItem, DemoInput, ProofLink } from "@/lib/types";

type Tab = "cv" | "blog" | "demo";

export default function CareerPage() {
  const career = useCareer();
  const { status, errMsg, warning, reload } = career;
  const [tab, setTab] = useState<Tab>("cv");

  return (
    <section className="view" data-screen="CAR" data-testid="career-screen">
      <div className="vtitle">
        <h1>Sự nghiệp & Thương hiệu</h1>
        <span className="sub">CV sống · Blog · Demo showcase</span>
        <span className="sp" />
      </div>

      <div className="row" style={{ gap: 6, flexWrap: "wrap", marginBottom: 6 }} data-testid="career-tabs">
        <span className={`tab${tab === "cv" ? " on" : ""}`} role="button" tabIndex={0} onClick={() => setTab("cv")} data-testid="tab-cv">
          <Icon name="i-doc" /> CV
        </span>
        <span className={`tab${tab === "blog" ? " on" : ""}`} role="button" tabIndex={0} onClick={() => setTab("blog")} data-testid="tab-blog">
          <Icon name="i-note" /> Blog
        </span>
        <span className={`tab${tab === "demo" ? " on" : ""}`} role="button" tabIndex={0} onClick={() => setTab("demo")} data-testid="tab-demo">
          <Icon name="i-bolt" /> Demo
        </span>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="career-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="career-loading">Đang tải…</div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="career-error">
          Không tải được dữ liệu sự nghiệp: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && tab === "cv" && <CvTab career={career} />}
      {status === "ready" && tab === "blog" && <BlogTab career={career} />}
      {status === "ready" && tab === "demo" && <DemoTab career={career} />}
    </section>
  );
}

/* ---------------------------------------------------------------- CV ------- */
const PROOF_ICON: Record<string, IconKey> = {
  "case-study": "i-doc", blog: "i-note", demo: "i-bolt", repo: "i-link", url: "i-link",
};

function ProofChip({ p }: { p: ProofLink }) {
  const internal = p.kind === "blog" || p.kind === "demo";
  const href = internal ? undefined : /^https?:\/\//.test(p.ref) ? p.ref : undefined;
  const body = (
    <>
      <Icon name={PROOF_ICON[p.kind] ?? "i-link"} /> {p.label}
    </>
  );
  if (href) {
    return (
      <a className="pill" href={href} target="_blank" rel="noreferrer" data-testid="cv-proof" title={p.ref}>
        {body}
      </a>
    );
  }
  return (
    <span className="pill" data-testid="cv-proof" title={`${p.kind}: ${p.ref}`}>
      {body}
    </span>
  );
}

function CvTab({ career }: { career: ReturnType<typeof useCareer> }) {
  const { cv, editCv, fetchCvRaw } = career;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [copied, setCopied] = useState(false);

  if (!cv) return <div className="hint" data-testid="cv-empty">Chưa có CV.</div>;

  async function openEdit() {
    setFormErr("");
    setBusy(true);
    try {
      const raw = await fetchCvRaw();
      setDraft(raw);
      setEditing(true);
    } catch (e) {
      setFormErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onSave() {
    if (!draft.trim()) { setFormErr("CV không được để trống."); return; }
    setFormErr("");
    setBusy(true);
    try {
      await editCv(draft);
      setEditing(false);
    } catch (e) {
      setFormErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onCopy() {
    try {
      const raw = await fetchCvRaw();
      await navigator.clipboard.writeText(raw);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard may be unavailable (e.g. insecure context) — surface softly
      setFormErr("Không copy được (clipboard không khả dụng).");
    }
  }

  return (
    <div data-testid="cv-tab">
      <div className="panel" style={{ marginBottom: 12 }}>
        <div className="phead" style={{ alignItems: "center" }}>
          <div>
            <div className="kicker">{cv.meta.title || "CV"}</div>
            <h2 style={{ margin: "2px 0 0" }} data-testid="cv-name">{cv.meta.name || "—"}</h2>
            {cv.meta.contact && (
              <div className="hint mid" style={{ marginTop: 4 }} data-testid="cv-contact">{cv.meta.contact}</div>
            )}
          </div>
          <span className="sp" />
          <span className="hint faint" style={{ marginRight: 8 }}>
            {cv.seeded ? "nguồn: CV gốc" : "đã chỉnh sửa"} · {cv.sections.length} mục
          </span>
          <button className="btn" type="button" onClick={onCopy} disabled={busy} data-testid="cv-copy">
            <Icon name="i-doc" /> {copied ? "Đã copy ✓" : "Copy markdown"}
          </button>
          {!editing && (
            <button className="btn accent" type="button" onClick={openEdit} disabled={busy} data-testid="cv-edit">
              <Icon name="i-note" /> Sửa
            </button>
          )}
        </div>
      </div>

      {formErr && !editing && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="cv-write-error">
          <span className="hint neg">⚠ {formErr}</span>
          <span className="link" style={{ marginLeft: 10 }} onClick={() => setFormErr("")}>đóng</span>
        </div>
      )}

      {editing ? (
        <div className="panel" data-testid="cv-editor">
          <div className="phead"><span className="kicker">Sửa CV (markdown)</span></div>
          <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
            <textarea
              className="tab"
              style={{ fontFamily: "var(--mono)", minHeight: 360, resize: "vertical", whiteSpace: "pre" }}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              data-testid="cv-textarea"
            />
            {formErr && <span className="hint neg" data-testid="cv-form-error">{formErr}</span>}
            <div className="row" style={{ gap: 8 }}>
              <button className="btn accent" type="button" onClick={onSave} disabled={busy} data-testid="cv-save">
                {busy ? "Đang lưu…" : "Lưu"}
              </button>
              <button className="btn" type="button" onClick={() => { setEditing(false); setFormErr(""); }} disabled={busy}>Hủy</button>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid" style={{ gap: 12 }} data-testid="cv-sections">
          {cv.sections.map((s) => (
            <div className="panel" key={s.id} data-testid={`cv-section-${s.id}`}>
              <div className="phead"><span className="kicker">{s.heading}</span></div>
              <div style={{ padding: "12px 16px" }}>
                {s.body ? <WikiMarkdown content={s.body} testId={`cv-body-${s.id}`} /> : <span className="hint faint">(trống)</span>}
                {s.proof.length > 0 && (
                  <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 10 }} data-testid={`cv-proof-${s.id}`}>
                    <span className="hint faint" style={{ marginRight: 4 }}>Bằng chứng:</span>
                    {s.proof.map((p, i) => <ProofChip key={i} p={p} />)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- Blog ------- */
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

function BlogTab({ career }: { career: ReturnType<typeof useCareer> }) {
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

/* -------------------------------------------------------------- Demo ------- */
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

function DemoTab({ career }: { career: ReturnType<typeof useCareer> }) {
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
