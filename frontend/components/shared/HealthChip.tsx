/* ============================================================
   HealthChip — project health bucket as a copper-token .sbadge.
   Ported from mock screens-projects.js `healthSb` + the .sbadge markup.
   Pure presentational (no client state). Backend derives `health`; we render.
   ============================================================ */
import type { ProjectHealth } from "@/lib/types";

/** health → (.sbadge variant class, label). Labels match mock `healthLbl`
 *  (data.js) + the S2-T1 dispatch: act→healthy, slow→chậm, stall→đứng, dead→chết. */
const HEALTH: Record<ProjectHealth, { cls: string; label: string }> = {
  act: { cls: "sb-act", label: "healthy" },
  slow: { cls: "sb-slow", label: "chậm" },
  stall: { cls: "sb-stall", label: "đứng" },
  dead: { cls: "sb-dead", label: "chết" },
};

export function HealthChip({ health }: { health: ProjectHealth }) {
  // Fall back to `dead` styling for any unexpected value rather than crashing
  // (defensive — backend is the source of truth but never trust a raw payload).
  const h = HEALTH[health] ?? HEALTH.dead;
  return (
    <span className={`sbadge ${h.cls}`} data-health={health} data-testid="health-chip">
      <span className="dot" style={{ width: 5, height: 5, background: "currentColor" }} />
      {h.label}
    </span>
  );
}
