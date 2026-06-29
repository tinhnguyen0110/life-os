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
/** zoom-aware labels: show MORE labels once zoomed in to < 70% of the FITTED width
 *  (GRAPH-POLISH-A makes the default = the fitted box, so "zoomed in" is relative to it). */
const LABEL_ZOOM_FRAC = 0.7;
/** click-vs-drag threshold (px). Movement under this = a click; over = a pan. */
const DRAG_THRESHOLD = 4;
type ViewBox = { x: number; y: number; w: number; h: number };
const DEFAULT_VIEW: ViewBox = { x: 0, y: 0, w: W, h: H };
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

/** GRAPH-CLUSTER D1 — CLIENT-SIDE connected components over the rendered edges (no BE).
 *  Union-find, then a DETERMINISTIC label: each component is identified by its MIN member
 *  node-id, components sorted by that min-id → a stable palette index (0,1,2,…). Same vault →
 *  same component-index → same colors on reload. Pure fn (no Math.random). Returns node-id →
 *  {comp: palette index, size}. A degree-0 / singleton node is its own (size-1) component. */
function connectedComponents(nodes: WikiGraphNode[], edges: WikiGraphEdge[]): Map<number, { comp: number; size: number }> {
  const parent = new Map<number, number>();
  const find = (x: number): number => { let r = x; while (parent.get(r) !== r) r = parent.get(r)!; while (parent.get(x) !== r) { const nx = parent.get(x)!; parent.set(x, r); x = nx; } return r; };
  const union = (a: number, b: number) => { const ra = find(a), rb = find(b); if (ra !== rb) parent.set(Math.max(ra, rb), Math.min(ra, rb)); };
  for (const nd of nodes) parent.set(nd.id, nd.id);
  for (const e of edges) if (parent.has(e.source) && parent.has(e.target)) union(e.source, e.target);
  // group by root → min member-id; sort roots by min-id → stable palette index.
  const rootMembers = new Map<number, number[]>();
  for (const nd of nodes) { const r = find(nd.id); (rootMembers.get(r) ?? rootMembers.set(r, []).get(r)!).push(nd.id); }
  const roots = [...rootMembers.keys()].sort((a, b) => a - b); // root == min member-id (union keeps the min)
  const out = new Map<number, { comp: number; size: number }>();
  roots.forEach((root, idx) => { const members = rootMembers.get(root)!; for (const id of members) out.set(id, { comp: idx, size: members.length }); });
  return out;
}

/** GRAPH-CLUSTER A — a fixed, distinct cluster palette (cycled by component index). Picked
 *  for hue separation on the dark base; singleton/orphan components render GREY instead (honest,
 *  not a fake group color). Inline fill (NOT a CSS class) → no dead-selector risk. */
