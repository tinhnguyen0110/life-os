# Plan Sprint 1A — hidden-dir phantom-project fix [Reactive, blocks Sprint 1 commit]

> Reactive sprint (CLAUDE.md §3.4b) — same theme as Sprint 1 (projects module), triggered by a real bug found in tester's cold run BEFORE the Sprint-1 commit. Folds into the `feat(sprint-1)` commit (it's a correctness fix for the data being shipped, not next-push).
> Author: architect · 2026-06-06 · Trigger: tester cold run + team-lead live repro.

## Bug
`GET /projects` (live) returns a phantom project `.claude`:
`ids = ['.claude', 'claudemanager', 'devcrew', 'groundwork', 'life-os', 'outboundos']`.

**Root cause:** `service.py::_tracked_repos()` iterates `settings.projects_dir` and skips only non-dirs. The agent-memory dir `backend/data/projects/.claude/` (a hidden dir physically under DATA_DIR) gets mounted as a project named ".claude". Tests didn't catch it (clean tmp dirs); only the live server with a real `.claude/` exposed it.

**Why blocking:** S2 Projects List is the FIRST real-data screen — a phantom ".claude" on day one violates the honest-mirror principle (SPEC §0). User-visible wrong data, not latent.

## Fix (backend, ~2 lines + 1 regression test)
1. `_tracked_repos()`: `if child.name.startswith("."): continue` — hidden dirs (`.claude`/`.git`/...) are never projects. Filter, not deletion (`.claude/` persists on disk as real agent-memory).
2. Regression test: a `.hidden` dir under an isolated `projects_dir` (isolated_paths) must NOT appear in `list_projects()`. RED without the filter, GREEN with it.
3. Confirm `slug()` can't produce a leading-dot id (it strips leading non-alnum → can't; just verify).

## Acceptance
- Live `GET /projects` ids = exactly the 6 real repos, NO `.claude`.
- `.claude/` still on disk under projects/ but absent from API output (proves the filter handles the real condition, not deletion).
- pytest green default + `-n auto` (217 with the new test).
- Gates 1/2/3 (same as Sprint 1; no shortcuts). Reader/service signatures FROZEN — filter inside an existing function, no API change.

## Flow
backend fix + test → team-lead re-verify live `/projects` → tester re-run → architect re-gate → commit `feat(sprint-1)` (Sprint 1 + 1A together).
