# End Sprint 2 — Projects FE (S2 List + S3 Detail) + CORS

> Result doc (CLAUDE.md §3.2). The first SCREENS the user actually SEES — consuming the Sprint-1 frozen ProjectStatus over the live API. FE-only + a backend CORS gap fix surfaced by the live browser.
> Author: architect · 2026-06-06 · Commit: `feat(sprint-2)` on `main`.

---

## 1. What shipped

### Frontend — Projects screens + shared component layer
- **`lib/types.ts`** — reconciled `ProjectStatus`/`ProjectMetrics` to mirror backend `schema.py` EXACTLY (kickoff caught the drift: nullable fields, `testPass` camelCase, `branch` added, `last`=ISO). + `ProjectsSummary`/`ProjectsListData`.
- **`components/shared/`** — `HealthChip` (act/slow/stall/dead → tokens + healthLbl labels), `ProgressBar` (value 0–100|null → "—", never fabricated), `KpiCard`, `DataTable<Row>` (generic, clickable rows). Wrap the existing Sprint-0 `tokens.css` classes (no new CSS authored).
- **`lib/api.ts`** — `getProjects()`, `getProject(id)`, `apiPost<T>()` on the existing `apiGet`/`ApiError` pattern.
- **`lib/format.ts`** — `relativeTime` (ISO→human), `orDash`, `idleDays`.
- **S2 Projects List** (`app/projects/page.tsx`) — KpiCard summary bar straight from `data.summary` (render-only, NOT recomputed), projects DataTable (HealthChip/ProgressBar/users/last/routines/next), row→detail, client-side tab filter, loading/error/empty states, "Đăng ký dự án" stub.
- **S3 Project Detail** (`app/projects/[id]/page.tsx`) — header + HealthChip + repo, the 4 core answers (SPEC §S3: đang đâu/mục tiêu/ai dùng/bước tiếp), metrics row, routine list + lastAuto, refresh + abandon buttons (POST → re-render from backend response, never local-mutate), 404 state.
- Both screens use `useSafeRouter` (Sprint-0 convention — degrade to no-op without a provider, testable).

### Backend — CORS (gap fix, surfaced by the live browser)
- **`main.py`** — `CORSMiddleware` in `create_app()` BEFORE `mount_all` (so every module inherits it). `allow_origins=settings.cors_origins`, methods/headers `*`.
- **`config.py`** — `cors_origins: list[str]` default `[:3010, :3000]`, `LIFEOS_CORS_ORIGINS` override (configurable, not hardcoded).
- **`test_cors.py`** — 4 tests locking the browser invariant curl can't see: OPTIONS preflight on /health + /projects → 200 + ACAO, simple GET carries ACAO, the :3000 origin allowed. RED without the middleware.

### Batched quick-fix (Sprint-1 carryover)
- tester's `api_client` fixture raw-assign → `monkeypatch.setattr` (auto-revert). Rode this push per the Quick-Fix batching rule.

---

## 2. Verification (Rule #0 — architect + team-lead + tester independently)

| Check | Result |
|---|---|
| frontend vitest | **170 passed (21 files)** |
| frontend `tsc --noEmit` | clean (exit 0) |
| backend pytest default | **221 passed** |
| backend pytest `-n auto` | 221 passed |
| CORS teeth (team-lead disabled middleware) | 4 RED → restore → pass |
| CORS live (OPTIONS /projects from :3010) | 200 + `access-control-allow-origin: http://localhost:3010` |
| **Live Chrome S2** (team-lead + tester, independent) | 6 real repos render: ClaudeManager/crewly/DevCrew/Groundwork/life-os/OutboundOS, correct health colors, summary KPIs MATCH API (Tổng 6 / Active 2 / Cần chú ý 3đứng·1chậm / Đã chôn 0), API pill "live" |
| **Live Chrome S3** | header + HealthChip + 4 core answers + metrics + routine/lastAuto + refresh/abandon buttons; nulls → honest "chưa có ai dùng"/"chưa có" |

**The user's first visible screen works** — real projects, correct health colors, honest nulls, live API through CORS.

---

## 3. The 3 Quality Gates

### Gate 1 — API (main.py CORS)
☑ CORSMiddleware before mount_all · ☑ regression test (OPTIONS→200+ACAO, RED without) · ☑ existing 221 pass · ☑ configurable origins (no hardcode) · ☑ no auth (localhost no-auth, documented) · ☑ envelope unchanged.

### Gate 2 — Function (FE screens + components)
☑ Observable-behavior vitest (component render/null/health variants; screen states/filter/nav/404) · ☑ existing pass (170) · ☑ edge cases (null progress/next/desc/lastAuto → "—"/"chưa chạy", API down → error state, empty list, unknown id → 404) · ☑ error path explicit (ApiError 404 vs generic) · ☑ types complete (tsc clean — caught the scaffold prop drift) · ☑ no self-confirming asserts · ☑ FE Chrome self-verify done (frontend + tester + team-lead).

