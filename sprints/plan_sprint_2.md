# Plan Sprint 2 — Projects FE (S2 List + S3 Detail) [consumes the frozen ProjectStatus]

> DRAFT (CLAUDE.md §3.3) — refresh via kickoff before dispatch. The first SCREENS that consume the Sprint-1 frozen ProjectStatus shape over the real API. FE-only (backend done); ports from the approved mock, never redesigns.
> Spec: SPEC §S2 (Projects List) / §S3 (Detail). ARCH §9 step 1 (FE half). Mock: `template/Life Command/app/screens-projects.js` + `screens.css`. API: `GET /projects`, `GET /projects/{id}`, the 3 POSTs (live at :8000).
> Author: architect · 2026-06-06 · Status: awaiting team-lead greenlight after Sprint 1 push.

## Objective
Build S2 Projects List + S3 Project Detail in Next.js, consuming the live projects API. Port the mock's structure + tokens exactly (no redesign). Wire real data via `apiGet`; render-only — all derivation (health/progress/summary) is computed server-side already (Sprint 1), FE just displays. Build the shared components the rest of the app will reuse.

## Tasks (4-5, ≥2 parallel)
- **T1 [frontend, GATING] — shared display components + types mirror.**
  - `lib/types.ts` — TS mirror of the frozen ProjectStatus (incl `desc`, the 13th field) + Metrics. Single source FE-side; later screens import it.
  - `components/shared/`: `HealthChip` (act/slow/stall/dead → mock `sb-act/slow/stall/dead` tokens + dot color), `ProgressBar` (mock `barc`/`i` width%), `KpiCard` (mock `stat` block: label/value/delta), `DataTable` (mock `dtable` thead/tbody, clickable rows). Port tokens from `screens.css` verbatim. Gates T2/T3 (they compose these).
- **T2 [frontend] — S2 Projects List screen** (`app/projects/page.tsx`, replace the EmptyScreen stub).
  - Summary stats bar (KpiCard ×4: total / active / needs-attention / real-users) from `GET /projects` `data.summary`. Projects DataTable (name/desc/HealthChip/ProgressBar/users/last/routines/next), row click → `/projects/{id}`. Tabs filter (Tất cả/Active/Chậm/Đứng) client-side. "Dự án mới" button → register form (can stub the modal this sprint or wire POST). Loading + error + empty states (API down → friendly, not crash). Blocked by T1.
- **T3 [frontend] — S3 Project Detail screen** (`app/projects/[id]/page.tsx`).
  - Header (name/HealthChip/repo link), the 4 core answers (đang đâu/mục tiêu/ai dùng/bước tiếp from progress/desc/users/next), metrics row (commits/branch/lang/lastDays), wiki/notes placeholders, routine list + lastAuto, refresh button → `POST /{id}/refresh`, abandon button → `POST /{id}/abandon` (confirm modal). 404 handling (unknown id). Blocked by T1.
- **T4 [tester] — verify FE** (parallel, pre-scaffold from T1 exports).
  - vitest for the shared components + screens (render, states, click-nav, filter). Chrome UI: BE :8000 + FE :3010, open /projects, verify the 6 real repos render with correct health colors / progress bars / summary counts, click into a detail, dark mode, console clean. Real-data check: the live list matches `GET /projects`.

