# Plan Sprint 12 — Settings / Registry (S12) [the FINAL screen — completes all 14]

> Author: architect · 2026-06-06 · Status: kickoff IN PROGRESS (team-lead provided honest-mirror + endpoint inventory) · awaiting 3 standups + team-lead greenlight (NOT dispatched yet).
> Spec: SPEC §S12 ("Settings / Registry — cấu hình toàn hệ, thêm dự án/kênh KHÔNG cần sửa code"). Mock: `screens-system.js` `SCREENS.settings` (LIGHT — 4 toggle/display panels). ARCH §7. The FINAL screen → all 14 done.
> Memory: `schema-freeze-gate`, `unhandled-errors-not-green`, `mock-diff-catches-dropped-feature`, `dev-server-ports`, `commit-must-match-last-report`, `verify-after-write-settles`, `single-dev-no-overengineering`, the existing write-endpoint inventory.

## THE BIG FINDING (team-lead's inventory, Rule#0-confirmed on disk) — S12 is ~90% FE-assembly
Most of S12's write surface ALREADY EXISTS — S12 is largely a FE control panel WIRING existing endpoints, NOT new backend:
| S12 config area | Endpoint | Exists? |
|---|---|---|
| Project registry (add/abandon/restore/refresh) | `POST /projects` + `/{id}/abandon\|restore\|refresh` | ✅ (projects/router 69-102) |
| Investment channel/allocation | `POST/DELETE /finance/holdings`, `GET/PUT /finance/golden-path` | ✅ (finance/router 39-72) |
| Per-asset alert threshold | `POST/DELETE /market/alerts` | ✅ (market/router 59-66) |
| Routine config | `PATCH /routines/{id}` + toggle md_store | ✅ (automation/router 32-41) |
| Claude usage source/cap | `PUT /claude-usage/override` | ✅ (claude_usage/router 38) |
| Appearance | shell Tweaks panel | ✅ (already in shell) |
→ **The ONE genuinely-new write = GLOBAL APP-CONFIG** (currently HARDCODED): idle-hunter threshold N (literal `lastDays > 7`, automation/service.py:76), morning-pull cron time (08:00 hardcoded), master-automation on/off, error/alert channel, timezone, display name. These have NO config home → the SPEC's "configure without editing code" is currently UNFULFILLABLE for them.

