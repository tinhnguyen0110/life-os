"use client";
/* ============================================================
   A1c — Sync & Integrity · /wiki/sync. Two integrity surfaces from W7:
   (1) CONFLICT RESOLUTION (A1a, deferred here) — GET /wiki/sync/conflicts +
       POST .../{id}/resolve. Block-level LWW keeps EVERY version (0 data loss);
       a TRUE conflict (same note+block edited divergently) surfaces here for the
       human to pick the winning content. Resolve writes THROUGH the single-writer
       queue (one auditable path). Fail-closed: a failed resolve surfaces, list unchanged.
   (2) CITATION VERIFY (A1b) — POST /wiki/citations/verify. The SPEC (L257) has NO
       in-app chat; grounded Q&A is EXTERNAL Claude Code (MCP). This is the
       "answered via MCP, N citations verified" surface: paste/inspect the cites an
       agent returned → deterministic CODE post-verify (verified/weak/rejected/
       ungrounded) → click a verified cite → jump to /wiki/[note]. NOT a chatbox.
   States per section: loading · error · empty (honest) · data.
   ============================================================ */
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useWikiConflicts } from "@/lib/useWiki";
import { verifyWikiCitations } from "@/lib/api";
import { Icon } from "@/lib/icons";
import { ApiError } from "@/lib/api";
import type { WikiConflict, WikiConflictVersion, WikiCitationVerifyResult, WikiCitationStatus } from "@/lib/types";

/* ---------------- Conflict resolution ---------------- */

