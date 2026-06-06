# End Sprint 12 — Settings / Registry (S12) [the FINAL screen — all 14 shipped · sơ bộ xong]

> Result doc (CLAUDE.md §3.2). The `settings` module + S12 Settings hub — "cấu hình toàn hệ KHÔNG cần sửa code." The FIRST write-heavy screen + the LAST screen. **On this commit, all 14 screens ship — the foundation build (sơ bộ) is complete.**
> Author: architect · 2026-06-06 · Commit: `feat(sprint-12)` on `main`.

---

## 1. What shipped

### Backend — `settings` module (the ONE genuinely-new write; ~90% of S12 wired existing endpoints)
- **`settings` module** (registry auto-discovered): `GET /settings` + `PATCH /settings` (partial-merge), persist md_store `settings/config.md` (Notes pattern, 1 commit/write, fail-open read).
- **AppConfig** `{automationEnabled, briefHour(0-23), idleThresholdDays(≥1), patternCheckEnabled, errorChannel(discord/inapp/none), timezone, displayName}`. Defaults = the CURRENT hardcoded values → behavior unchanged until edited. Per-field 422 (Pydantic boundary, field `loc` for inline echo). `set_config`/`get_config` service fns.
- **Wired the readers to CONSUME config (the real value — config replaces hardcoded):** idle_hunter reads `idleThresholdDays` (the literal `> 7` is GONE); scheduler/master respects `automationEnabled` (scheduled path; manual POST /run still runs); brief reads `briefHour`; patternCheckEnabled gates pattern-check. Live-consumed: idle/automation/briefHour/patternCheck. Stored-only (logged): timezone/displayName/errorChannel.

### Frontend — S12 Settings hub (`app/settings/page.tsx`) + shared form components + ApiError 422-normalize
- The HUB: (a) Automation toàn cục form → PATCH /settings, (b) Tài khoản (displayName/timezone/errorChannel), (c) **Tích hợp & MCP HONEST STATUS panel** (Claude/MCP/Webhook=phase2, GitHub/Market=live — NOT fake toggles), (d) API-endpoint live-status, (e) link-outs (projects→/projects, finance→/finance — NOT rebuilt; pointer-edit OUT), (f) Mở Tweaks (honest coming-soon).
- **Shared `components/shared/` form set** (Field/TextInput/NumberInput/Select/Toggle) — all CONTROLLED (parent owns value, fail-closed writes), per-field 422 echo (parent passes `error={fieldErrors[name]}` → red border + inline msg). Reusable for any future write form.
- **ApiError 422-normalization (api.ts)** — `errorFromBody()` handles BOTH the FastAPI 422 array (`detail:[{loc,msg}]`) AND the string-detail/message case; `fieldErrors()` maps `loc[1]`→field. Replaced the old extraction that would've stringified a 422 array to "[object Object]" (a latent swallowed-422 bug FE pre-empted). Additive + backward-compatible.
- **Fail-closed writes:** mutate→await→refetch, NO optimistic. A failed PATCH surfaces the error visibly, never a fake success.

---

## 2. Verification (Rule #0) — the FIRST write-heavy screen

### The write-form verify shape (memory `write-form-roundtrip-verify`)
S12 is the first primarily-WRITE screen → verify shifted from "rendered==read-payload" to the ROUND-TRIP: submit→2xx→re-GET reflects→reload persists (3 values agree) + the 3 silent-fail probes (swallowed-422→VISIBLE, partial-write→all-fields, optimistic-over-failed-POST→post-reload-rollback). FE built fail-closed (no optimistic) so the round-trip holds.

### The config-consumed proof (the real win — memory `verify-with-the-distinguishing-case`)
idle_hunter now CONSUMES `idleThresholdDays` at runtime, not the literal 7 — proven by the FILTERING distinguishing case (tester + team-lead, live): threshold=40 → only crewly(69d) flags, 29/35/35d EXCLUDED; threshold=100 → none; threshold=7 → all 4. The boundary genuinely filters on config. SPEC §S12's "cấu hình KHÔNG cần sửa code" is fulfilled.

### Architect 4-step (full functions + live container)
| Check | Result |
|---|---|
| pytest | **674 passed** (settings 25; the config-consumed FILTERING distinguishing) |
| vitest | **367 passed** (≥347 baseline; +20 settings/forms) |
| tsc | clean |
| Container `/settings` | 7-field AppConfig defaults; PATCH round-trips; per-field 422 (each names its field) |
| ApiError 422-normalize (api.ts) | handles the 422 array + string cases, fieldErrors loc[1]→field ✓ |
| Honest Tích hợp panel (page.tsx:28-33) | phase2/live status, NOT fake toggles ✓ |
| NO phantom displayName-required validator | confirmed absent (the post-freeze trap I flagged) ✓ |
| fail-closed writes | mutate→await→refetch, no optimistic ✓ |

