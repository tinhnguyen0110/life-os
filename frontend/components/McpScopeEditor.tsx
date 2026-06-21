"use client";
/* ============================================================
   McpScopeEditor (#88-part-2) — tick a scope for an MCP key. Shows ALL catalog tools
   grouped BY DOMAIN (`server`); tick a whole DOMAIN (selects all its tools) AND/OR
   tick INDIVIDUAL tools — BOTH (the saved scope = {domains, tools}). Also the catalog
   AUDIT: each tool's name + description + per-domain counts + the honest capability
   boundary. RENDER-ONLY against the live catalog; the scope math is pure (lib/mcpScope).
   ============================================================ */
import { useMemo } from "react";
import type { McpScope, McpCatalog } from "@/lib/types";
import {
  groupByDomain, isDomainSelected, isToolSelected, toggleDomain, toggleTool, resolvedTools,
} from "@/lib/mcpScope";

export function McpScopeEditor({
  catalog, scope, onChange,
}: {
  catalog: McpCatalog;
  scope: McpScope;
  onChange: (next: McpScope) => void;
}) {
  const groups = useMemo(() => groupByDomain(catalog.tools), [catalog.tools]);
  const selectedCount = useMemo(() => resolvedTools(scope, catalog.tools).length, [scope, catalog.tools]);

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
              {tools.map((t) => (
                <label className="scope-tool" key={t.name} title={t.description} data-testid={`tool-row-${t.name}`}>
                  <input
                    type="checkbox"
                    checked={isToolSelected(scope, t)}
                    onChange={() => onChange(toggleTool(scope, t, catalog.tools))}
                    data-testid={`tool-check-${t.name}`}
                  />
                  <span className="scope-tool-name">{t.name}</span>
                  {t.capability !== "read" && <span className="tagchip mid" style={{ fontSize: 9 }}>{t.capability}</span>}
                  <span className="scope-tool-desc hint faint">{t.description}</span>
                </label>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** The catalog AUDIT view (read-only) — the user eyeballs which tools exist + the honest
 *  capability boundary. Separate from the editor (no ticks) for the "what tools are
 *  useful" 2nd reason. */
export function McpCatalogAudit({ catalog }: { catalog: McpCatalog }) {
  const groups = useMemo(() => groupByDomain(catalog.tools), [catalog.tools]);
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
            {tools.map((t) => (
              <div className="scope-tool" key={t.name} data-testid={`audit-tool-${t.name}`}>
                <span className="scope-tool-name">{t.name}</span>
                {t.capability !== "read" && <span className="tagchip mid" style={{ fontSize: 9 }}>{t.capability}</span>}
                <span className="scope-tool-desc hint faint">{t.description}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
