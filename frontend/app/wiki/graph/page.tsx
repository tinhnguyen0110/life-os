"use client";
/* ============================================================
   W4 — Graph Explorer · /wiki/graph. Ported from mock screens-wiki.js
   SCREENS.graph + wiki.css (W4 block). Ego-graph (1–2 hop around ONE center
   note) — see neighbors + clusters by eye. NOT a global graph (>5k notes = Phase 2).

   Live from GET /wiki/graph?note=X&depth=N (custom SVG, no heavy lib).
   - The API returns {center, nodes, edges, clusters} with NO x/y → the FE computes
     a deterministic RADIAL ego-layout client-side (center fixed at middle; neighbors
     placed on rings by hop distance, evenly spread by index). Node size ∝ degree,
     color by status; edges typed (label = edge.type), ghost edges dashed.
   - Pick the center note via the FTS search picker (no center → "chọn note tâm" prompt).
   - depth 1↔2 toggle. Node click → /wiki/[id].
   - clusters is EMPTY at M1 (no embedded clustering) → honest empty cluster-hint.
   States: idle (no center) · loading · error (404 center) · ready.
   ============================================================ */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useWikiGraph } from "@/lib/useWiki";
import { searchWiki } from "@/lib/api";
import { Icon } from "@/lib/icons";
import type { WikiGraphNode, WikiGraphEdge, WikiSearchHit, WikiStatus } from "@/lib/types";

const W = 760;
const H = 440;
const STATUS_COLOR: Record<WikiStatus, string> = {
  evergreen: "var(--green)",
  developing: "var(--blue)",
  fleeting: "var(--amber)",
};

/** Deterministic radial ego-layout. center → middle; every other node on a ring
 *  (r=0.30 of the smaller half-axis), spread evenly by its index. The API has no
 *  coords, so we synthesize them — same input → same layout (no Math.random). */
function layout(nodes: WikiGraphNode[], center: number): Map<number, { x: number; y: number }> {
  const pos = new Map<number, { x: number; y: number }>();
  const cx = 50, cy = 48; // percent of viewBox
  pos.set(center, { x: cx, y: cy });
  const others = nodes.filter((n) => n.id !== center);
  const ring = 34; // percent radius
  const n = others.length || 1;
  others.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    pos.set(node.id, {
      x: cx + ring * Math.cos(angle),
      y: cy + ring * 0.92 * Math.sin(angle),
    });
  });
  return pos;
}

