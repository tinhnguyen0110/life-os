"use client";
/* ============================================================
   W3 — Inbox / Refine · /wiki/inbox. Ported from mock screens-wiki.js SCREENS.inbox
   + wiki.css. Triage fleeting notes → atomic + ≥1 link before they leave triage.

   2-col: fleeting list (left) + refine panel (right, one note at a time).
   - Refine = rewrite raw → claim-title + atomic prose + status flip + ≥1 link.
   - HARD GATE is SERVER-enforced (POST /wiki/notes/{id}/refine → 422 when linkCount==0
     & vault ≥ cold-start threshold). FE SURFACES the 422 visibly; the cold-start case
     returns 200 + warning (shown, not an error). The client-side `[[...]]` count only
     drives the advisory gate banner / Done-button hint — it does NOT reimplement the
     rule (single source of truth = server).
   - AI aiSuggest is null at M1 → render the empty state (no embedded AI; M4 populates).
   States: loading · error · empty (inbox clear) · ready.
   ============================================================ */
import { useEffect, useMemo, useState } from "react";
import { useWikiInbox } from "@/lib/useWiki";
import { WikiEditor } from "@/components/shared";
import { Field, TextInput } from "@/components/shared/Field";
import { Icon } from "@/lib/icons";
import { ApiError } from "@/lib/api";
import type { WikiInboxItem, WikiStatus } from "@/lib/types";

const CAP_LABEL: Record<string, string> = {
  command_bar: "⌘ cmd",
  quick_add: "+ quick",
  mcp_agent: "◇ MCP",
  daily_note: "☷ daily",
};
function capLabel(s: string): string {
  return CAP_LABEL[s] ?? s;
}

const REFINE_STATUS: { value: WikiStatus; label: string }[] = [
  { value: "fleeting", label: "fleeting" },
  { value: "developing", label: "developing" },
  { value: "evergreen", label: "evergreen" },
];

/** Count resolvable/ghost `[[...]]` wikilinks in a draft body — advisory only (the
 *  gate is server-enforced). Matches the three mock link forms. */
function countWikilinks(body: string): number {
  const m = body.match(/\[\[[^\]]+\]\]/g);
  return m ? m.length : 0;
}

type Draft = { title: string; content: string; status: WikiStatus };

