# End Sprint 1 — Projects module (BE) + the common ProjectStatus shape [Tier-S]

> Result doc (CLAUDE.md §3.2). Sprint 1 = the FIRST feature module plugged into the Sprint-0 core, and the sprint that LOCKS the common ProjectStatus shape every one of the 14 screens + every later reader (finance/market/journal) inherits.
> Author: architect · 2026-06-06 · Branch: `sprint-0-wip` (continued) → squash to `feat(sprint-1)` on `main`.

---

## 1. What shipped

### `backend/modules/projects/` — first registry-discovered feature module (zero core edit)
- **schema.py** — the FROZEN `ProjectStatus` (12 SPEC keys + additive `desc`), `ProjectMetrics`, `ProjectRegisterInput`, `ProjectAbandonInput`. Constraints: id/name min_length, progress/users ge/le bounds, health `Literal[act|slow|stall|dead]`.
- **reader.py** — READ-ONLY local git reader. `read_project(repo_path, *, meta=None) -> ProjectStatus`. Hard read-only invariant: a `_READ_ONLY_GIT` whitelist (`rev-list/rev-parse/log/status/ls-files/cat-file/show-ref`) is enforced BEFORE exec — a mutating subcommand is structurally impossible. Fail-open: missing/non-git/empty/unreadable → `health="dead"`, never raises. Derives lastDays/health/metrics; human fields from meta (never fabricated). bool-as-int edge rejected; lang tie-break deterministic.
- **service.py** — project registry + orchestration. `_tracked_repos()` = `config.project_repos` ∪ registered `status.md` dirs in DATA_DIR. `list_projects() -> (statuses, warnings)` (excludes abandoned, fail-open), `get_project(id)` (includes abandoned), `register/abandon/refresh_project` write paths (each one md_store commit). YAML front-matter parse fail-open. abandon orthogonal to health.
- **router.py** — 5 endpoints, locked envelope `{success,data,warning?}`: `GET /projects` (+ server-computed health summary for the S2 bar, excl abandoned), `GET /{id}` (incl abandoned, 404), `POST /projects` (register, 400 non-git / 409 collision / 422 body), `POST /{id}/refresh` (lastAuto), `POST /{id}/abandon` (graveyard flag). `MODULE = BaseModule(name="projects", router, routines=[wiki-refresh])` → registry auto-discovers it.
- **wiki-refresh routine** (T3) — interval 6h, re-reads every tracked project's git + persists lastAuto, fail-open per project, never pulls. Same code path as `POST /{id}/refresh`.
- **config** (T3) — shortlist into `project_repos` via a PORTABLE `TINHDEV_ROOT = BACKEND_ROOT.parent.parent` derivation (+ `LIFEOS_PROJECT_REPOS` env override), per-host dir-existence check — no machine-hardcoded path.

### Live milestone (verified by team-lead booting the app)
`/health` → modules:["projects"], routines:["wiki-refresh"] · `/projects` → summary {act:2,slow:1,stall:3,dead:0,total:6} over 6 REAL repos · `/projects/outboundos` → act, 1 day, 500 commits, Python · `/projects/nope` → 404. **First real API serving real data from the user's actual git repos, end-to-end through the registry.**

### Sprint 1A (reactive, folded into this commit) — hidden-dir phantom-project fix
- **Live-facing data bug caught at the gate** (NOT by the 216-green suite — only the live app with a real `.claude/` exposed it): `GET /projects` returned a phantom `.claude` project because `_tracked_repos()` mounted EVERY subdir of `projects_dir`, including the hidden `.claude/` agent-memory dir landing under DATA_DIR. Fix: `service.py` skip `child.name.startswith(".")` (hidden dirs are never projects — honest-mirror, SPEC §0). It's a FILTER not deletion (`.claude/` persists on disk; the code excludes it structurally). Regression test `test_hidden_dirs_are_not_projects` (RED without filter, surgical: hidden excluded + real project kept + no dot-id in public list). 217 passed all orders. See plan_sprint_1A.md.

### Sprint 1A-isolation (hardening, same theme) — test isolation + stale-assertion fixes
- Group A: 3 Sprint-0 tests that hardcoded "zero modules" (`test_health::test_empty_modules_on_scaffold`, `test_health_after_empty_registry`, `test_registry::test_modules_clean_after_injection_scope`) updated for the now-present projects module. The registry guard's **canary-leak detection kept at full strength** (asserts injected `canary` absent from mounted + sys.modules) — only the obsolete `mounted == []` environment assumption dropped. Assert the INVARIANT, not the environment.
- Group B: `TestServiceListProjects` tests now use the `isolated_paths` fixture (clean tmp DATA_DIR) — fixes the cross-test/xdist state bleed (they were reading/writing the REAL `backend/data/projects/`).

---

## 2. Verification (Rule #0 — re-run independently by architect AND team-lead)

