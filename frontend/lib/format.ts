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
