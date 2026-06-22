# end_sprint_115-SHARED-GIT-READER — consolidate read-only git-exec into core/git.py (Cairn #115, PROJECTS-UNIFY T4)

> Result. projects/reader.py and dev_activity/service.py each spawned `git` read subprocesses with DUPLICATE exec impls (different timeouts + failure contracts). Extracted ONE shared `core/git.py` read-only git-exec layer; both modules thin-route to it, BYTE-IDENTICAL behavior (both failure contracts preserved). Commit `<hash>` `refactor(sprint-115-shared-git-reader)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT mypy --no-incremental + suite + whitelist-superset check). Cairn #115 PROJECTS-UNIFY T4 — be-only, CLOSES on this commit. Pure refactor (no behavior change). Disjoint from #114 (FE, parallel).

## What shipped
| File | Change |
|---|---|
| `core/git.py` (NEW) | `READ_ONLY_GIT` whitelist (7 read subcommands — HARD invariant, refuses any mutating op) · `run_read_git(repo, args, *, timeout=10)` → stripped stdout, RAISE on fail (fail-CLOSED — the projects contract) · `run_read_git_proc(path, args, *, timeout)` → RAW CompletedProcess, no-strip/no-raise (fail-SOFT — the dev_activity contract) · `RepoUnreadable` · `is_git_repo`. |
| `tests/test_core_git.py` (NEW, 24) | deterministic fixed-input proof (same git log via old-inline AND new helper → byte-identical) + the whitelist refuses 16 mutating ops + both failure contracts pinned. |
| `projects/reader.py` (−24) | thin re-export aliases: `_READ_ONLY_GIT=core_git.READ_ONLY_GIT`, `_RepoUnreadable=core_git.RepoUnreadable` (same class → existing `except _RepoUnreadable` still catches), `_git=core_git.run_read_git`, `_is_git_repo=core_git.is_git_repo`. Old inline impl deleted. Zero caller change; the test import `from reader import _git, _READ_ONLY_GIT` still works. |
| `dev_activity/service.py` (routed) | `_scan_repo` git log → `core_git.run_read_git_proc(...)` preserving the 60s timeout + RAW (un-stripped) .stdout + the fail-SOFT try/except. Byte-identical. |

## Design (LOCKED — one exec layer, TWO contracts preserved, read-only HARD)
- **One safe exec point, module-specific PARSE stays put.** core/git.py owns the spawn + the read-only whitelist; projects keeps its health-bucket parse, dev_activity keeps its numstat/LOC parse. Only the EXEC moved.
- **🔴 read-only HARD invariant:** `_check_read_only` refuses any subcommand not on `READ_ONLY_GIT` → this module can NEVER run a mutating git op (defense-in-depth). The whitelist is a SUPERSET of both callers' needs (verified: reader uses log/ls-files/rev-list/rev-parse; dev_activity uses log — all whitelisted).
- **BOTH failure contracts kept distinct (the refactor's core correctness):** `run_read_git` = strip + RAISE (projects → dead status); `run_read_git_proc` = raw + FAIL-SOFT (dev_activity → skip+continue the scan). NOT collapsed — they differ on purpose.

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** core/git.py both fns + the reader aliases (the class alias preserves `except _RepoUnreadable`; the test import names preserved) + dev_activity routing (raw .stdout + 60s + fail-soft wrapper intact). **Whitelist-superset check:** grepped every git subcommand both callers use → all 7 in `READ_ONLY_GIT`, no out-of-whitelist → no `ValueError` regression. Staged #115-only (4 BE files; the 12 #114 FE files left dirty + untouched — parallel lane). ✅
- **🔴 mypy --no-incremental (cache OFF, the #113 stale-cache lesson):** core/git + reader + dev_activity → ZERO non-yaml errors. ✅
- **INDEPENDENT suite:** 214 passed (core/git 24 + projects + reader + dev_activity, forward); the whitelist teeth = 18 passed (refuses mutating ops — a real invariant test, not self-confirming). backend: 2356/0 FORWARD == REVERSE. ✅
- **🔴 pure-refactor proof methodology (backend's standout, recorded as a lesson):** backend FIRST tried a LIVE before/after snapshot → dozens of diffs, but ALL real-world DRIFT (commits landed mid-run, an auto→registered reclassify, scan re-reads) — **a live moving system CANNOT prove pure-refactor by snapshot.** Switched to DETERMINISTIC fixed-input (test_core_git.py: same git log vs a FIXED repo through old-inline AND new helper → byte-identical). The CORRECT proof. ✅

## 3 Gates
- **Gate 1 (n/a — no endpoint change):** internal helper refactor; no router/schema touched.
- **Gate 2 (Function):** the deterministic byte-identical proof + whitelist-refuses-mutating teeth + both contracts pinned + 214 passed + mypy --no-incremental clean + whitelist-superset. NOT self-confirming. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent mypy/suite; staged EXACTLY #115 BE (4 files, NO #114 FE / read_server / data / template leak — the 12 FE files correctly left dirty); commit format `refactor(sprint-115-…)`. ✅

## Assumptions (user-review)
- **core/git.py is read-only by whitelist** (7 subcommands). **How to change:** add a subcommand to `READ_ONLY_GIT` (only read-only ones — never a mutating op).
- **two failure contracts (raise vs fail-soft) kept distinct.** **How to change:** n/a — they're intentionally different (projects fail-closed, dev_activity fail-soft).

## Notes
- Cairn #115 PROJECTS-UNIFY T4 — be-only pure refactor. backend-w3 built; architect committed (§3 sole-committer). 🔴 **Lesson (recorded `pure-refactor-verify-deterministic-not-live-snapshot`):** a pure-refactor's "byte-identical" proof must use DETERMINISTIC fixed input, NOT a live before/after snapshot — a live system drifts (new commits, reclassifies, re-reads) and produces false diffs that mask whether the CODE changed behavior. backend caught this itself + switched. **Parallel-lane staging:** #115 (BE) committed while #114 (FE) is still in-flight in the SAME working tree — disjoint files, so I staged ONLY the 4 BE files + left the 12 FE files dirty/untouched (leak-check confirmed no FE in the staged set). This is the safe parallel pattern: implement ∥, commit serial, surgical-stage per lane. ⚠️ `code_insight/service.py:30` carries a 3RD copy of the git helper (out of #115 scope, correctly untouched) → logged #118 (low-pri, a future consolidation). Closes #115; PROJECTS-UNIFY (#112/#113/#114/#115) now BE-complete (#114 FE in flight).