function ConflictCard({ c, onResolve }: { c: WikiConflict; onResolve: (conflictId: number, noteId: number, content: string) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [picked, setPicked] = useState<number | null>(null); // index of chosen version

  async function resolve(version: WikiConflictVersion, idx: number) {
    setErr("");
    setPicked(idx);
    setBusy(true);
    try {
      await onResolve(c.id, c.noteId, version.content); // throws → surface (fail-closed)
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : (e as Error).message);
      setPicked(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`wprop-card ${busy ? "deciding" : ""}`} data-testid="conflict-card" data-conflict-id={c.id}>
      <div className="wprop-head">
        <span className="wprop-kind-badge" style={{ color: "var(--red)", background: "color-mix(in oklch,var(--red) 14%,transparent)" }}>
          <Icon name="i-merge" /> conflict
        </span>
        <Link className="wlink" href={`/wiki/${c.noteId}`} data-testid="conflict-note">note #{c.noteId}</Link>
        <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>block {c.blockIndex}</span>
        <span className="sp" style={{ flex: 1 }} />
        <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>{c.detected}</span>
      </div>
      <div className="wprop-why mut">
        Cùng một block bị sửa khác nhau trên ≥2 thiết bị. Mọi version được giữ (LWW loser khôi phục được) — chọn bản đúng:
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {c.versions.map((v, i) => (
          <div key={i} className="wprop-content" data-testid="conflict-version" style={{ borderLeft: picked === i ? "2px solid var(--green)" : "2px solid var(--line-2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
              <span className="wact-actor agent" style={{ fontSize: 10.5 }}>◆ {v.device}</span>
              <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{v.ts}</span>
              <span className="sp" style={{ flex: 1 }} />
              <button type="button" className="btn sm accent" disabled={busy} onClick={() => resolve(v, i)} data-testid="conflict-pick">
                <Icon name="i-check" /> Chọn bản này
              </button>
            </div>
            <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{v.content || <span className="faint">(rỗng)</span>}</div>
          </div>
        ))}
      </div>
      {err && <div className="wprop-err" data-testid="conflict-error">⚠ {err}</div>}
    </div>
  );
}

function ConflictsSection() {
  const { conflicts, status, errMsg, reload, resolve } = useWikiConflicts();

  return (
    <div className="panel" data-testid="conflicts-section">
      <div className="phead">
        <span className="kicker">Conflict resolution · M3 sync</span>
        <span className="hint" style={{ marginLeft: "auto" }}>
          {status === "ready" ? `${conflicts.length} mở` : "…"}
        </span>
      </div>
      <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        {status === "loading" ? (
          <div className="hint" data-testid="conflicts-loading">Đang tải conflicts…</div>
        ) : status === "error" ? (
          <div className="hint" style={{ color: "var(--red)" }} data-testid="conflicts-error">
            {errMsg || "Không tải được conflicts."}
            <button type="button" className="btn ghost" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
          </div>
        ) : conflicts.length === 0 ? (
          <div className="wlist-empty" data-testid="conflicts-empty">
            ✓ Không có xung đột nào. Block-level LWW hội tụ tự động; chỉ true-conflict (cùng block sửa khác nhau) mới cần bạn quyết.
          </div>
        ) : (
          conflicts.map((c) => <ConflictCard key={c.id} c={c} onResolve={resolve} />)
        )}
      </div>
    </div>
  );
}

/* ---------------- Citation verify ---------------- */

const CITE_META: Record<WikiCitationStatus, { lbl: string; color: string }> = {
  verified: { lbl: "verified", color: "var(--green)" },
  weaklyGrounded: { lbl: "weak", color: "var(--amber)" },
  rejected: { lbl: "rejected", color: "var(--red)" },
  ungrounded: { lbl: "ungrounded", color: "var(--tx-2)" },
};

function CitationSection() {
  const router = useRouter();
  const [raw, setRaw] = useState("");
  const [result, setResult] = useState<WikiCitationVerifyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  /** Parse the pasted MCP answer into claims. Accepts either JSON
   *  ({claims:[...]} or [...]) or simple lines "claim | noteId | span". Lenient —
   *  this is a verify TOOL, not a strict form. */
  function parseClaims(text: string): { claim: string; noteId?: number | null; span?: string | null }[] {
    const t = text.trim();
    if (!t) return [];
    try {
      const j = JSON.parse(t);
      const arr = Array.isArray(j) ? j : Array.isArray(j.claims) ? j.claims : null;
      if (arr) {
        return arr.map((c: Record<string, unknown>) => ({
          claim: String(c.claim ?? ""),
          noteId: c.noteId == null ? null : Number(c.noteId),
          span: c.span == null ? null : String(c.span),
        }));
      }
    } catch {
      /* not JSON → line format */
    }
    return t.split("\n").map((line) => {
      const [claim, noteId, span] = line.split("|").map((s) => s.trim());
      return {
        claim: claim ?? line.trim(),
        noteId: noteId ? Number(noteId) : null,
        span: span || null,
      };
    }).filter((c) => c.claim);
  }

  async function onVerify() {
    setErr("");
    const claims = parseClaims(raw);
    if (!claims.length) {
      setErr("Dán các citation (JSON {claims:[...]} hoặc mỗi dòng: claim | noteId | span).");
      return;
    }
    setBusy(true);
    try {
      const res = await verifyWikiCitations({ claims });
      setResult(res?.data ?? null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const s = result?.summary;

  return (
    <div className="panel" data-testid="citations-section">
      <div className="phead">
        <span className="kicker">Citation verify · answered via MCP</span>
        <span className="hint" style={{ marginLeft: "auto" }}>code post-verify</span>
      </div>
      <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="hint" style={{ lineHeight: 1.5 }}>
          Không có chat trong app — hỏi-đáp grounded là Claude Code (MCP). Dán các citation agent trả về để
          <b> kiểm chứng bằng code</b> (note + span có thật không). Click cite đã verified → nhảy tới note.
        </div>
        <textarea
          data-testid="cite-input"
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          placeholder={'{"claims":[{"claim":"...","noteId":1,"span":"..."}]}\nhoặc mỗi dòng:  claim | noteId | span'}
          rows={5}
          style={{
            width: "100%", fontFamily: "var(--mono)", fontSize: 12, resize: "vertical",
            background: "var(--bg-0)", color: "var(--tx-0)", border: "1px solid var(--line-2)",
            borderRadius: 8, padding: "8px 10px", outline: "none",
          }}
        />
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <button type="button" className="btn accent" onClick={onVerify} disabled={busy} data-testid="cite-verify">
            <Icon name="i-check" /> {busy ? "Đang kiểm…" : "Verify citations"}
          </button>
          {s && (
            <span className="hint" data-testid="cite-summary">
              <b className="num pos">{s.verified}</b> verified · <b className="num">{s.weaklyGrounded}</b> weak ·{" "}
              <b className="num neg">{s.rejected}</b> rejected · <b className="num">{s.ungrounded}</b> ungrounded / {s.total}
            </span>
          )}
        </div>
        {err && <div className="wprop-err" data-testid="cite-error">⚠ {err}</div>}
        {result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }} data-testid="cite-results">
            {result.results.length === 0 ? (
              <div className="wlist-empty" data-testid="cite-empty">Không có citation nào để hiển thị.</div>
            ) : (
              result.results.map((r, i) => {
                const m = CITE_META[r.status];
                const jumpId = r.resolvedNoteId ?? r.noteId;
                const clickable = (r.status === "verified" || r.status === "weaklyGrounded") && jumpId != null;
                return (
                  <div
                    key={i}
                    className="wlist-row"
                    data-testid="cite-row"
                    data-status={r.status}
                    onClick={clickable ? () => router.push(`/wiki/${jumpId}`) : undefined}
                    role={clickable ? "button" : undefined}
                    tabIndex={clickable ? 0 : undefined}
                    onKeyDown={clickable ? (e) => { if (e.key === "Enter") router.push(`/wiki/${jumpId}`); } : undefined}
                    style={{ cursor: clickable ? "pointer" : "default" }}
                  >
                    <span className="wprop-kind-badge" style={{ color: m.color, background: `color-mix(in oklch,${m.color} 14%,transparent)` }}>
                      {m.lbl}
                    </span>
                    <div className="wlr-body">
                      <div className="wlr-t">{r.claim}</div>
                      <div className="wlr-s mut">
                        {jumpId != null ? `#${jumpId}` : "no citation"} · {r.reason}
                      </div>
                    </div>
                    {clickable && <span className="link" data-testid="cite-jump">→ note</span>}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function WikiSyncPage() {
  return (
    <div data-testid="sync-screen">
      <div className="vtitle">
        <h1>Sync & Integrity</h1>
        <span className="sub">conflict resolution · citation verify (no in-app chat — Claude Code via MCP)</span>
        <span className="sp" style={{ flex: 1 }} />
        <Link href="/wiki" className="btn" data-testid="sync-home-link">
          <Icon name="i-home" /> Vault
        </Link>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", alignItems: "start" }}>
        <ConflictsSection />
        <CitationSection />
      </div>
    </div>
  );
}
