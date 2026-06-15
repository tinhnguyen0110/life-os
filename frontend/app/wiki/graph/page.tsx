"use client";
/* ============================================================
   Graph Explorer · /wiki/graph (GLOBAL-GRAPH T2). Obsidian-style: the WHOLE-VAULT
   graph is the DEFAULT view (no ?note=); clicking a node focuses it (local/ego
   mode, ?note=id). Two modes, like Obsidian's global + local.

   - DEFAULT (no ?note=): useWikiGraph(null) → GET /wiki/graph (global) → ALL nodes
     + edges + clusters. Layout = a DETERMINISTIC force-relaxed layout (positions
     seeded by a hash of node id, then a FIXED iteration count — NO Math.random, so
     the same vault always lays out identically).
   - LOCAL (?note=X): useWikiGraph(X) → ego-graph, deterministic RADIAL layout (center
     fixed middle, neighbors on a ring). The existing focus mode, kept intact.
   - Obsidian-parity: node size ∝ degree · color by status (legend) · hover-highlight
     neighbors · click → open note · status-filter + orphan-highlight carried into both.
   - clusters → cluster-hint panel. Honest-empty (0 notes) → friendly panel, not blank.
   States: loading · error · empty (0 nodes) · ready.
   ============================================================ */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useWikiGraph } from "@/lib/useWiki";
import { searchWiki } from "@/lib/api";
import { Icon } from "@/lib/icons";
import type { WikiGraph, WikiGraphNode, WikiGraphEdge, WikiSearchHit, WikiStatus } from "@/lib/types";

const W = 760;
const H = 460;
const STATUS_COLOR: Record<WikiStatus, string> = {
  evergreen: "var(--green)",
  developing: "var(--blue)",
  fleeting: "var(--amber)",
};

type Pos = { x: number; y: number };

/* ---------------- layouts (both deterministic, NO Math.random) ---------------- */

/** Ego radial layout: center at middle, others evenly on a ring (local mode). */
function egoLayout(nodes: WikiGraphNode[], center: number | null): Map<number, Pos> {
  const pos = new Map<number, Pos>();
  const cx = 50, cy = 48;
  if (center != null) pos.set(center, { x: cx, y: cy });
  const others = nodes.filter((n) => n.id !== center);
  const ring = 34;
  const n = others.length || 1;
  others.forEach((node, i) => {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    pos.set(node.id, { x: cx + ring * Math.cos(a), y: cy + ring * 0.92 * Math.sin(a) });
  });
  return pos;
}

/** Deterministic hash → [0,1) (mulberry-ish; pure fn of the integer id). */
function hash01(id: number): number {
  let h = (id * 2654435761) >>> 0;
  h ^= h >>> 15; h = (h * 2246822519) >>> 0; h ^= h >>> 13;
  return (h >>> 0) / 4294967296;
}

/** Deterministic global layout: seed each node on a spiral by hash(id), then run a
 *  FIXED number of force iterations (repulsion + edge springs + centering). Pure
 *  function of (nodes, edges) — same vault → identical layout. Coords in 0..100 %. */