## Logic/Algorithm
N/A — render-only. ALL derivation (health, progress, summary counts) is computed server-side in Sprint 1. FE MUST NOT recompute any derived metric — display what the API returns (raw-data-first; if a count looks wrong, it's a backend bug, not an FE fix). The ONLY client-side logic = tab filtering (filter the already-fetched list by health) + form state.

## Defensive cases (MANDATORY)
- API down / fetch throws → friendly error state (the TopBar API-pill pattern from Sprint 0), never a white-screen crash.
- Empty list (no projects) → empty state, not a broken table.
- `progress: null` → render "—" (NOT 0%, NOT a fabricated bar). `next: null`/`desc: null` → "—". `lastAuto: null` → "chưa chạy".
- Unknown id on detail → 404 state with a back link.
- Long desc → truncate (mock uses max-width 220px).

## Dispatch standards (every task)
- **Runtime:** BE `uvicorn main:app` :8000 (already running w/ projects) · FE `npm run dev` :3010 (NOT :3000=PlatformDTC / :3100=stale — memory `dev-server-ports`).
- **Baseline:** pytest 217, vitest 90 (FE additions raise vitest; keep pytest 217).
- **Ownership:** failing test → report to team-lead, don't edit; frontend owns vitest fixes; tester reports.
- **FE screen specifics (memory `dispatch-standards-additions`):** mock file = `template/Life Command/app/screens-projects.js` (S2 = `SCREENS.projects`, S3 = `SCREENS.project`); schema = the frozen ProjectStatus (lib/types.ts mirror); "render-only — backend computed health/progress/summary, do NOT recompute in UI."

## Dispatch ordering (refresh at kickoff)
1. T1 GATING (shared components + types) alone.
2. T2 + T3 fan out after T1.
3. T4 pre-scaffolds from T1 exports; Chrome verify after T2/T3.

## Kickoff — 2026-06-06
### Drift caught (the reason kickoff is mandatory)
- **`lib/types.ts` ProjectStatus is STALE vs the Sprint-1 frozen backend shape** — MUST reconcile in T1 (source of truth = `backend/modules/projects/schema.py`):
  - Nullable wrong: `desc`/`progress`/`next`/`lastDays`/`lastAuto` are non-null in types.ts but backend returns `| null`. FE WILL break on real nulls if not fixed.
  - `metrics`: types.ts has `stars:number, lang:string, test_pass:number` — backend is `stars:int|null, lang:str|null, testPass:int|null` (camelCase `testPass`, NOT snake) AND is MISSING `branch:str`.
  - `last`: types.ts comments "human 2h trước" — backend returns ISO-8601 UTC. FE formats it for display (don't expect pre-humanized).
  → T1 rewrites `lib/types.ts` ProjectStatus + ProjectMetrics to mirror schema.py EXACTLY (incl `last:string|null`, `desc:string|null`, `branch:string`, `testPass:number|null`).
### Good news (scope lighter than planned)
- **Design tokens ALREADY ported** to `frontend/lib/tokens.css` (Sprint 0): `sbadge`, `sb-act/slow/stall/dead`, `barc`, `dtable`, `panel`, `phead`, `kicker` all present. T1 components WRAP these existing classes — NOT author new CSS. Verify each class renders as the mock expects; add only what's missing.
- `api.ts` has `apiGet<T>` + `ApiError` ready. T1/T2/T3 add `getProjects()`/`getProject(id)` + an `apiPost` helper for refresh/abandon.
- Route stubs (`app/projects/page.tsx`, `[id]/page.tsx`) are EmptyScreen — T2/T3 replace them.

### Decisions (decide-and-log — the 3 open questions, finalized)
1. **Register modal:** STUB the "Dự án mới" button (opens a placeholder/disabled modal) this sprint; wire `POST /projects` in a follow-up. S2's core value is the list+detail READ; registration is secondary. → §Assumptions.
2. **Tokens portability:** CONFIRMED already in tokens.css — components wrap existing classes. No new design work.
3. **HealthChip labels:** match the mock's `healthLbl` set — act→"healthy", slow→"chậm", stall→"đứng", dead→(mock has no dead example; use "chết"). Keep the dot color from `healthDot`. → §Assumptions.

### No major plan revision — T1 scope adjusted (types-reconcile in, heavy-CSS out); tasks unchanged.

## Open items at kickoff
- Register modal (T2 "Dự án mới") — wire POST /projects this sprint or stub the button? Lean: stub the modal open, wire the POST in a follow-up if time-boxed (S2's core value is the list+detail read).
- Confirm the Sprint-0 design tokens + `screens.css` classes are portable into the component layer (they were ported to globals in Sprint 0 — verify).
- HealthChip label text (act→"Active"/slow→"Chậm"/stall→"Đứng"/dead→"Chết"?) — match the mock's `healthLbl`.
