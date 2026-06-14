"use client";
/* ============================================================
   W2 — Note View/Edit · /wiki/[id]. Ported from mock screens-wiki.js SCREENS.note
   (L151+) + wiki.css. Reads one wiki note + all its connections; edits in place.

   - VIEW: header (#id / status pill / type / trust badge + candidate-warning) +
     title + meta (aliases/tags/created/updated) + body via WikiLinkRenderer +
     outbound (resolved clickable / ghost "+ tạo note") + AI link-suggestions panel
     (EMPTY at M1 — render the empty state, NEVER fabricate; M4 populates via Claude
     Code/MCP) + BacklinksPanel (linked + unlinked).
   - EDIT: title input + status select + tags + body via WikiEditor → save = PUT
     /wiki/notes/{id} → refetch (server-truth, NOT optimistic). FAIL-CLOSED: a failed
     save keeps edit mode open + surfaces the error; the note is NOT shown as saved.

   Derived (backlinks/isResolved/trustTier) are backend-computed — FE renders only.
   States: loading · error (incl. 404) · ready(view) · ready(edit).
   ============================================================ */
import { useEffect, useState } from "react";
import { useWikiNote } from "@/lib/useWiki";
import {
  WikiMarkdown,
  WikiEditor,
  BacklinksPanel,
  StatusPill,
  TrustTierBadge,
  TypeBadge,
  CandidateWarning,
} from "@/components/shared";
import { Field, TextInput, Select } from "@/components/shared/Field";
import { Icon } from "@/lib/icons";
import { ApiError } from "@/lib/api";
import type { WikiStatus } from "@/lib/types";

const STATUS_OPTS: { value: WikiStatus; label: string }[] = [
  { value: "fleeting", label: "fleeting" },
  { value: "developing", label: "developing" },
  { value: "evergreen", label: "evergreen" },
];

type EditDraft = { title: string; content: string; status: WikiStatus; tags: string };

