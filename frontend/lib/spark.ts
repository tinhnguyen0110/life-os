/* ============================================================
   spark() / gauge() — PORTED VERBATIM from mock shell.js.
   Return raw SVG markup strings (caller injects via dangerouslySetInnerHTML
   or wraps in a Sparkline/RingGauge component later). Pure, deterministic
   except the gradient id — kept stable here (seeded by caller) for SSR safety.
   ============================================================ */

let _sgCounter = 0;
/** Deterministic id source (Math.random would break SSR hydration). */
function nextId(): string {
  _sgCounter += 1;
  return "sg" + _sgCounter.toString(36);
}

/**
 * Area+line sparkline SVG. Verbatim shape from mock spark(), hardened against
 * empty / single-point / all-equal inputs (return a valid empty-ish SVG, never NaN).
 * `color` defaults to the copper accent so callers may omit it.
 */
export function spark(
  points: number[],
  color = "var(--accent)",
  w = 560,
  h = 70,
  fill = true
): string {
  const id = nextId();
  // Defensive: 0 or 1 points cannot form a line — emit a valid empty svg.
  if (!points || points.length < 2) {
    return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:100%;display:block"></svg>`;
  }
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const step = w / (points.length - 1);
  const pts = points.map(
    (p, i) => `${(i * step).toFixed(1)},${(h - ((p - min) / range) * h).toFixed(1)}`
  );
  const area = `M0,${h} L${pts.join(" L")} L${w},${h} Z`;
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:100%;display:block">
    ${
      fill
        ? `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity=".24"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><path d="${area}" fill="url(#${id})"/>`
        : ""
    }
    <polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

/**
 * Ring/gauge SVG. Verbatim shape from mock gauge(). `color` defaults to copper accent.
 * `pct` is clamped to [0,100] so values >100 / <0 never produce a negative dashoffset.
 */
export function gauge(
  pct: number,
  color = "var(--accent)",
  size = 108,
  sw = 9,
  track = "var(--bg-3)"
): string {
  const clamped = Math.max(0, Math.min(100, pct));
  const r = size / 2 - sw;
  const c = 2 * Math.PI * r;
  const off = c * (1 - clamped / 100);
  const cx = size / 2;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${track}" stroke-width="${sw}"/>
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 ${cx} ${cx})" style="filter:drop-shadow(0 0 5px ${color}90)"/></svg>`;
}

/**
 * Allocation donut SVG. Verbatim shape from mock SCREENS.portfolio donut(). Each
 * segment is {pct (0-100), color}. Pcts need NOT sum to 100 (a gap = un-allocated).
 * Hardened: empty / all-zero input → a valid empty ring (hole only), never NaN.
 * `size`/`hole` let callers size it; center label is overlaid by the caller.
 */
export function donut(
  segments: { pct: number; color: string }[],
  size = 180,
  hole = 48
): string {
  const cx = size / 2;
  const r = cx - 20;
  const c = 2 * Math.PI * r;
  const segs = (segments ?? []).filter((s) => Number.isFinite(s.pct) && s.pct > 0);
  let acc = 0;
  const rings = segs
    .map((s) => {
      const start = acc;
      acc += s.pct;
      const len = (Math.min(s.pct, 100) / 100) * c;
      const off = c - (start / 100) * c;
      return `<circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${s.color}" stroke-width="22" stroke-dasharray="${len.toFixed(2)} ${(c - len).toFixed(2)}" stroke-dashoffset="${off.toFixed(2)}" transform="rotate(-90 ${cx} ${cx})"/>`;
    })
    .join("");
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${rings}<circle cx="${cx}" cy="${cx}" r="${hole}" fill="var(--bg-1)"/></svg>`;
}
