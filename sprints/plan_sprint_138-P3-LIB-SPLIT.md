# plan_sprint_138-P3 — split lib/types.ts (2336) + lib/api.ts (1105) by domain (barrel-safe)

> User CHỐT (via team-lead): split the two lib monoliths by domain. Rationale: app will EXPAND + AI agents read/edit code → a 2336-line monolith is fragile (touching it risks the whole file) + hard to navigate; per-module files = touching ONE module is isolated + AI-readable. Scale-investment, approved.
> 🔴 HIGHEST blast radius (171 import sites). Behavior-IMPOSSIBLE-to-change (types are erased at runtime; api fns are pure moves). The safety net = a BARREL re-export so every existing import resolves ZERO-change. Surfaced to team-lead for explicit sign-off BEFORE any edit.

## Disk-measured state (Rule#0, 2026-06-22, HEAD=855b337)
- `lib/types.ts` = **2336 lines**, ~190 exported symbols (interfaces/types/enums).
- `lib/api.ts` = **1105 lines**, ~130 exported fns + the shared HTTP core.
- **Import surface:** 83 files import `@/lib/types`, 88 files import `@/lib/api` — **ALL via the `@/lib/...` alias** (zero relative `../lib/types`). → a barrel at `lib/types/index.ts` + `lib/api/index.ts` makes all 171 sites resolve unchanged (Next/tsc resolves `@/lib/types` → `lib/types/index.ts` automatically). No call-site edit anywhere.

## 1. Domain boundaries (match the backend module structure)
Grouped from the actual exports on disk. **Cross-domain type refs are resolved by importing from the barrel** (`@/lib/types`) inside a domain file, so order doesn't matter and there are no circular-file traps (a barrel import is a single resolved module).

### types/ (split lib/types.ts → lib/types/<domain>.ts + barrel)
| File | Symbols (representative) |
|---|---|
| `types/_common.ts` | `ApiResponse<T>`, `HealthData`, `ValidationErrorItem`, `Severity` (cross-cutting; imported by many) |
| `types/projects.ts` | ProjectHealth, ProjectMetrics, ProjectStatus, ProjectSource, ProjectDevActivity, ProjectsSummary, ProjectsListData, ProjectRegisterInput, ProjectAbandonInput |
| `types/market.ts` | AssetClass, AlertOp/State, AssetQuote, AlertRule(+Input/Trigger/Event), MacroSignal, PricePoint, MarketData |
| `types/finance.ts` | Holding, PnL, PnlScope, ChannelAlloc, PricedHolding, ChannelDetail, HoldingInput, LadderState, Change, FinanceOverview, OkxBalance/Position, CryptoBasis, ExchangeOverview |
| `types/notes.ts` | Attach, AttachType, Note, NoteInput |
| `types/claude.ts` | DayBurn, ModelBurn, ProjectBurn, ClaudeUsage |
| `types/settings.ts` | ErrorChannel, AppConfig, AppConfigPatch |
| `types/brief.ts` | PrioritySource, Priority, BriefSummary, Brief |
| `types/activity.ts` | RunStatus, ActivityRun, RoutineBreakdown, ActivityFeed, Trigger, RunResult, RoutineInfo, RoutinesView, RunResultView |
| `types/journal.ts` | JournalAction/Channel/Outcome, JournalEntry, JournalInput, CalibrationBand, JournalStats |
| `types/graveyard.ts` | GraveProject, ReasonCount, GraveyardStats |
| `types/wiki.ts` | the Wiki* block (~60 symbols, 834→1404) |
| `types/decision.ts` | DecisionStatus/Outcome, DecisionEntry(+Create/Patch), DecisionCalibrationBand, DecisionBiasFlag, DecisionJournalData, DecisionLayer, DecisionWeight, CycleAxis, CycleQInput, CycleQ, MacroCycle, AllocTargets, DecisionAllocation, GuardianAlert, DecisionGuardian, NavPoint, NavHistory |
| `types/career.ts` | ProofKind, ProofLink, CvSection, CvMeta, Cv, BlogStatus, BlogPost, BlogInput, DemoStatus, DemoItem, DemoInput |
| `types/reminders.ts` | ReminderRepeat, Reminder, ReminderSource, ReminderInput, ReminderList |
| `types/tracing.ts` | TracingToday, ActivityView, RemindRepeat, TracingScore, TracingOverview, TracingTemplate(+List/Input), TemplateMember, TemplateSet(+List/Input), TemplateImportResult, TracingLogInput, ActivityInput, RemindChannel, ReminderChannelOption/List, ActivityPatch, Activity, TracingNote(+Input/Update/List) |
| `types/dev.ts` | RepoDay, DayView, RepoSummary, DevActivitySummary, DevActivityOverview, DevScanResult, RepoCommit, CodeInsight, RepoMemoryNote, RepoMemory |
| `types/mcp.ts` | McpScope, McpKey(+Create/Update), McpCatalogTool, McpToolParam, McpCatalogCounts, McpCatalog |
| `types/index.ts` (BARREL) | `export * from "./_common"; export * from "./projects"; …` (every file) |

