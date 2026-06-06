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
