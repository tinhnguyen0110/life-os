/* ============================================================
   Graveyard (S4) — MIRRORS backend modules/graveyard/schema.py (Sprint 8, FROZEN).
   A grave = an abandoned project. lesson is null when not recorded (never
   fabricated). Derived pattern stats (avgPeak) carry their inputs. render-only.
   ============================================================ */
export interface GraveProject {
  id: string;
  name: string;
  /** abandonedProgress; fallback progress; else 0. */
  peak: number;
  reason: string;
  /** status.md lesson, else null (never fabricated). */
  lesson: string | null;
  /** abandonedAt ISO-8601 UTC; FE formats. */
  died: string;
  users: number;
  /** commit-age health — DISPLAY ONLY (abandoned ≠ dead). */
  health: string;
  repo: string;
}
export interface ReasonCount {
  reason: string;
  count: number;
}
export interface GraveyardStats {
  graves: GraveProject[];
  count: number;
  avgPeak: number;
  commonReasons: ReasonCount[];
  /** graves with users>0 at abandon. */
  reachedUser: number;
  /** graves with users==0 (build-to-90/0-user pattern). */
  beforeUser: number;
  lessons: string[];
}