### Gate 3 — Sprint
☑ end_sprint_2.md + counts re-confirmed (architect + team-lead) · ☑ architect 4-step on full functions (screens + CORS) · ☑ tester vitest + live Chrome (the critical gate) + team-lead independent Chrome · ☑ counts ≥ baseline (pytest 217→221, vitest 90→170) · ☑ out-of-scope flagged (§5) · ☑ commit format `feat(sprint-2)`.

**VERDICT: ✅ All 3 gates GREEN.**

---

## 4. Assumptions (user-review queue — decide-and-log)

- **CORS `allow_origins` = [http://localhost:3010, http://localhost:3000]** (`LIFEOS_CORS_ORIGINS` override), methods/headers `*`. — Single-user localhost no-auth (CLAUDE.md §2): CORS is a browser-functionality ENABLER, not a security boundary. — To change: tighten to one origin, or open to `*`, via the env override.
- **Register modal STUBBED** ("Đăng ký dự án (sắp có)") this sprint — S2's core value is the list+detail READ; POST /projects wiring is a follow-up. — To change: wire the modal → `apiPost('/projects', body)` (the endpoint already exists from Sprint 1).
- **HealthChip labels** = mock `healthLbl`: act→"healthy", slow→"chậm", stall→"đứng", dead→"chết". — Match the approved mock. — To change: edit the HEALTH map in HealthChip.tsx.
- **Render-only discipline** — FE NEVER recomputes a derived metric; it displays the API's `summary`/health/progress verbatim. A wrong count is a backend bug, not an FE fix. (raw-data-first, SPEC §0.)
- (Carried, still in force: the S1 list = config ∪ registered-status.md union; abandon orthogonal to health.)

---

## 5. Risks / out-of-scope (future sprints)

- **Filter-tab + some action elements render as `<span onClick>` (with role/tabIndex/keydown) not `<button>`** — works + keyboard-accessible, but a DOM note: future test selectors should target by `data-testid`/role, not assume `<button>`. (This sprint already bit us once — the "Dự án" selector collision.)
- **Register modal is a stub** — the "new project" flow isn't usable yet (S2 read works fully). Follow-up.
- **CORS `*` methods/headers** — fine for localhost-single-user; if this ever goes multi-origin/networked, revisit (but that contradicts the no-auth single-user architecture — unlikely).
- **`last` formatting** is client-side relative-time; very old timestamps just show the date. Acceptable.

---

## 6. Sprint Sync — Retro (process learnings)

1. **Stale-snapshot false-reports recurred 4× this sprint** (tester ×2 on mid-write screens, architect ×1 on a pre-fix page.tsx, architect ×1 on a mis-invoked `npx vitest`). All from acting on an un-settled measurement. → PROMOTED `verify-after-write-settles` to a TEAM rule: before reporting/dispatching a failure tied to another teammate's file, re-read at current mtime / confirm `git diff` stable across 2 reads. Added to the tester playbook (run tsc-too + re-read cross-file). Same family: **validate the measurement before trusting the result** — incl. your own command invocation (the `npx vitest` from the wrong cwd grabbed a stray bundler and faked a 15-file failure).
2. **No single verification layer is sufficient — the sprint's sharpest lesson:**
   - Sprint 1: **live app** caught a phantom project the suite missed.
   - S2 router: the **suite** caught a useRouter bypass live-Chrome would've passed (real browser has the provider).
   - S2 CORS: the **browser** caught a gap BOTH curl (ignores CORS) AND vitest (mocks fetch) are structurally blind to.
   → curl + vitest + live-browser each catch a DIFFERENT class. The live-app checklist now must include "the browser can actually FETCH the API (CORS preflight + ACAO)." → memory `verify-live-app-not-just-suite`.
3. **CORS was a Sprint-0 architecture gap** that only surfaced when a browser first called the API (Sprint 2). Curl-verification in S0/S1 structurally couldn't catch it. Not a regression — a latent gap exposed by the first real consumer. Pattern: the first time a new consumer-type appears (browser, external AI), expect to surface latent gaps the prior consumers never exercised.
4. **tsc is a separate gate from vitest** — a scaffold passed vitest while failing tsc (JSX runtime skips prop type-checks). Always run BOTH on FE. → tester playbook.
5. **Kickoff earned its keep again** — caught the stale `lib/types.ts` before T1 coded against it.

---

## 7. Commit
- `feat(sprint-2): Projects FE (S2 list + S3 detail)` — FE screens/components + CORS + the batched api_client quick-fix + plan/end docs. One commit.
- After: `sleep 120 && git push` (background, 2-min window) → notify.py the user → team-lead's 2-part Sprint Sync report → propose Sprint 3 (Market BE + ticker, ARCH §9 step 2).
