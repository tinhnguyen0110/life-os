# Sprint 72-BE — finance change.abs real nav day-over-day (Cairn #72 BE-half)

> The BE half of #72 (FE = e8d7e5b shipped the honest 3-way render). Replace the finance/service.py change stub with a REAL day-over-day delta from the equity snapshots, honest-null when no prior-day baseline. backend BUILT; architect commits (§3). Quick reactive lane.

## Context
finance/service.py hardcoded `change=Change(abs=0.0, pct=None) if total_value else None` — a stub. The FE-half (#72-FE) already renders the honest 3-way (flat→neutral ▬, null→"—", nonzero→arrow). This wires the BE to feed REAL movement.

## Logic (real nav day-over-day, honest-null)
- `_nav_change(total_value)`: current total − the most-recent PRIOR-DAY snapshot (a `db.snapshots` row with `day != today`). No prior baseline (0/1 snapshot or only today's) → None (honest-null, NOT fabricated 0). Real equal-value-with-prior → abs 0.0/pct 0.0 (honest flat). prior_total==0 → pct None. Fail-soft on store error (None + log, mirrors _series).

## Verification (architect 4-step + backend evidence)
- **architect 4-step:** read `_nav_change` full — matches spec (prior_rows filter day!=today; most-recent-prior via rows[-1] oldest→newest; honest-null; no div-by-zero; fail-soft); wired at service.py:820 (former stub); Change schema UNTOUCHED (frozen); 2-file surface.
- **backend evidence:** 8 EXERCISE tests (2-day delta 1000→1100=abs100/pct10; 1-snap→None; 0→None; flat-with-prior→0.0/0.0; prior=0→pct None; **most-recent-prior-not-oldest** distinguishing; store-error→None; e2e). RED-proven (e2e fails with old stub). pytest INCLUSIVE 2026/0/0; mypy clean. Live :8686: real delta + honest-null both confirmed.
- **architect re-run:** test_finance.py 71/0.

## ⚠️ INCIDENT (data-loss — team-lead + user own the resolution)
During backend's live-verify, a blanket `DELETE FROM portfolio_snapshot` (to test the null branch) wiped ALL equity-curve history on the dev container (not just the seeded row). **The CODE is unaffected/correct** — this is a live-store data-loss (the test-writes-pollute-prod-store lesson, severe). The held-history cron rebuilds forward; past history is gone. Flagged to team-lead → user's call on recovery. Lesson saved (delete-only-the-seeded-key; verify empty-branches in an isolated tmp db, not the live store). This does NOT block the code commit (correct + isolated); the data matter is separate + team-lead-owned.

## 3 Gates — PASS (code)
- Gate 2: the distinguishing set (delta/honest-null/most-recent-prior/no-div-zero/fail-soft) RED-proven; INCLUSIVE 2026/0/0; mypy clean. ✅
- Gate 3: docs; architect 4-step + backend evidence + live; commit-hygiene (2 explicit files, no leak); commit format. ✅

## Assumptions (user-review)
- change = current total − most-recent prior-DAY snapshot; no prior → honest-null (NOT 0); prior-exists-equal → 0.0/0.0; prior=0 → pct None. **How to change:** _nav_change.
- (on-record, no code) tracing goal=0 = valid no-target activity, KEEP accepting (FE div-guards, P1 pct=0/never-done).

## Notes
- Cairn #72 BE-half (FE = e8d7e5b). backend BUILT; architect commits fix(sprint-72-be). The INCIDENT (snapshot-history wipe) is a separate data matter — team-lead + user own recovery; the code is correct. Next: #63-P1 (backend starting now).
