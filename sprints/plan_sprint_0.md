# Sprint 0 — Core + Shell

> ARCH §9 step 0. Outcome: skeleton runs end-to-end, empty navigation works (FE shell renders all 14 routes as empty placeholders; BE FastAPI boots with registry auto-discovery + a health endpoint). NO feature modules yet.
> Written: 2026-06-06 (architect, fresh — no prior plan).

---

## Objective

Stand up the **skeleton both halves of the app run on** so every later sprint just "adds a folder":
- **Backend:** `core/` contract (BaseModule + registry auto-discover + config paths + scheduler engine), `store/` (md+git, SQLite), `main.py` wiring `registry.mount_all()`, `pyproject.toml`. Boots clean, `GET /health` returns ok, registry discovers zero modules without error.
- **Frontend:** Next.js App Router shell (Sidebar / TopBar / CommandBar / TickerTape) + 14 empty route placeholders + design tokens ported verbatim from mock `app.css` → `lib/tokens.css`. Navigation works, dark copper theme renders.

This is **pure scaffold** — no feature logic, no real data. The bar is: *the frame runs and you can navigate it empty.*

---

## Tasks

| # | Task | Owner | Gates | Depends |
|---|------|-------|-------|---------|
| T0.1 | BE core contract: `core/base.py`, `core/registry.py`, `core/config.py`, `core/scheduler.py` | backend | G2 | — (gating) |
| T0.2 | BE store layer: `store/md_store.py` (md+git), `store/db.py` (SQLite) | backend | G2 | — (parallel w/ T0.1) |
| T0.3 | BE app entry: `main.py` (`registry.mount_all()` + `/health`), `pyproject.toml`, dir scaffold (`data/`, `modules/__init__.py` empty) | backend | G1,G2 | T0.1, T0.2 |
| T0.4 | FE design tokens: port mock `app.css` → `frontend/lib/tokens.css` (vars, themes, fonts, component classes); `lib/api.ts` client stub; `lib/types.ts` shared ProjectStatus shape | frontend | G2 | — (parallel) |
| T0.5 | FE shell: `Sidebar` (6 nav groups, collapse), `TopBar` (crumb/API-live pill/refresh/bell), `CommandBar` (`>` prefix, ⌘K), `TickerTape` (mock loop) + root `layout.tsx` grid | frontend | G2 | T0.4 |
| T0.6 | FE 14 route placeholders: `app/page.tsx` + 13 route folders, each an empty `<EmptyScreen name=.../>` panel; sidebar links navigate correctly | frontend | G2 | T0.5 |

**Ordering:** T0.1 + T0.2 + T0.4 dispatch first (parallel, no deps). T0.3 after T0.1+T0.2 land. T0.5 after T0.4. T0.6 after T0.5. tester pre-scaffolds from Exports while BE/FE build.

**Parallelism:** backend (T0.1→T0.2→T0.3) and frontend (T0.4→T0.5→T0.6) run as two independent chains — no cross-dependency in Sprint 0. ≥2 agents working simultaneously ✓.

---

## Logic / Algorithm

Sprint 0 is **scaffold, not features** — almost all CRUD/wiring. The only non-trivial design decisions (architect-owned, decide-and-log):

### D1 — Registry auto-discovery mechanism (T0.1)
- **Rule:** `registry.mount_all(app)` scans `backend/modules/*/` for a package exposing a `module: BaseModule` (a `MODULE = SomeModule()` instance in `modules/<name>/__init__.py` or `router.py`). For each: `app.include_router(module.router, prefix=f"/{module.name}")` and collect `module.routines()` into the scheduler. Empty `modules/` → mount nothing, no error.
- **Discovery via** `pkgutil.iter_modules` over the `modules` package + `importlib.import_module`. NOT a manual import list. Adding a module = adding a folder (ARCH §4 core promise).
- **Why:** ARCH §4 locks "thêm module = thêm folder, không sửa core/main.py". This is the single most important contract in the codebase.
- **How to change:** convention (where `MODULE` lives, attr name) documented in `core/base.py` docstring; change there + registry scan.

