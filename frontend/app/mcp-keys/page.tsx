"use client";
/* ============================================================
   /mcp-keys (#88 · MCPKEYS) — manage per-key MCP tool scoping. An agent connects with
   a key; the key sees only the tools its scope grants (a whole DOMAIN's tools + explicit
   tools). This screen: LIST keys · CREATE (label + scope) · EDIT a key's scope · DELETE ·
   a connect-hint (endpoint + the X-MCP-Key header) · the tool-catalog AUDIT.

   #88 complete (part-1 CRUD + part-2 scope-editor). RENDER-ONLY: the backend owns the
   store + computes toolCount; the FE displays + lets the user tick a scope. The scope
   math is pure (lib/mcpScope). The catalog comes from GET /mcp_keys/catalog (#87).
   ============================================================ */
import { useState, useRef, useCallback } from "react";
import { useMcpKeys } from "@/lib/useMcpKeys";
import { useMcpCatalog } from "@/lib/useMcpCatalog";
import { apiBase, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { McpScopeEditor, McpCatalogAudit } from "@/components/McpScopeEditor";
import { EMPTY_SCOPE, resolvedTools, groupByDomain } from "@/lib/mcpScope";
import type { McpKey, McpScope, McpCatalog } from "@/lib/types";

/** the MCP endpoint base (mounts live at <base>/mcp/<server>/mcp). */
const MCP_BASE = `${apiBase}/mcp`;

/** the connect-config snippet (one source for the <pre> + the copy button). */
const CONFIG_SNIPPET = `{
  "mcpServers": {
    "lifeos-read": {
      "url": "${MCP_BASE}/read/mcp",
      "headers": { "X-MCP-Key": "<your-key>" }
    }
  }
}`;

/** #128 — mask a key value for display: show a short prefix + a dotted tail (never the
 *  full secret on screen unless the user reveals). Short keys → all dots. */
function maskKey(key: string): string {
  if (!key) return "";
  if (key.length <= 8) return "•".repeat(key.length);
  return `${key.slice(0, 6)}${"•".repeat(Math.max(8, key.length - 6))}`;
}

/** #162 — APERTURE coverage, computed FE-side from the REAL catalog (template:596-612).
 *  Per domain: granted = the key's resolved tools in that domain; total = byMount[domain].
 *  The segmented bar shows on(granted)/off(remaining) widths across all domains, and the
 *  headline "N / TOTAL tool trong tầm nhìn". Honest: empty catalog → empty segs + 0/0. */
type ApertureSeg = { domain: string; on: number; off: number };
function computeAperture(scope: McpScope, catalog: McpCatalog): { segs: ApertureSeg[]; granted: number; total: number } {
  const grantedNames = new Set(resolvedTools(scope, catalog.tools));
  // Per domain: total = the domain's actual tool count in the catalog (groupByDomain — the
  // SAME source granted is counted from, so on+off always equals the domain total exactly);
  // granted = how many of those the key's resolved scope grants. (byMount is the BE display
  // count; using the group's own length keeps the segment widths internally consistent.)
  const segs: ApertureSeg[] = groupByDomain(catalog.tools).map(({ domain, tools }) => {
    const on = tools.filter((t) => grantedNames.has(t.name)).length;
    return { domain, on, off: tools.length - on };
  });
  return { segs, granted: grantedNames.size, total: catalog.tools.length };
}

export default function McpKeysPage() {
  const { keys, status, errMsg, reload, create, update, remove } = useMcpKeys();
  const { catalog, status: catStatus, errMsg: catErr, reload: catReload } = useMcpCatalog();

  // create form (label + scope)
  const [label, setLabel] = useState("");
  const [createScope, setCreateScope] = useState<McpScope>(EMPTY_SCOPE);
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState("");
  const [justCreated, setJustCreated] = useState<McpKey | null>(null);

  // edit-scope (per row)
  const [editKey, setEditKey] = useState<string | null>(null);
  const [editScope, setEditScope] = useState<McpScope>(EMPTY_SCOPE);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editErr, setEditErr] = useState("");

  // in-page delete confirm (NOT a JS confirm() — that blocks the browser extension).
  const [confirmDel, setConfirmDel] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [deleteErr, setDeleteErr] = useState("");

  // the catalog-audit panel toggle
  const [showAudit, setShowAudit] = useState(false);
  // #160 redesign — KEYS-FIRST: the create form (label + the 98-tool scope picker) is
  // COLLAPSED by default (open via "+ Key mới") so the daily task (manage keys) sits at
  // the top, not buried below the picker. The connect block is reference info → collapsed.
  const [showCreate, setShowCreate] = useState(false);
  const [showConnect, setShowConnect] = useState(false);

  // #128 — mask the just-created key VALUE (reveal-on-demand security hygiene). Default
  // masked; the user reveals to copy by eye, or just clicks Copy (no reveal needed).
  const [keyRevealed, setKeyRevealed] = useState(false);

  // #162 — toast (fixed bottom-center pill) for copy / update / delete feedback.
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toast = useCallback((msg: string) => {
    setToastMsg(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastMsg(null), 1800);
  }, []);
  async function copyText(text: string, okMsg: string) {
    try { await navigator.clipboard?.writeText(text); toast(okMsg); }
    catch { toast("Không sao chép được"); }
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = label.trim();
    if (!trimmed) { setCreateErr("Nhập nhãn cho key"); return; }
    setCreateErr(""); setCreating(true);
    try {
      const row = await create({ label: trimmed, scope: createScope });
      setJustCreated(row);
      setKeyRevealed(false); // #128 — a fresh key starts MASKED
      setLabel("");
      setCreateScope(EMPTY_SCOPE);
      setShowCreate(false); // #160 — collapse the form on success so the key-once reveal is the focus
    } catch (err) {
      setCreateErr(err instanceof ApiError ? (err.hint ? `${err.message} (${err.hint})` : err.message) : (err as Error).message);
    } finally {
      setCreating(false);
    }
  }

  function startEdit(k: McpKey) {
    setEditKey(k.key);
    setEditScope({ domains: [...k.scope.domains], tools: [...k.scope.tools] });
    setEditErr("");
  }

  async function onSaveEdit() {
    if (editKey == null) return;
    setEditErr(""); setSavingEdit(true);
    try {
      await update(editKey, { scope: editScope });
      setEditKey(null);
      toast("Đã cập nhật phạm vi"); // #162
    } catch (err) {
      setEditErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setSavingEdit(false);
    }
  }

  async function onDelete(key: string) {
    setDeleteErr(""); setDeletingKey(key);
    try {
      await remove(key);
      setConfirmDel(null);
      if (justCreated?.key === key) setJustCreated(null);
      if (editKey === key) setEditKey(null);
      toast("Đã xoá key"); // #162
    } catch (err) {
      setDeleteErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setDeletingKey(null);
    }
  }

  return (
    <section className="view" data-screen="MCPKEYS" data-testid="mcp-keys-screen">
      {/* #162 — MASTHEAD (template:246-256, adapted to DARK): accent top-rule + display h1
          + sub + right meta (tool/domain · localhost). Replaces the plain vtitle. */}
      <div className="mcpk-toprule" aria-hidden="true" />
      {/* #164c — masthead meta (98 tool · 7 domain / localhost) removed per user. */}
      <header className="mcpk-mast">
        <div>
          <h1 className="mcpk-h1">MCP <span className="dim">Keys</span></h1>
          <p className="mcpk-sub">Cấp key cho agent. Mỗi key chỉ thấy các tool nằm trong phạm vi của nó — để giới hạn tool cho từng agent, không phải để chống tấn công.</p>
        </div>
      </header>

      {/* #162 — TOOLBAR (template:258-263): primary create + spacer + catalog toggle + reload. */}
      <div className="mcpk-toolbar">
        {/* #160 — primary action: open the (collapsed) create form. */}
        <button className="btn accent" type="button" onClick={() => { setShowCreate((s) => !s); setCreateErr(""); }} data-testid="key-new-toggle">
          {showCreate ? "✕ Đóng" : "+ Tạo key mới"}
        </button>
        <span className="mcpk-spacer" />
        <button className="btn" type="button" aria-pressed={showAudit} onClick={() => setShowAudit((s) => !s)} data-testid="audit-toggle">
          {showAudit ? "Ẩn danh mục tool" : "Xem danh mục tool"}
        </button>
        <button className="btn ghost" type="button" onClick={reload} data-testid="keys-reload">↻ Tải lại</button>
      </div>

      {/* #164 — render order COPIED from template/mcp-key.html: key-once (created) → the
          CREATE PANEL directly under the toolbar → then the keys list. (Was: list first,
          then key-once + create at the bottom — the "có giống mẫu đâu" mismatch.) */}

      {/* key shown ONCE after create (template #created, L266-279) — under the toolbar so
          a fresh key is seen immediately. #128 MASK + reveal/copy/dismiss unchanged. */}
      {justCreated && (
        <div className="panel" style={{ padding: "12px 14px", marginTop: 12, borderColor: "var(--accent)" }} data-testid="key-once">
          <div className="kicker pos" style={{ marginBottom: 6 }}>✓ Đã tạo · sao chép key NGAY (chỉ hiện một lần)</div>
          {/* #128 — the key value is MASKED by default; reveal-on-demand (security hygiene).
              Copy works without revealing (clipboard, never on-screen). */}
          <code className="key-once-token" data-testid="key-once-token" style={{ fontFamily: "var(--mono)", wordBreak: "break-all" }}>
            {keyRevealed ? justCreated.key : maskKey(justCreated.key)}
          </code>
          <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn sm" type="button" data-testid="key-once-reveal"
              onClick={() => setKeyRevealed((r) => !r)} aria-pressed={keyRevealed}>
              {keyRevealed ? "🙈 Ẩn" : "👁 Hiện"}
            </button>
            <button className="btn sm" type="button" data-testid="key-once-copy"
              onClick={() => copyText(justCreated.key, "Đã sao chép key vào clipboard")}>Sao chép</button>
            <button className="btn sm" type="button" data-testid="key-once-dismiss"
              onClick={() => setJustCreated(null)}>Đã lưu, ẩn đi</button>
          </div>
          <div className="hint faint" style={{ marginTop: 6 }}>Sau khi ẩn, key không hiện lại — chỉ còn nhãn + phạm vi trong danh sách.</div>
        </div>
      )}

      {/* CREATE PANEL — COPIED 1:1 from template #createPanel (L281-299), dark palette.
          Directly under the toolbar (template position), collapsed by default (#160). */}
      {showCreate && (
        <section className="panel mcpk-create-panel" data-testid="key-create-form">
          <div className="mcpk-ph">
            <span className="t">Tạo key mới</span>
            <span className="mcpk-ph-close" onClick={() => { setShowCreate(false); setCreateErr(""); }} data-testid="mcpk-create-close" role="button" tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter") { setShowCreate(false); setCreateErr(""); } }}>✕ đóng</span>
          </div>
          <form className="mcpk-pb" onSubmit={onCreate}>
            <div className="mcpk-field">
              <label className="mcpk-flabel">Nhãn key <span className="mcpk-fhint">— tên gợi nhớ, vd "finance-agent" (tối đa 80 ký tự)</span></label>
              <input
                type="text"
                className="finput"
                placeholder="Nhãn (vd: finance-agent)"
                value={label}
                maxLength={80}
                onChange={(e) => setLabel(e.target.value)}
                data-testid="key-label-input"
              />
            </div>
            <div className="mcpk-field" style={{ marginBottom: 18 }} data-testid="scope-seam">
              <label className="mcpk-flabel">Phạm vi <span className="mcpk-fhint">— chọn domain hoặc tool lẻ mà key này được thấy</span></label>
              {catStatus === "loading" && <div className="hint faint" data-testid="scope-cat-loading">Đang tải danh mục tool…</div>}
              {catStatus === "error" && (
                <div className="hint neg" data-testid="scope-cat-error">Không tải được danh mục: {catErr}.
                  <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={catReload}>Thử lại</button>
                </div>
              )}
              {catStatus === "ready" && catalog && (
                <McpScopeEditor catalog={catalog} scope={createScope} onChange={setCreateScope} />
              )}
            </div>
            {createErr && <div className="hint neg" data-testid="create-error">⚠ {createErr}</div>}
            <div className="mcpk-editor-actions">
              <button className="btn accent" type="submit" disabled={creating} data-testid="key-create-btn">
                {creating ? "Đang tạo…" : "Tạo key"}
              </button>
              <button className="btn" type="button" onClick={() => { setShowCreate(false); setCreateErr(""); }}>Huỷ</button>
            </div>
          </form>
        </section>
      )}

      {/* keylist header — eyebrow "Keys đang có" + count (template L302-305). */}
      {status === "ready" && (
        <div className="mcpk-keylist-head" data-testid="mcpk-keylist-head">
          <span className="mcpk-eyebrow">Keys đang có</span>
          <span className="mcpk-eyebrow">{keys.length} key</span>
        </div>
      )}

      {/* ───────── KEYS-FIRST (#160): the list is the top, daily-task content ───────── */}
      {status === "loading" && (
        <div data-testid="keys-loading" aria-busy="true" style={{ marginTop: 12 }}>
          {Array.from({ length: 2 }).map((_, i) => (
            <div className="panel" key={i} style={{ padding: "12px 14px", marginTop: 8 }} aria-hidden="true">
              <div className="sk-line" style={{ width: "30%" }} />
              <div className="sk-line" style={{ width: "60%", marginTop: 8 }} />
            </div>
          ))}
        </div>
      )}

      {status === "error" && (
        <div className="hint neg" style={{ marginTop: 12, padding: "12px 14px" }} data-testid="keys-error">
          Không tải được danh sách key: {errMsg}.
          <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {/* #164b — empty-state block removed per user ("bỏ luôn phần này đi"): when 0 keys,
          the eyebrow "Keys đang có · 0 key" + the toolbar "+ Tạo key mới" are signal enough. */}

      {status === "ready" && keys.length > 0 && (
        <div data-testid="keys-list" style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
          {keys.map((k) => (
            <div className="panel" key={k.key} style={{ padding: "12px 14px" }} data-testid={`key-row-${k.key}`}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span className="mcpk-keylabel" data-testid={`key-label-${k.key}`}>
                  <span className="mcpk-keyglyph" aria-hidden="true">⚷</span>{k.label}
                </span>
                <span className="tagchip" data-testid={`key-toolcount-${k.key}`} title="số tool key này thấy (BE tính)">
                  {k.toolCount} tool
                </span>
                <span className="hint faint" style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
                  tạo {relativeTime(k.createdAt)}
                </span>
                <span className="sp" style={{ flex: 1 }} />
                {editKey !== k.key && (
                  <button className="btn sm" type="button" onClick={() => startEdit(k)} data-testid={`key-edit-${k.key}`}>Sửa phạm vi</button>
                )}
                {confirmDel === k.key ? (
                  <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }} data-testid={`confirm-del-${k.key}`}>
                    <span className="hint neg">Xoá key này?</span>
                    <button className="btn sm neg" type="button" disabled={deletingKey === k.key}
                      onClick={() => onDelete(k.key)} data-testid={`confirm-yes-${k.key}`}>
                      {deletingKey === k.key ? "Đang xoá…" : "Xoá"}
                    </button>
                    <button className="btn sm" type="button" onClick={() => setConfirmDel(null)} data-testid={`confirm-no-${k.key}`}>Huỷ</button>
                  </span>
                ) : (
                  <button className="btn sm" type="button" onClick={() => { setConfirmDel(k.key); setDeleteErr(""); }} data-testid={`key-del-${k.key}`}>Xoá</button>
                )}
              </div>
              {/* scope summary (render-only) — #162: domains/loose-tools as TAG-CHIPS. */}
              <div className="mcpk-scope-sum" data-testid={`key-scope-${k.key}`}>
                <span className="k">domain:</span>{" "}
                {k.scope.domains.length
                  ? k.scope.domains.map((d) => <span className="mcpk-tag" key={d}>{d}</span>)
                  : <span className="k">—</span>}
                {" · "}
                <span className="k">tool lẻ:</span>{" "}
                {k.scope.tools.length
                  ? k.scope.tools.map((t) => <span className="mcpk-tag" key={t}>{t}</span>)
                  : <span className="k">—</span>}
              </div>

              {/* #162 — APERTURE bar (signature): per-domain on/off coverage, REAL catalog. */}
              {catStatus === "ready" && catalog && (() => {
                const ap = computeAperture(k.scope, catalog);
                return (
                  <div className="mcpk-aperture" data-testid={`key-aperture-${k.key}`}>
                    <div className="mcpk-meterline">
                      <span className="num"><b data-testid={`aperture-granted-${k.key}`}>{ap.granted}</b> / {ap.total} tool trong tầm nhìn của key</span>
                      <span className="legend">▨ trong phạm vi</span>
                    </div>
                    <div className="mcpk-bar" role="img" aria-label={`${ap.granted} trên ${ap.total} tool trong phạm vi`}>
                      {ap.segs.map((s) => (
                        <span key={s.domain} style={{ display: "contents" }}>
                          {s.on > 0 && <i className="seg on" style={{ flex: s.on }} title={`${s.domain}: ${s.on} tool`} />}
                          {s.off > 0 && <i className="seg off" style={{ flex: s.off }} title={`${s.domain}: ${s.off} tool ngoài phạm vi`} />}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* inline scope EDIT (part-2) */}
              {editKey === k.key && (
                <div style={{ marginTop: 10, borderTop: "1px solid var(--line-2)", paddingTop: 10 }} data-testid={`edit-scope-${k.key}`}>
                  {catStatus === "ready" && catalog ? (
                    <McpScopeEditor catalog={catalog} scope={editScope} onChange={setEditScope} />
                  ) : (
                    <div className="hint faint">Đang tải danh mục tool…</div>
                  )}
                  {editErr && <div className="hint neg" style={{ marginTop: 4 }} data-testid={`edit-error-${k.key}`}>⚠ {editErr}</div>}
                  <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                    <button className="btn sm acc" type="button" disabled={savingEdit} onClick={onSaveEdit} data-testid={`edit-save-${k.key}`}>
                      {savingEdit ? "Đang lưu…" : "Lưu phạm vi"}
                    </button>
                    <button className="btn sm" type="button" onClick={() => setEditKey(null)} data-testid={`edit-cancel-${k.key}`}>Huỷ</button>
                  </div>
                </div>
              )}

              {deleteErr && confirmDel === k.key && <div className="hint neg" style={{ marginTop: 4 }} data-testid={`del-error-${k.key}`}>⚠ {deleteErr}</div>}
            </div>
          ))}
        </div>
      )}

      {/* ───────── CONNECT — reference info, collapsed (#160) ───────── */}
      <div className="panel" style={{ padding: "10px 14px", marginTop: 12 }} data-testid="connect-hint">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div className="kicker">Kết nối</div>
          <span className="hint faint" style={{ fontSize: 11 }}>endpoint + header để agent kết nối</span>
          <span className="sp" style={{ flex: 1 }} />
          <button className="btn sm" type="button" onClick={() => setShowConnect((s) => !s)} data-testid="connect-toggle">
            {showConnect ? "Ẩn" : "Xem"}
          </button>
        </div>
        {showConnect && (
          <div style={{ marginTop: 8 }} data-testid="connect-body">
            <div className="hint" style={{ lineHeight: 1.6 }}>
              Endpoint MCP: <span className="acc" style={{ fontFamily: "var(--mono)" }} data-testid="mcp-endpoint">{MCP_BASE}/&lt;server&gt;/mcp</span>
              <br />
              Truyền key qua header <span className="acc" style={{ fontFamily: "var(--mono)" }} data-testid="key-header">X-MCP-Key</span> trên endpoint đó.
            </div>
            <div style={{ position: "relative", marginTop: 8 }}>
              <button
                className="btn sm"
                type="button"
                style={{ position: "absolute", top: 6, right: 6 }}
                onClick={() => copyText(CONFIG_SNIPPET, "Đã sao chép cấu hình")}
                data-testid="connect-copy"
              >
                Sao chép
              </button>
              <pre className="key-once-token" style={{ margin: 0, color: "var(--tx-1)", borderColor: "var(--line-2)" }} data-testid="mcp-json-snippet">{CONFIG_SNIPPET}</pre>
            </div>
          </div>
        )}
      </div>

      {/* catalog-audit (the user's 2nd reason: eyeball which tools exist/are useful). */}
      {showAudit && (
        <div className="panel" style={{ padding: "12px 14px", marginTop: 12 }} data-testid="audit-panel">
          <div className="kicker" style={{ marginBottom: 6 }}>Danh mục tool</div>
          {catStatus === "loading" && <div className="hint faint" data-testid="audit-loading">Đang tải danh mục…</div>}
          {catStatus === "error" && (
            <div className="hint neg" data-testid="audit-error">Không tải được danh mục: {catErr}.
              <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={catReload}>Thử lại</button>
            </div>
          )}
          {catStatus === "ready" && catalog && <McpCatalogAudit catalog={catalog} />}
        </div>
      )}

      {/* #162 — TOAST: fixed bottom-center pill for copy / update / delete feedback. */}
      {toastMsg && (
        <div className="mcpk-toast show" role="status" aria-live="polite" data-testid="mcpk-toast">
          <span className="ok" aria-hidden="true">✓</span>{toastMsg}
        </div>
      )}
    </section>
  );
}