export default function WikiInboxPage() {
  const { items, status, errMsg, reload, refine } = useWikiInbox();

  const [activeId, setActiveId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState(""); // the VISIBLE 422 / write error (fail-closed)
  const [okWarn, setOkWarn] = useState(""); // cold-start success warning

  const active = useMemo<WikiInboxItem | null>(() => {
    if (!items.length) return null;
    const found = activeId != null ? items.find((i) => i.id === activeId) : null;
    return found ?? items[0];
  }, [items, activeId]);

  // Seed the draft when the active item changes.
  useEffect(() => {
    if (!active) {
      setDraft(null);
      return;
    }
    setDraft({
      title: active.title ?? "",
      content: active.rawContent,
      status: "developing",
    });
    setFormErr("");
    // NOTE: do NOT clear okWarn here — a cold-start success warning is about the
    // refine that JUST happened; clearing it on the auto-advance to the next item
    // would wipe it before the user sees it. It's cleared at the start of onDone.
  }, [active?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (status === "loading") {
    return <div className="hint" style={{ padding: "24px 4px" }} data-testid="inbox-loading">Đang tải inbox…</div>;
  }
  if (status === "error") {
    return (
      <div className="hint" style={{ padding: "24px 4px", color: "var(--red)" }} data-testid="inbox-error">
        {errMsg || "Không tải được inbox."}
      </div>
    );
  }
  if (!items.length) {
    return (
      <div data-testid="inbox-screen">
        <div className="vtitle">
          <h1>Inbox / Refine</h1>
          <span className="sub">triage fleeting → atomic + ≥1 link</span>
        </div>
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="inbox-empty">
          🎉 Inbox trống — không có note fleeting nào chờ triage.
        </div>
      </div>
    );
  }

  const linkN = draft ? countWikilinks(draft.content) : 0;
  const hasLink = linkN > 0;

  async function onDone() {
    if (!active || !draft) return;
    setFormErr("");
    setOkWarn("");
    if (!draft.content.trim()) {
      setFormErr("Cần nội dung trước khi refine.");
      return;
    }
    setBusy(true);
    try {
      const warning = await refine(active.id, {
        title: draft.title,
        content: draft.content,
        status: draft.status,
      });
      // success: cold-start may carry a warning (shown, not an error). The list
      // refetches (the note left fleeting) — pick the next item.
      if (warning) setOkWarn(warning);
      setActiveId(null);
    } catch (e) {
      // FAIL-CLOSED: surface the gate 422 (or any write error) VISIBLY; the note
      // is NOT refined; the panel stays so the user can add a link and retry.
      setFormErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-testid="inbox-screen">
      <div className="vtitle">
        <h1>Inbox / Refine</h1>
        <span className="sub">{items.length} fleeting · triage → atomic + ≥1 link</span>
        <span className="sp" style={{ flex: 1 }} />
        <span className="winbox-progress" data-testid="inbox-progress">
          <b className="num">{items.length}</b> → <b className="num pos">0</b>
        </span>
      </div>

      {/* cold-start success warning — screen-level so it survives the auto-advance
          to the next inbox item (the refine succeeded; the note left fleeting). */}
      {okWarn && (
        <div className="wgate warn" data-testid="refine-warning" style={{ marginBottom: 12 }}>
          <div className="wgate-body">
            <b>Đã refine (cold-start)</b>
            <span className="mut">{okWarn}</span>
          </div>
        </div>
      )}

      <div className="winbox-grid">
        {/* list */}
        <div className="panel" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div className="phead">
            <span className="kicker">Hàng chờ · cũ → mới</span>
            <span className="hint" style={{ marginLeft: "auto" }}>
              {items.length}
            </span>
          </div>
          <div className="winbox-list">
            {items.map((it) => (
              <div
                key={it.id}
                className={`winbox-row ${active && active.id === it.id ? "on" : ""}`}
                onClick={() => setActiveId(it.id)}
                data-testid="inbox-row"
                data-active={active?.id === it.id || undefined}
              >
                <span className={`wcap-src ${it.captureSource}`}>{capLabel(it.captureSource)}</span>
                <div className="wlr-body">
                  <div className="wlr-t">
                    {it.title ?? <span className="faint">— chưa title —</span>}
                  </div>
                  <div className="wlr-s mut">{it.rawContent.slice(0, 56)}…</div>
                </div>
                <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10, whiteSpace: "nowrap" }}>
                  {it.captured}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* refine panel */}
        {active && draft && (
          <div className="panel wrefine" data-testid="refine-panel">
            <div className="phead">
              <span className="kicker">Refine · 1 note</span>
              <span className={`wcap-src ${active.captureSource}`} style={{ marginLeft: 8 }}>
                {capLabel(active.captureSource)} · {active.captured}
              </span>
            </div>
            <div className="wrefine-body">
              {/* raw */}
              <div className="wrefine-sec">
                <div className="wrefine-lbl">
                  Raw capture <span className="faint">— giữ nguyên, không sửa lúc capture</span>
                </div>
                <div className="wraw" data-testid="refine-raw">
                  {active.rawContent}
                </div>
              </div>

              {/* AI suggest — null at M1 → empty state (NOT fabricated) */}
              <div className="wrefine-sec wai-box">
                <div className="wrefine-lbl">AI gợi ý</div>
                <div className="wai-empty" data-testid="refine-ai-empty">
                  Chưa có gợi ý AI (title-claim / atomicity / dupe). Phân tích sẽ đến qua Claude Code
                  (MCP) ở giai đoạn sau — bạn tự viết lại + gắn link.
                </div>
              </div>

              {/* human edit */}
              <div className="wrefine-sec">
                <div className="wrefine-lbl">Viết lại → atomic prose + claim-title</div>
                <Field label="Claim-title" testId="refine-f-title">
                  <TextInput
                    value={draft.title}
                    onChange={(v) => setDraft({ ...draft, title: v })}
                    placeholder="Claim-title (một mệnh đề khẳng định)…"
                    maxLength={200}
                    testId="refine-title"
                  />
                </Field>
                <WikiEditor
                  value={draft.content}
                  onChange={(v) => setDraft({ ...draft, content: v })}
                  disabled={busy}
                  placeholder="Viết lại thành atomic prose + gắn [[id|title]]…"
                  testId="refine-body"
                />
                <div className="wrefine-status">
                  <span className="faint" style={{ fontSize: 11 }}>
                    Status:
                  </span>
                  <div className="seg" role="group">
                    {REFINE_STATUS.map((s) => (
                      <button
                        key={s.value}
                        type="button"
                        className={draft.status === s.value ? "on" : ""}
                        onClick={() => setDraft({ ...draft, status: s.value })}
                        data-testid={`refine-status-${s.value}`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* hard gate (advisory banner — rule enforced server-side) */}
              <div className={`wgate ${hasLink ? "ok" : "blocked"}`} data-testid="refine-gate" data-gate={hasLink ? "ok" : "blocked"}>
                <div className="wgate-icon">
                  <Icon name={hasLink ? "i-check" : "i-link"} />
                </div>
                <div className="wgate-body">
                  <b>{hasLink ? "Cổng link: đã qua" : "Cổng cứng: cần ≥1 link"}</b>
                  <span className="mut">
                    {hasLink
                      ? `Note có ${linkN} liên kết — sẵn sàng rời triage.`
                      : "Thêm 1 link ([[id|title]] trong nội dung) trước khi Done. (Vault nhỏ → cold-start được miễn.)"}
                  </span>
                </div>
              </div>

              {/* VISIBLE error (fail-closed) / cold-start warning */}
              {formErr && (
                <div className="wgate blocked" data-testid="refine-error">
                  <div className="wgate-icon">
                    <Icon name="i-link" />
                  </div>
                  <div className="wgate-body">
                    <b>Refine bị chặn</b>
                    <span className="mut">{formErr}</span>
                  </div>
                </div>
              )}
              <div className="wrefine-foot">
                <button type="button" className="btn ghost" onClick={() => reload()} disabled={busy} data-testid="refine-skip">
                  Tải lại
                </button>
                <button
                  type="button"
                  className="btn accent"
                  onClick={onDone}
                  disabled={busy}
                  data-testid="refine-done"
                >
                  <Icon name="i-check" /> {busy ? "Đang lưu…" : "Done refine"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