| Check | Result |
|---|---|
| pytest default | **216 passed** |
| pytest `-p no:randomly` | 216 passed |
| pytest `-n auto` (xdist) ×3 | 216 / 216 / 216 — no parallel flakiness |
| pytest `tests/test_projects.py` alone | green |
| `backend/data/projects/` clean post-`-n auto` run | PASS — only `.gitkeep` (no test writes to real DATA_DIR) |
| read-only guard teeth (team-lead broke `_READ_ONLY_GIT`) | RED→revert→green ✓ |
| registry canary guard teeth (team-lead forced a leak) | RED→revert→green ✓ |
| Production read-only: OutboundOS HEAD | `87bb944` UNCHANGED since sprint start — reader never wrote to repos |
| ProjectStatus shape vs SPEC §0 line 207 | 12 keys exact + order + types ✓ (architect key-by-key) |

**Acceptance bar met:** stable green in EVERY order (incl xdist), DATA_DIR clean, both guards proven to have teeth, production read-only proven.

---

## 3. The 3 Quality Gates

### Gate 1 — API (router.py)
☑ Schema constraints (min_length, ge/le, Literal) · ☑ integration test per endpoint (16) · ☑ existing tests pass (216) · ☑ module auto-discovered (NO core/main edit — verified in /health) · ☑ envelope `{success,data,warning?}` · ☑ error codes 400/404/409/422 (no 401/403 — no auth).

### Gate 2 — Function (backend)
☑ Observable-behavior asserts (reader derivation, fail-open, read-only invariant, service union, write paths) · ☑ existing pass (216) · ☑ edge cases (missing/empty/detached/non-git/malformed-YAML/bool-as-int) · ☑ error path explicit (reader fail-open; md_store fail-closed; ProjectError→HTTP code) · ☑ types complete (mypy clean) · ☑ no self-confirming asserts — both guards teeth-proven · ☑ N/A FE (BE-only sprint).

### Gate 3 — Sprint
☑ end_sprint_1.md written + counts re-confirmed by architect AND team-lead · ☑ architect 4-step review on full functions (reader/service/router read entry→exit) · ☑ tester cold run (serial + xdist) + team-lead teeth-check · ☑ counts ≥ baseline (Sprint-0 76 → 216, +140 from projects + un-skipped API) · ☑ out-of-scope flagged (§5) · ☑ commit format `feat(sprint-1)`.

**VERDICT: ✅ All 3 gates GREEN.**

---

## 4. Assumptions (user-review queue — decide-and-log)