### D2 — Common status shape (T0.4 `types.ts`, mirrors future BE schema)
- **Rule:** `ProjectStatus = {id, name, desc, health: 'act'|'slow'|'stall'|'dead', progress: number, users: number, last: string, lastDays: number, next: string, repo: string, metrics: {commits, stars, lang, test_pass}, routines: string[], lastAuto: string}` — verbatim from ARCH §5 / mock data.js.
- **Why:** every reader returns this one shape so core+FE+AI handle uniformly. Locking it in Sprint 0 prevents drift in Sprint 1 (Projects).
- **How to change:** edit `lib/types.ts` + the future `modules/projects/schema.py` together.

### D3 — Nav groups & routing (T0.5 Sidebar)
- **Rule:** 6 sidebar groups per SPEC §1 / mock NAV: Tổng quan(Home) · Dự án(Projects, Graveyard) · Tài chính(Finance, Portfolio, Journal, Market) · Hằng ngày(Claude Usage, Notes) · Hệ thống/Active(Routines/Automation, Activity) · Cấu hình(Brief, Settings). **14 screens S1–S14.**
- **Deviation from mock:** mock NAV has an "AI Brain" item — DROPPED (ARCH §11 excludes embedded AI this build). Mock groups "AI & Config" → renamed "Cấu hình" holding Brief + Settings. Badges shown as static placeholders in Sprint 0 (wired to real counts later).
- **Why:** SPEC §7 is the authority on the 14 screens; mock is design baseline not feature authority.
- **How to change:** edit Sidebar nav config array.

### D4 — Token port = verbatim, no redesign (T0.4)
- **Rule:** copy mock `app.css` `:root` vars, `.num/.pos/.neg/.mid/.acc/.kicker` helpers, component classes (`.card .panel .sbadge .bar .dtable .gauge` etc.), and THEMES/BG from `shell.js` into `tokens.css`. Port `spark()` SVG helper into a `lib/spark.ts`. Do NOT invent colors/spacing.
- **Why:** ARCH §8 / SPEC §5 — design is approved, port not redesign. Past projects drifted by "improving" tokens.

No finance/market/threshold logic this sprint (those land S2/S3/S5/S6 per implement order).

---

## Defensive cases (per task — detailed in dispatch)
- Registry: empty `modules/` dir, a module missing `router`/`name`, import error in one module must not crash the whole app (log + skip).
- md_store: data dir not a git repo yet (init on first write), concurrent write, write = atomic single commit.
- db: SQLite file absent (create + migrate schema on boot), WAL mode for the local single-user case.
- FE shell: collapsed sidebar state, route not found, ⌘K palette open/close, ticker with empty data.

---

## Verification (Sprint 0 done = all true)
- `uvicorn main:app` boots with **zero** modules, no traceback; `GET /health` → `{success:true,...}`; OpenAPI docs load at `/docs`.
- `registry.mount_all` proven to discover a *fake* test module (tester drops a throwaway `modules/_probe/` → endpoint appears → removed).
- `npm run dev` (or `next dev`) serves; all 14 routes reachable from sidebar; copper dark theme matches mock; console clean.
- pytest (core+store unit) 100%; vitest (shell components) 100%; tsc/mypy clean.
- Chrome self-verify (frontend) + tester Chrome pass on the shell.

## Gates
- G1 (API): `/health` only this sprint — schema + 200 + `{success,...}` shape + registry integration test.
- G2 (Function): unit tests for registry discovery, md_store commit, db init; shell components render; types clean.
- G3 (Sprint): end_sprint_0.md written, architect spot-check, tester 100% + Chrome, commit format `feat(sprint-0): core + shell scaffold`.

---

## Kickoff — 2026-06-06

### State check (no prior code)
- `backend/` and `frontend/` do **not exist yet** — this is greenfield scaffold. Repo currently holds only docs + mock `template/`.
- Mock confirmed at `template/Life Command/app/` — `app.css` (269 lines, full token set), `shell.js` (THEMES/BG/spark/gauge/tickerHTML), `data.js` (DB + NAV + CRUMB). All shapes verified.
- ARCH §1 path note: app repo root = `life-os/`; data lives `backend/data/` git-versioned. life-os itself is dogfooded as a tracked project later.
- Stack locked: Next.js App Router (FE), FastAPI + module/registry (BE), md+git & SQLite (data), APScheduler (sched). No-auth, single-user, no embedded AI.