const CLUSTER_PALETTE = [
  "#5aa9ff", "#34e08a", "#f5b43d", "#ff6a8a", "#b78bff", "#3ed6c4",
  "#ff9a5c", "#9ad24e", "#ff5c5c", "#4dd0e1", "#e57fd8", "#c0ca33",
];
const ORPHAN_FILL = "#5b6472"; // grey for singleton/orphan components
function clusterFill(comp: number, size: number): string {
  if (size <= 1) return ORPHAN_FILL;
  return CLUSTER_PALETTE[comp % CLUSTER_PALETTE.length];
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
  const iters = n > 200 ? 70 : n > 60 ? 110 : 150; // GRAPH-POLISH-C — more iters to settle the wider spread
  const adj = edges.filter((e) => pos.has(e.source) && pos.has(e.target));
  const ids = nodes.map((nd) => nd.id);
  // GRAPH-POLISH-A (B) — OBSIDIAN force formulas (lifted, NOT d3 — written by hand; our
  // hash-seed init is KEPT for determinism). Tuned to our 0..100 layout space:
  //  · charge = −repel³ (the CUBE is the point — strong separation). Obsidian repel=10
  //    → −1000 in d3 world units; scaled to ~−0.9 here so spread is organic not explosive.
  //  · link strength = linkForce / min(deg_s,deg_t) (adaptive — hubs pull LESS per-edge →
  //    organic clusters, hubs don't collapse). · link distance ~16.
  //  · center via easeStrength(0.52)≈0.1 → ~0.055 in our space (centers WITHOUT a box).
  //  · collide: soft push when two nodes overlap their layout radii (anti-stack).
  // GRAPH-POLISH-C — force-param TUNE for a measurable gap (target nearest-dist/radius ~4-5×,
  // up from 2.84×). Stronger charge + firmer/wider collide + longer springs → thoáng but still
  // ONE connected cluster (adaptive link holds it; #174 auto-fit re-frames the wider spread).
  const REPEL = 14;                           // 9.7→14 → CHARGE = repel³/1000 ≈ 2.7 (≈3× global pressure)
  const CHARGE = Math.pow(REPEL, 3) / 1000;   // pairwise f = CHARGE/d²
  const LINK_FORCE = 0.9, SPRING_LEN = 36, CENTER = 0.035; // SPRING_LEN 22→36 (connected nodes sit farther)
  const COLLIDE_STR = 0.7;                     // 0.5→0.7 — a FIRM bubble push, not a nudge
  const COLLIDE_GAP = 1.8;                     // keep ≥ ~1.5-2× a node's diameter between neighbors
  // per-node degree (for adaptive link strength + collide radius + the F1 charge lever). ≥1.
  const deg = new Map<number, number>(nodes.map((nd) => [nd.id, Math.max(1, nd.degree || 0)]));
  // GRAPH-POLISH-B F1 — degree-scaled charge multiplier: a HUB exerts MORE repulsion than a
  // leaf, so hubs carve personal space + leaves bunch near their hub (hierarchy). Applied as
  // the EXERTING node's multiplier on the OTHER's displacement (asymmetric from a symmetric loop).
  const chargeMul = (id: number) => 1 + 0.5 * Math.sqrt(deg.get(id) ?? 1);
  // GRAPH-POLISH-C — layoutR MIRRORS the render radius (px) in LAYOUT units (1 unit = W/100 px):
  // render r = max(6, min(4+6√deg, 30)) px → /(W/100). So the collide bubble ≈ the VISUAL node
  // size; minD = (layoutR_i+layoutR_j)×COLLIDE_GAP gives the measurable breathing gap.
  const renderRpx = (id: number) => Math.max(6, Math.min(4 + 6 * Math.sqrt(deg.get(id) ?? 1), 30));
  const layoutR = (id: number) => renderRpx(id) / (W / 100);
  // GRAPH-CLUSTER B — cluster-aware force: components attract to their own centroid (island)
  // + repel HARDER across components (so islands separate). GENTLE — must compose with the
  // #176 spacing (4.79×) + #175 hierarchy, not overwhelm them. Deterministic (CC is pure).
  const comps = connectedComponents(nodes, edges);
  const compOf = (id: number) => comps.get(id)?.comp ?? -1;
  const SAME_CLUSTER_PULL = 0.018;  // gentle pull toward own-component centroid (the island)
  const CROSS_REPEL_MULT = 1.5;     // cross-component pairs repel 1.5× → islands push apart
  for (let it = 0; it < iters; it++) {
    const disp = new Map<number, Pos>(ids.map((id) => [id, { x: 0, y: 0 }]));
    // pairwise repulsion (charge cube × degree-lever) + soft collide (O(n²) — fine at vault scale).
    for (let i = 0; i < n; i++) {
      const pi = pos.get(ids[i])!; const di = disp.get(ids[i])!;
      const muli = chargeMul(ids[i]);
      for (let j = i + 1; j < n; j++) {
        const pj = pos.get(ids[j])!; const dj = disp.get(ids[j])!;
        let dx = pi.x - pj.x, dy = pi.y - pj.y;
        let d2 = dx * dx + dy * dy; if (d2 < 0.01) { dx = (hash01(ids[i] + it) - 0.5); dy = (hash01(ids[j] + it) - 0.5); d2 = 0.01; }
        // GRAPH-CLUSTER B — cross-component pairs repel HARDER (×CROSS_REPEL_MULT) → the two
        // components push apart into separate islands; same-component charge is unchanged.
        const crossMult = compOf(ids[i]) !== compOf(ids[j]) ? CROSS_REPEL_MULT : 1;
        const f = (CHARGE / d2) * crossMult; // charge-cube repulsion (base × cross-cluster lever)
        let fx = dx * f, fy = dy * f;
        // GRAPH-POLISH-C collide: keep a GAP of ≥ COLLIDE_GAP × the summed radii between
        // neighbors (the measurable breathing gap). Firmer COLLIDE_STR enforces it.
        const dist = Math.sqrt(d2);
        const minD = (layoutR(ids[i]) + layoutR(ids[j])) * COLLIDE_GAP;
        if (dist < minD) {
          const push = COLLIDE_STR * (minD - dist) / dist;
          fx += dx * push; fy += dy * push;
        }
        // F1 — i is pushed by j's charge (mulj), j is pushed by i's charge (muli). A hub j
        // shoves leaf i hard; leaf i barely moves hub j → hubs get personal space, leaves bunch.
        const mulj = chargeMul(ids[j]);
        di.x += fx * mulj; di.y += fy * mulj; dj.x -= fx * muli; dj.y -= fy * muli;
      }
    }
    // edge springs (attraction) — ADAPTIVE strength = linkForce / min(deg_s, deg_t).
    for (const e of adj) {
      const a = pos.get(e.source)!, b = pos.get(e.target)!;
      const da = disp.get(e.source)!, db = disp.get(e.target)!;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const strength = LINK_FORCE / Math.min(deg.get(e.source) ?? 1, deg.get(e.target) ?? 1);
      const f = 0.02 * strength * (dist - SPRING_LEN);
      const fx = (dx / dist) * f, fy = (dy / dist) * f;
      da.x += fx; da.y += fy; db.x -= fx; db.y -= fy;
    }
    // GRAPH-CLUSTER B — per-iter component CENTROIDS (mean position of each component's nodes)
    // → each node gets pulled gently toward its own centroid (the island cohesion). Skips
    // singletons (no centroid pull for orphans — they sit where charge/center put them).
    const cAcc = new Map<number, { x: number; y: number; n: number }>();
    for (const id of ids) {
      const c = compOf(id); if (c < 0) continue;
      const p = pos.get(id)!;
      const acc = cAcc.get(c) ?? cAcc.set(c, { x: 0, y: 0, n: 0 }).get(c)!;
      acc.x += p.x; acc.y += p.y; acc.n++;
    }
    const centroid = (c: number): Pos | null => { const a = cAcc.get(c); return a && a.n > 1 ? { x: a.x / a.n, y: a.y / a.n } : null; };
    // apply + centering (easeStrength) + same-cluster pull, with a cooling factor + a per-frame
    // STEP clamp (±6, stability — NOT the old box clamp). NO hard box clamp → nodes spread; the
    // auto-fit viewBox frames them.
    const cool = 1 - it / (iters * 1.4);
    for (const id of ids) {
      const p = pos.get(id)!; const d = disp.get(id)!;
      p.x += Math.max(-6, Math.min(6, d.x)) * cool + (50 - p.x) * CENTER;
      p.y += Math.max(-6, Math.min(6, d.y)) * cool + (50 - p.y) * CENTER;
      const ce = centroid(compOf(id));
      if (ce) { p.x += (ce.x - p.x) * SAME_CLUSTER_PULL; p.y += (ce.y - p.y) * SAME_CLUSTER_PULL; }
    }
  }
  return pos;
}