export default function WikiNotePage({ params }: { params?: { id?: string } }) {
  const rawId = params?.id ?? "";
  const id = /^\d+$/.test(rawId) ? parseInt(rawId, 10) : null;
  const { note, backlinks, status, errMsg, warning, save } = useWikiNote(id);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<EditDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");

  // Leaving a note (id change) → drop any open edit.
  useEffect(() => {
    setEditing(false);
    setDraft(null);
    setFormErr("");
  }, [id]);

  if (status === "loading") {
    return <div className="hint" style={{ padding: "24px 4px" }} data-testid="wiki-loading">Đang tải note…</div>;
  }
  if (status === "error" || !note) {
    return (
      <div className="hint" style={{ padding: "24px 4px", color: "var(--red)" }} data-testid="wiki-error">
        {errMsg || "Không tải được note."}
      </div>
    );
  }

  const bl = backlinks ?? { linked: [], unlinked: [], outbound: [] };

  // Title→id resolution for body `[[Title]]` links: the backend already resolved this
  // note's outbound edges (backlinks.outbound). Map each RESOLVED edge's title
  // (lowercased) → id so a body `[[Linking Notes]]` of an existing note renders a
  // clickable link, consistent with the OUTBOUND LINKS panel. Unresolved titles (not
  // in the map) stay ghosts.
  const linkResolve = new Map<string, number>(
    bl.outbound
      .filter((o): o is { id: number; title: string; isResolved: true } => o.isResolved && o.id !== undefined)
      .map((o) => [o.title.trim().toLowerCase(), o.id] as const),
  );

  function openEdit() {
    if (!note) return;
    setFormErr("");
    setDraft({
      title: note.title,
      content: note.content,
      status: note.status,
      tags: note.tags.join(", "),
    });
    setEditing(true);
  }

  async function onSave() {
    if (!draft) return;
    setFormErr("");
    setBusy(true);
    try {
      await save({
        title: draft.title,
        content: draft.content,
        status: draft.status,
        tags: draft.tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setEditing(false); // close only on SUCCESS (fail-closed)
      setDraft(null);
    } catch (e) {
      // fail-closed: stay in edit mode, surface the error; note NOT saved.
      setFormErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-testid="wiki-note-screen">
      {warning && (
        <div className="hint" style={{ padding: "8px 4px", color: "var(--amber)" }} data-testid="wiki-warning">
          {warning}
        </div>
      )}

      {/* Header */}
      <div className="wnote-head">
        <a className="btn sm ghost" href="/wiki/inbox" data-testid="wiki-back">
          <Icon name="i-back" /> Inbox
        </a>
        <span className="wnote-id num" data-testid="wiki-id">
          #{note.id}
        </span>
        <StatusPill status={note.status} testId="wiki-status" />
        <TypeBadge type={note.noteType} testId="wiki-type" />
        <TrustTierBadge tier={note.trustTier} testId="wiki-trust" />
        <span className="sp" style={{ flex: 1 }} />
        {!editing && (
          <button type="button" className="btn sm accent" onClick={openEdit} data-testid="wiki-edit-btn">
            <Icon name="i-note" /> Sửa
          </button>
        )}
      </div>

      <div className="wnote-grid">
        {/* main column */}
        <div className="wnote-main">
          <div className="panel wnote-body-panel">
            {editing && draft ? (
              <>
                <Field label="Tiêu đề" testId="wiki-f-title">
                  <TextInput
                    value={draft.title}
                    onChange={(v) => setDraft({ ...draft, title: v })}
                    placeholder="Claim-title…"
                    maxLength={200}
                    testId="wiki-edit-title"
                  />
                </Field>
                <div className="wnote-meta" style={{ border: 0, marginBottom: 10 }}>
                  <Field label="Status" testId="wiki-f-status">
                    <Select
                      value={draft.status}
                      onChange={(v) => setDraft({ ...draft, status: v as WikiStatus })}
                      options={STATUS_OPTS}
                      testId="wiki-edit-status"
                    />
                  </Field>
                  <Field label="Tags (phẩy)" testId="wiki-f-tags">
                    <TextInput
                      value={draft.tags}
                      onChange={(v) => setDraft({ ...draft, tags: v })}
                      placeholder="pkm, learning"
                      testId="wiki-edit-tags"
                    />
                  </Field>
                </div>
                <WikiEditor
                  value={draft.content}
                  onChange={(v) => setDraft({ ...draft, content: v })}
                  disabled={busy}
                  testId="wiki-edit-body"
                />
                {formErr && (
                  <div className="ferr" data-testid="wiki-edit-error" style={{ marginTop: 10 }}>
                    {formErr}
                  </div>
                )}
                <div className="wrefine-foot" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn sm"
                    onClick={() => {
                      setEditing(false);
                      setDraft(null);
                      setFormErr("");
                    }}
                    disabled={busy}
                    data-testid="wiki-edit-cancel"
                  >
                    Huỷ
                  </button>
                  <button
                    type="button"
                    className="btn sm accent"
                    onClick={onSave}
                    disabled={busy}
                    data-testid="wiki-edit-save"
                  >
                    {busy ? "Đang lưu…" : "Lưu"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="wnote-title" data-testid="wiki-title">
                  {note.title || <span className="faint">— chưa có title —</span>}
                </div>
                <div className="wnote-meta">
                  {note.aliases.length > 0 && (
                    <>
                      <span className="wmeta-k">aliases:</span>{" "}
                      {note.aliases.map((a) => (
                        <span className="tagchip" key={a}>
                          {a}
                        </span>
                      ))}
                    </>
                  )}
                  <span className="wmeta-k" style={{ marginLeft: note.aliases.length ? 10 : 0 }}>
                    tags:
                  </span>{" "}
                  {note.tags.length > 0 ? (
                    note.tags.map((t) => (
                      <span className="tagchip" key={t}>
                        #{t}
                      </span>
                    ))
                  ) : (
                    <span className="faint">—</span>
                  )}
                  <span className="sp" style={{ flex: 1 }} />
                  <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: "10.5px" }}>
                    tạo {note.created} · sửa {note.updated}
                  </span>
                </div>
                <WikiMarkdown content={note.content} resolve={linkResolve} />
                {note.trustTier === "candidate" && <CandidateWarning testId="wiki-candidate-warn" />}
              </>
            )}
          </div>

          {/* outbound + backlinks (linked/unlinked) — the shared panel renders both;
              shown only in view mode (edit mode focuses the body). */}
          {!editing && <BacklinksPanel backlinks={bl} />}
        </div>

        {/* side column */}
        <div className="wnote-side">
          {/* AI suggestions — EMPTY at M1 (no embedded AI; M4 via Claude Code) */}
          <div className="panel wsugg-panel" data-testid="wiki-suggestions-panel">
            <div className="phead">
              <span className="kicker">Link gợi ý · AI candidate</span>
            </div>
            <div className="wsugg-empty" data-testid="wiki-suggestions-empty">
              Chưa có gợi ý. Link-suggestion sẽ đến qua Claude Code (MCP) ở giai đoạn sau — chỉ là
              candidate tới khi bạn accept, không bao giờ tự ghi.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
