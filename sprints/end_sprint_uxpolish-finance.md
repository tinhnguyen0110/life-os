# end_sprint_uxpolish-finance — #143 finance F1: coordinate KPI + equity-curve first paint

> #143 UX-polish, finance F1. BE-side DIAGNOSED benign (backend-w3: F1 = cold-start, memo already done 42d1232, BE SKIP). The FE-side fix (team-lead approved): the perceived split-paint (curve drawn while KPIs skeleton). FE-only, behavior-preserving, no data change.

## What shipped (2 files)
- **components/EquityCurve.tsx:** split into `<EquityCurveView history={UseFinanceHistory}>` (presentational, takes the hook as a prop) + `EquityCurve()` wrapper (`return <EquityCurveView history={useFinanceHistory()} />`). Backward-compatible: the existing self-fetch usage + EquityCurve.test (12) unchanged + green.
- **app/finance/page.tsx:** lifted `useFinanceHistory` into the page; added a `historyFirstReady` LATCH (set once history is `ready` OR `error`); gate the LoadErrorShell on a COMBINED `gateStatus` (finance error → error; finance loading OR !historyFirstReady → loading; else ready); render `<EquityCurveView history={history} />`. So KPIs + curve paint TOGETHER on first load.

## Why the latch (the design crux — FE's call, verified correct)
The curve's range toggle (7N/30N/90N/1năm) re-fetches history (status→loading). Gating the page directly on `history.status` would flash the WHOLE page to loading on every range toggle. The latch tracks only the INITIAL readiness → first paint is coordinated; subsequent range re-fetches stay LOCAL to the curve panel. A history ERROR also sets the latch (never pins the page on loading — the curve shows its own error inside the panel). A finance error still gates the page (page error). Error/empty paths preserved.

## Verify (architect 4-step + live Chrome via javascript_tool — Rule#0)
1. **git diff:** 2 files. EquityCurve View-split (backward-compat) + page.tsx latch/gate. No data change (KPIs render the same `data.*`; curve gets the same hook result).
2. **Read full:** latch logic correct — first-paint waits both, range-toggle stays local, history-error doesn't pin page, finance-error still gates. Behavior-preserving.
3. **tsc 0** (cwd-corrected — an initial wrong-dir run gave a false error; from frontend/ tsc exit 0).
4. **vitest 1115** — finance 15 / EquityCurve 12 / useFinanceHistory 6 CONSISTENTLY green across 3 runs. (One run showed an intermittent 1-fail ELSEWHERE = the known reminders-class flake B-T1 is fixing — NOT this change; finance/equity/history never failed.)
5. **🔴 Live Chrome (architect, :3010):**
   - First-paint: no split-paint detected (KPI + curve appear together; warm load resolved with both present, console clean).
   - 🔴 LATCH PROOF (the design crux): clicked 90N → KPI tile STAYED mounted during the re-fetch (`kpiDuringRefetch: true`) + page did NOT flash to loading (`pageReGatedToLoading: false`) → `latchWorks: true`. Range-toggle stays local, exactly as intended.
   - $10,624 correct; console clean.

## Gates
- Gate 2 (Function): FE render-coordination; behavior preserved (no data change, error/empty/range-toggle paths intact); tsc clean; vitest no-delta; live Chrome latch + paint-together verified. ✓
- Gate 3 (Sprint): this doc + 4-step + live Chrome (incl the latch distinguishing case) + count == baseline. ✓

## Assumptions (user-review)
- **First-paint coordinated, range-toggle local (the latch).** The finance KPIs + equity-curve paint together on first load (one gate); the curve's range toggle re-fetches without re-gating the page. How to change: drop the latch + gate directly on history.status (but then range toggles flash the page — the latch is the better UX).
- **A history fetch error does NOT block the finance page** (the curve shows its own error; the page renders KPIs). Finance fetch error still shows the page error.

## Commit
- Hash: (filled) — `fix(sprint-uxpolish-finance): coordinate KPI + equity-curve first paint (one loading gate, range-toggle stays local)`
- Files: components/EquityCurve.tsx + app/finance/page.tsx + sprints/plan_sprint_uxpolish-finance.md + sprints/end_sprint_uxpolish-finance.md.
- HOLD push for team-lead's before/after Chrome gate (paint together, range-toggle no re-gate, $10,624 correct, console clean) → OK → push. (B-T4 backend = SKIP, diagnosed clean.)