### Drift since plan was written
- None — plan written same day as kickoff. Mock "AI Brain" nav item resolved (D3: dropped per ARCH §11).
- Open question for backend at dispatch: exact Python/Node toolchain (`uv`/`pip`, `pnpm`/`npm`) — backend/frontend choose per their playbook; not architect's call. Default to `pip`+`venv` / `npm` unless playbook says otherwise.

### Final task list
T0.1, T0.2, T0.3 (backend chain) · T0.4, T0.5, T0.6 (frontend chain). 6 tasks, 2 parallel chains, single session. No revisions to the table above.

## Kickoff confirmation — 2026-06-06 (post-approval, dispatch)

- User approved ROADMAP direction → Sprint 0 GO. Re-verified state: still greenfield (`backend/`, `frontend/` absent; only docs + `template/` + `sprints/`). No drift since plan written.
- TaskList already holds 3 grouped tasks (#1 backend = T0.1+T0.2+T0.3, #2 frontend = T0.4+T0.5+T0.6, #3 tester = verify). Dispatching as 3 units, not 6 — sub-tasks live inside each dispatch.
- Mock source re-confirmed for FE port: `app.css` `:root` (copper/warm tokens, `.num/.pos/.neg/.mid/.acc/.kicker`, `#app` 228px/64px grid, `.scanline`), `shell.js` `THEMES`(6)/`BG`(warm,cool)/`spark()`/`gauge()`/`tickerHTML()`/`applyTweaks()`. FE ports these verbatim.
- **Mock deviations locked (ARCH §11):** mock top-bar "Hỏi AI" button + `ai`/"AI Brain" nav item + `data-route="ai"` are DROPPED (no embedded AI this build). 6 nav groups → SPEC §1 grouping (Tổng quan / Dự án / Tài chính / Hằng ngày / Hệ thống(Active) / Cấu hình); 14 routes only.
- **Mode B note:** first execution under user's watch — architect reports gates-green to team-lead BEFORE commit/push (no silent auto-push this one time).
- First gate I check at review: **G1 on `/health`** (proves C4 response shape + C2 registry-discovery integration) — it's the foundation contract everything else inherits.

## Kickoff — 2026-06-06 (Sprint 0A: test-isolation regression guard)

### Drift / finding since last dispatch
- During backend build, a **test-fixture isolation risk** was found + root-caused in `backend/tests/test_registry.py::TestMountAllHappy._inject_module` (lines ~169-178): the helper injects a fake `modules` package whose `__path__` → tmp dir, so a registry-discovery test could make `/health` see phantom modules (e.g. `['probe']`) instead of `[]` if the injection ever survives teardown. Sprint-13 class: order-dependent, currently latent.
- **Empirical correction to the original note (Rule #0):** the on-disk code already uses `monkeypatch.setitem` (which auto-reverts) at every inject site — there are NO raw `sys.modules[...] =` writes remaining. Verified: `pytest -q` = 74 passed in BOTH default and forced (registry-before-health) order. The leak is **defended-by-luck**, not firing. `test_registry_discovery.py::test_sys_modules_invariant_after_registry_injections` already asserts cleanup-on-context-exit for the *correct* pattern.
- **Real gap:** there is no guard that goes RED if the isolation protection is ever *stripped* (someone swaps `setitem`→raw assignment in a future sprint). The invariant is unenforced against regression. That guard is the deliverable.

### Plan revision — Sprint 0A (reactive, §3.4b)
- T0A.1: Harden `test_registry.py` inject helpers — confirm/lock every `sys.modules` mutation goes through `monkeypatch.setitem`/`delitem` (save & restore), with an explanatory comment so no future edit reintroduces a raw write. Production `registry.py` untouched.
- T0A.2 (**the real deliverable**): a **deterministic regression guard** that FORCES the bad order in one session — inject a fake `modules` pkg via the registry path, then assert `/health` (real app) sees `modules == []`. Must be provably RED if isolation is removed, GREEN with it. Makes the latent bug deterministic so it cannot silently resurface.

### Final task list
T0A.1 + T0A.2 → backend (one dispatch, same theme). tester re-runs full suite in forced orders after. Gates 1/2/3 apply.