### api/ (split lib/api.ts → lib/api/<domain>.ts + barrel)
| File | Contents |
|---|---|
| `api/_client.ts` | **the shared HTTP core** — `BASE`, `ApiError`, `parseFieldsFromMessage`, `errorFromBody`, `apiGet/apiPost/apiPut/apiPatch/apiDelete`, `apiBase`. Every domain file imports from here. |
| `api/projects.ts` | getHealth, getProjects, getProject, hide/unhideProject, getProjectDevActivity, restoreProject |
| `api/finance.ts` | getFinance, createHolding, getChannelDetail, getExchange, syncExchange, getCryptoBasis, setCryptoBasis, verifyPrivacyPass |
| `api/market.ts` | getMarket |
| `api/claude.ts` | getClaudeUsage |
| `api/graveyard.ts` | getGraveyard |
| `api/journal.ts` | getJournal, createJournal, updateJournal |
| `api/activity.ts` | getRoutines, getActivity, getActivityRun, toggleRoutine, runRoutine |
| `api/brief.ts` | getBrief, getBriefHistory |
| `api/settings.ts` | getSettings, patchSettings |
| `api/wiki.ts` | the wiki block + co-located `bumpTree` + `encodeWikiPath` (wiki-only helpers) |
| `api/decision.ts` | getDecisionJournal, create/update/deleteDecision, getDecisionWeight, getMacroCycle, getDecisionAllocation, getDecisionGuardian, getNavHistory |
| `api/career.ts` | getCareerCv(+Raw), updateCareerCv, get/create/update/deleteCareerBlog, get/create/update/deleteCareerDemo |
| `api/reminders.ts` | getReminders, getReminderChannels, createReminder, tickReminder, deleteReminder |
| `api/tracing.ts` | getTracing, logTracingSession, untickActivity, create/update/archiveActivity, the template + template-set + tracing-note fns |
| `api/dev.ts` | getDevActivity, scanDevActivity, getCodeInsight, getRepoMemory |
| `api/mcp.ts` | getMcpKeys, create/update/deleteMcpKey, getMcpCatalog |
| `api/index.ts` (BARREL) | `export * from "./_client"; export * from "./projects"; …` (every file) |

## 2. Barrel re-export (the safety net) — CONFIRMED
- `lib/types/index.ts` `export *`s every domain file → `@/lib/types` keeps resolving (Next maps `@/lib/types` → `lib/types/index.ts`).
- `lib/api/index.ts` `export *`s every domain file → `@/lib/api` keeps resolving.
- **Zero change to any of the 171 import sites.** A missed export = a tsc error at the importing site, caught instantly.
- `lib/api.ts`'s current internal `from "./types"` becomes, in each `api/<domain>.ts`, `from "@/lib/types"` (the types barrel) — keeps working.

