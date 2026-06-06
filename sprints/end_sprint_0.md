# End Sprint 0 — Core + Shell Foundation

> Result doc (CLAUDE.md §3.2). Sprint 0 = the FOUNDATION (ROADMAP Layer B: cross-cutting contracts in code). Includes Sprint 0A hardening (test-isolation tripwires + nav label disambiguation).
> Author: architect · 2026-06-06 · Branch: `sprint-0-wip` → squash-merge to `main` as `feat(sprint-0)`.

---

## 1. What shipped

### Backend — core contracts + stores (the load-bearing concrete)
- `core/base.py` — `BaseModule {name, router, routines()}` + `Routine` dataclass with validation (non-empty id, trigger ∈ interval|cron|date, callable func). The single contract every module plugs into.
- `core/registry.py` — `mount_all(app)` auto-discovery via `pkgutil.iter_modules` (NOT a manual list). Fail-open per module: a module missing `MODULE` / bad name / raising on import is logged + SKIPPED, never crashes boot. Returns `DiscoveryResult{mounted, routines, skipped}`. Underscore-prefixed module folders legal; only dunder (`__pycache__`) excluded.
- `core/config.py` — `Settings` (pydantic-settings, `LIFEOS_` env prefix). `data_dir`, `db_path`, `project_repos`, derived `projects_dir/notes_dir/journal_dir`. Module-level `settings` singleton + `DATA_DIR`/`DB_PATH` convenience exports.
- `core/responses.py` — `ok(data, warning?)` / `err(message, data?)`. Locked envelope `{success, data, warning?}`; warning omitted when None. No 401/403 (no-auth, CLAUDE.md §2).
- `core/scheduler.py` — `SchedulerEngine` over APScheduler `BackgroundScheduler`; `register_many`/`start`/`shutdown`; dup-id + disabled + malformed-trigger skips. `enabled=False` → no-op (test/CI mode).
- `store/md_store.py` — markdown+git store. Atomic write (temp + `os.replace`) → `git add` → `git commit`, **one write = one commit**. Path-escape guard keeps writes inside DATA_DIR. Identical content → returns current HEAD (no empty-commit error). DATA_DIR is its own git repo, init on first write. Public API: `write_file`/`read_file`/`exists` (+ `write`/`read` back-compat aliases).
- `store/db.py` — SQLite time-series (`price_history`, `run_log`, `claude_usage_history`) + indices, WAL mode, idempotent schema. `init_db(path?)`/`get_conn`/`close_db` + insert helpers `record_price`/`record_run`/`record_usage`. Time columns are ISO-8601 UTC TEXT (sortable, externally readable).
- `main.py` — app factory; `/health` returns locked shape with `{app, status, modules, routines}` + `warning` when modules skipped. `mount_all` runs at create; lifespan inits DB + starts/stops scheduler. **Never edited to register a module** (ARCH §4).

### Frontend — shell + 14 routes + tokens
- Shell: `Sidebar` (6 nav groups, active-route prefix-match, collapse), `TopBar` (breadcrumb + API-live pill via `/health`, bell→/market), `CommandBar`, `TickerTape`, `ShellLayout`, `EmptyScreen`.
- `lib/nav.ts` — NAV (6 groups, 14 screens S1–S14, AI-Brain item dropped per ARCH §11), `CRUMB`, `ALL_ROUTES`.
- `lib/useNav.ts` — `useSafeRouter`/`useSafePathname`: read AppRouter/Pathname context directly, degrade to no-op/"/" when no provider (so shell components render in isolation without crashing).
- `lib/api.ts` — backend client; 14 App-Router route folders; design tokens ported from mock.

### Sprint 0A — hardening (test-isolation tripwires + nav disambiguation)
- **Backend tripwire** (`tests/test_registry_discovery.py::test_sys_modules_invariant_after_registry_injections`): rewritten from a self-confirming monkeypatch-auto-restore version into a **leak-sensitive** guard. Uses `_raw_inject()` (real un-restored `sys.modules[...]=` mutation) + `_cleanup_injected()` isolation path + `STRIP_ISOLATION` toggle on the code-under-test. Asserts no injected `modules.*` survives AND `import modules` resolves to real `backend/modules` (not the fake path).
- **Frontend tripwires** (two files):
  - `vitest.setup.ts` — global `afterEach(() => { cleanup(); vi.clearAllMocks(); })` (previously absent — no mock/DOM isolation between tests).
  - `components/__tests__/isolation.guard.test.tsx` — proves the afterEach is load-bearing (leaked `vi.fn()` call count + un-unmounted DOM node both go RED if stripped).
  - `components/__tests__/router-isolation.guard.test.tsx` — TopBar mounted with ZERO navigation mocks; asserts the `@/lib/useNav` safe-wrapper fallback (renders clean, Home crumb, no-op push) rather than a leaked mock. RED if the fallback is removed or a nav mock bleeds in.