- **ProjectStatus shape FROZEN** (SPEC §0 line 207): `{id,name,health,progress,users,last,lastDays,next,repo,metrics{commits,branch,lang,testPass,stars},routines,lastAuto}` + additive `desc`. — Every later reader inherits it. — To change: a coordinated migration across all readers + frontend types.
- **health buckets**: act ≤7d · slow ≤30d · stall ≤90d · dead >90d (or unreadable). — From the real repo-age spread (decide-and-log). — To change: edit the `_ACT/_SLOW/_STALL_MAX_DAYS` constants in reader.py.
- **progress = status.md `progress:` else None; next = status.md `next:` else None; users = status.md else 0.** — NO heuristic / NO TODO-scrape: a fabricated progress % or scraped "next" is plausible-but-wrong derived data; honest None ("—") beats a confident lie. — To change: add a derivation source.
- **list_projects = `config.project_repos` ∪ {projects with a registered status.md in DATA_DIR}.** A project registered via `POST /projects` persists a status.md and surfaces in the list independent of the config dict — runtime registration is first-class (SPEC §S12 ref-not-embed, add-a-project-without-code). — This was surfaced by a flaky test whose assumption ("empty config → empty list") was WRONG; the service union is correct intent. — To change: make list config-only + a separate `/projects/registered` endpoint.
- **abandon is ORTHOGONAL to health**: `POST /{id}/abandon` sets `abandoned/reason/at/progress` in status.md (graveyard, S4) and does NOT touch the commit-age `health` field. list excludes abandoned; get includes it; the wiki-refresh routine skips abandoned (they're not re-read). — Keeps an explicit human "I quit this" separate from "no recent commits". — To change: couple them (not recommended).
- **status.md = single persisted source** (human fields name/desc/goal/progress/next/users + cached derived abandoned*/lastAuto); git read live each call. YAML front-matter `---\n…\n---`. — One source for everything human/cached; git for everything derived. — To change: split human vs cached into separate files.
- **wiki-refresh cadence = interval 6h.** — Cheap local-git read, idempotent, not so frequent it churns. — To change: trigger_args in router.py.
- **stars/testPass = None this build** (no GitHub API / no test-artifact parser); **repo pointers READ-ONLY local git, never pull/fetch** (hard invariant, asserted). **config paths derived from `TINHDEV_ROOT` (portable), `LIFEOS_PROJECT_REPOS` override.**

---

## 5. Risks / out-of-scope findings (for future sprints)

- **wiki-refresh re-reads on a 6h interval but `lastAuto` write = one git commit to DATA_DIR each.** Over time the DATA_DIR git repo accumulates a refresh commit per project per 6h. Not a problem at this scale (single user, ~6 projects), but if project count grows, consider only committing on actual change (md_store already returns HEAD on identical content — verify the routine isn't forcing no-op `lastAuto`-only commits churn; `lastAuto` always changes so it WILL commit each run). **Mitigation later:** make the routine skip the lastAuto write when nothing else changed, or batch.
- **`register_project` validates the repo is a git repo, but a registered status.md with a repo pointer that later disappears** → that project reads as dead (fail-open, correct) but stays in the list forever. No "unregister" endpoint this sprint. Flag for the Projects-management sprint (S12).
- **Frozen shape has `desc` (13th field)** beyond SPEC's 12 — additive + nullable, safe, but the frontend `types.ts` mirror (future FE sprint) must include it.
- **[Quick-Fix, next push] `api_client` fixture (test_projects.py:518) raw-assigns `config.settings.data_dir`** instead of `monkeypatch.setattr` → never auto-restored, leaves the global mutated within a pytest session. NON-HARMFUL now (every service test isolates via `isolated_paths`, so 216 passes every order incl `-n auto` ×7 across backend+team-lead), but it's a latent global-state leak of the same class that bit us — it WILL bite the day a test relies on `data_dir` being the real path after `api_client` runs. Owner: tester (its own fixture). Tier: Quick Fix (<10 lines, raw-assign → monkeypatch). Batched into the NEXT push, not a separate commit (CLAUDE.md §3.4).
- **[carried from Sprint 0] `init_db(path)` module-level `DB_PATH` override** persists across tests until reset; conftest resets via `close_db()` not `DB_PATH=None`. Not triggered this sprint (no test calls `init_db(path)`). Mitigation: conftest teardown should also reset `db.DB_PATH = None`.

---

## 6. Sprint Sync — Retro (process learnings)

1. **Stale-snapshot false-divergence (×2)** — twice a teammate (and team-lead) read a file mid-write and reported a conflict/state that had already changed by current mtime (the reader-signature "collision", the "test untouched at 15:19" when it was realigned at 15:31). ROOT: reading at an un-settled moment. FIX: read at current mtime / confirm git diff byte-stable across two reads before arbitrating. → memory `verify-after-write-settles` (extended to inter-teammate reads).
2. **Ownership deadlock + the nuance** — architect over-applied "tester doesn't edit tests" to tester's OWN scaffold → both tester and backend refused to touch it → deadlock. FIX (the nuance): tester MAY sync its own scaffold to a ratified contract; may NOT edit others' tests or mask failures. → memory `tester-scaffold-ownership` + tester playbook.
3. **Guard asserts the INVARIANT, not the environment** — the Sprint-0 registry guard hardcoded `mounted == []` ("no modules yet"), which the first real module legitimately invalidated. The canary-leak half (the real teeth) was written right; the `==[]` half baked in a transient fact. FIX: guards assert the invariant (no leak), never the current-sprint environment.
4. **DATA_DIR-clean-as-acceptance-gate** — a test passing ≠ a test isolated; an un-isolated test can pass while still writing to real DATA_DIR. Asserting `data/projects/` stays clean (.gitkeep only) after a full `-n auto` run is concrete proof of isolation. New acceptance gate for any sprint with DATA_DIR writes.
5. **Order-dependent green ≠ acceptance** — the suite was green serial, red under xdist (config/DATA_DIR bleeding across parallel workers). tester's cold run was serial-only and missed it. FIX: cold run + acceptance MUST include `-n auto` (run 2-3× for non-determinism). The Sprint-0 "green in every order" standard now explicitly includes parallel.
6. **The catch of the sprint:** running the suite myself (Rule #0) instead of accepting the "it's just signature churn" framing surfaced a REAL unspecified product behavior (list union) AND the xdist isolation bug — both would have shipped silently under the churn framing. decide-and-log + verify-don't-trust working as designed.
7. **Live-app verification caught what the suite couldn't (Sprint 1A).** The test suite was 216-green, but tester's LIVE `/projects` curl exposed a phantom `.claude` project — a real production data bug invisible to tmp-dir tests (they never create a real `.claude/` under DATA_DIR). team-lead's HOLD was correct: a junk project on the user's day-one S2 screen violates honest-mirror. **Learning: for a real-data screen, "suite green" is necessary but NOT sufficient — verify the LIVE app against the REAL environment** (real hidden dirs, real repos) before shipping. The gate now includes a live `/projects` check, not just pytest.

---

## 7. Commit

- Squash the Sprint-1 work into one `feat(sprint-1): Projects module + ProjectStatus shape` on `main` (code + plan_sprint_1.md + end_sprint_1.md). `backend/data/` stays gitignored. Agent-memory stays gitignored.
- After commit: `sleep 120 && git push` (background, 2-min interrupt window) → notify.py the user → team-lead sends the 2-part Sprint Sync report → propose Sprint 2.
