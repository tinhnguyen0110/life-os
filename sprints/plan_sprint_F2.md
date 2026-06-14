# Sprint F2 — Dogfood-audit minor fixes · H2 + M3 + M4 + M5 + S2 · PLAN

> The 5 minor findings from the dogfood audit (memory `dogfood-audit-findings-2026-06-15`). Smaller → one batched sprint.
> Split: M4 [frontend/shell] · H2/M3/M5/S2 [backend].

## Kickoff — 2026-06-15

### Code read (all 5 surfaces confirmed on disk)
- **H2** — `reliability/service.py:142` `run_suite` does `create_note(...) + delete_note(...)` on EVERY `GET /reliability` → a read-looking GET mutates git history (delete is best-effort → orphan-probe risk on race).
- **M3** — `router.py` `resolve_conflict` calls `service.update_note(...)` (writes the vault) BEFORE checking the conflict exists/is-open → resolving an absent/already-resolved id mutates the note, THEN 404s (fail-open write).
- **M4** — `nav.ts` badges hardcoded: routines `"5"` but live = **6** (confirmed via /routines); projects `"4"`, market `"2"`, claude `"71%"` all static = honest-mirror violation.
- **M5** — `decision_journal/router.py` `get_decision` returns 404 for BOTH absent AND malformed (`get_entry` returns None for both) → a corrupt file reads as "not found" (corrupt ≠ absent). LIST honestly skips-with-warning; GET should too.
- **S2** — `reliability/service.py` `run_fail_closed_check` inspects `vars(read_server)`/`vars(write_server)` top-level names; the forbidden sets miss `insert_proposal`/`mark_decided`. Passes truthfully today but not regression-robust.

### Design decisions (logged)
- **H2:** `run_suite` should NOT mutate the vault on a GET. Fix = the grounding-eval runs against a READ-ONLY fixture — either (a) a dedicated pre-seeded probe note created ONCE at module init (not per-request), or (b) run the eval against an in-memory/synthetic note that doesn't go through the single-writer. Simplest: (a) but reuse an existing note if one exists, OR make the grounding-eval note-agnostic (the corpus's "real_span" case can target any existing note + a known substring). **Backend's call; the constraint = a GET must not write git history.** If no clean read-only path, the alternative is making it `POST /reliability/run` (a GET shouldn't mutate). Lean (a)/note-agnostic.
- **M3:** check `sync_store`-conflict validity (exists + open) BEFORE the `update_note` write. Reorder: validate conflict → write → mark resolved. A failed validity check must NOT have mutated the note.
- **M4:** wire all 4 sidebar badges live (one shell task, per `sidebar-badges-static-placeholder` — wire ALL together, not piecemeal): routines (live count from /routines = 6), projects (live count), market (live count), claude-usage (live %). The badges should read from the same live data the screens use.
- **M5:** `get_decision` distinguishes malformed (the file exists but `_parse` fails) → **422** "malformed", from absent (no file) → **404**. The service needs to signal which (e.g. `get_entry` returns a sentinel, or a separate `entry_exists` check + a parse attempt).
- **S2:** add `insert_proposal` + `mark_decided` to the forbidden sets AND assert on the registered TOOLS surface (the real capability boundary the agent sees), not just the module top-level names. Keep it deterministic.

### Final task list (F2)
- **M4 [frontend]** — wire all 4 sidebar badges live.
- **H2 + M3 + M5 + S2 [backend]** — read-only reliability GET, conflict-validity-before-write, malformed→422, reliability-gate hardening.

## Assumptions (user-review) — finalized in end_sprint_F2.md
- H2: reliability GET is read-only (no per-request vault write); fixture-based or note-agnostic eval.
- M3: conflict validity checked before the note write (no fail-open mutation).
- M4: all 4 sidebar badges live-wired (honest-mirror); routines now shows 6.
- M5: malformed decision file → 422 (distinct from absent → 404).
- S2: reliability gate asserts the registered TOOLS surface + insert_proposal/mark_decided forbidden.
