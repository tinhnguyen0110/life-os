# End Sprint 9 — Investment Journal (S7) [write module · md_store · two-axes calibration]

> Result doc (CLAUDE.md §3.2). The `journal` module: turn investment DECISIONS into learning data (calibration). A WRITE module via md_store (1 git commit/entry, Notes-pattern). Closes the S6 finance→journal loop. The headline: a real two-axes-calibration bug caught by a divergent value-diff.
> Author: architect · 2026-06-06 · Commit: `feat(sprint-9)` on `main`.

---

## 1. What shipped

### Backend — `journal` module (registry auto-discovered, md_store write store)
- **schema.py (FROZEN)** — `JournalEntry{id,date,action(BUY/SELL),asset,size,px,tag,reason,channel|None,thesis|None,negationCondition|None,confidence|None(0-100),pnl|None,outcome(open/right/wrong),lesson|None,createdAt,updatedAt}` + `JournalStats{entries,count,winRate|None,avgPnl|None,ladderDiscipline|None,thisMonth{total,buy,sell,ladder},calibration[{band,predicted,actual,n}]}`.
- **service.py** — md_store `journal/<id>.md` (YAML front-matter + body), 1 commit/write (Notes pattern). Derived stats (the 5). pnl-string parse fail-soft. **Writes fail-CLOSED** (md_store error propagates, no silent loss); reads fail-open (malformed entry skip+warn).
- **router.py** — `GET /journal?action=&tag=&channel=&asset=` (list+stats) + GET/{id} + POST + PUT/{id} (close) + DELETE/{id}. Envelope, 404/422. Auto-discovered.

### Frontend — S7 Journal screen (`app/journal/page.tsx`, replaced EmptyScreen)
- Ported `SCREENS.journal`: tabs filter (Tất cả/Mua/Bán/Ladder), 4 stat cards, trade-log table, "Ghi lệnh" create form (execution + SPEC decision fields thesis/negation/confidence/channel), close-entry form (pnl+outcome+lesson via PUT), calibration panel.
- **Honest labels baked in:** ladderDiscipline = "Tỷ lệ ladder · % lệnh gắn tag 'ladder'" (NOT plan-adherence); null→"—" (winRate/avgPnl/ladderDiscipline = no-data, not 0%); calibration `[]`→"Chưa đủ dữ liệu để hiệu chỉnh"; low-n bands → "⚠ Band n<3 là nhiễu thống kê"; write-fail-closed (throws→surfaces, no optimistic add).

### Logic (architect-decided — see §4)
The 5 stats + the **two-axes design:** winRate/avgPnl = MONEY (pnl-based); calibration = THESIS (outcome-based). ladderDiscipline = ladder-tag ratio (honest, not adherence).

---

## 2. Verification (Rule #0) — the calibration two-axes catch

### The headline bug (caught + fixed pre-FE-wire)
Calibration's `actual` keyed on `pnl>0` instead of `outcome=="right"` → the two intended axes COLLAPSED (calibration mirrored winRate, both pnl-based). **A green suite (543/0) AND tester's first PASS both missed it** — because the aligned fixture (pnl+/outcome-right) gives the SAME answer under pnl-based and outcome-based. **team-lead's divergent value-diff** (pnl=+20% profit + outcome=wrong thesis) exposed it: returned actual=100 when the design wants 0. Fixed (service.py: `p>0` → `e.outcome=="right"`) + a divergent teeth-test (`test_calibration_scores_THESIS_not_pnl`, RED against the bug) + docstring reconciled. → memory `verify-with-the-distinguishing-case`.

### Architect 4-step (full functions + live container)
| Check | Result |
|---|---|
| pytest | **544 passed, 0 errors** (+ the divergent calibration teeth-test) |
| vitest | **295 passed** (≥281 baseline; +14 journal) |
| tsc | clean |
| Container `/journal` | all 7 JournalStats keys; empty → winRate/avgPnl/ladderDiscipline null, calibration [], thisMonth {0,0,0,0} (honest empty) |
| Calibration two-axes (FE read: page.tsx calibration panel) | renders thực(actual) vs dự(predicted) + low-n warning + empty-state ✓ |
| Honest labels | ladder="% lệnh gắn tag ladder" not adherence; null→"—"; calibration []→"chưa đủ dữ liệu" ✓ |
| Write-fail-closed (hook) | createJournal throws→surfaces, no optimistic add ✓ |

### team-lead Rule#0 live two-axes value-diff
✅ Divergent entry (BTC +12% profit BUT outcome=wrong, conf 75) → live S7 showed **Win rate 100% (money) AND calibration "70-79% n=1 · thực 0% · dự 75%" (thesis)** — the two axes VISIBLY diverge on screen, end-to-end (backend→API→UI). create→close→calibration round-trip + git-commits (dd787d9/9526e60). PASS, pre-greenlit.

