# Plan Sprint 1 — Projects module (BE) + the common ProjectStatus shape [Tier-S]

> DRAFT (CLAUDE.md §3.3) — refresh via kickoff before dispatch. Tier-S: this sprint LOCKS the `ProjectStatus` shape every one of the 14 screens + external AI reads. Get it right; the cost of a wrong shape compounds across all later sprints.
> Spec: SPEC §S2 (Projects List) / §S3 (Detail) / §0 line 207 (status shape). ARCH §9 step 1. Memory: `trackable-repos-inventory` (real repos + user's locked "track few big repos, read-only, no pull" decision).
> Author: architect · 2026-06-06 · Status: awaiting team-lead greenlight after Sprint 0 Sync.

---

## Objective

Build the `projects` feature module (router/schema/service/reader) as the FIRST module that plugs into the Sprint 0 core, and in doing so **lock the common ProjectStatus shape**. The git-reader derives health/progress/idle from REAL local repos (read-only, no pull) per the registered shortlist. Raw-data-first: the reader returns real git facts + server-computed derived metrics; inference stays external.

---

## The locked contract — ProjectStatus shape (SPEC §0 line 207)

```
{
  id: str,            # stable slug, e.g. "devcrew"
  name: str,          # display name
  health: "act"|"slow"|"stall"|"dead",   # derived from commit recency (see Logic)
  progress: int,      # 0–100 % (see Logic — non-AI derivation)
  users: int,         # registered/known users (manual metadata; 0 until set)
  last: str,          # ISO-8601 UTC of last commit (raw git fact)
  lastDays: int,      # whole days since last commit (derived)
  next: str,          # next action (non-AI source — see Logic)
  repo: str,          # absolute local path (read-only pointer)
  metrics: {          # raw git/derived facts
    commits: int, branch: str, lang: str|null,
    testPass: int|null, stars: int|null
  },
  routines: [str],    # routine ids attached to this project (e.g. ["wiki-refresh"])
  lastAuto: str|null  # ISO-8601 of last auto-refresh (null until a routine runs)
}
```
This shape is FROZEN at end of Sprint 1. Later modules extend metadata around it but do not change these keys.

## Tasks (3-4, themed, ≥2 parallel)

- **T1 [backend, GATING] — projects schema + the git-reader + derivation logic.**
  - `modules/projects/schema.py`: Pydantic models for ProjectStatus (above) + the registry-entry input (repo path, name, goal, reader-enabled).
  - `modules/projects/reader.py`: read-only local git reader. Inputs = registered repo path. Runs `git log`/`git rev-list`/`git status` (NEVER `pull`/`fetch`/write). Derives health/progress/lastDays/metrics per the Logic block. Fail-open: a missing/corrupt repo → status with `health:"dead"` + a warning, never crashes.
  - `modules/projects/service.py`: registry of tracked projects (from `config.project_repos` + md_store metadata), orchestrates reader over the shortlist.
  - Depends on: Sprint 0 store + config (done). GATES T2/T3.

- **T2 [backend] — projects router (REST) over the service.**
  - `modules/projects/router.py`: `GET /projects` (list of ProjectStatus), `GET /projects/{id}` (detail incl wiki/notes refs), `POST /projects` (register a repo pointer + goal), `POST /projects/{id}/refresh` (re-run reader), `POST /projects/{id}/abandon` (→ graveyard metadata, reason + % — feeds S4 later). `MODULE = BaseModule(...)` so registry auto-discovers it. Locked response envelope `{success,data,warning?}`. Depends on T1 schema/service.

- **T3 [backend] — wire the shortlist + the `wiki-refresh` routine.**
  - Populate `config.project_repos` with the user-approved shortlist (DevCrew, OutboundOS, crewly, ClaudeManager, Groundwork, life-os) as read-only pointers. Add the `wiki-refresh` Routine (commit-new → reader re-derives status; interval/cron TBD at kickoff) returned from `BaseModule.routines()`. Depends on T1.

- **T4 [tester] — verify (parallel, unblocked early via T1/T2 exports).**
  - pytest for reader derivation against REAL repos (intent-mirror/melodyforge = stall/slow cases, OutboundOS = act, a non-existent path = dead/fail-open). API curl on all 5 endpoints. Confirm registry auto-discovered the module (appears in `/health` modules list). NO editing source/tests (Sprint 0 retro).

---

## Logic/Algorithm — git-reader derivation (architect decides, decide-and-log)

> SPEC does NOT specify these formulas. I decide them per CLAUDE.md §3 decide-and-log; log each to end_sprint_1 §Assumptions + notify user. Implementer (backend) does NOT improvise — this block is the contract.

**Inputs:** registered repo absolute path. Read-only git commands only.

**health** (commit-recency based; `lastDays` = whole days since last commit, UTC):
- `act`   — lastDays ≤ 7    (committed within a week)
- `slow`  — 7 < lastDays ≤ 30
- `stall` — 30 < lastDays ≤ 90
- `dead`  — lastDays > 90, OR repo unreadable/missing (fail-open default)
- Thresholds chosen from the real inventory spread (OutboundOS 27h=act, ClaudeManager 4wk=slow/stall boundary, intent-mirror 6wk=stall, melodyforge 9wk=stall). Tunable — logged as an assumption.

**progress %** (NON-AI; no LLM this build — ARCH §11). Source priority, first available wins:
1. Manual `progress` field in the project's md_store `status.md` front-matter (user/AI-set) — authoritative when present.
2. Else `null` → FE shows "—".
- **RATIFIED backend's proposal over my earlier heuristic draft.** I had drafted a commit-milestone fallback (`commits/target_commits`); backend recommended null-when-absent, and that is the stronger raw-data-first call: a commit-count heuristic *fabricates* a progress number that looks authoritative but is arbitrary — exactly the plausible-but-wrong derived data the playbook warns against, and it'd show a misleading % on every screen from day one. progress is a human judgment; git can't infer it. So: status.md `progress:` field, else null. (test_pass artifact parsing deferred — see metrics.) Logged to §Assumptions with this reasoning.

**next** (NON-AI):
1. Manual `next` field in status.md front-matter (authoritative).
2. Else `null` (UI shows "—"). Never fabricated.
- RATIFIED backend's null-when-absent. I dropped my earlier draft step that scraped the latest `- [ ]` TODO from wiki/README — same fabrication risk as the progress heuristic (a stale/irrelevant TODO line masquerading as "the next action"). Keep it honest: human-authored or "—".

**users** (NON-AI; no analytics exists this build): optional `users` field in status.md front-matter; absent → `0`. Logged as assumption.

**metrics:** `commits` = `git rev-list --count HEAD`; `branch` = current; `lang` = dominant tracked-file extension or null; `stars` = null/stub (needs GitHub API — no network dep this build); `testPass` = null unless the project exposes a known local artifact (deferred — no parser this sprint). No network calls anywhere in the reader.

**Defensive (MANDATORY):** missing repo path → `health:"dead"`, metrics zeroed, warning in envelope, no crash. Detached HEAD / empty repo (0 commits) → `health:"dead"`, lastDays=null-safe. Non-git dir → skip with warning. Reader NEVER writes to or pulls the source repo (read-only is a hard invariant — assert in tests).

---

## Cross-cutting / gates

- Module auto-discovered (no core/main edit) — verify in T4 via `/health`.
- Response envelope `{success,data,warning?}`; errors 400/404/422/500 (no auth).
- Raw-data-first: reader returns real git facts + derived metrics server-side.
- Ref-not-embed: repos stay in place, read-only; app holds only the pointer + md_store metadata.
- 3 Gates apply. Tier-S → extra care on the shape: once shipped it's frozen.

## Dispatch standards (NEW from Sprint-0 Standup — every task carries these)
- **Runtime:** BE `uvicorn main:app` at `:8000` · FE (n/a this sprint — BE-only) · life-os FE is `:3010` NOT `:3000` (PlatformDTC) / `:3100` (stale) — memory `dev-server-ports`.
- **Baseline:** pytest **76**, vitest **90** (the regression anchor — flag any drop instantly).
- **Ownership:** failing test → report to team-lead with repro, do NOT edit. Backend owns pytest failures; tester REPORTS, never fixes (Sprint-0 retro #7). Tester's own stop-signal: "if I open an editor, stop."

## Dispatch ordering (refresh at kickoff)
1. T1 GATING (schema + reader + derivation) — dispatched alone first.
2. T2 + T3 fan out after T1 lands.
3. T4 (tester) unblocked early to pre-scaffold against T1/T2 exports.

## Open items to resolve at kickoff (architect decides — decide-and-log, don't block)
- `wiki-refresh` routine cadence — DECIDE: interval, every 6h (rule-based, cheap local git read; not so frequent it churns). Log as assumption.
- status.md front-matter format — LOCK as a YAML block: `progress:int|absent`, `next:str|absent`, `users:int|absent`, `goal:str`, `repo:str`. This is the manual-override source of truth for progress/next/users; the reader parses it, git fills the rest.
- No `target_commits` needed anymore — progress heuristic dropped (ratified null-when-absent). One fewer config knob.

## POST write contracts (decided when backend surfaced them — decide-and-log → §Assumptions)
- **POST /projects** (register): body `{name, repo(abs), goal?, progress?, next?, users?}` → id=slug(name); write `projects/<id>/status.md` YAML front-matter (one md_store commit); repo must exist + be a git repo (else 400); id collision → 409; return freshly-read ProjectStatus. status.md existence = registration (built-ins also in config dict).
- **POST /projects/{id}/abandon**: body `{reason, atProgress?}` → merge `abandoned:true, abandonedReason, abandonedAt(ISO now), abandonedProgress` into status.md (one commit). Feeds S4 Graveyard. **abandon is ORTHOGONAL to health** — it's an explicit human flag, NOT health="dead" (which is commit-age). `list_projects()` excludes abandoned; `get_project(id)` includes it.
- **POST /projects/{id}/refresh**: re-run reader, set `lastAuto=ISO now` persisted to status.md (one commit), return fresh status. Same path wiki-refresh routine calls (T3).
- **status.md = single persisted source** for human fields (name/desc/goal/progress/next/users) + cached derived (abandoned*/lastAuto); git read live each call. `desc` field ADDED to shape (nullable; `goal` is an alias).

## Kickoff — 2026-06-06
### Verified vs current code + real repos (no drift)
- md_store exposes `write_file/read_file/exists` (+ `read`→None) — backend uses these for status.md. ✓
- `config.project_repos: dict[str,str]` ready to populate (T3). `BaseModule(name, router, routines=...)` signature confirmed. ✓
- All 5 shortlist repos present with expected history: OutboundOS 500c/28h, DevCrew 590c/5wk, crewly 560c/2mo, ClaudeManager 241c/4wk, Groundwork 140c/5wk; life-os 3c/now (dogfood). ✓
### Real-data note for T4 health test cases (current commit ages)
- OutboundOS 28h → **act** (≤7d) · ClaudeManager ~28d → **slow** (≤30d, near boundary) · DevCrew/Groundwork ~35d + crewly ~60d → **stall** (≤90d) · **no repo is >90d** right now → the **`dead` case MUST be tested via a bogus/missing path** (fail-open), not a real repo. Already in the plan; reaffirmed.
- ClaudeManager sits near the 30d slow/stall boundary — exact bucket depends on run date; T4 should assert the BUCKET LOGIC (a repo at 28d is slow, at 35d is stall) rather than hard-coding ClaudeManager's bucket, so the test isn't date-fragile.
### No plan revisions needed — contract greenlit, assumptions hold.

## Verification / gates (Tier-S)
- Reader run against REAL repos: OutboundOS→act, ClaudeManager/intent-mirror→slow/stall, a bogus path→dead+warning (fail-open). Assert reader issues NO write/pull (read-only hard invariant).
- All 5 endpoints curl-verified; module appears in `/health` modules list (registry auto-discovery).
- Gates 1+2+3. Shape frozen on commit → spot-check the schema against SPEC §0 line 207 key-by-key before commit.
