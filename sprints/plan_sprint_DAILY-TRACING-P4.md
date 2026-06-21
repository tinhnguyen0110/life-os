# Sprint DAILY-TRACING-P4 — brief-wire streak-at-risk (Cairn #65 Phase 4, FINAL)

> Created 2026-06-21 by architect (designed ∥ while #65-P3 builds). #65 Phase 4 of 4 — the LAST link: wire the tracing module into life_brief so "what's on my plate today" surfaces a streak about to break. HOLD dispatch until #65-P3 commits (sequential). backend BUILDS; architect commits (§3). After this → #65 DONE (mốc lớn → team-lead reports user).

## Context
P1 (BE) + P2 (MCP) + P3 (FE) built the tracing module end-to-end. P4 closes the loop: life_brief/daily_brief should tell the user "streak X about to break — do it today" so a hard-won streak isn't lost. Mirrors the reminders brief-wire (#30 `_reminders_priority`) EXACTLY — same pattern, 4 edits.

## Scope
IN: `modules/brief/reader.py` (pull tracing, fail-soft) + `modules/brief/service.py` (a `_tracing_priority` rule + register it + bump PRIORITY_CAP) + tests. The brief reads through to GET /tracing's overview (the same TracingOverview).
OUT: NO change to the tracing module (P1-P3 frozen). NO new tracing derivation (the brief READS the already-derived streak/today; it does NOT compute).

## Logic/Algorithm (the streak-at-risk rule — reuse P1's derived fields, zero new derivation)
The rule reads the already-derived `ActivityView.streak` + `ActivityView.today.done` from the tracing overview. An activity is **at-risk** when it has a meaningful streak that today would BREAK if not done.

1. **reader.pull():** add `src.tracing = tracing_service.reader.get_overview()` in a fail-soft try/except (mirror the reminders block — on failure log + append warning + leave None). Add `tracing: object | None = None` to the Sources dataclass.
2. **_tracing_priority(tracing) -> Priority | None** (0-1 priority, like every sibling rule):
   - `tracing is None` (source failed) or `not tracing.activities` → None.
   - **at_risk** = activities where `streak >= STREAK_AT_RISK_MIN` AND `today.done is False` (a real streak that today hasn't extended yet — the at-risk-not-break semantic from P1: today-incomplete doesn't break the streak YET, but EOD it will).
   - **STREAK_AT_RISK_MIN = 3** (decide-and-log: a 1-2 day streak isn't "hard-won"; 3+ matches the mock's ✦ badge threshold — surfacing what the UI already flags as a streak. Tunable.).
   - if at_risk:
     - the longest at-risk streak `top = max(a.streak for a in at_risk)`.
     - severity = **warn** (it's a today-actionable nudge, not an overdue-urgent — distinct from reminders' urgent-overdue; nothing here is past-due, the day isn't over).
     - text (vi, matching the brief's voice): `f"{len(at_risk)} chuỗi sắp đứt (dài nhất {top} ngày) — hoàn thành hôm nay để giữ streak."`
   - else → None.
3. **register:** add `"tracing": 7` to `_RULE_ORDER` (after reminders=6); add `("tracing", lambda: _tracing_priority(src.tracing))` to the rules list in generate_brief(); bump `PRIORITY_CAP = 7` (so 7 rules → none silently dropped, exactly as #30 did for 6).

## REST≡MCP / consumer note
The brief is a synthesis surface (daily_brief + life_brief both read generate_brief). Wiring tracing into generate_brief means BOTH daily_brief AND life_brief auto-surface the streak-at-risk priority (the dissolved-finding-recheck-all-consumers lesson: one rule, all brief consumers). No separate life_brief edit needed if life_brief composes daily_brief's priorities — VERIFY at kickoff which consumer assembles what (grep life_brief's source; if it independently lists sections, wire there too).

## HARD GATE (distinguishing — behavior, not field-read)
- streak=5 + today.done=False → priority FIRES (warn, "sắp đứt", count + longest).
- streak=5 + today.done=True → NO priority (already safe today).
- streak=2 + today.done=False → NO priority (below STREAK_AT_RISK_MIN=3).
- 0 activities OR tracing source fail → None (honest, no crash; fail-soft warning appended).
- the rule appears in BOTH daily_brief and life_brief output (the synthesis-consumer check).
- PRIORITY_CAP=7 → with all 7 rules firing, none dropped.
- pytest 0-failed; the brief's existing tests still green (the cap bump + rule-order didn't break ordering).

## Baseline
pytest = post-P3 count. Keep 0-failed/0-errors.

## Test ownership split
backend: _tracing_priority fires/doesn't-fire per the distinguishing cases (streak≥3+undone→warn; done→none; <3→none; empty/fail→none); the reader fail-soft (tracing source down → None + warning, brief still produced); the rule in both brief consumers; cap=7. tester: live daily_brief + life_brief over MCP/curl after seeding an at-risk activity (throwaway → assert → clean up).

## Assumptions (user-review)
- **streak-at-risk rule:** an activity with streak ≥ 3 AND today not-done → a WARN brief priority "chuỗi sắp đứt, hoàn thành hôm nay". STREAK_AT_RISK_MIN=3 (matches the ✦ badge; 1-2 isn't hard-won). severity=warn (today-actionable, not overdue-urgent). **How to change:** STREAK_AT_RISK_MIN / the severity in _tracing_priority.
- wired into generate_brief → BOTH daily_brief + life_brief surface it (one rule, all consumers).

## Notes
- #65 Phase 4 of 4 — FINAL. Mirrors the reminders brief-wire (#30) exactly (4 edits: Sources field + reader pull + the rule + register/cap). backend BUILDS; architect commits fix(sprint-DAILY-TRACING-P4). HOLD until P3 commits. After this → #65 DONE: the full G-HABIT module (BE + MCP + FE + brief) shipped — team-lead reports the user (mốc lớn) + the /tracing UI for an async look. Then #63 (dev-git-tracing) → #64 (per-repo-memory).
