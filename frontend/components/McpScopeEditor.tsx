"use client";
/* ============================================================
   McpScopeEditor (#88-part-2 · #128 polish · #129 tool-detail) — tick a scope for an MCP
   key. Shows ALL catalog tools grouped BY DOMAIN (`server`); tick a whole DOMAIN (selects
   all its tools) AND/OR tick INDIVIDUAL tools — BOTH (the saved scope = {domains, tools}).
   Also the catalog AUDIT: each tool's name + description + per-domain counts + the honest
   capability boundary.

   #129 — each tool row is EXPANDABLE: collapsed = the 1-line label (lean default); expand
   → fullDescription + a params TABLE (name · type · required · default). honest-empty: a
   no-arg tool → "không tham số" (params:[]).

   RENDER-ONLY against the live catalog; the scope math is pure (lib/mcpScope).
   ============================================================ */
import { useMemo, useState } from "react";
import type { McpScope, McpCatalog, McpCatalogTool } from "@/lib/types";
import {
  groupByDomain, isDomainSelected, isToolSelected, toggleDomain, toggleTool, resolvedTools,
} from "@/lib/mcpScope";

/** #129 — the expandable detail body for one tool: full docstring + a params table
 *  (honest-empty → "không tham số"). Shared by the editor + the audit. */
