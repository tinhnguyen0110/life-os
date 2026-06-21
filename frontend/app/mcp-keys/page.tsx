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
import { useState } from "react";
import { useMcpKeys } from "@/lib/useMcpKeys";
import { useMcpCatalog } from "@/lib/useMcpCatalog";
import { apiBase, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { McpScopeEditor, McpCatalogAudit } from "@/components/McpScopeEditor";
import { EMPTY_SCOPE } from "@/lib/mcpScope";
import type { McpKey, McpScope } from "@/lib/types";

/** the MCP endpoint base (mounts live at <base>/mcp/<server>/mcp). */
const MCP_BASE = `${apiBase}/mcp`;

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

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = label.trim();
    if (!trimmed) { setCreateErr("Nhập nhãn cho key"); return; }
    setCreateErr(""); setCreating(true);
    try {
      const row = await create({ label: trimmed, scope: createScope });
      setJustCreated(row);
      setLabel("");
      setCreateScope(EMPTY_SCOPE);
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
    } catch (err) {
      setDeleteErr(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setDeletingKey(null);
    }
  }

  return (
    <section className="view" data-screen="MCPKEYS" data-testid="mcp-keys-screen">
      <div className="vtitle">
        <h1>MCP Keys</h1>
        <span className="sub">cấp key cho agent · mỗi key chỉ thấy các tool trong phạm vi của nó</span>
        <span className="sp" />
        <button className="btn" type="button" onClick={() => setShowAudit((s) => !s)} data-testid="audit-toggle">
          {showAudit ? "Ẩn danh mục tool" : "Xem danh mục tool"}
        </button>
        <button className="btn" type="button" onClick={reload} data-testid="keys-reload">↻ Tải lại</button>
      </div>

      {/* connect-hint: endpoint + X-MCP-Key header (the #87 mechanism). */}
      <div className="panel" style={{ padding: "12px 14px" }} data-testid="connect-hint">
        <div className="kicker" style={{ marginBottom: 6 }}>Kết nối</div>
        <div className="hint" style={{ lineHeight: 1.6 }}>
          Endpoint MCP: <span className="acc" style={{ fontFamily: "var(--mono)" }} data-testid="mcp-endpoint">{MCP_BASE}/&lt;server&gt;/mcp</span>
          <br />
          Truyền key qua header <span className="acc" style={{ fontFamily: "var(--mono)" }} data-testid="key-header">X-MCP-Key</span> trên endpoint đó.
        </div>
        <pre className="key-once-token" style={{ marginTop: 8, color: "var(--tx-1)", borderColor: "var(--line-2)" }} data-testid="mcp-json-snippet">{`{
  "mcpServers": {
    "lifeos-read": {
      "url": "${MCP_BASE}/read/mcp",
      "headers": { "X-MCP-Key": "<your-key>" }
    }
  }
}`}</pre>
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

      {/* create form (label + scope editor) */}
      <form className="panel" style={{ padding: "12px 14px", marginTop: 12 }} onSubmit={onCreate} data-testid="key-create-form">
        <div className="kicker" style={{ marginBottom: 6 }}>Tạo key mới</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="text"
            placeholder="Nhãn (vd: finance-agent)"
            value={label}
            maxLength={80}
            onChange={(e) => setLabel(e.target.value)}
            data-testid="key-label-input"
            style={{ flex: 1, minWidth: 200 }}
          />
          <button className="btn acc" type="submit" disabled={creating} data-testid="key-create-btn">
            {creating ? "Đang tạo…" : "Tạo key"}
          </button>
        </div>

        {/* scope editor — tick domains + tools (part-2). honest about the catalog state. */}
        <div style={{ marginTop: 10 }} data-testid="scope-seam">
          <div className="kicker" style={{ marginBottom: 4 }}>Phạm vi (chọn tool key được thấy)</div>
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

        {createErr && <div className="hint neg" style={{ marginTop: 6 }} data-testid="create-error">⚠ {createErr}</div>}
      </form>

      {/* key shown ONCE after create */}
      {justCreated && (
        <div className="panel" style={{ padding: "12px 14px", marginTop: 12, borderColor: "var(--accent)" }} data-testid="key-once">
          <div className="kicker pos" style={{ marginBottom: 6 }}>✓ Đã tạo · sao chép key NGAY (chỉ hiện một lần)</div>
          <code className="key-once-token" data-testid="key-once-token" style={{ fontFamily: "var(--mono)", wordBreak: "break-all" }}>{justCreated.key}</code>
          <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
            <button className="btn sm" type="button" data-testid="key-once-copy"
              onClick={() => navigator.clipboard?.writeText(justCreated.key)}>Sao chép</button>
            <button className="btn sm" type="button" data-testid="key-once-dismiss"
              onClick={() => setJustCreated(null)}>Đã lưu, ẩn đi</button>
          </div>
          <div className="hint faint" style={{ marginTop: 6 }}>Sau khi ẩn, key không hiện lại — chỉ còn nhãn + phạm vi trong danh sách.</div>
        </div>
      )}

      {/* list */}
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

      {status === "ready" && keys.length === 0 && (
        <div className="panel" style={{ padding: "20px", marginTop: 12 }} data-testid="keys-empty">
          <div className="hint faint">Chưa có key nào. Tạo một key ở trên để cấp cho agent.</div>
        </div>
      )}

      {status === "ready" && keys.length > 0 && (
        <div data-testid="keys-list" style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
          {keys.map((k) => (
            <div className="panel" key={k.key} style={{ padding: "12px 14px" }} data-testid={`key-row-${k.key}`}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span style={{ fontWeight: 600 }} data-testid={`key-label-${k.key}`}>{k.label}</span>
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
              {/* scope summary (render-only) */}
              <div className="hint faint" style={{ marginTop: 6, fontFamily: "var(--mono)", fontSize: 11 }} data-testid={`key-scope-${k.key}`}>
                domain: {k.scope.domains.length ? k.scope.domains.join(", ") : "—"} · tool: {k.scope.tools.length ? k.scope.tools.join(", ") : "—"}
              </div>

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
    </section>
  );
}
