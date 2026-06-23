"use client";
/* ============================================================
   Career · CV tab (extracted from page.tsx, #138-P2 — pure MOVE, no logic change).
   The living CV: sections + proof chips, raw export/copy, edit. ProofChip +
   PROOF_ICON live here too (CvTab is their only consumer).
   ============================================================ */
import { useState } from "react";
import { useCareer } from "@/lib/useCareer";
import { WikiMarkdown } from "@/components/shared";
import { Icon, type IconKey } from "@/lib/icons";
import { ApiError } from "@/lib/api";
import type { ProofLink } from "@/lib/types";

const PROOF_ICON: Record<string, IconKey> = {
  "case-study": "i-doc", blog: "i-note", demo: "i-bolt", repo: "i-link", url: "i-link",
};

export function ProofChip({ p }: { p: ProofLink }) {
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

export function CvTab({ career }: { career: ReturnType<typeof useCareer> }) {
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
              {/* #156-R1: constrain the CV prose to a comfortable reading line-length
                  (~75ch ≈ 800px) — at 1920px the full-panel prose runs far past the
                  readable 65-75ch. Left-aligned (a CV reads from the left margin, NOT
                  centered). INLINE on career's instance only — the shared global `.wmd`
                  rule (wiki/notes also use it) is NOT modified. */}
              <div style={{ padding: "12px 16px", maxWidth: "75ch" }}>
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