### Tester T4 (PENDING Chrome — their lane)
pytest 544 (incl divergent teeth) + API + Chrome value-by-value (with the divergent entry) + write-fail.

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema (JournalEntry/JournalStats frozen, Literal action/outcome, confidence ge0 le100) · ☑ integration tests · ☑ existing pass · ☑ auto-discovered · ☑ envelope · ☑ codes (404/422, fail-closed write surfaces error) · ☑ self-describing (winRate {wins,closed}, avgPnl {sum,closed}, ladderDiscipline {ladderCount,total}, calibration n).

### Gate 2 — Function
☑ unit tests (5 stats math, **calibration divergent teeth-test**, pnl-parse fail-soft, write-fail teeth, sparse→[], empty-journal) · ☑ pytest 544/0 + vitest 295/0 · ☑ edge cases (empty, null pnl/confidence, unparseable pnl, divergent calibration) · ☑ error path (write-fail-closed, read-fail-open) · ☑ tsc clean · ☑ FE Chrome self-verify.

### Gate 3 — Sprint
☑ end_sprint_9 written · ☑ architect 4-step (full functions + live container) · ☐ **tester T4 Chrome — PENDING** · ☑ counts ≥ baseline (pytest 499→544, vitest 281→295) · ☑ findings flagged (§5) · ☑ format `feat(sprint-9)`.

**VERDICT: backend + FE GREEN. Gate 3 holds on tester T4 Chrome + team-lead pre-greenlit → commit on T4 report.**

---

## 4. Assumptions (user-review — decide-and-log)

- **Unified JournalEntry = mock trade-log + SPEC decision/calibration fields.** Execution fields (date/action/asset/size/px/tag/reason) required-ish; decision fields (thesis/negation/confidence/channel/outcome/lesson) OPTIONAL. A quick log needn't fill thesis, but can — full feature available. To change: split into two entry types (more complex, not north-star).
- **TWO AXES (the key design):** **winRate/avgPnl = MONEY** (computed from `pnl`); **calibration = THESIS** (computed from `outcome`). A lucky profit on a wrong thesis = winRate WIN + calibration MISS (SPEC §S7 "process tách P&L"). `outcome` is pnl-SEEDED at close (pnl>0→right default) + user-overridable. To change: would conflate the axes (the bug we fixed) — don't.
- **calibration:** bands 50-59/.../90-100 (drop confidence<50 or null), predicted=midpoint, actual=%(outcome=="right"), n=0 bands omitted, all-empty→[]. To change: adjust bands or use Brier scoring (more complex).
- **ladderDiscipline = count(tag=="ladder")/count(total)**, labeled "% lệnh ladder-tagged" NOT plan-adherence — no per-trade followed-plan field, so true adherence can't be computed. To change: add a `followedPlan` field for real adherence.
- **pnl is a free-form display string** ("+5.5%"); parsed (fail-soft) only for stats. size/px also display strings (mock fidelity). To change: structured numerics + currency.
- **Writes fail-CLOSED, reads fail-open** — a lost entry must not look saved; a malformed entry must not sink the list.
- **No finance/market tie-back this sprint** — pnl is user-entered; auto-pull-price deferred.

---

## 5. Risks / out-of-scope (future)

- **journal-nudge routine** (price-hits-rung → remind to log) — Automation sprint.
- **Finance/Market tie-back** — auto-pull current price to compute pnl; deferred (pnl user-entered now).
- **Real ladder-adherence** — needs a per-trade followedPlan field (current = tag ratio).
- **Backend container flapping** — recurring infra (BE foreground exits → HTTP-000); the up-detached rule is in backend.md for next spawn; this-sprint's backend predated it.

---

## 6. Retro (process learnings)

1. **Two-axes calibration collapse caught ONLY by a divergent value-diff (the headline) → memory `verify-with-the-distinguishing-case`:** calibration scored pnl not outcome; the green suite (543/0) + tester's aligned-fixture PASS both missed it because pnl+/right gives the same answer under both impls. A profit+wrong-thesis entry (the distinguishing case) exposed it. **Rule: when two derived fields SHOULD differ, verify with a DIVERGENT case so a correct impl ≠ a collapsed one.** Now pinned by a teeth-test.
2. **Unified-shape framing (mock vs SPEC)** — the mock showed a trade log, SPEC wanted a calibration journal; resolved to ONE entry carrying both (decision fields optional). Full feature per SPEC, port the mock — cut complexity not user value.
3. **Notes md_store precedent reused** — Journal mirrored the frozen Notes write pattern (slug-id/yaml/glob/fail-open/write_file); lowest-risk write-module path.
4. **Honest labels enforced in the dispatch** — ladderDiscipline "% ladder-tagged" not adherence, null→"—" not 0%, calibration empty-state — all specced so FE couldn't render the misleading mock label.

---

## 7. Commit
- `feat(sprint-9): journal module (S7) — md_store trade-decision log + two-axes calibration + S7 screen` — journal module (schema/service/router) + useJournal/journal page + plan_9 + end_9. One commit.
- Gated on tester T4 Chrome + team-lead pre-greenlit. After: `sleep 120 && git push` → notify user → Sprint Sync → next sprint.
