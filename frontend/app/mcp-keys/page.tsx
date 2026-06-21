"use client";
/* ============================================================
   /mcp-keys (#88 · MCPKEYS) — manage per-key MCP tool scoping. An agent connects
   with a key; the key sees only the tools its scope grants (a whole DOMAIN's tools +
   explicit tools). This screen: LIST keys · CREATE (label + scope) · DELETE · a
   connect-hint (endpoint + how to pass the key) · the tool-catalog AUDIT + scope editor.

   #88 status: the CRUD half is LIVE (this screen). The SCOPE EDITOR + catalog AUDIT
   need GET /mcp_keys/catalog (list_tools_catalog over REST) which is being added — a
   CLEAN SEAM is left for it below ("scope-editor seam"). Until then, create makes a
   sees-nothing key (scope {[],[]}) the user scopes once the editor lands. RENDER-ONLY:
   the backend owns the store + computes toolCount.
   ============================================================ */
import { useState } from "react";
import { useMcpKeys } from "@/lib/useMcpKeys";
import { apiBase, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { McpKey } from "@/lib/types";

/** the MCP endpoint base (mounts live at <base>/mcp/<server>/mcp). */
const MCP_BASE = `${apiBase}/mcp`;

export default function McpKeysPage() {
  const { keys, status, errMsg, reload, create, remove } = useMcpKeys();

  // create form
  const [label, setLabel] = useState("");
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState("");
  // the key shown ONCE right after creation (the only time the full token is surfaced).
  const [justCreated, setJustCreated] = useState<McpKey | null>(null);

  // in-page delete confirm (NOT a JS confirm() — that blocks the browser extension).
  const [confirmDel, setConfirmDel] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [deleteErr, setDeleteErr] = useState("");

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = label.trim();
    if (!trimmed) { setCreateErr("Nhập nhãn cho key"); return; }
    setCreateErr(""); setCreating(true);
    try {
      // scope-editor seam: until GET /mcp_keys/catalog lands, create a sees-nothing key
      // (scope defaults to {[],[]}); the user scopes it via the editor once available.
      const row = await create({ label: trimmed });
      setJustCreated(row);
      setLabel("");
    } catch (err) {
      setCreateErr(err instanceof ApiError ? (err.hint ? `${err.message} (${err.hint})` : err.message) : (err as Error).message);
    } finally {
      setCreating(false);
    }
  }

  async function onDelete(key: string) {
    setDeleteErr(""); setDeletingKey(key);
    try {
      await remove(key);
      setConfirmDel(null);
      if (justCreated?.key === key) setJustCreated(null);
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
        <button className="btn" type="button" onClick={reload} data-testid="keys-reload">↻ Tải lại</button>
      </div>

      {/* connect-hint: endpoint + how to pass the key (mechanism placeholder until #87). */}
      <div className="panel" style={{ padding: "12px 14px" }} data-testid="connect-hint">
        <div className="kicker" style={{ marginBottom: 6 }}>Kết nối</div>
        <div className="hint" style={{ lineHeight: 1.5 }}>
          Endpoint MCP: <span className="acc" style={{ fontFamily: "var(--mono)" }} data-testid="mcp-endpoint">{MCP_BASE}/&lt;server&gt;/mcp</span>
          <br />
          Truyền key qua <span className="mid">cơ chế đang chốt (query vs header — xác nhận với bộ lọc /mcp)</span>.
          Mẫu <span style={{ fontFamily: "var(--mono)" }}>.mcp.json</span> sẽ hiện đầy đủ khi cơ chế truyền key được chốt.
        </div>
      </div>

      {/* create form */}
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
        {/* scope-editor seam — the per-domain/per-tool tick + catalog audit drops in here. */}
        <div className="hint faint" style={{ marginTop: 8 }} data-testid="scope-seam">
          Phạm vi (chọn domain + tool) sẽ thêm ở đây khi danh mục tool sẵn sàng — key tạo bây giờ mặc định <b>không thấy tool nào</b>, bạn cấp phạm vi sau.
        </div>
        {createErr && <div className="hint neg" style={{ marginTop: 6 }} data-testid="create-error">⚠ {createErr}</div>}
      </form>

      {/* key shown ONCE after create (the only time the full token appears). */}
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
              {/* scope summary (render-only). The EDITOR to change it drops into the seam. */}
              <div className="hint faint" style={{ marginTop: 6, fontFamily: "var(--mono)", fontSize: 11 }} data-testid={`key-scope-${k.key}`}>
                domain: {k.scope.domains.length ? k.scope.domains.join(", ") : "—"} · tool: {k.scope.tools.length ? k.scope.tools.join(", ") : "—"}
              </div>
              {deleteErr && confirmDel === k.key && <div className="hint neg" style={{ marginTop: 4 }} data-testid={`del-error-${k.key}`}>⚠ {deleteErr}</div>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