## 3. Order — one domain per commit, lowest-risk-first, test-gated each
**Phase A (types — pure type moves, runtime-impossible-to-change):**
1. `types/_common.ts` (the shared types FIRST — others may ref them) + barrel skeleton.
2. then one commit per domain in this order (leaf/independent first): mcp, dev, graveyard, claude, notes, settings, brief, activity, journal, reminders, career, projects, market, finance, decision, tracing, wiki.
   - Each commit: cut the domain's symbols out of `types.ts` → `types/<domain>.ts`, add to barrel, leave the rest of `types.ts` intact (the barrel also `export *`s the shrinking `types.ts` until it's empty, OR we move all at once per-domain — see "execution note").
3. Final: `types.ts` is empty → delete it; barrel is the only `lib/types` entry.

**Phase B (api — pure fn moves, depends on `_client`):**
1. `api/_client.ts` (the shared HTTP core FIRST) + barrel skeleton re-exporting `_client` + the still-intact `api.ts`.
2. one commit per domain, same order, each importing helpers from `api/_client` + types from `@/lib/types`.
3. Final: `api.ts` empty → delete; barrel is the only `lib/api` entry.

**Execution note (per-commit integrity):** each commit must compile + pass full vitest STANDALONE. To keep `api.ts`/`types.ts` valid while half-emptied, the barrel `export *`s BOTH the new domain files AND the shrinking original until the original is empty. The original loses only the moved symbols per commit (no dangling refs because moved symbols are re-exported via the barrel; intra-file refs in the original resolve because they're still in the original until their own domain's commit). Simpler alternative if cleaner in practice: the implementer may do types in ONE commit (all domain files + barrel + delete types.ts) and api in ONE commit — both are pure moves with a tsc+vitest gate; per-domain commits are the conservative default but a single clean per-file move with full green is acceptable. **Recommend: per-domain for types is overkill (pure type erasure) → do types as 1 commit (all files + barrel), api as 1 commit (all files + barrel). 2 commits total, each fully green, fully revertible.** ← my recommendation; defer to team-lead.

## 4. Pure move + re-export, NO logic change
- Types: cut/paste symbols verbatim. No rename, no field change.
- Api: cut/paste fn bodies verbatim; only the IMPORT lines change (helpers from `_client`, types from `@/lib/types`).
- Wiki helpers `bumpTree`/`encodeWikiPath` co-locate into `api/wiki.ts` (their only callers).

## Verify (each commit)
- `npx tsc --noEmit` clean (a missed export → tsc error at the importer = instant catch).
- full `npx vitest run` SAME count (currently ~1104) — zero added/removed tests; a count change = behavior changed = STOP.
- 🔴 **live Chrome spot-check** 2-3 representative routes (finance + wiki + tracing) — the SWC>tsc gate (a barrel/import reshuffle is exactly the kind of move that can compile in tsc but trip SWC). Console clean + real render.
- one commit per phase (revertible); `refactor(sprint-138-p3-types)` + `refactor(sprint-138-p3-api)`.

## Risks / honest flags
- **Only real risk = a missed/duplicated export** → tsc catches it immediately at the importer (the barrel makes it loud, not silent). Not a behavior risk.
- **Circular import?** None — domain files import types from the `@/lib/types` barrel (a single resolved module) + api helpers from `_client`; no domain↔domain file edge. Barrel `export *` is not circular with its members.
- **No in-flight conflict:** lib/types.ts + lib/api.ts are CLEAN on disk (no feature lane touching them — #136/#137/#139 all landed). This is the right window (the plan's own guardrail: lib split goes LAST, after features land).

## Recommendation to team-lead
Sign off on: (a) the domain boundaries above, (b) the barrel safety net (zero call-site change), (c) **2 commits total (types-all, api-all) each fully tsc+vitest green + Chrome-spot-checked** — per-domain-per-commit is available if you prefer maximum granularity, but for PURE moves with a barrel + tsc gate, 1-commit-per-file (types) + 1 (api) is clean and faster with the same safety. Then I dispatch frontend-w3-2 one phase at a time, serial (these are the shared files — never two refactor commits in flight). #141 (tester) runs parallel — disjoint.