### Other Rule#0 episodes this sprint (caught + fixed)
- **Write-side root-ownership trap (memory `host-file-source-must-mount` rule #8):** container-as-root wrote root-owned files into the bind-mount → first PATCH 500'd; broader set found (6 projects/* + notes/*.md root-owned); fixed `chown -R`. I re-verified 0 root files + PATCH works. The verify-live-app discipline at the WRITE layer (TestClient/tmp_path misses it).
- **Post-freeze schema reconcile (memory `schema-freeze-gate`):** backend reconciled 3 deltas (set_config rename, TZ→Asia/Ho_Chi_Minh, displayName-blank-allowed) after the freeze; caught + re-broadcast before FE/tester mirrored stale (the S3 moving-schema trap). All dispatch-aligned.

### team-lead Rule#0 + tester (PENDING tester Chrome — their lane)
team-lead: freeze gatekeeper-verified on disk + the FILTERING distinguishing behavior-test. tester: pytest+API 674/674 (all 3 deltas aligned, no false-greens); Chrome write-form teeth pending.

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema (AppConfig/AppConfigPatch frozen, per-field 422, extra=forbid) · ☑ integration tests · ☑ existing pass · ☑ auto-discovered · ☑ envelope · ☑ codes (422 per-field, fail-open GET) · ☑ self-describing (config returns full shape).

### Gate 2 — Function
☑ unit tests (config round-trip; the FILTERING config-consumed distinguishing; defaults=old-hardcoded; partial-merge; per-field 422; fail-open) · ☑ pytest 674/0 + vitest 367/0 · ☑ edge cases (config absent, partial, bad value, root-ownership) · ☑ **write-form teeth** (fail-closed, visible-422) · ☑ tsc clean · ☑ FE Chrome self-verify (briefHour=99→red border + exact backend msg, round-trip persisted).

### Gate 3 — Sprint
☑ end_sprint_12 written · ☑ architect 4-step · ☐ **tester Chrome — PENDING** · ☑ counts ≥ baseline (pytest 649→674, vitest 347→367) · ☑ findings flagged (§5) · ☑ format `feat(sprint-12)`.

**VERDICT: backend + FE GREEN. Gate 3 holds on tester Chrome → commit on report → ALL 14 SHIP.**

---

## 4. Assumptions (user-review — decide-and-log)

- **S12 = settings HUB** — hosts global-config + wires toggles + LINKS OUT to registry CRUD on its owning screen (Projects/Finance), NOT rebuilt. Pointer-edit OUT (register on Projects = lowest-risk). Full-feature-per-SPEC without duplication.
- **The global-config makes hardcoded constants config-driven** — idle_hunter `> idleThresholdDays` not literal-7; defaults = old values so behavior unchanged until edited. The SPEC's "cấu hình KHÔNG cần sửa code".
- **Live-consumed: idle/automation/briefHour/patternCheck.** Stored-only this sprint: timezone (display label), displayName (owner name), errorChannel (default inapp=run_log already surfaces errors; discord wiring = phase 2). To change: wire the stored-only fields to consumers.
- **briefHour applied at boot** (live change → next restart) — acceptable single-user (documented).
- **automationEnabled=false gates the SCHEDULED path; manual POST /run still runs** (explicit user action). To change: gate manual runs too.
- **Tích hợp & MCP = honest STATUS panel** (live vs phase-2), NOT functional toggles — faking absent capability violates honest-mirror.
- **displayName MAY BE EMPTY** (stored-only, no min_length — dispatch never required it; the post-freeze reconcile removed an over-constraint).

---

## 5. ALL 14 SHIPPED — "sơ bộ xong" + what phase 2 DEFERS

**14 screens shipped** (S1 Home · S2 Projects · S3 Detail · S4 Graveyard · S5 Finance · S6 Portfolio · S7 Journal · S8 Market · S9 Claude Usage · S10 Notes · S11 Brief · S12 Settings · S13 Routines · S14 Activity). 11 backend modules, the scheduler + 6 rule-based routines + run-log, md+git store + SQLite, the open API, the command bar, the template brief. **Home has 0 stubs — every tile live.**

**Phase 2 (DEFERRED — honestly, per ARCH §11):**
- **MCP / AI-actor** — FastMCP wrapper; Claude Code generating briefs/routines (the "AI brief" + "AI routine" later phase). This build = template/rule-based, API-open for an external AI to read.
- **Sidebar badges** — 3 of 4 still static (`sidebar-badges-static-placeholder` — the automation badge is live; the shell-task wires the rest).
- **Per-project token attribution** (S9 — .jsonl transcript parse; ClaudeManager shows the path).
- **Live 5h/weekly reset countdown** (S9 — not persisted readably).
- **AI-generated brief** (S11 — template now).
- **GCP 24/7 scheduler** (local APScheduler now).
- **Net-worth daily-snapshot chart** (S1/S5 — flat until a snapshot routine).
- **errorChannel→Discord, timezone/displayName consumers** (S12 stored-only now).

---

## 6. Retro (process learnings)

1. **The kickoff-inventory de-risked the closer** — Rule#0 found ~90% of S12's write surface already existed (behavior-verified, not just grep) → S12 was mostly FE-assembly + the ONE new global-config write. Don't assume greenfield; Rule#0-check for existing infra first.
2. **The write-form verify-shape change** (memory `write-form-roundtrip-verify`) — S12 being the first write-heavy screen, verify shifted to round-trip + the 3 silent-fail probes. FE pre-empted the swallowed-422 bug (the ApiError 422-array normalize).
3. **Two env-class write-layer catches** — the root-ownership trap (rule #8) + the post-freeze reconcile (schema-freeze-gate) — both caught by Rule#0 on the live/disk state before they cost a round.
4. **The honest-mirror net held on the closer** — team-lead's catch of the dropped Tích hợp panel → render as honest status (not dropped, not fake toggles). The dropped-feature net works even on the last screen.

---

## 7. Commit
- `feat(sprint-12): settings module (S12) — global app-config + config-driven readers + S12 hub + shared form components` — settings module + the wired readers + settings page + shared Field components + ApiError 422-normalize + plan_12 + end_12. One commit. **The closer — all 14 ship.**
- Gated on tester Chrome. Commit hygiene (commit-must-match-last-report): settled tree + grep the reported symbols (set_config) + explicit-path staging (exclude backend/data + .claude). After: `sleep 120 && git push` → notify user "14 shipped" → final Sprint Sync.
