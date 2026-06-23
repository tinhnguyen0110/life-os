/* ============================================================
   ProgressBar — percent fill, health-colored. Ported from mock
   screens-projects.js `.barc > i` (inline variant w/ trailing % label) and the
   `.bar > i` block variant. Handles null progress (backend returns null when
   status.md omits it): renders ONLY a muted em-dash — NO empty track. An empty
   0%-width track reads as "0% done" (a fabricated low value); an honest
   "unknown" must be visually distinct from a real 0%, so we omit the bar.
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
  // Clamp to [0,100]; null/NaN → unknown: NO track, just a muted em-dash
  // (an empty 0%-width track would masquerade as a real 0% — honest-mirror).
  const known = value != null && Number.isFinite(value);
  const pct = known ? Math.max(0, Math.min(100, value as number)) : 0;
  const color = FILL[health] ?? FILL.act;
  const barClass = variant === "block" ? "bar" : "barc";

  // Unknown progress → render only the em-dash (no fake bar). Muted so it reads
  // as "no data" rather than a value. data-value="none" preserved for tests.
  if (!known) {
    return (
      <span data-testid="progress-bar" data-value="none">
        {showLabel && (
          <span
            className="num"
            style={{ color: "var(--tx-2)", opacity: 0.7 }}
            title="Chưa có tiến độ trong status.md"
          >
            —
          </span>
        )}
      </span>
    );
  }

  return (
    <span data-testid="progress-bar" data-value={pct}>
      <span className={barClass}>
        <i style={{ width: `${pct}%`, background: color }} />
      </span>
      {showLabel && (
        <span className="num" style={{ marginLeft: variant === "inline" ? 0 : 8 }}>
          {`${pct}%`}
        </span>
      )}
    </span>
  );
}