/** GRAPH-POLISH-A — auto-fit the viewBox to the REAL node bounds (rendered coord space:
 *  each node draws at (p.x/100)*W, (p.y/100)*H). Pads ~8% of the larger side. With the
 *  hard clamp removed, nodes can spread past 0..100; the fitted box is what frames them.
 *  Degenerate (no nodes / w or h ~0 — 1 node or all-same-pos) → a default-sized box
 *  centered on the node. Pure fn of `pos` → deterministic (memoized off the layout deps). */
function fitBounds(pos: Map<number, Pos>): ViewBox {
  if (pos.size === 0) return { ...DEFAULT_VIEW };
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const p of pos.values()) {
    const X = (p.x / 100) * W, Y = (p.y / 100) * H;
    if (X < minX) minX = X; if (X > maxX) maxX = X;
    if (Y < minY) minY = Y; if (Y > maxY) maxY = Y;
  }
  const bw = maxX - minX, bh = maxY - minY;
  // degenerate (single node / all-same-position) → a sensible default box around the center.
  if (bw < 1 && bh < 1) {
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    return { x: cx - W / 2, y: cy - H / 2, w: W, h: H };
  }
  const pad = Math.max(40, 0.08 * Math.max(bw, bh));
  return { x: minX - pad, y: minY - pad, w: bw + 2 * pad, h: bh + 2 * pad };
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
  // GRAPH-POLISH-A (D) — the cluster list is a collapsible popover (out of the always-on
  // toolbar) so the graph gets full width; the feature is KEPT, just tucked behind a toggle.
  const [showClusters, setShowClusters] = useState(false);

  /* ---- GRAPH-POLISH: Obsidian-style zoom/pan via a stateful viewBox ----
     The deterministic layout (globalLayout/egoLayout) is UNTOUCHED — the viewBox
     transform sits ON TOP, so node positions never change; we only move the camera. */
  const [view, setView] = useState<ViewBox>({ ...DEFAULT_VIEW });
  const svgRef = useRef<SVGSVGElement | null>(null);
  // pan bookkeeping: the mousedown anchor + a didPan flag (gates node click-vs-drag).
  const panRef = useRef<{ active: boolean; startX: number; startY: number; viewX: number; viewY: number }>(
    { active: false, startX: 0, startY: 0, viewX: 0, viewY: 0 });
  const didPanRef = useRef(false);
  // GRAPH-POLISH-A (C) — smooth zoom-lerp state: a viewRef mirror (read inside rAF without a
  // stale closure), the target view.w the wheel sets, the anchor viewBox-point to pin, and
  // the rAF handle (cleaned up on unmount).
  const viewRef = useRef<ViewBox>(view);
  viewRef.current = view; // keep the mirror current every render
  // a ref mirror of the fitted box (declared after `pos`); the wheel handler reads it to
  // clamp zoom RELATIVE to the natural graph size. Assigned just below fitView's useMemo.
  const fitViewRef = useRef<ViewBox>(DEFAULT_VIEW);
  const zoomTargetWRef = useRef<number | null>(null);     // target view.w (null = no zoom anim)
  const zoomAnchorRef = useRef<{ wx: number; wy: number } | null>(null); // viewBox point to pin
  const rafRef = useRef<number | null>(null);
  // GRAPH-POLISH-A — the camera re-frames to the auto-fit bounds on a NEW layout (graph
  // load / global↔local mode); that effect lives next to `fitView` (after `pos` is known).

  // px → viewBox-unit scale (the SVG renders at width:100%, so client width varies).
  function pxToViewScale(): number {
    const el = svgRef.current;
    const cw = el?.clientWidth || W;
    return view.w / cw; // viewBox units per CSS pixel (x); y uses the same since aspect is locked
  }

  // PAN — mousedown on the SVG background starts a drag; mousemove past the threshold pans.
  function onSvgMouseDown(e: React.MouseEvent<SVGSVGElement>) {
    // left button only; ignore if the press began on a node (let the node handle hover/click).
    if (e.button !== 0) return;
    didPanRef.current = false;
    panRef.current = { active: true, startX: e.clientX, startY: e.clientY, viewX: view.x, viewY: view.y };
  }
  function onSvgMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const p = panRef.current;
    if (!p.active) return;
    const dxPx = e.clientX - p.startX, dyPx = e.clientY - p.startY;
    if (!didPanRef.current && Math.hypot(dxPx, dyPx) < DRAG_THRESHOLD) return; // under threshold = still a click
    didPanRef.current = true;
    const s = pxToViewScale();
    // drag right → camera moves left (content follows the cursor) → view.x decreases.
    setView((v) => ({ ...v, x: p.viewX - dxPx * s, y: p.viewY - dyPx * s }));
  }
  function endPan() { panRef.current.active = false; }

  // GRAPH-POLISH-A (C) — SMOOTH zoom: one rAF step lerps view.w 15%/frame toward the target,
  // pinning the anchor's viewBox-point (Obsidian's updateZoom 0.85/0.15 ease). Returns true
  // while still animating. NOTE: smaller view.w = zoomed IN (maps to Obsidian's k = 1/w).
  function stepZoom(): boolean {
    const target = zoomTargetWRef.current;
    if (target == null) return false;
    const v = viewRef.current;
    const anchor = zoomAnchorRef.current ?? { wx: v.x + v.w / 2, wy: v.y + v.h / 2 };
    // converged → snap to the exact target + stop.
    if (Math.abs(v.w - target) / target < 0.01) {
      const ratio = target / v.w;
      const next: ViewBox = {
        x: anchor.wx - (anchor.wx - v.x) * ratio,
        y: anchor.wy - (anchor.wy - v.y) * ratio,
        w: target, h: v.h * ratio,
      };
      viewRef.current = next; // 🔴 update the mirror NOW so the next frame reads fresh
      setView(next);
      zoomTargetWRef.current = null;
      return false;
    }
    const nw = v.w * 0.85 + target * 0.15; // ease 15%/frame
    const ratio = nw / v.w;
    const next: ViewBox = {
      x: anchor.wx - (anchor.wx - v.x) * ratio,
      y: anchor.wy - (anchor.wy - v.y) * ratio,
      w: nw, h: v.h * ratio,
    };
    // 🔴 update the ref mirror SYNCHRONOUSLY (don't wait for React's render to refresh it)
    // so consecutive rAF frames lerp off the latest value — else it'd recompute the same
    // step forever and never converge (the live-stuck bug jsdom's sync-raf hid).
    viewRef.current = next;
    setView(next);
    return true;
  }
  function runZoomLoop() {
    if (rafRef.current != null) return; // already looping
    const tick = () => {
      const more = stepZoom();
      rafRef.current = more ? requestAnimationFrame(tick) : null;
    };
    rafRef.current = requestAnimationFrame(tick);
  }
  // ZOOM — wheel sets a TARGET view.w (Obsidian targetScale ×= 1.5^(−ΔY/120)); the rAF loop
  // eases the actual view.w toward it. Anchor: zoom-IN at the cursor, zoom-OUT at the center.
  // NATIVE non-passive listener (attached in an effect below): React's onWheel is PASSIVE so
  // e.preventDefault() there would no-op + log a console warning; a native {passive:false}
  // listener lets preventDefault actually stop page-scroll-during-zoom + keeps the console clean.
  function onWheelNative(e: WheelEvent) {
    const el = svgRef.current;
    if (!el) return;
    e.preventDefault();
    const rect = el.getBoundingClientRect();
    let dy = e.deltaY;
    if (e.deltaMode === 1) dy *= 40; else if (e.deltaMode === 2) dy *= 800; // line / page → px
    const v = viewRef.current;
    const baseW = zoomTargetWRef.current ?? v.w;
    // wheel UP (dy<0) → zoom IN → SMALLER w. factor = 1 / 1.5^(−dy/120) = 1.5^(dy/120).
    let targetW = baseW * Math.pow(1.5, dy / 120);
    // clamp RELATIVE to the natural graph size (the fitted box) — NOT the fixed W. The
    // fitted box can be far smaller/larger than W now (organic spread), so a W-based clamp
    // would block zooming in on a small graph. min = 0.12× fit (deep in), max = 3× fit (out).
    const fw = fitViewRef.current.w || W;
    targetW = Math.max(fw * 0.12, Math.min(fw * 3, targetW));
    zoomTargetWRef.current = targetW;
    if (targetW < v.w) {
      // zoom IN → anchor at the cursor's current viewBox point.
      const wx = v.x + ((e.clientX - rect.left) / (rect.width || 1)) * v.w;
      const wy = v.y + ((e.clientY - rect.top) / (rect.height || 1)) * v.h;
      zoomAnchorRef.current = { wx, wy };
    } else {
      zoomAnchorRef.current = null; // zoom OUT → anchor at the viewport center
    }
    runZoomLoop();
  }
  // keep a ref to the latest wheel handler so the native listener (attached once) always
  // calls the current closure (which reads up-to-date refs).
  const wheelHandlerRef = useRef(onWheelNative);
  wheelHandlerRef.current = onWheelNative;
  // attach the NATIVE non-passive wheel listener (once) so preventDefault works + no warning.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => wheelHandlerRef.current(e);
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [svgRef.current]); // re-attach if the SVG element instance changes (e.g. after a remount)

  // GRAPH-POLISH-A — ⟲ reset frames the WHOLE graph (the auto-fit bounds), not the old
  // hardcoded 0,0,W,H. Cancels any in-flight zoom-lerp so the reset lands cleanly (instant).
  // (fitView is declared just below, after `pos`; referenced at call-time.)
  function resetView() {
    zoomTargetWRef.current = null;
    if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    setView(fitView);
  }

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

  // GRAPH-POLISH-A — the auto-fit viewBox: frames the real node bounds (deterministic,
  // memoized off the same layout). This is the INITIAL view + the ⟲ RESET target. When
  // the layout identity changes (graph loaded / global↔local mode), snap the camera to it.
  const fitView = useMemo<ViewBox>(() => fitBounds(pos), [pos]);
  fitViewRef.current = fitView; // mirror for the wheel handler's fit-relative zoom clamp
  // zoom-aware labels: "zoomed in" = the current view is < 70% of the FITTED width.
  const isZoomedIn = view.w < fitView.w * LABEL_ZOOM_FRAC;
  // sync the camera to the fitted box on a NEW layout (initial load or mode change) — keyed
  // on the fitView identity so a user's pan/zoom (which only changes `view`, not the layout)
  // is NOT overridden. useMemo gives a fresh fitView object only when `pos` changes.
  const lastFitRef = useRef<ViewBox | null>(null);
  useEffect(() => {
    if (lastFitRef.current !== fitView) {
      lastFitRef.current = fitView;
      // a NEW layout cancels any in-flight zoom-lerp + snaps to the fitted frame.
      zoomTargetWRef.current = null;
      if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      setView(fitView);
    }
  }, [fitView]);

  // GRAPH-POLISH-A (C) — cancel the zoom rAF on unmount (no leak).
  useEffect(() => () => {
    if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
  }, []);

  // adjacency for hover-highlight (neighbors of the hovered node).
  const neighbors = useMemo<Map<number, Set<number>>>(() => {
    const m = new Map<number, Set<number>>();
    if (!graph) return m;
    const add = (a: number, b: number) => { (m.get(a) ?? m.set(a, new Set()).get(a)!).add(b); };
    for (const e of graph.edges) { add(e.source, e.target); add(e.target, e.source); }
    return m;
  }, [graph]);

  // GRAPH-CLUSTER A — node-id → connected-component {comp, size} (same fn the layout uses for
  // the island force, so color + position agree). Deterministic; memoized off the graph.
  const clusterMap = useMemo(() => graph ? connectedComponents(graph.nodes, graph.edges) : new Map<number, { comp: number; size: number }>(), [graph]);

  // GRAPH-POLISH-A (E) — GREEDY collision-cull of GLOBAL labels (the tight Obsidian cluster
  // packed many deg≥6 hubs → labels overlapped). Sort by degree desc, place a label only if
  // its bbox doesn't overlap an already-placed one. Deterministic (pure fn of pos+nodes+zoom);
  // recomputed only when the layout / zoom-band changes (NOT on hover — hover labels render on
  // top separately). Caps the count too (Obsidian global shows very few by default). Returns
  // the set of node-ids that get a base label. Ego mode = always-label (empty set, the node
  // render labels all in ego). */
  const labeledIds = useMemo<Set<number>>(() => {
    const ids = new Set<number>();
    if (!graph || !isGlobal) return ids; // ego labels everything itself
    // candidacy threshold: zoomed-IN → deg≥2 pool (room to show more), default → deg≥4 pool.
    const minDeg = isZoomedIn ? 2 : 4;
    // GRAPH-POLISH-B F4(c) — FEWER labels by default (few-and-readable > many-and-piled).
    // Obsidian global shows very few; hover/zoom-in reveals more.
    const cap = isZoomedIn ? 16 : 5;
    const placed: { x1: number; y1: number; x2: number; y2: number }[] = [];
    // 10.5px label + the 3.5px halo → a touch wider; pad generously so labels don't kiss.
    const CHAR_W = 5.6, FONT_H = 13, PAD = 3;
    const cand = graph.nodes
      .filter((n) => n.degree >= minDeg && pos.has(n.id))
      .sort((a, b) => b.degree - a.degree || a.id - b.id); // degree desc, id tiebreak = deterministic
    for (const n of cand) {
      if (ids.size >= cap) break;
      const p = pos.get(n.id)!;
      const nx = (p.x / 100) * W, ny = (p.y / 100) * H;
      const r = Math.max(6, Math.min(4 + 6 * Math.sqrt(n.degree), 30)); // match the F5 render radius
      const text = n.title && n.title.length > 22 ? n.title.slice(0, 20) + "…" : (n.title || `#${n.id}`);
      const halfW = (text.length * CHAR_W) / 2 + PAD;
      // the label sits centered under the node at the F4 y-offset (matches the render).
      const cy = ny + r + Math.max(12, r * 0.5 + 7);
      const box = { x1: nx - halfW, y1: cy - FONT_H / 2, x2: nx + halfW, y2: cy + FONT_H / 2 };
      const overlaps = placed.some((q) => box.x1 < q.x2 && box.x2 > q.x1 && box.y1 < q.y2 && box.y2 > q.y1);
      if (overlaps) continue;
      placed.push(box);
      ids.add(n.id);
    }
    return ids;
  }, [graph, isGlobal, isZoomedIn, pos]);

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
    // GRAPH-POLISH-B F5 (STRONGER) — BOLD size hierarchy, a hub reads as 3-4× a leaf at a
    // glance. leaf (deg0) → 6px floor (clickable); deg1 → ~10; deg4 → ~16; top hub → ~30.
    // A bigger √-coefficient separates even at the low real degrees in this vault. Collide
    // uses this big radius → hubs carve room. "Glance → that big one is a hub."
    const r = (isGlobal ? 1 : 1.2) * Math.max(6, Math.min(4 + 6 * Math.sqrt(n.degree), 30));
    const isCenter = !isGlobal && n.id === graph?.center;
    const statusCol = STATUS_COLOR[n.status] ?? "var(--tx-1)";
    // GRAPH-CLUSTER A — in GLOBAL mode: fill = CLUSTER color (palette by component, grey for
    // orphan/singleton); status moves to a thin RING (stroke) on the main circle so status info
    // isn't lost. In ego/local mode: keep the status fill (focused view, clusters N/A). The
    // center-ring (r+6) + orphan-ring (r+3) are separate concentric rings — no conflict.
    const cm = clusterMap.get(n.id);
    const clusterCol = cm ? clusterFill(cm.comp, cm.size) : "var(--tx-1)";
    const col = isGlobal ? clusterCol : statusCol; // node FILL
    const isOrphan = n.degree === 0 && !isCenter;
    const label = n.title && n.title.length > 22 ? n.title.slice(0, 20) + "…" : (n.title || `#${n.id}`);
    const dimmedByFilter = statusFilter !== "all" && n.status !== statusFilter && !isCenter;
    // hover-highlight: when hovering, dim nodes that aren't the hovered one or its neighbor.
    const litByHover = hovered == null || n.id === hovered || neighbors.get(hovered)?.has(n.id);
    const dimmed = dimmedByFilter || !litByHover;
    const orphanRing = isOrphan || (highlightOrphan && n.degree === 0);
    // GRAPH-POLISH-A (E) — labels: always in ego; ALWAYS on hover; in global, only the
    // COLLISION-CULLED set (labeledIds — greedy by degree, non-overlapping bbox, capped) so
    // the tight cluster's hub labels don't overlap/pile up. Zoom-in widens the culled set.
    const showLabel = !isGlobal || n.id === hovered || labeledIds.has(n.id);
    return (
      <g
        key={`n-${n.id}`}
        className="wgnode clickable"
        transform={`translate(${x},${y})`}
        // GRAPH-POLISH req3 — a click that was actually a PAN must NOT open the note.
        // didPanRef is set true on a drag past the threshold; reset on each mousedown.
        onClick={() => { if (didPanRef.current) return; focusNote(n.id); }}
        onMouseEnter={() => setHovered(n.id)}
        onMouseLeave={() => setHovered((h) => (h === n.id ? null : h))}
        data-testid="graph-node"
        data-node-id={n.id}
        data-center={isCenter || undefined}
        data-dimmed={dimmed || undefined}
        opacity={dimmed ? 0.2 : 1}
      >
        {isCenter && <circle r={r + 6} fill="none" stroke={statusCol} strokeWidth={1.5} strokeDasharray="2 3" opacity={0.6} />}
        {/* GRAPH-CLUSTER A — main circle: CLUSTER fill (global) + a STATUS ring (stroke) so the
            status (green/blue/amber) is still readable on the cluster-colored node. Orphan = grey
            fill + no status ring (a degree-0 node's status is incidental). */}
        <circle
          r={r}
          fill={col}
          fillOpacity={isOrphan ? 0.45 : 1}
          stroke={isGlobal && !isOrphan ? statusCol : "none"}
          strokeWidth={isGlobal && !isOrphan ? 2 : 0}
          data-status={n.status}
          style={isCenter ? { filter: `drop-shadow(0 0 8px ${statusCol})` } : undefined}
        />
        {orphanRing && <circle r={r + 3} fill="none" stroke="var(--red)" strokeWidth={highlightOrphan ? 1.6 : 1} strokeDasharray="2 2" />}
        {showLabel && (
          // GRAPH-POLISH-B F4 — READABLE labels: (a) y clears the (bigger) node radius so the
          // text lands BELOW it, not on top; (b) bright fill (--tx-0) + a dark HALO via
          // paint-order:stroke + a bg-colored stroke → reads over a dense cluster. data-testid
          // for the test. (Center node = bold, same.)
          <text
            y={r + Math.max(12, r * 0.5 + 7)}
            className="wgnode-lbl wgnode-lbl-halo"
            data-testid="graph-label"
            style={isCenter ? { fontWeight: 700 } : undefined}
          >{label}</text>
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

      {/* GRAPH-POLISH-A (D) — a thin filter TOOLBAR above the graph (was a right side column).
          Status chips + orphan toggle + Nodes·Edges inline + a Clusters popover toggle. The
          graph below is FULL-WIDTH (the auto-fit + zoom from A/B/C get the whole canvas). */}
      <div className="wgtoolbar" data-testid="graph-toolbar">
        <div className="seg" role="group" aria-label="status filter">
          {(["all", "evergreen", "developing", "fleeting"] as const).map((s) => (
            <button key={s} type="button" className={statusFilter === s ? "on" : ""} onClick={() => setStatusFilter(s)} data-testid={`graph-filter-${s}`}>
              {s === "all" ? "all" : s.slice(0, 4)}
            </button>
          ))}
        </div>
        <button type="button" className={`tab ${highlightOrphan ? "on" : ""}`} onClick={() => setHighlightOrphan((v) => !v)} aria-pressed={highlightOrphan} data-testid="graph-highlight-orphan" title="Làm nổi orphan (degree 0)">
          ⊘ orphan {highlightOrphan ? "ON" : "OFF"}
        </button>
        <span className="wgtb-count" data-testid="graph-counts">
          <b className="num">{graph?.nodes.length ?? 0}</b> nodes · <b className="num">{graph?.edges.length ?? 0}</b> edges
        </span>
        {/* clusters popover toggle (the big cluster panel moved out of an always-on column) */}
        <button type="button" className={`tab ${showClusters ? "on" : ""}`} onClick={() => setShowClusters((v) => !v)} aria-expanded={showClusters} data-testid="graph-clusters-toggle" title="Cụm / Groups">
          ◳ Cụm{graph && graph.clusters.length > 0 ? ` (${graph.clusters.length})` : ""}
        </button>
        <span className="sp" style={{ flex: 1 }} />
        {/* GRAPH-CLUSTER A — legend reflects the new encoding: FILL = cụm (cluster palette),
            VIỀN/ring = trạng thái (status). Status shown as ring-dots; cluster encoded by the
            node fills themselves (too many to legend). Local/ego mode = status fill (no clusters). */}
        {isGlobal && <span className="wgleg" data-testid="graph-legend-note" style={{ color: "var(--tx-2)" }}>màu = cụm · viền =</span>}
        <span className="wgleg"><span className="wgl-dot" style={{ border: "2px solid var(--green)", background: "transparent" }} />evergreen</span>
        <span className="wgleg"><span className="wgl-dot" style={{ border: "2px solid var(--blue)", background: "transparent" }} />developing</span>
        <span className="wgleg"><span className="wgl-dot" style={{ border: "2px solid var(--amber)", background: "transparent" }} />fleeting</span>
        <span className="wgleg"><span className="wgl-dot" style={{ background: "#5b6472" }} />orphan</span>
        <button type="button" className="wgraph-reset" onClick={resetView} data-testid="graph-reset-view" title="Đặt lại khung nhìn (zoom/pan)" aria-label="Đặt lại khung nhìn">⟲</button>
      </div>

      {/* the cluster popover (collapsible — KEPT feature, out of the toolbar) */}
      {showClusters && (
        <div className="panel wcluster-pop" data-testid="graph-clusters-pop">
          <div className="phead">
            <span className="kicker">Cluster · Groups</span>
            <span className="sp" style={{ flex: 1 }} />
            <button type="button" className="wgraph-reset" onClick={() => setShowClusters(false)} aria-label="Đóng" title="Đóng">✕</button>
          </div>
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
      )}

      {/* the graph — FULL WIDTH (single column, no side panel) */}
      <div className="panel wgraph-canvas" data-testid="graph-canvas">
        <div className="phead">
          <span className="kicker">{isGlobal ? "Global graph · toàn vault" : `Ego · #${graph?.center} ${centerNode?.title ?? ""}`}</span>
          <span className="sp" style={{ flex: 1 }} />
          <span className="hint" style={{ fontSize: 11 }}>Click node → focus · kéo để pan · cuộn để zoom</span>
        </div>
        <div className="wgraph-stage">
            {status === "loading" ? (
              <div className="wgraph-empty" data-testid="graph-loading">Đang dựng graph…</div>
            ) : status === "error" ? (
              <div className="wgraph-empty" data-testid="graph-error" style={{ color: "var(--red)" }}>
                {errMsg || "Không tải được graph."}
              </div>
            ) : hasNodes ? (
              <svg
                ref={svgRef}
                viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
                preserveAspectRatio="xMidYMid meet"
                style={{ width: "100%", height: "100%", cursor: panRef.current.active ? "grabbing" : "grab", touchAction: "none", userSelect: "none", WebkitUserSelect: "none" }}
                data-testid="graph-svg"
                data-view-w={view.w}
                onMouseLeave={() => { setHovered(null); endPan(); }}
                onMouseDown={onSvgMouseDown}
                onMouseMove={onSvgMouseMove}
                onMouseUp={endPan}
              >
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