function globalLayout(nodes: WikiGraphNode[], edges: WikiGraphEdge[]): Map<number, Pos> {
  const pos = new Map<number, Pos>();
  const n = nodes.length;
  if (n === 0) return pos;
  // seed: golden-angle spiral, radius + jitter from the id hash (deterministic).
  const GA = Math.PI * (3 - Math.sqrt(5));
  nodes.forEach((node, i) => {
    const r = 6 + 40 * Math.sqrt((i + 0.5) / n) * (0.85 + 0.3 * hash01(node.id));
    const a = i * GA + hash01(node.id ^ 0x9e3779b9) * 0.6;
    pos.set(node.id, { x: 50 + r * Math.cos(a), y: 50 + r * Math.sin(a) });
  });
  if (n === 1) return pos;
  // force relaxation — fixed iters, deterministic. Scale work down as n grows.
  const iters = n > 200 ? 60 : n > 60 ? 90 : 120;
  const adj = edges.filter((e) => pos.has(e.source) && pos.has(e.target));
  const ids = nodes.map((nd) => nd.id);
  const REPULSE = 14, SPRING = 0.02, SPRING_LEN = 14, CENTER = 0.012;
  for (let it = 0; it < iters; it++) {
    const disp = new Map<number, Pos>(ids.map((id) => [id, { x: 0, y: 0 }]));
    // pairwise repulsion (O(n²) — fine at vault scale; T1 left the >cap seam to BE)
    for (let i = 0; i < n; i++) {
      const pi = pos.get(ids[i])!; const di = disp.get(ids[i])!;
      for (let j = i + 1; j < n; j++) {
        const pj = pos.get(ids[j])!; const dj = disp.get(ids[j])!;
        let dx = pi.x - pj.x, dy = pi.y - pj.y;
        let d2 = dx * dx + dy * dy; if (d2 < 0.01) { dx = (hash01(ids[i] + it) - 0.5); dy = (hash01(ids[j] + it) - 0.5); d2 = 0.01; }
        const f = REPULSE / d2;
        const fx = dx * f, fy = dy * f;
        di.x += fx; di.y += fy; dj.x -= fx; dj.y -= fy;
      }
    }
    // edge springs (attraction)
    for (const e of adj) {
      const a = pos.get(e.source)!, b = pos.get(e.target)!;
      const da = disp.get(e.source)!, db = disp.get(e.target)!;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const f = SPRING * (dist - SPRING_LEN);
      const fx = (dx / dist) * f, fy = (dy / dist) * f;
      da.x += fx; da.y += fy; db.x -= fx; db.y -= fy;
    }
    // apply + centering + clamp, with a cooling factor
    const cool = 1 - it / (iters * 1.4);
    for (const id of ids) {
      const p = pos.get(id)!; const d = disp.get(id)!;
      p.x += Math.max(-6, Math.min(6, d.x)) * cool + (50 - p.x) * CENTER;
      p.y += Math.max(-6, Math.min(6, d.y)) * cool + (50 - p.y) * CENTER;
      p.x = Math.max(3, Math.min(97, p.x));
      p.y = Math.max(4, Math.min(96, p.y));
    }
  }
  return pos;
}

