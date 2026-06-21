# end_sprint_91-DEV-ACTIVITY-BOUNDED — dev_activity bounded output + days-window + otherRepos de-dup (Cairn #91, HIGH)

> Result. `GET /dev_activity` was UNUSABLE by an agent at the real "xem 1 năm" use-case: days=365 → ~186KB / ~46K tokens → broke the agent's token-limit. Fixed (agent-first, principle #38 bounded-output): days>90 → AGGREGATE mode (per-day repos[] + otherRepos omitted, byRepo + summary + daily counts kept) + a STRUCTURED `truncated` flag (cairn #295 pattern); days-window made exact (days=1 = today VN only, days=0 → honest 422); otherRepos de-duped. **The #97 FE is preserved by construction (threshold=90 = the FE's max → ≤90 keeps full detail; the agent's >90 call aggregates).** Commit `<hash>` `fix(sprint-91-dev-activity-bounded): days>90 aggregate + days-window + otherRepos de-dup (#91)`. Status: ✅ verified (backend-w3 built; architect 4-step + THE #97-FE-vitest-gate re-run + INDEPENDENT live days=365/1/90/0 + stale-container catch). Cairn #91 HIGH — tool-hardening lane 1.

## What shipped (reader.py + schema.py + test)
| File | Change |
|---|---|
| `dev_activity/reader.py` | `_DETAIL_THRESHOLD=90`; `get_overview`: days≤0 → `_empty_overview` (honest, NOT silent=1); days=N = EXACTLY N VN-days (`since = today_vn − (N−1)` → days=1 = today only, off-by-one fixed); days>90 → aggregate: byDay `repos=([] if aggregate else day_rows)` (per-day flood dropped, date/totalCommits/activeRepos kept) + otherRepos dropped + a STRUCTURED `truncated` flag. ≤90 → full detail (FE unaffected). |
| `dev_activity/schema.py` | `aggregated: bool` + `truncated: {daysSummarized, detailThresholdDays, perDayDetailOmitted, otherReposOmitted} | None` (the cairn #295 structured-policy-data, NOT a transport-baked prose hint); `rangeDays ge=0` (the 0-empty case). |
| `tests/test_dev_activity.py` (+6) | days=365-bounded · days=1=today-only · days=0-empty · otherRepos-de-dup · ≤90-full-detail · the aggregate threshold. |

## Design (LOCKED — bounded-by-design, threshold=FE-max, structured truncation, FE-preserved)
- **🔴 the FE-preservation (the load-bearing recheck-all-consumers):** `get_overview` feeds BOTH the agent/MCP surface AND the #97 FE (/dev-activity reads byDay[].repos[] for heatmap/peak-hours/devStats + otherRepos for the you-vs-other bar, ≤90d). The threshold = 90 (the FE's MAX range) → ≤90 keeps FULL detail (FE byte-identical) + the aggregate only kicks in >90 (the agent's large call, where the FE never goes). So the token-overflow fix is ADDITIVE to the FE's range, NOT a change — #97 preserved by construction.
- **bounded-by-design (principle #38):** days>90 omits the per-day repos[] flood (the 186KB source) + otherRepos → ~9KB, agent-readable. NOT a silent cap — `aggregated=True` + a `truncated` STRUCTURED flag (daysSummarized/detailThresholdDays/perDayDetailOmitted) so the agent reads WHAT was omitted + can re-query ≤90 for detail. (cairn #295: structured policy-data, not a transport-specific prose hint — the agent + the FE each interpret the flag.)
- **days-window exact:** days=N = exactly N VN-days ending today VN (days=1 = today only — the off-by-one fixed); days≤0 → honest reject (422 INVALID_INPUT at the router's `ge=1` Query validation; the reader's `_empty_overview` is the belt). NOT silent=1.
- **otherRepos de-dup:** kept at ≤90 (the FE's bar reads it) / dropped >90 (the agent's large view isn't byte-doubled with the 'other' rows already in byDay).

## Verification (Rule#0 — architect INDEPENDENT, the FE-gate + a stale-container catch)
- **🔴 THE FE-protection gate — RE-RAN the #97 FE vitest MYSELF:** devStats + dev-activity = **35 passed** (#91 touches their data source; the gate is green — #91 did NOT break the UI the user just got). ✅
- **architect 4-step (read FULL):** the threshold-90 aggregate (repos dropped >90, kept ≤90); days-window since=today_vn−(N−1) (exact); the structured `truncated` flag (not prose); schema additive (aggregated/truncated/rangeDays ge=0). ✅
- **🔴 a stale-container catch (the stale-container-not-code-bug lesson):** the live :8686 days=365 first returned HTTP 500 → I did NOT conclude a code bug → called get_overview(365) directly in-container (OK, aggregated=True) + a FRESH TestClient(app) (HTTP 200 + the structured truncated) → proved the DISK code is correct → the 500 was STALE container bytes → restarted → 200. (Verify disk-first before a code-bug conclusion.)
- **INDEPENDENT live (post-restart):** days=365 → HTTP 200, **9223B (~9KB, was ~186KB = ~20× reduction)**, aggregated=True, byDay-detail=False, otherRepos=0, truncated=True (the agent reads a 1-year call); days=1 → byDay = today VN only (off-by-one fixed); days=90 → aggregated=False, byDay-detail=True, otherRepos present (the FE gets its detail); days=0 → HTTP 422 INVALID_INPUT (honest, not silent=1). ✅
- **Suite:** the dev_activity file 46 passed; DEFAULT (`-m 'not slow'` deterministic) = **2213 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2206→2213 = +7 #91 tests) 0-failed; never staged backend/data/.

## 3 Gates
- **Gate 1 (API/agent):** days=365 bounded + agent-readable + structured truncated flag; days-window exact; days≤0 honest-422; otherRepos de-dup; honest-empty/warnings kept. ✅
- **Gate 2 (Function):** the distinguishing tests (days=365-bounded / days=1=today / days=0-empty / otherRepos-de-dup / ≤90-detail); independent live + the FE-vitest gate; the stale-container catch; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + #97-FE-gate + independent live; staged set EXACTLY reader.py + schema.py + test + end doc (NO frontend, no data/.env/template); commit format. ✅

## Assumptions (user-review)
- **detail threshold = 90 days (the FE's max range)** — ≤90 full detail, >90 aggregate. **Why:** the FE never asks past 90 → it always gets full detail; only the agent's large call aggregates. **How to change:** `_DETAIL_THRESHOLD`.
- **days≤0 → 422 INVALID_INPUT** (the router's `ge=1` Query); the reader's `_empty_overview` is the unreachable belt. **How to change:** loosen the Query `ge` if a 0=empty-200 is wanted (the reader already handles it).
- **the ≤90 'other' rows still appear in byDay.repos AND otherRepos** (a tolerated dup for the FE-fixture safety; the agent's >90 view is the de-duped one). **How to change:** dedup at ≤90 too if the FE switches to reading byRepo for the bar (a coordinated FE change).

## Notes
- Cairn #91 HIGH — the most painful tool-hardening (days=365 broke the agent token-limit → tool unusable for "xem 1 năm"). backend-w3 built; architect committed (§3 sole-committer). The FE-preservation (threshold=FE-max) is the load-bearing recheck-all-consumers call — #91's data source is #97's read, and the threshold makes the fix additive (the #97-FE-vitest gate re-run by me proves it). Reused the cairn #294/#295 bounded-output pattern (structured truncation flag, not transport-baked prose). The live 500 was a stale-container artifact (disk-verified-first, restarted) — NOT a code bug. Tool-hardening lane 1 of the batch (#91 → #92 → #99 → #98 + re-scoped hash-validate). BE-only stage (no FE leak). team-lead re-Chromes /dev-activity at 7/14/30/90d in the push-window (the user's UI must not regress).