function WikiGraphInner() {
  const router = useRouter();
  const sp = useSearchParams();

  const [center, setCenter] = useState<number | null>(null);
  const [depth, setDepth] = useState<number>(2);
  // A1c graph polish: status filter (dims non-matching nodes) + orphan highlight.
  const [statusFilter, setStatusFilter] = useState<"all" | WikiStatus>("all");
  const [highlightOrphan, setHighlightOrphan] = useState(false);

  // seed center from ?note= query (so /wiki/graph?note=12 deep-links, e.g. from a note's "graph quanh note").
  useEffect(() => {
    const raw = sp.get("note");
    if (raw != null) {
      const n = parseInt(raw, 10);
      if (!Number.isNaN(n)) setCenter(n);
    }
  }, [sp]);

  const { graph, status, errMsg } = useWikiGraph(center, depth);

  /* ---- center picker (FTS) ---- */
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<WikiSearchHit[]>([]);
  const debRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runSearch = useCallback(async (term: string) => {
    const t = term.trim();
    if (!t) { setHits([]); return; }
    try {
      const res = await searchWiki(t);
      setHits(Array.isArray(res?.data) ? res.data : []);
    } catch {
      setHits([]);
    }
  }, []);
  useEffect(() => {
    if (debRef.current) clearTimeout(debRef.current);
    debRef.current = setTimeout(() => runSearch(q), 250);
    return () => { if (debRef.current) clearTimeout(debRef.current); };
  }, [q, runSearch]);

  const pos = useMemo(
    () => (graph ? layout(graph.nodes, graph.center) : new Map<number, { x: number; y: number }>()),
    [graph],
  );

  const centerNode = graph?.nodes.find((n) => n.id === graph.center) ?? null;

  function chooseCenter(id: number) {
    setCenter(id);
    setQ("");
    setHits([]);
    // reflect in URL (shareable / refresh-stable) without a full nav.
    router.replace(`/wiki/graph?note=${id}`);
  }

  const edge = (e: WikiGraphEdge, i: number) => {
    const a = pos.get(e.source), b = pos.get(e.target);
    if (!a || !b) return null;
    const x1 = (a.x / 100) * W, y1 = (a.y / 100) * H, x2 = (b.x / 100) * W, y2 = (b.y / 100) * H;
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    return (
      <g key={`e-${e.source}-${e.target}-${i}`} data-testid="graph-edge">
        <line
          x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={e.isResolved ? "var(--line-2)" : "var(--amber)"}
          strokeWidth={1.4}
          strokeDasharray={e.isResolved ? undefined : "3 3"}
        />
        <text x={mx} y={my - 3} className="wedge-lbl">{e.type}</text>
      </g>
    );
  };

  const node = (n: WikiGraphNode) => {
    const p = pos.get(n.id);
    if (!p) return null;
    const x = (p.x / 100) * W, y = (p.y / 100) * H;
    const r = 8 + n.degree * 2.4;
    const isCenter = graph != null && n.id === graph.center;
    const col = STATUS_COLOR[n.status] ?? "var(--tx-1)";
    const isOrphan = n.degree === 0 && !isCenter;
    const label = n.title && n.title.length > 22 ? n.title.slice(0, 20) + "…" : (n.title || `#${n.id}`);
    // A1c polish: status filter dims non-matching nodes (center always shown);
    // orphan-highlight ring when toggled. Filter is VISUAL (dim), not removal — keeps
    // the ego-graph topology intact so you see what's filtered out, not a blank.
    const dimmed = statusFilter !== "all" && n.status !== statusFilter && !isCenter;
    const orphanRing = isOrphan || (highlightOrphan && n.degree === 0);
    return (
      <g
        key={`n-${n.id}`}
        className="wgnode clickable"
        transform={`translate(${x},${y})`}
        onClick={() => router.push(`/wiki/${n.id}`)}
        data-testid="graph-node"
        data-node-id={n.id}
        data-center={isCenter || undefined}
        data-dimmed={dimmed || undefined}
        opacity={dimmed ? 0.22 : 1}
      >
        {isCenter && (
          <circle r={r + 6} fill="none" stroke={col} strokeWidth={1.5} strokeDasharray="2 3" opacity={0.6} />
        )}
        <circle
          r={r}
          fill={col}
          fillOpacity={isOrphan ? 0.25 : 1}
          style={isCenter ? { filter: `drop-shadow(0 0 8px ${col})` } : undefined}
        />
        {orphanRing && <circle r={r + 3} fill="none" stroke="var(--red)" strokeWidth={highlightOrphan ? 1.6 : 1} strokeDasharray="2 2" />}
        <text y={r + 13} className="wgnode-lbl" style={isCenter ? { fontWeight: 700, fill: "var(--tx-0)" } : undefined}>
          {label}
        </text>
        <text y={3} textAnchor="middle" className="wgnode-id">{n.id}</text>
      </g>
    );
  };

  return (
    <div data-testid="graph-screen">
      <div className="vtitle">
        <h1>Graph Explorer</h1>
        <span className="sub">
          {graph
            ? `ego-graph quanh #${graph.center} · depth ${depth} · ${graph.nodes.length} nodes`
            : "ego-graph (1–2 hop quanh 1 note) — chọn note tâm"}
        </span>
        <span className="sp" style={{ flex: 1 }} />
        <div className="seg" role="group" aria-label="depth">
          <button type="button" className={depth === 1 ? "on" : ""} onClick={() => setDepth(1)} data-testid="graph-depth-1">depth 1</button>
          <button type="button" className={depth === 2 ? "on" : ""} onClick={() => setDepth(2)} data-testid="graph-depth-2">depth 2</button>
        </div>
      </div>

      {/* center picker */}
      <div className="wsearch" style={{ marginBottom: 12 }}>
        <span className="pr"><Icon name="i-search" /></span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Đổi note tâm — tìm theo title/nội dung (FTS5)…"
          data-testid="graph-search-input"
          aria-label="Chọn note tâm"
        />
      </div>
      {q.trim() && (
        <div className="wsearch-res" data-testid="graph-search-results" style={{ marginTop: -8, marginBottom: 12, borderRadius: 11, borderTop: "1px solid var(--line-2)" }}>
          {hits.length === 0 ? (
            <div className="wsearch-empty">Không có kết quả.</div>
          ) : (
            hits.map((h) => (
              <div
                key={h.id}
                className="wsearch-row"
                data-testid="graph-search-hit"
                onClick={() => chooseCenter(h.id)}
                onKeyDown={(e) => { if (e.key === "Enter") chooseCenter(h.id); }}
                role="button"
                tabIndex={0}
              >
                <span className={`wstatus ${h.status}`}>{h.status}</span>
                <div className="wlr-body">
                  <div className="wlr-t">{h.title ?? <span className="faint">#{h.id}</span>}</div>
                  <div className="wlr-s mut">{h.snippet}</div>
                </div>
                <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10 }}>#{h.id}</span>
              </div>
            ))
          )}
        </div>
      )}

      <div className="wgraph-grid">
        <div className="panel wgraph-canvas">
          <div className="phead">
            <span className="kicker">Ego-graph {graph ? `· #${graph.center} ${centerNode?.title ?? ""}` : ""}</span>
            <span className="sp" style={{ flex: 1 }} />
            <span className="wgleg"><span className="wgl-dot" style={{ background: "var(--green)" }} />evergreen</span>
            <span className="wgleg"><span className="wgl-dot" style={{ background: "var(--blue)" }} />developing</span>
            <span className="wgleg"><span className="wgl-dot" style={{ background: "var(--amber)" }} />fleeting</span>
            <span className="wgleg"><span className="wgl-dot" style={{ border: "1px dashed var(--red)", background: "transparent" }} />orphan</span>
          </div>
          <div className="wgraph-stage">
            {center == null ? (
              <div className="wgraph-empty" data-testid="graph-idle">
                Chọn 1 note tâm ở ô tìm phía trên để vẽ ego-graph 1–2 hop quanh nó.
              </div>
            ) : status === "loading" ? (
              <div className="wgraph-empty" data-testid="graph-loading">Đang dựng graph…</div>
            ) : status === "error" ? (
              <div className="wgraph-empty" data-testid="graph-error" style={{ color: "var(--red)" }}>
                {errMsg || `Không tải được graph cho note #${center}.`}
              </div>
            ) : graph && graph.nodes.length > 0 ? (
              <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "100%" }} data-testid="graph-svg">
                <g className="wedges">{graph.edges.map(edge)}</g>
                <g className="wnodes">{graph.nodes.map(node)}</g>
              </svg>
            ) : (
              <div className="wgraph-empty" data-testid="graph-empty">
                Note #{center} chưa có hàng xóm — chỉ mình nó trong vùng này (degree 0).
              </div>
            )}
          </div>
        </div>

        <div className="wgraph-side">
          {/* A1c polish: filter controls (status dim + orphan highlight) + summary */}
          <div className="panel">
            <div className="phead"><span className="kicker">Bộ lọc & tóm tắt</span></div>
            <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="wfilter-row">
                <span className="mut">Status</span>
                <div className="seg" role="group" aria-label="status filter">
                  {(["all", "evergreen", "developing", "fleeting"] as const).map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={statusFilter === s ? "on" : ""}
                      onClick={() => setStatusFilter(s)}
                      data-testid={`graph-filter-${s}`}
                    >
                      {s === "all" ? "all" : s.slice(0, 4)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="wfilter-row">
                <span className="mut">Highlight orphan</span>
                <button
                  type="button"
                  className={`tab ${highlightOrphan ? "on" : ""}`}
                  onClick={() => setHighlightOrphan((v) => !v)}
                  aria-pressed={highlightOrphan}
                  data-testid="graph-highlight-orphan"
                >
                  {highlightOrphan ? "ON" : "OFF"}
                </button>
              </div>
              <div className="wfilter-row"><span className="mut">Nodes</span><span className="num">{graph?.nodes.length ?? 0}</span></div>
              <div className="wfilter-row"><span className="mut">Edges</span><span className="num">{graph?.edges.length ?? 0}</span></div>
              <div className="wfilter-row"><span className="mut">Depth</span><span className="num">{depth} hop</span></div>
              {centerNode && (
                <div className="wfilter-row"><span className="mut">Tâm</span><span className={`wstatus ${centerNode.status}`}>{centerNode.status}</span></div>
              )}
            </div>
          </div>

          <div className="panel wcluster-box">
            <div className="phead"><span className="kicker">Cluster hint · MOC candidate</span></div>
            {graph && graph.clusters.length > 0 ? (
              graph.clusters.map((c, i) => (
                <div className="wcluster" key={`c-${i}`} data-testid="graph-cluster">
                  <div className="wcluster-top">
                    <b>{c.suggestedTitle ?? `Cụm ${c.size} note`}</b>
                    <span className="wconf">mật độ {(c.density * 100).toFixed(0)}%</span>
                  </div>
                  <div className="wcluster-members">
                    {c.members.map((m) => (
                      <span key={m.id} className="tagchip clickable" onClick={() => router.push(`/wiki/${m.id}`)}>
                        #{m.id} {(m.title || "").slice(0, 14)}
                      </span>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              /* M1: clusters EMPTY (no embedded clustering). Honest empty — no fake MOC suggestion. */
              <div className="wcluster-empty" data-testid="graph-cluster-empty">
                Chưa có cụm. Khoanh vùng cụm dày (ứng viên Map of Content) sẽ đến qua Claude Code (MCP) ở giai đoạn sau —
                AI propose, bạn quyết.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** useSearchParams() must sit under a Suspense boundary (Next App Router prerender
 *  requirement) — wrap the inner client component. */
export default function WikiGraphPage() {
  return (
    <Suspense fallback={<div className="hint" style={{ padding: "24px 4px" }} data-testid="graph-suspense">Đang tải graph…</div>}>
      <WikiGraphInner />
    </Suspense>
  );
}
