/* ============================================================
   Display formatters — backend returns ISO-8601 UTC / raw numbers; the UI
   humanizes them here (NEVER the backend). Pure, null-safe: null/invalid → "—"
   (or a caller-supplied fallback), never "NaN" / "Invalid Date".
   ============================================================ */

/** ISO-8601 (or null) → Vietnamese relative time, e.g. "2 giờ trước", "3 ngày trước". */
export function relativeTime(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return fallback;
  const diffMs = Date.now() - t;
  const sec = Math.floor(diffMs / 1000);
  if (sec < 0) return "vừa xong";
  if (sec < 60) return `${sec} giây trước`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} phút trước`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} giờ trước`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} ngày trước`;
  const mon = Math.floor(day / 30);
  if (mon < 12) return `${mon} tháng trước`;
  return `${Math.floor(mon / 12)} năm trước`;
}

/** idle-days number (or null) → "N ngày" / "hôm nay", null → fallback. */
export function idleDays(days: number | null | undefined, fallback = "—"): string {
  if (days == null || !Number.isFinite(days)) return fallback;
  if (days <= 0) return "hôm nay";
  return `${days} ngày`;
}

/** Any nullable string → itself or the fallback (centralizes the "—" rule). */
export function orDash(v: string | null | undefined, fallback = "—"): string {
  return v == null || v === "" ? fallback : v;
}

/** ISO date (or null) → "MM/YYYY" (graveyard died date). null/invalid → fallback. */
export function fmtMonthYear(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return fallback;
  const d = new Date(t);
  return `${String(d.getUTCMonth() + 1).padStart(2, "0")}/${d.getUTCFullYear()}`;
}

/** token count (or null) → compact "37.7k" / "1.2M" / "950". null/NaN → fallback. */
export function fmtTokens(v: number | null | undefined, fallback = "—"): string {
  if (v == null || !Number.isFinite(v)) return fallback;
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toLocaleString("en-US", { maximumFractionDigits: 1 })}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toLocaleString("en-US", { maximumFractionDigits: 1 })}k`;
  return `${sign}${abs}`;
}

/** number (or null) → "$1,234" / "$1.2M" style USD. null/NaN → fallback "—".
 *  Compact for ≥1M so big net-worth numbers stay readable; plain otherwise. */
export function fmtUSD(v: number | null | undefined, fallback = "—"): string {
  if (v == null || !Number.isFinite(v)) return fallback;
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1_000_000) {
    return `${sign}$${(abs / 1_000_000).toLocaleString("en-US", { maximumFractionDigits: 2 })}M`;
  }
  return `${sign}$${abs.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

/** signed number → "+$1,234" / "−$1,234" (true minus). null/NaN → fallback.
 *  Use for day/week deltas where the +/− sign carries meaning (color drives tone). */
export function fmtSign(v: number | null | undefined, fallback = "—"): string {
  if (v == null || !Number.isFinite(v)) return fallback;
  const abs = Math.abs(v);
  const body = abs >= 1_000_000
    ? `$${(abs / 1_000_000).toLocaleString("en-US", { maximumFractionDigits: 2 })}M`
    : `$${abs.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return v < 0 ? `−${body}` : `+${body}`;
}

/** signed percent → "+1.4%" / "−0.6%". null/NaN → fallback. */
export function fmtPct(v: number | null | undefined, fallback = "—"): string {
  if (v == null || !Number.isFinite(v)) return fallback;
  return `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}%`;
}

/** A change value (abs OR pct — either nullable number) → the honest 3-way glyph + tone.
 *  This is the SINGLE source of the delta arrow/color rule across every delta widget
 *  (Home net-worth, Finance net-worth, EquityCurve, MarketChart). Extracted from the
 *  #72-FE inline `dayDelta` so the rule can't drift per-widget again (#81).
 *
 *  Honest mapping (the distinguishing cases a 2-way `up ? pos : neg` gets WRONG):
 *   - `< 0`            → ▼ / "neg"   (a real loss, red-down)
 *   - `> 0`            → ▲ / "pos"   (a real gain, green-up)
 *   - `=== 0` (FLAT)   → ▬ / "faint" (NOT a green ▲ — flat is not a gain)
 *   - `null`/NaN       → ▬ / "faint" (NO data — never a fabricated arrow/color)
 *
 *  The neutral tone is the existing `.faint` class (var(--tx-2), tone-less) — the same
 *  class Home's #72-FE inline helper used, so this extraction is behavior-identical for
 *  Home and merely PROPAGATES the honest rule to the 3 widgets that were still 2-way.
 *  It must NOT resolve to the green `.pos` or red `.neg` tone. Callers format the
 *  number/percent text themselves (fmtSign / fmtPct / toFixed) — this returns ONLY
 *  the arrow + tone class so the rule lives in one place. */
export function deltaGlyph(v: number | null | undefined): { arrow: string; cls: string } {
  if (v == null || !Number.isFinite(v) || v === 0) return { arrow: "▬", cls: "faint" };
  return v < 0 ? { arrow: "▼", cls: "neg" } : { arrow: "▲", cls: "pos" };
}

/** #110 — slugify a (Vietnamese) name → a kebab id, matching the BE slug so the user
 *  doesn't type an id (e.g. "Uống nước" → "uong-nuoc", "Tập thể dục" → "tap-the-duc").
 *  Strips diacritics (NFD + combining marks), maps đ→d, lowercases, non-alnum→hyphen,
 *  collapses + trims hyphens. Empty/diacritic-only → "". */
export function slugifyVi(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")   // strip combining diacritical marks
    .replace(/đ/g, "d").replace(/Đ/g, "d")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")       // any run of non-alnum → a single hyphen
    .replace(/^-+|-+$/g, "");          // trim leading/trailing hyphens
}

/** duration in ms (or null) → "405ms" / "3.1s" / "2m 5s". null/NaN/neg → fallback. */
export function fmtDuration(ms: number | null | undefined, fallback = "—"): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return fallback;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

/** ISO-8601 (or null) → "HH:MM" clock (local). null/invalid → fallback. */
export function fmtClock(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return fallback;
  const d = new Date(t);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** percent value (0-100) → "80.8%". null → fallback (NOT "0%" — null means no data). */
export function fmtRate(v: number | null | undefined, fallback = "—"): string {
  if (v == null || !Number.isFinite(v)) return fallback;
  return `${v.toFixed(1)}%`;
}

/** ISO-8601 due instant → Vietnamese FUTURE-OR-PAST relative phrase, e.g.
 *  "trong 3 giờ" (future) / "2 ngày trước" (past) / "vừa tới hạn" (within a min).
 *  Display-only — does NOT decide overdue (the backend `overdue` boolean does).
 *  null/invalid → fallback. */
export function fmtDueAt(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return fallback;
  const diffMs = t - Date.now(); // >0 = future (due later), <0 = past (overdue-ish)
  const future = diffMs >= 0;
  const sec = Math.floor(Math.abs(diffMs) / 1000);
  if (sec < 60) return "vừa tới hạn";
  const min = Math.floor(sec / 60);
  const unit =
    min < 60 ? `${min} phút`
    : min < 1440 ? `${Math.floor(min / 60)} giờ`
    : min < 43200 ? `${Math.floor(min / 1440)} ngày`
    : `${Math.floor(min / 43200)} tháng`;
  return future ? `trong ${unit}` : `${unit} trước`;
}

/** ISO-8601 → absolute "DD/MM HH:MM" stamp (local) for a precise due time. null → fallback. */
export function fmtDateTime(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return fallback;
  const d = new Date(t);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${dd}/${mm} ${hh}:${mi}`;
}
