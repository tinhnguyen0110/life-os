# end_sprint_DAILY-TRACING-P4 — brief-wire streak-at-risk (Cairn #65 Phase 4, FINAL)

> Result. The LAST link of #65: life_brief/daily_brief now surface a hard-won streak about to break ("chuỗi sắp đứt — hoàn thành hôm nay"). Commit `<hash>` `fix(sprint-DAILY-TRACING-P4)`. Status: ✅ all gates pass. backend-w3 BUILT (brief reader/schema/service + read_server life_brief section + 3 tests); architect 4-step + committed (§3, sole serialized committer). **#65 EPIC COMPLETE** (BE + MCP + FE + brief). Phase 4 of 4.

## What shipped (4 code + 3 test files)
| File | Change |
|---|---|
| `modules/brief/reader.py` | + `tracing: object | None` to Sources; fail-soft pull (`from modules.tracing import reader as trc; src.tracing = trc.get_overview()` — on Exception: log + warning + leave None). The SAME derived overview as GET /tracing + the MCP wrap (no new read path/derivation). |
| `modules/brief/service.py` | + `_tracing_priority(tracing)` — at-risk = `streak >= STREAK_AT_RISK_MIN(3) and today.done is False`; fires WARN (today-actionable, not urgent) "N chuỗi sắp đứt (dài nhất {top} ngày)"; None if no source/no activities/none-at-risk. `_RULE_ORDER` += `tracing:7`; `PRIORITY_CAP 6→7`; registered in generate_brief. |
| `modules/brief/schema.py` | + the tracing brief section type. |
| `mcp_servers/read_server.py` | + `_brief_tracing()` — the life_brief habit-board SECTION (atRisk/atRiskCount/doneToday/total/topStreak, lean+honest-empty), wired via `_section("tracing", _brief_tracing)`. **Beyond the original dispatch but CORRECT**: life_brief composes its OWN sections (does NOT reuse daily_brief's priorities) — so the both-consumers requirement needs this separate wire (the dissolved-finding-recheck-ALL-consumers lesson, which the dispatch flagged). |
| `tests/test_brief_tracing.py` (NEW) | the distinguishing set + BOTH-consumers asserts (below). |
| `tests/test_mcp_read.py` · `tests/test_mcp_e2e.py` | the life_brief section-list now includes "tracing" (11th section). |

## Design (LOCKED — reuse derived, both consumers)
- the brief READS the already-derived `streak` + `today.done` (no new derivation — raw-data-first held).
- **BOTH brief consumers carry the signal:** daily_brief via the `_tracing_priority` rule; life_brief via the `_brief_tracing` section. life_brief composes its OWN sections (not daily_brief's priorities), so each needed its own wire — verified by 2 explicit tests, not assumed (the dissolved-finding lesson).
- STREAK_AT_RISK_MIN=3 (matches the ✦ badge; 1-2 isn't hard-won). severity=warn (nothing past-due; the day isn't over).

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read FULL diffs on disk):** `_tracing_priority` matches the dispatch spec EXACTLY (None-guards, streak≥3+undone, max-streak, warn, vi text) ✅; cap=7 + rule-order=7 + registered ✅; reader fail-soft (tracing fails → None + warning, brief still built) ✅; `_brief_tracing` lean+honest-empty (atRisk:[] when none) ✅; the test set has REAL teeth (fires/done/below-min/count-longest/empty/none-source + BOTH-consumers + cap=7) ✅; the intermixed-tree lane-assignment done by CONTENT (read_server.py + test_mcp_read.py + test_mcp_e2e.py are P4 by their tracing content, NOT #58's mark-sweep — confirmed each file's diff). 
- **backend-w3 evidence:** mypy clean; FULL pytest (with all 3 lanes coexisting on disk) confirmed green by architect's independent re-run.

## 3 Gates — ALL PASS
- **Gate 1 (API):** the brief (daily + life) surfaces the tracing signal honestly; fail-soft per source; honest-empty (atRisk:[]). ✅
- **Gate 2 (Function):** the distinguishing set (fires/done/below-min/count-longest/empty/none-source) + BOTH-consumers (daily_brief priority + life_brief section, explicitly tested) + cap=7; mypy clean; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend evidence; SURGICAL stage (P4-only, content-verified vs the intermixed #58/#72 files — no cross-lane leak); commit format. ✅

## Assumptions (user-review)
- **streak-at-risk rule:** activity with streak ≥ 3 AND today not-done → a WARN brief priority + a life_brief section. STREAK_AT_RISK_MIN=3 (matches ✦; 1-2 not hard-won); severity=warn (today-actionable, not overdue-urgent). **How to change:** STREAK_AT_RISK_MIN / the severity in _tracing_priority.
- **both consumers wired separately:** daily_brief = the priority rule; life_brief = the `_brief_tracing` section (life_brief composes its own sections, not daily_brief's priorities). **How to change:** the two wire sites.

## Notes
- #65 Phase 4 of 4 — FINAL. backend BUILT; architect committed (§3, sole serialized committer). Committed from an INTERMIXED working tree (#58 + #72 also done-on-disk) — lane-assigned by CONTENT (the content-diff-not-just-filenames hazard), surgically staged P4-only. **#65 G-HABIT EPIC COMPLETE: BE (P1) + MCP (P2) + FE /tracing S14 (P3) + brief-wire (P4).** team-lead triggers the milestone (Chrome /tracing + /decision + /macro in one session + surface to user). Next: #58 + #72 in arrival order → #63 (dev-git-tracing) → #64 (per-repo-memory).
