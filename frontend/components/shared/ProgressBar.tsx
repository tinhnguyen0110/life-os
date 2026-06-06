/* ============================================================
   ProgressBar — percent fill, health-colored. Ported from mock
   screens-projects.js `.barc > i` (inline variant w/ trailing % label) and the
   `.bar > i` block variant. Handles null progress (backend returns null when
   status.md omits it) → renders an em-dash, no fill, never NaN width.
   ============================================================ */
import type { ProjectHealth } from "@/lib/types";

/** health → fill color (CSS var). Mock `healthDot`. dead = muted text color. */
const FILL: Record<ProjectHealth, string> = {
  act: "var(--green)",
  slow: "var(--amber)",
  stall: "var(--red)",
  dead: "var(--tx-2)",
};

export function ProgressBar({
  value = null,
  health = "act",
  variant = "inline",
  showLabel = true,
}: {
  /** 0..100 or null (unknown — backend omitted progress). Optional → null. */
  value?: number | null;
  /** drives fill color; defaults to act. */
  health?: ProjectHealth;
  /** "inline" = .barc + trailing %, "block" = full-width .bar. */
  variant?: "inline" | "block";
  showLabel?: boolean;
}) {
  // Clamp to [0,100]; null/NaN → 0 width + em-dash label (no fabricated value).
  const known = value != null && Number.isFinite(value);
  const pct = known ? Math.max(0, Math.min(100, value as number)) : 0;
  const color = FILL[health] ?? FILL.act;
  const barClass = variant === "block" ? "bar" : "barc";

  return (
    <span data-testid="progress-bar" data-value={known ? pct : "none"}>
      <span className={barClass}>
        <i style={{ width: `${pct}%`, background: color }} />
      </span>
      {showLabel && (
        <span className="num" style={{ marginLeft: variant === "inline" ? 0 : 8 }}>
          {known ? `${pct}%` : "—"}
        </span>
      )}
    </span>
  );
}