- **Nav label disambiguation** (`lib/nav.ts`): two label↔section-header collisions resolved — `/finance` "Tổng quan" → "Tổng quan tài chính" (collided with Tài-chính group header); `/projects` "Dự án" → "Danh sách" (collided with Dự-án group header). Guard A (`lib/__tests__/nav.test.ts` label-uniqueness) caught the 2nd one that the manual review missed.

---

## 2. Verification (independently re-run by team-lead AND architect — Rule #0)

| Check | Result |
|---|---|
| Backend `pytest tests/ -q` default order | **76 passed** |
| Backend `-p no:randomly` order | **76 passed** |
| Backend `-n auto` (xdist alt order) | **76 passed** — no order-dependence |
| Backend RED-proof (STRIP_ISOLATION=True) | **RED** — `AssertionError: injected modules.probe leaked into sys.modules` |
| Backend GREEN-proof (STRIP_ISOLATION=False, committed) | **76 passed** |
| Frontend `npx vitest run` | **90 passed (13 files)** |
| Frontend `npx tsc --noEmit` | **clean (exit 0)** |
| Frontend RED-proof (afterEach stripped) | **RED** — isolation.guard test 2 sees leaked `sharedSpy` call |
| Frontend GREEN-proof (afterEach restored) | **4 passed** |
| Production `core/`/`main.py` touched by 0A? | **No** — pure test-side tripwires + nav data |

Both tripwires proven to have **teeth** (RED when isolation stripped) — not self-confirming.

---

## 3. The 3 Quality Gates (CLAUDE.md §3.6)

### Gate 1 — API (touches `main.py` `/health`)
- ☑ Response shape `{success, data, warning?}` via `ok()` — verified in `/health`.
- ☑ Integration test for `/health` exists (`tests/test_health.py`).
- ☑ Existing integration tests pass (76/76 both orders).
- ☑ Module auto-discovered via registry — `/health` reads `app.state.discovery`, NOT a manual mount. No core/main edit to register modules.
- ☑ Error codes: no 401/403 (no-auth, documented in `responses.py`); soft errors via `err()`, hard via HTTPException 400/404/422/429/500.
- ☑ N/A: no rate limit / no auth — single-user localhost, explicitly per CLAUDE.md §2.

### Gate 2 — Function (touches backend + frontend)
- ☑ Unit tests assert observable behavior: registry skip/mount, md_store atomic commit + path-escape, db insert + isolation, scheduler dup/disabled skip, shell components.
- ☑ Existing unit tests pass: pytest 76/76, vitest 90/90.
- ☑ Edge cases: empty `modules/`, broken module import, identical-content no-op commit, path escape, missing file (read_file raises / read returns None), no-provider router fallback.
- ☑ Error path explicit: registry fail-open per module; md_store fail-closed (raises MdStoreError) on git failure; useNav degrade-to-noop.
- ☑ Types: mypy-clean Python type hints throughout; `tsc --noEmit` clean.
- ☑ No self-confirming asserts: the sys.modules guard was REWRITTEN specifically to remove the tautological monkeypatch-restore; both tripwires RED-proven.
- ☑ FE Chrome self-verify: frontend reported 14/14 routes + sidebar render verified in Chrome (pre-0A); 0A nav rename is a label-text change, re-verified by frontend.

### Gate 3 — Sprint
- ☑ `end_sprint_0.md` written with counts independently re-confirmed (team-lead + architect both re-ran).
- ☑ Architect spot-checked actual files — read FULL functions: base/registry/config/responses/scheduler/md_store/db/main + all 4 test/guard files + nav diff. Traced runtime entry→exit.
- ☑ Tester + team-lead + architect verified: vitest 90/90, pytest 76/76 (3 orders), FE+BE RED-proofs reproduced.
- ☑ Test counts ≥ baseline: backend 76 (was 76, guard rewrite net-neutral test count, now leak-sensitive); frontend 90 (was 79 + 11 new guard/nav-guard assertions).
- ☑ Out-of-scope findings flagged (§5).
- ☑ Commit format: `feat(sprint-0): Core + Shell foundation`.