**Inventory BEHAVIOR-verified (Rule#0, not just route-exists):** on the live container — GET /finance/golden-path round-trips (targets present); PATCH /routines/idle-hunter {enabled:false} → enabled False → restored; /health 200. So the existing endpoints WORK, not just exist. S12 wiring them is safe.

## Write-form verify teeth (memory `write-form-roundtrip-verify` — S12 is the FIRST write-heavy screen)
The verify shape CHANGES from "rendered==read-payload" to a ROUND-TRIP. Bake into the FE+tester dispatch:
- **Round-trip teeth (the new pass criterion):** submit form → 2xx → re-GET reflects the submitted value → reload → persists. THREE values must agree (submitted == re-GET == post-reload). NOT "the form closed", NOT "the immediate render updated" (optimistic).
- **3 silent-fail modes to FORCE (not just happy path):** (1) **swallowed-422** — bad input → BE 422 but UI closes as if succeeded → assert the error is VISIBLE IN THE UI; (2) **partial-write** — N-field form, BE accepts some/ignores others → assert ALL fields reflected in re-GET; (3) **optimistic-over-failed-POST** — POST fails but FE updates local state → assert the re-GET AFTER RELOAD (rollback on failure).
- **Backend Gate-1:** every config write 422s on bad input (Pydantic at the boundary). **FE Gate-2:** surfaces the 422 visibly. **Tester Gate-3:** the 3-value agreement + the 3 failure-mode probes, against the REAL endpoint (a mocked unit suite hides swallowed-422/optimistic-fail).

## Scope decision 1 — mock-vs-SPEC CRUD depth (decide-and-log)
**Mock = LIGHT** (4 panels, toggles + display + "open Tweaks"). **SPEC = HEAVY** (full registry CRUD: add/edit projects + channels + thresholds). They diverge.
**RESOLUTION (north-star: full FEATURE per SPEC, but don't rebuild what exists):**
- **S12 surfaces the registry CRUD the SPEC wants — but by WIRING the existing endpoints into Settings forms, NOT rebuilding forms that live elsewhere.** Where a full add/edit form already exists on another screen (e.g. project registry on Projects S2, holdings on Finance/Portfolio), S12 **links out** to it ("Quản lý dự án →" → /projects) rather than duplicating. Where there's NO home (the global config), S12 hosts the form.
- So S12 = a settings HUB: (a) global app-config forms (the new part), (b) the mock's toggle panels wired live, (c) link-outs to the registry CRUD that lives on its owning screen, (d) API-endpoint live-status list, (e) "Mở Tweaks", (f) **Tích hợp & MCP panel = HONEST STATUS display** (see below). This is full-feature (every SPEC config reachable) without rebuilding existing forms (north-star).

**Tích hợp & MCP panel (team-lead honest-mirror catch — do NOT drop the visible mock panel, do NOT fake toggles):** render it as an honest STATUS display matching the mock's look, truthful states — NOT 4 functional toggles (faking absent capability violates honest-mirror + over-builds toward phase-2):
- **Claude Code (MCP):** "🔜 phase 2 · chưa kết nối" (deferred, honest).
- **GitHub:** "active" if the projects reader is reading real repos (live — it is), else off.
- **Market data feed:** "active · mỗi 10 phút" if market-poll routine enabled (live from /routines), else off.
- **Webhook:** "🔜 phase 2 · off" (deferred inbound).
Visible + matches mock + tells the truth (live vs deferred). §Assumptions: "Tích hợp panel = honest status display, not functional toggles; Claude/MCP + Webhook = phase-2-deferred."

**Confirmed scope guards (team-lead):**
- **Project-pointer EDIT is OUT of S12** — pointer is set only at register (POST /projects), per the link-out-to-Projects decision. (Backend's risk: editing a repo-pointer needs validate-real-git-repo; keep it out = lowest-risk closer.)
- **Error-echo contract = per-field 422** (FastAPI default validation → field-level `loc`) → FE renders inline per-field errors. FROZEN in T1's AppConfig announce.
- **Live-consumed config this sprint:** idleThresholdDays / automationEnabled / briefHour (the distinguishing-test trio). timezone / displayName / errorChannel = stored+displayed (stored-only — log it).
- Log: "S12 = settings hub — hosts global-config + wires toggles + links to existing registry CRUD; doesn't duplicate Projects/Finance add-forms."

## Scope decision 2 — the global-config module (the one new write)
**DECISION: a NEW small `settings` module** (NOT reuse automation toggles — those are per-routine on/off; global app-config is broader).
- `backend/modules/settings/` — `GET /settings` (current config) + `PATCH /settings` (update). Persist to md_store `settings/config.md` (YAML, 1 commit/write — the Notes pattern). The config the app READS (idle threshold, brief cron, master-automation, etc.) — so the hardcoded constants become config-driven (the SPEC's "without editing code").
- **AppConfig shape** (draft — freeze at dispatch): `{automationEnabled: bool, briefHour: int(0-23), idleThresholdDays: int, patternCheckEnabled: bool, errorChannel: "discord"|"inapp"|"none", timezone: str, displayName: str}`. Each field defaults to the current hardcoded value (idleThresholdDays=7, briefHour=8, etc.) so behavior is unchanged until the user edits.
- **Wire the readers to it:** idle_hunter reads `settings.idleThresholdDays` (not the literal 7); morning-pull reads `settings.briefHour`; the scheduler respects `automationEnabled`. (This is the real value — config replaces hardcoded constants.) Scope-guard: wire the 2-3 highest-value ones (idle threshold, automation master, brief hour); the rest (timezone/displayName/errorChannel) can be stored+displayed even if not yet consumed everywhere (log which are live-consumed vs stored-only).

## Tasks (DRAFT — 4, refine after standups)
- **T1 [backend, GATING] — settings module** (`GET /settings` + `PATCH /settings`, md_store persist) + wire idle_hunter/morning-pull/scheduler to read it (replace the hardcoded constants). FREEZE AppConfig + curl.
- **T2 [frontend] — S12 Settings hub screen** (`app/settings/page.tsx`) — global-config forms (wired to /settings), the mock's toggle panels (wired to existing endpoints), link-outs to registry CRUD (/projects, /finance), API-endpoint live-status, Mở Tweaks. Blocked by T1.
- **T3 [tester] — verify settings** — pytest (config round-trip via md_store; the readers actually CONSUME the config — e.g. set idleThresholdDays=14 → idle_hunter uses 14 not 7, the DISTINGUISHING behavior-test; defaults match the old hardcoded values; fail-soft). API curl + Chrome (edit a setting → persists + a reader respects it). Pre-scaffold from T1.
- (Possibly fold the FE link-outs / no new backend for the existing endpoints — most of T2 is wiring.)

## Logic/Algorithm (decided)
- **config persistence:** md_store `settings/config.md` (YAML), 1 commit/write (Notes pattern). GET reads it (defaults if absent); PATCH merges + writes.
- **defaults = the CURRENT hardcoded values** (idleThresholdDays=7, briefHour=8, automationEnabled=true, patternCheckEnabled=true) so nothing changes until edited.
- **readers consume config:** idle_hunter `lastDays > settings.idleThresholdDays`; morning-pull cron uses `settings.briefHour` (or reads at run-time); scheduler skips routines if `not automationEnabled` (master toggle). The DISTINGUISHING test: change a threshold → the reader's behavior changes (proves it's config-driven not hardcoded).
- **validation:** briefHour 0-23, idleThresholdDays ≥1, errorChannel Literal, timezone valid → 422 on bad.

## Defensive (MANDATORY)
- settings/config.md absent → all defaults (the current hardcoded values), 200. Never crash.
- PATCH partial → merge (only the sent fields change). Malformed config file → defaults + warn (fail-open read).
- Invalid value (briefHour 25, idleThresholdDays 0) → 422.
- A reader consuming config when config is absent → its default (idle uses 7). No behavior change until edited.

## "All 14 done" — what's DEFERRED (for end_sprint_12 "sơ bộ xong" honesty)
Per ARCH §11 / the build plan, completing 14 screens leaves explicitly deferred (phase 2):
- **MCP / AI-actor** — FastMCP wrapper, Claude Code generating briefs/routines (the "AI brief" + "AI routine" later phase). This build = template/rule-based, API-open for an external AI to read.
- **Sidebar badges** (3 of 4 still static — `sidebar-badges-static-placeholder` backlog; the shell-task).
- **Per-project token attribution** (S9 — needs .jsonl transcript parse; marked stub).
- **Live reset countdown** (S9 — not on disk).
- **Brief history as AI-summarized** (S11 — template now; AI later).
- **GCP 24/7 scheduler** (local APScheduler now).
- **Net-worth daily-snapshot chart** (S1/S5 — flat until a snapshot routine).
end_sprint_12 declares "14 screens shipped (sơ bộ xong) — phase 2 = MCP/AI-actor + the deferred polish above."

## Dispatch standards (when greenlit)
- Runtime: `docker compose up -d` (DETACHED, the new CLAUDE.md §Dev runtime rule — no --build for code, confirm UP via /health). Baseline: pytest 649, vitest 347.
- **`## Read first` per role (HARD GATE):** BE → `schema-freeze-gate`, `unhandled-errors-not-green`, the existing endpoint inventory, `dev-server-ports`; FE → `mock-diff-catches-dropped-feature`, `unhandled-errors-not-green`, `dev-server-ports`; tester → `verify-live-app-not-just-suite`, `behavior-test-not-field-read`, `verify-with-the-distinguishing-case` (the config-consumed-by-reader test).
- Full field list msg #1 (AppConfig) + freeze field-by-field + commit-must-match-last-report (the S11 lesson — confirm tree settled before commit) + test-ownership-split.

## Open at kickoff (resolve with standups)
- Which global-config fields are LIVE-CONSUMED (idle/automation/briefHour) vs stored-only (timezone/displayName/errorChannel) this sprint — backend's standup informs.
- How much registry-CRUD is link-out vs in-Settings (FE's standup on form-reuse).
- Tester's config-consumed-by-reader distinguishing test plan.
