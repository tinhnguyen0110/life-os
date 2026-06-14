# Sprint F2 — END · dogfood-audit minor fixes (H2/M3/M4/M5/S2) + M6 dissolved

> The 5 minor audit findings fixed. M6 (a 9th finding the M4 fix surfaced) correctly DISSOLVED — no fix.

## Commits (origin/main)
- `9e96304` — **M4** wire all 4 sidebar badges live (honest-mirror). [FE]
- `393a526` — **H2 + M3 + M5 + S2** backend minor fixes (batched). [backend]
- `3098582` — **M4** pct5h regression test follow-up. [FE]

## What shipped

### M4 — sidebar badges live (honest-mirror) [FE]
Badges read LIVE data (was static placeholders, all wired together per `sidebar-badges-static-placeholder`):
routines→activeCount (6, was 5), projects→summary.total (7, was 4), market→triggers.length (hidden when 0
alerts, was 2), **claude-usage→pct5h%** (matching the S9 screen + Home tile single-source). Parallel
`Promise.allSettled`, each fail-soft (null → falls back to static nav text, never blocks the sidebar).
**The honest-mirror gate ("badge must MATCH its screen's number") caught a wrong-FIELD read** — the badge
first used raw `pct` (1873%) while the screen uses `pct5h` (~13%); fixed to pct5h. The lesson: "wire to the
same source the screen uses" = the same FIELD, not just the same endpoint.

### H2 — GET /reliability read-only [backend]
`run_suite` no longer creates+deletes a probe note per request (a git write on a read). Grounding-eval reads
an EXISTING note read-only (`_pick_probe_note`); empty vault → honest `skipped_empty_vault` (not a write, not
a false pass). **Teeth (backend added): a test that SPIES md_store.write_file + delete_file and asserts NEITHER
is called across 2 run_suite calls** (catches a create+delete that nets zero — stronger than a commit-count).

### M3 — resolve_conflict validate-before-write [backend]
`conflict_is_open(id)` checked BEFORE `update_note` — a bad/already-resolved id → 404 with the target note
UNCHANGED (was a fail-open write-then-404). Both directions tested.

### M5 — decision_journal malformed → 422 [backend]
`get_decision` distinguishes malformed (file exists, parse fails → **422**) from absent (→ **404**) via
`entry_file_exists`. Corrupt ≠ not-found. Both tested.

### S2 — reliability fail-closed gate hardened [backend]
Added `insert_proposal`+`mark_decided` to both forbidden sets + asserts the registered-TOOLS reachable surface
(`_tool_reachable_symbols` = union of each tool's `__globals__` + module top-level), not just module names.
**Teeth (backend added): `test_S2_distinguishing_a_leaked_symbol_is_caught`** — plant a forbidden symbol
reachable from a fake server's tool surface → assert the gate WOULD report it leaked (same self-test principle
as the A3 harness; a gate that can't catch a planted leak is worthless).

## M6 — DISSOLVED (no fix) — team-lead decide-and-log
Wiring the claude-usage badge live (M4) surfaced raw top-level `pct = used/cap = ~1910%` (cumulative tokens ÷
a too-small 200k context-window cap). Investigated: it's a **latently-mismatched orphan field — NOTHING reads
it** (S9 screen + Home tile + the corrected badge ALL use `pct5h ?? pct` → show ~13%, correct). Disposition:
**NO ACTION** — not user-visible, the field is unused; fixing it adds no value (north-star). Revisit only if
raw `pct` is ever surfaced. (Logged as "no-action, by-consumer-mitigation.")

## Verified
Full pytest **1057 / 0 errors**, mypy clean. M4: vitest 531, tsc clean, Chrome live (badges match screens).
Architect Rule#0: H2 GET ×2 → 0 git commits; M5 corrupt → 422 / missing → 404; M3 (team-lead) bad-id → note
unchanged; S2 teeth in-suite. Each commit content-diffed (no cross-task/mining leak).

## Assumptions (user-review) — F2
- M4 badges: live data is source-of-truth; static nav.ts values are the fail-soft fallback (shown only on
  fetch-fail), NOT a competing source. claude badge uses pct5h (matches the screen).
- M6: raw top-level `pct` left as-is (unused orphan field; no consumer reads it). Revisit if ever surfaced.
- H2: GET /reliability is read-only (reads an existing note; empty vault → honest skip).

## Cycle closed
**All 8 dogfood-audit findings fixed** (S1/H1/P1 in F1; H2/M3/M4/M5/S2 in F2) + M6 correctly dissolved.
The dogfood → audit → fix cycle is complete.