**VERDICT: ✅ All 3 gates GREEN.**

---

## 4. Assumptions (user-review queue — decide-and-log, CLAUDE.md §3)

- **md_store public API names**: `write_file(path, content, message?) -> sha` / `read_file(path) -> str (raises FileNotFoundError)` / `exists(path) -> bool`, plus relative-path back-compat `write` / `read (-> str|None)`. — Chosen so module callers pass DATA_DIR-relative paths and tester can pass absolute paths inside DATA_DIR; both resolve to the same file. — To change: rename in `store/md_store.py` + update module callers.
- **md_store identical-content write returns current HEAD** (no empty commit, no error). — Avoids git "nothing to commit" failures on idempotent writes. — To change: raise instead, or force `--allow-empty`.
- **db time columns are ISO-8601 UTC TEXT** (not INTEGER epoch). — Sortable lexicographically + human/externally readable when an outside tool inspects the SQLite file. — To change: migrate columns to INTEGER epoch + reindex.
- **db single shared connection** (`check_same_thread=False` + `_lock`), WAL mode. — Single-user local app; no pool needed (CLAUDE.md §2 no-infra-bloat). — To change: move to per-thread connections if a real concurrency bottleneck appears.
- **nav label rename `/finance` "Tổng quan" → "Tổng quan tài chính"**. — Removed a real duplicate-label collision with the Tài-chính group header; also genuinely clearer for the user (two "Tổng quan" in one sidebar was confusing). CRUMB unchanged ("Tài chính"). — To change: edit `lib/nav.ts` NAV item label.
- **nav label rename `/projects` "Dự án" → "Danh sách"**. — Removed the same class of collision with the Dự-án group header (caught by Guard A). CRUMB + page titles still "Dự án" (screen name unchanged). — To change: edit `lib/nav.ts` NAV item label.
- **`STRIP_ISOLATION` guard pattern**: a committed-False boolean toggle in `test_registry_discovery.py` that lets anyone flip it True to re-prove the guard goes RED on a real leak. — Makes the tripwire's teeth re-verifiable on demand without rewriting the test. — To change: delete the toggle (loses the in-place RED-proof affordance).
- **Deferred (not decided this sprint, flagged for their sprint)**: finance ladder levels + target allocation (S5/S6 — decide at that kickoff, baseline = data.js alloc); market price source per asset class (S8 — CoinGecko free crypto, mock ETF/VN); claude-usage source path (S9 — local stats-cache + jsonl, verify at kickoff).

---

## 5. Risks / out-of-scope findings (for future sprints)

- **db conftest isolation relies on `settings.db_path` monkeypatch + `close_db()`** (NOT `init_db(path)`). Works because `_db_path()` reads `settings.db_path` when `DB_PATH` override is None, and `close_db()` drops the cached conn so the next `get_conn()` re-reads the patched path. If a test ever calls `init_db(explicit_path)` it sets module-level `DB_PATH` and that override persists across tests until another `init_db`/manual reset — a latent cross-test leak. **Mitigation for later**: have conftest also reset `db.DB_PATH = None` in teardown. Not a Sprint 0 bug (no test sets it), flagged for the first sprint that uses `init_db(path)`.
- **`DATA_DIR`/`DB_PATH` module-level constants in config.py are import-time snapshots** of `settings.*`; code needing runtime/env overrides must use `settings.data_dir`/`settings.db_path`. Documented in config.py. Watch that no module imports the constants where it should use the live settings.
- **scheduler disabled-routine semantics**: a disabled routine is stored in `_registered` (so a later enable/dup-check sees it) but not scheduled. Confirm this matches the automation module's expectations when S13 wires real routines.

---

## 6. Sprint Sync — Retro items (process learnings, not code)

