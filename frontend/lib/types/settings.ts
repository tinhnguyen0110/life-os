/* ============================================================
   Settings / AppConfig (S12) — MIRRORS backend modules/settings/schema.py (FROZEN).
   Global app-config the Settings screen edits + routines read. PATCH is partial
   (every field optional → AppConfigPatch); a bad field is a PER-FIELD 422 (FastAPI
   detail[] with loc:["body",<field>]). Defaults = current hardcoded behavior.
   ============================================================ */
export type ErrorChannel = "discord" | "inapp" | "none";
export interface AppConfig {
  automationEnabled: boolean;
  /** hour-of-day 0-23 (UTC) morning-pull + brief run. */
  briefHour: number;
  /** idle-hunter flags projects idle > this many days (≥1). */
  idleThresholdDays: number;
  patternCheckEnabled: boolean;
  errorChannel: ErrorChannel;
  /** display timezone label (stored-only this sprint), 1-64 chars. */
  timezone: string;
  /** owner display name (stored-only; may be empty), ≤80 chars. */
  displayName: string;
  /** W4d (USER-ORDERED, reverses D8 proposals-only): ON = agent writes land in the
   *  wiki vault DIRECTLY (auto-accepted at the create_proposal chokepoint, decidedBy
   *  "agent:auto", still fully audited); OFF (default) = proposals-only, human ratifies
   *  in P1. Optional in the TS type because the backend field lands in W4d-BE (parallel) —
   *  the FE treats a missing value as `false` (safe default) so it's robust pre-BE. */
  wikiAgentAutonomous?: boolean;
  /** FINANCE-ASSISTANT capital-tilt (user-configurable): the USD thresholds that pick
   *  the allocation capitalTier ("small" below smallUsd, scaling toward largeUsd). The
   *  decision/allocation tilt reads these — surfaced here so the user can tune them. */
  riskCapitalSmallUsd?: number;
  riskCapitalLargeUsd?: number;
  /** #72 SIDEBAR-UX (feature B): user-pinned nav routes, rendered as a "📌 Ghim" group
   *  at the top of the sidebar (in this order). Persisted BACKEND (not localStorage) —
   *  this is the multi-device-sync point. Optional in the type until backend-2 freezes
   *  the field; the FE treats a missing value as [] (no Ghim group). */
  pinnedRoutes?: string[];
}
/** Partial update — only provided keys change. extra=forbid (unknown key → 422). */
export type AppConfigPatch = Partial<AppConfig>;