function WikiGraphInner() {
  const router = useRouter();
  const sp = useSearchParams();

  // center: numeric → local/ego mode; null → GLOBAL (default) mode.
  const [center, setCenter] = useState<number | null>(null);
  const [depth, setDepth] = useState<number>(2);
  const [statusFilter, setStatusFilter] = useState<"all" | WikiStatus>("all");
  const [highlightOrphan, setHighlightOrphan] = useState(false);
  const [hovered, setHovered] = useState<number | null>(null);

  // seed mode from ?note= (deep-link to local); absent → global.
  useEffect(() => {
    const raw = sp.get("note");
    if (raw != null) {
      const n = parseInt(raw, 10);
      setCenter(Number.isNaN(n) ? null : n);
    } else {
      setCenter(null);
    }
  }, [sp]);

  const { graph, status, errMsg } = useWikiGraph(center, depth);
  const isGlobal = center == null;

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
    } catch { setHits([]); }
  }, []);
  useEffect(() => {
    if (debRef.current) clearTimeout(debRef.current);
    debRef.current = setTimeout(() => runSearch(q), 250);
    return () => { if (debRef.current) clearTimeout(debRef.current); };
  }, [q, runSearch]);

  // layout: global (force) vs ego (radial), memoized — deterministic, so stable.
  const pos = useMemo<Map<number, Pos>>(() => {
    if (!graph) return new Map();
    return isGlobal ? globalLayout(graph.nodes, graph.edges) : egoLayout(graph.nodes, graph.center);
  }, [graph, isGlobal]);

  // adjacency for hover-highlight (neighbors of the hovered node).
  const neighbors = useMemo<Map<number, Set<number>>>(() => {
    const m = new Map<number, Set<number>>();
    if (!graph) return m;
    const add = (a: number, b: number) => { (m.get(a) ?? m.set(a, new Set()).get(a)!).add(b); };
    for (const e of graph.edges) { add(e.source, e.target); add(e.target, e.source); }
    return m;
  }, [graph]);

  const centerNode = graph?.nodes.find((n) => n.id === graph.center) ?? null;

  function focusNote(id: number) {
    // global → local focus (Obsidian "click a node"); reflect in URL.
    setCenter(id);
    router.replace(`/wiki/graph?note=${id}`);
  }
  function goGlobal() {
    setCenter(null);
    setQ(""); setHits([]);
    router.replace("/wiki/graph");
  }
  function chooseCenter(id: number) { setQ(""); setHits([]); focusNote(id); }

  const edge = (e: WikiGraphEdge, i: number) => {
    const a = pos.get(e.source), b = pos.get(e.target);
    if (!a || !b) return null;
    const x1 = (a.x / 100) * W, y1 = (a.y / 100) * H, x2 = (b.x / 100) * W, y2 = (b.y / 100) * H;
    // hover-highlight: dim edges not touching the hovered node.
    const lit = hovered == null || e.source === hovered || e.target === hovered;
    return (
      <g key={`e-${e.source}-${e.target}-${i}`} data-testid="graph-edge">
        <line
          x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={e.isResolved ? "var(--line-2)" : "var(--amber)"}
          strokeWidth={lit ? 1.5 : 1}
          strokeDasharray={e.isResolved ? undefined : "3 3"}
          opacity={lit ? 0.85 : 0.18}
        />
        {!isGlobal && <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 3} className="wedge-lbl">{e.type}</text>}
      </g>
    );
  };

  const node = (n: WikiGraphNode) => {
    const p = pos.get(n.id);
    if (!p) return null;
    const x = (p.x / 100) * W, y = (p.y / 100) * H;
    const r = (isGlobal ? 5 : 8) + n.degree * (isGlobal ? 1.6 : 2.4);
    const isCenter = !isGlobal && n.id === graph?.center;
    const col = STATUS_COLOR[n.status] ?? "var(--tx-1)";
    const isOrphan = n.degree === 0 && !isCenter;
    const label = n.title && n.title.length > 22 ? n.title.slice(0, 20) + "…" : (n.title || `#${n.id}`);
    const dimmedByFilter = statusFilter !== "all" && n.status !== statusFilter && !isCenter;
    // hover-highlight: when hovering, dim nodes that aren't the hovered one or its neighbor.
    const litByHover = hovered == null || n.id === hovered || neighbors.get(hovered)?.has(n.id);
    const dimmed = dimmedByFilter || !litByHover;
    const orphanRing = isOrphan || (highlightOrphan && n.degree === 0);
    // labels: always in ego; in global only for hovered/high-degree (avoid clutter).
    const showLabel = !isGlobal || n.id === hovered || n.degree >= 4;
    return (
      <g
        key={`n-${n.id}`}
        className="wgnode clickable"
        transform={`translate(${x},${y})`}
        onClick={() => focusNote(n.id)}
        onMouseEnter={() => setHovered(n.id)}
        onMouseLeave={() => setHovered((h) => (h === n.id ? null : h))}
        data-testid="graph-node"
        data-node-id={n.id}
        data-center={isCenter || undefined}
        data-dimmed={dimmed || undefined}
        opacity={dimmed ? 0.2 : 1}
      >
        {isCenter && <circle r={r + 6} fill="none" stroke={col} strokeWidth={1.5} strokeDasharray="2 3" opacity={0.6} />}
        <circle r={r} fill={col} fillOpacity={isOrphan ? 0.3 : 1} style={isCenter ? { filter: `drop-shadow(0 0 8px ${col})` } : undefined} />
        {orphanRing && <circle r={r + 3} fill="none" stroke="var(--red)" strokeWidth={highlightOrphan ? 1.6 : 1} strokeDasharray="2 2" />}
        {showLabel && (
          <text y={r + 11} className="wgnode-lbl" style={isCenter ? { fontWeight: 700, fill: "var(--tx-0)" } : undefined}>{label}</text>
        )}
        {!isGlobal && <text y={3} textAnchor="middle" className="wgnode-id">{n.id}</text>}
      </g>
    );
  };

  const hasNodes = graph != null && graph.nodes.length > 0;

  return (
    <div data-testid="graph-screen">
      <div className="vtitle">
        <h1>Graph Explorer</h1>
        <span className="sub">
          {isGlobal
            ? `toàn vault · ${graph?.nodes.length ?? 0} nodes · ${graph?.edges.length ?? 0} edges`
            : `local · ego quanh #${graph?.center} · depth ${depth} · ${graph?.nodes.length ?? 0} nodes`}
        </span>
        <span className="sp" style={{ flex: 1 }} />
        {/* global ↔ local toggle (Obsidian parity) */}
        <div className="seg" role="group" aria-label="graph mode">
          <button type="button" className={isGlobal ? "on" : ""} onClick={goGlobal} data-testid="graph-mode-global">Global</button>
          <button type="button" className={!isGlobal ? "on" : ""} onClick={() => centerNode && focusNote(centerNode.id)} disabled={isGlobal} data-testid="graph-mode-local">Local</button>
        </div>
        {!isGlobal && (
          <div className="seg" role="group" aria-label="depth" style={{ marginLeft: 8 }}>
            <button type="button" className={depth === 1 ? "on" : ""} onClick={() => setDepth(1)} data-testid="graph-depth-1">depth 1</button>
            <button type="button" className={depth === 2 ? "on" : ""} onClick={() => setDepth(2)} data-testid="graph-depth-2">depth 2</button>
          </div>
        )}
      </div>

      {/* center picker (focus a note → local mode) */}
      <div className="wsearch" style={{ marginBottom: 12 }}>
        <span className="pr"><Icon name="i-search" /></span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm note để focus (local mode)…" data-testid="graph-search-input" aria-label="Focus một note" />
      </div>
      {q.trim() && (
        <div className="wsearch-res" data-testid="graph-search-results" style={{ marginTop: -8, marginBottom: 12, borderRadius: 11, borderTop: "1px solid var(--line-2)" }}>
          {hits.length === 0 ? (
            <div className="wsearch-empty">Không có kết quả.</div>
          ) : (
            hits.map((h) => (
              <div key={h.id} className="wsearch-row" data-testid="graph-search-hit" onClick={() => chooseCenter(h.id)} onKeyDown={(e) => { if (e.key === "Enter") chooseCenter(h.id); }} role="button" tabIndex={0}>
                <span className={`wstatus ${h.status}`}>{h.status}</span>
                <div className="wlr-body"><div className="wlr-t">{h.title ?? <span className="faint">#{h.id}</span>}</div><div className="wlr-s mut">{h.snippet}</div></div>
                <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10 }}>#{h.id}</span>
              </div>
            ))
          )}
        </div>
      )}

      <div className="wgraph-grid">
        <div className="panel wgraph-canvas">
          <div className="phead">
            <span className="kicker">{isGlobal ? "Global graph · toàn vault" : `Ego · #${graph?.center} ${centerNode?.title ?? ""}`}</span>
            <span className="sp" style={{ flex: 1 }} />
            <span className="wgleg"><span className="wgl-dot" style={{ background: "var(--green)" }} />evergreen</span>
            <span className="wgleg"><span className="wgl-dot" style={{ background: "var(--blue)" }} />developing</span>
            <span className="wgleg"><span className="wgl-dot" style={{ background: "var(--amber)" }} />fleeting</span>
            <span className="wgleg"><span className="wgl-dot" style={{ border: "1px dashed var(--red)", background: "transparent" }} />orphan</span>
          </div>
          <div className="wgraph-stage">
            {status === "loading" ? (
              <div className="wgraph-empty" data-testid="graph-loading">Đang dựng graph…</div>
            ) : status === "error" ? (
              <div className="wgraph-empty" data-testid="graph-error" style={{ color: "var(--red)" }}>
                {errMsg || "Không tải được graph."}
              </div>
            ) : hasNodes ? (
              <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "100%" }} data-testid="graph-svg" onMouseLeave={() => setHovered(null)}>
                <g className="wedges">{graph!.edges.map(edge)}</g>
                <g className="wnodes">{graph!.nodes.map(node)}</g>
              </svg>
            ) : isGlobal ? (
              <div className="wgraph-empty" data-testid="graph-empty-global">
                Vault chưa có note nào — chưa có gì để vẽ. Capture vài note + liên kết chúng, graph sẽ hiện ra.
              </div>
            ) : (
              <div className="wgraph-empty" data-testid="graph-empty">
                Note #{center} chưa có hàng xóm — chỉ mình nó trong vùng này (degree 0). <button type="button" className="link" onClick={goGlobal}>← về global</button>
              </div>
            )}
          </div>
        </div>

        <div className="wgraph-side">
          <div className="panel">
            <div className="phead"><span className="kicker">Bộ lọc & tóm tắt</span></div>
            <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="wfilter-row">
                <span className="mut">Status</span>
                <div className="seg" role="group" aria-label="status filter">
                  {(["all", "evergreen", "developing", "fleeting"] as const).map((s) => (
                    <button key={s} type="button" className={statusFilter === s ? "on" : ""} onClick={() => setStatusFilter(s)} data-testid={`graph-filter-${s}`}>
                      {s === "all" ? "all" : s.slice(0, 4)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="wfilter-row">
                <span className="mut">Highlight orphan</span>
                <button type="button" className={`tab ${highlightOrphan ? "on" : ""}`} onClick={() => setHighlightOrphan((v) => !v)} aria-pressed={highlightOrphan} data-testid="graph-highlight-orphan">
                  {highlightOrphan ? "ON" : "OFF"}
                </button>
              </div>
              <div className="wfilter-row"><span className="mut">Mode</span><span className="num">{isGlobal ? "global" : "local"}</span></div>
              <div className="wfilter-row"><span className="mut">Nodes</span><span className="num">{graph?.nodes.length ?? 0}</span></div>
              <div className="wfilter-row"><span className="mut">Edges</span><span className="num">{graph?.edges.length ?? 0}</span></div>
              {!isGlobal && centerNode && (
                <div className="wfilter-row"><span className="mut">Tâm</span><span className={`wstatus ${centerNode.status}`}>{centerNode.status}</span></div>
              )}
              <div className="hint" style={{ lineHeight: 1.5 }}>Click một node → focus (local). Hover → sáng hàng xóm.</div>
            </div>
          </div>

          <div className="panel wcluster-box">
            <div className="phead"><span className="kicker">Cluster · Groups</span></div>
            {graph && graph.clusters.length > 0 ? (
              graph.clusters.map((c, i) => (
                <div className="wcluster" key={`c-${i}`} data-testid="graph-cluster">
                  <div className="wcluster-top">
                    <b>{c.suggestedTitle ?? `Cụm ${c.size} note`}</b>
                    <span className="wconf">mật độ {(c.density * 100).toFixed(0)}%</span>
                  </div>
                  <div className="wcluster-members">
                    {c.members.map((m) => (
                      <span key={m.id} className="tagchip clickable" onClick={() => focusNote(m.id)}>#{m.id} {(m.title || "").slice(0, 14)}</span>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <div className="wcluster-empty" data-testid="graph-cluster-empty">
                Chưa có cụm. Khoanh vùng cụm dày (ứng viên MOC) đến qua Claude Code (MCP) ở giai đoạn sau — AI propose, bạn quyết.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WikiGraphPage() {
  return (
    <Suspense fallback={<div className="hint" style={{ padding: "24px 4px" }} data-testid="graph-suspense">Đang tải graph…</div>}>
      <WikiGraphInner />
    </Suspense>
  );
}