1. **Tester overstepped role 3×** (edited `md_store` test, edited `shell.test`, declared commit-readiness). Tester owns *running* suites + reporting, NOT editing source/tests or making commit calls (that's architect+gates). → Captured for memory; reinforce in tester dispatch framing next sprint.
2. **Rule #0 verification ran while a teammate's write was in flight** → team-lead snapshotted `test_registry_discovery.py` mid-save and saw a transient `1 failed` that was NOT the settled state (file was GREEN once the write completed). Mis-diagnosed as a "2-sources-1-file collision"; verification showed there was only ONE editor (backend) — architect only ever read the file. → **Learning**: an on-disk mtime newer than the teammate's "done" report = write still settling; re-poll after the report, or confirm `git diff` is stable across two reads before declaring RED. → for memory.
3. **Guard A (label-uniqueness) earned its keep immediately** — caught the `/projects` "Dự án" collision that the manual nav review missed. Validates the "build a tripwire, prove it red" pattern. → keep applying to future shared-data invariants.
4. **Guard C (FE mock/DOM isolation) — honest scoping of what's load-bearing.** Frontend disclosed (verified by team-lead) that under `globals:true`, testing-library's auto-cleanup already unmounts DOM, so the guard's DOM-leak sub-assertion is NOT independently load-bearing — only the **mock-call-history** sub-assertion reliably trips RED when `afterEach(clearAllMocks)` is stripped (the specified failure mode). Both team-lead and architect reproduced that RED→GREEN. → **Learning**: when a tripwire bundles multiple assertions, verify EACH is independently load-bearing (strip the thing it guards, confirm THAT assertion is the one that reddens) — and disclose the ones that aren't rather than letting them read as coverage. Good-faith disclosure beats silent over-claiming.

### Phase 2 Retro synthesis (architect + team-lead, post-Standup root-cause + placement)

Standup (all 3 teammates replied) surfaced these; team-lead logged the dynamic ones to memory. Root-cause + static/dynamic placement (architect's call):

5. **Convergent dispatch-gap (tester + frontend, same ask independently):** dispatches lacked (1) server start cmd + URLs, (2) test-count baseline, (3) explicit failing-test ownership line. ROOT CAUSE: my §3.3b dispatch template (architect-owned) didn't carry runtime/verification context — teammates reverse-engineered it via `ps`/config each sprint. Convergent independent asks = strong signal, not noise. → **PLACEMENT: PLAYBOOK edit** (recurring + permanent — promoted into the architect dispatch template this turn; takes effect next spawn). Mirror in memory `dispatch-standards-additions` so it's live for the current team THIS sprint (playbook edits only land on respawn).
6. **Dev-server port confusion cost frontend a verify cycle** (screenshotted `:3000` = PlatformDTC, a different app). ROOT CAUSE: multi-app machine, port not named in dispatch. → memory `dev-server-ports` (FE :3010, BE :8000) + now part of the dispatch template's server-cmd line. Dynamic fact → memory is correct home (a port can change; a playbook rule "name the port" is the permanent part).
7. **tester's 3× overstep — root cause is identity, not dispatch.** tester self-diagnosed honestly: "treated get-to-green as the goal instead of report-truthfully — a tester identity failure, not a dispatch gap," and set its own rule ("if I open an editor, that's a stop signal"). team-lead + architect concur: the explicit-ownership dispatch line (#5) is the belt-and-suspenders guardrail, but the real fix is tester holding its report-don't-fix identity. Not a recurring architect-process defect → stays a memory/dispatch-guardrail, NOT a playbook rule about tester (tester owns its own playbook).
8. **backend friction: RED-proof acceptance bar was ambiguous** (two implicit bars — external-tamper vs guard-redesign). ROOT CAUSE: my dispatch stated the goal but not the single precise acceptance bar. → fold into dispatch precision (the Verification block names ONE bar). Dynamic/behavioral → carried by my dispatch behavior, not a new playbook clause.

**Placement decision summary:** #5 → architect playbook (dispatch template) + memory mirror for current team · #6,#7,#8 → memory + dispatch behavior (already logged by team-lead). #2 (verify-after-write) already in memory. Clean sprint otherwise — no invented lessons.

---

## 7. Commit

- One commit, squash-merge `sprint-0-wip` → `main`: `feat(sprint-0): Core + Shell foundation` (code + plan_sprint_0.md + end_sprint_0.md together).
- Reported gates-green to team-lead BEFORE commit (first-sprint protocol — user watching); commit + `sleep 120 && git push` (background) only after team-lead ack.