function ToolDetail({ tool }: { tool: McpCatalogTool }) {
  return (
    <div className="tool-detail" data-testid={`tool-detail-${tool.name}`}>
      {tool.fullDescription && (
        <pre className="tool-fulldesc" data-testid={`tool-fulldesc-${tool.name}`}>{tool.fullDescription}</pre>
      )}
      {tool.params.length === 0 ? (
        <div className="hint faint tool-noparams" data-testid={`tool-noparams-${tool.name}`}>không tham số</div>
      ) : (
        <table className="tool-params" data-testid={`tool-params-${tool.name}`}>
          <thead>
            <tr><th>Tham số</th><th>Kiểu</th><th>Bắt buộc</th><th>Mặc định</th></tr>
          </thead>
          <tbody>
            {tool.params.map((p) => (
              <tr key={p.name} data-testid={`tool-param-${tool.name}-${p.name}`}>
                <td className="tp-name">{p.name}</td>
                <td className="tp-type">{p.type}</td>
                <td className="tp-req">{p.required ? <span className="acc">có</span> : <span className="faint">không</span>}</td>
                <td className="tp-default faint">{p.default === undefined ? "—" : String(p.default)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** the small ⓘ expand toggle shown on every tool row (editor + audit). */
function DetailToggle({ open, onToggle, name }: { open: boolean; onToggle: () => void; name: string }) {
  return (
    <button
      type="button"
      className={`tool-info${open ? " on" : ""}`}
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggle(); }}
      data-testid={`tool-expand-${name}`}
      aria-expanded={open}
      aria-label={open ? `Ẩn chi tiết ${name}` : `Xem chi tiết ${name}`}
      title="Chi tiết tool (mô tả đầy đủ + tham số)"
    >
      {open ? "▾" : "ⓘ"}
    </button>
  );
}

export function McpScopeEditor({
  catalog, scope, onChange,
}: {
  catalog: McpCatalog;
  scope: McpScope;
  onChange: (next: McpScope) => void;
}) {
  const groups = useMemo(() => groupByDomain(catalog.tools), [catalog.tools]);
  const selectedCount = useMemo(() => resolvedTools(scope, catalog.tools).length, [scope, catalog.tools]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (name: string) => setExpanded((prev) => {
    const next = new Set(prev);
    next.has(name) ? next.delete(name) : next.add(name);
    return next;
  });

  return (
    <div className="scope-editor" data-testid="scope-editor">
      <div className="hint faint" style={{ marginBottom: 8 }}>
        Đã chọn <b className="acc" data-testid="scope-selected-count">{selectedCount}</b> / {catalog.tools.length} tool
        {" "}({scope.domains.length} domain + {scope.tools.length} tool lẻ)
      </div>

      {groups.map(({ domain, tools }) => {
        const domainOn = isDomainSelected(scope, domain);
        const count = catalog.counts.byMount[domain] ?? tools.length;
        return (
          <div className="scope-domain" key={domain} data-testid={`scope-domain-${domain}`}>
            <label className="scope-domain-head">
              <input
                type="checkbox"
                checked={domainOn}
                onChange={() => onChange(toggleDomain(scope, domain, catalog.tools))}
                data-testid={`domain-check-${domain}`}
              />
              <span className="scope-domain-name acc">{domain}</span>
              <span className="tagchip" data-testid={`domain-count-${domain}`}>{count} tool</span>
            </label>
            <div className="scope-tools">
              {tools.map((t) => {
                const isOpen = expanded.has(t.name);
                return (
                  <div className="scope-tool-wrap" key={t.name}>
                    <label className="scope-tool" title={t.description} data-testid={`tool-row-${t.name}`}>
                      <input
                        type="checkbox"
                        checked={isToolSelected(scope, t)}
                        onChange={() => onChange(toggleTool(scope, t, catalog.tools))}
                        data-testid={`tool-check-${t.name}`}
                      />
                      <span className="scope-tool-name">{t.name}</span>
                      {t.capability !== "read" && <span className="tagchip mid" style={{ fontSize: 9 }}>{t.capability}</span>}
                      <span className="scope-tool-desc hint faint">{t.description}</span>
                      <DetailToggle open={isOpen} onToggle={() => toggle(t.name)} name={t.name} />
                    </label>
                    {isOpen && <ToolDetail tool={t} />}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** The catalog AUDIT view (read-only) — the user eyeballs which tools exist + the honest
 *  capability boundary. Separate from the editor (no ticks). #129 — each tool expands to
 *  its full docstring + params table. */
export function McpCatalogAudit({ catalog }: { catalog: McpCatalog }) {
  const groups = useMemo(() => groupByDomain(catalog.tools), [catalog.tools]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (name: string) => setExpanded((prev) => {
    const next = new Set(prev);
    next.has(name) ? next.delete(name) : next.add(name);
    return next;
  });

  return (
    <div data-testid="catalog-audit">
      <div className="hint faint" style={{ marginBottom: 8 }} data-testid="audit-counts">
        {catalog.tools.length} tool · {groups.length} domain · {catalog.counts.read} read / {catalog.counts.write} propose
      </div>
      {/* honest capability boundary — what each capability class can/can't do */}
      <div className="panel" style={{ padding: "10px 12px", marginBottom: 10 }} data-testid="audit-boundary">
        <div className="kicker" style={{ marginBottom: 4 }}>Ranh giới quyền</div>
        {Object.entries(catalog.capabilityBoundary).map(([cap, text]) => (
          <div className="hint faint" key={cap} style={{ lineHeight: 1.5 }} data-testid={`boundary-${cap}`}>
            <span className="acc" style={{ fontFamily: "var(--mono)" }}>{cap}</span>: {text}
          </div>
        ))}
      </div>
      {groups.map(({ domain, tools }) => (
        <div className="scope-domain" key={domain} data-testid={`audit-domain-${domain}`}>
          <div className="scope-domain-head" style={{ cursor: "default" }}>
            <span className="scope-domain-name acc">{domain}</span>
            <span className="tagchip">{catalog.counts.byMount[domain] ?? tools.length} tool</span>
          </div>
          <div className="scope-tools">
            {tools.map((t) => {
              const isOpen = expanded.has(t.name);
              return (
                <div className="scope-tool-wrap" key={t.name}>
                  <div className="scope-tool" data-testid={`audit-tool-${t.name}`}>
                    <span className="scope-tool-name">{t.name}</span>
                    {t.capability !== "read" && <span className="tagchip mid" style={{ fontSize: 9 }}>{t.capability}</span>}
                    <span className="scope-tool-desc hint faint">{t.description}</span>
                    <DetailToggle open={isOpen} onToggle={() => toggle(t.name)} name={t.name} />
                  </div>
                  {isOpen && <ToolDetail tool={t} />}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
