# Sprint W7 — END

> A1c (FE wiki finish) + A2 (Decision Journal). Parallel tracks → separate commits (A2 backend / A1c FE,
> zero file overlap). This doc covers A2; A1c section appended when frontend lands + is reviewed.

---

## A2 — Decision Journal + Calibration · ✅ SHIPPED + verified live (Rule#0 — architect; team-lead spot-check pending)

**Commit:** `feat(sprint-W7): A2 decision journal — Brier + calibration + rule-based bias-cluster` (hash at commit).

### What shipped — the decision-learning loop (the "self-improve" thesis on the user)
A NEW `modules/decision_journal/` for GENERAL decisions (investment AND project, not trades): log a
decision + thesis + falsification condition + a confidence% (the probability claim) → on resolve, an
outcome (right/wrong) drives **calibration** (Brier + confidence-band predicted-vs-actual) and **rule-based
bias detection** (a domain whose resolved-wrong-rate is high over a min sample). The learning loop:
"is your 80%-confidence actually right 80% of the time, and which domains do you systematically misjudge?"

### Architecture decision (the key kickoff call — logged)
**NEW `modules/decision_journal/`, NOT folded into the trade `modules/journal/`.** The existing journal is
trade-shaped (BUY/SELL/asset/px/pnl/channel); a general decision journal would be bloated by trade fields
and needs a different stats surface (Brier + bias-cluster vs win-rate/ladder-discipline). REUSED journal's
`_BANDS` + thesis-axis calibration MATH as prior art (reference, not fork). Cohesion + north-star (simplest
impl, full feature) — both modules stay clean. (plan_sprint_W7 §Kickoff Finding 2.)

### Files
- `modules/decision_journal/{__init__,router,schema,service}.py` — md_store-backed CRUD (journal template, fail-CLOSED writes) + pure `compute_stats`. `MODULE = BaseModule(name="decision-journal")` → auto-discovered (NO core/main.py edit).
- `core/config.py` — `decision_journal_dir` property (`data_dir / "decision_journal"`).
- `tests/test_decision_journal.py` (21).

### Algorithm (deterministic, no LLM — team-lead-tightened)
- **resolved set** = `status=="resolved" AND outcome in (right,wrong)`. Open excluded from ALL stats.
- **Brier** = `mean((p − o)²)` over resolved; `p = predicted if not None else confidence/100`; `o = 1 right / 0 wrong`. 0 resolved → None. Lower = better.
- **Calibration bands** = journal's `_BANDS` (50-59…90-100; confidence<50/None dropped). Per band: predicted=midpoint, `actual = %(outcome=="right")`, n=count, omit empty. The THESIS/outcome axis — a high-confidence-WRONG band scores actual LOW, NOT ~95.
- **Bias** = group resolved by `domain`; for domains with `n >= 4`, `wrongRate = wrong/n`; flag if `> 0.60` (strict). min-n gate → no sparse-data false positives.

### Verified LIVE (architect, Rule#0 — independent re-run, not backend's word)
- **full pytest 985 (+21) / 0 fail / 0 error**, 21 def==collected, mypy clean (4 files), `decision-journal` auto-discovered in `/health`.
- **THE 3 TEETH (my own run):**
  1. **Brier = 0.325** exact (conf90-right + conf80-wrong) + predicted-override = 0.25.
  2. **Two-axis distinguishing case**: 90-100 band all-WRONG → `actual=0.0` (a confidence-only collapse would report ~95); all-RIGHT → 100.0. The axes do NOT collapse.
  3. **Bias gate**: 3-all-wrong → NOT flagged (n<4); 4@75%-wrong → flagged `(invest, 0.75, 4)`; 5-entry@60% (3/5) → NOT flagged (strict `>0.60`).
- **LIVE CRUD round-trip on :8686**: create → resolve(wrong) → stats (brier 0.5625 = (0.75−0)²) → delete. All correct.

## Assumptions (user-review) — A2
1. **A2 = NEW `modules/decision_journal/`**, separate from the trade `modules/journal/` (cohesion + different stats surface). Reuses journal's calibration-band/thesis-axis math. — to change: merge the two modules (would force trade fields onto general decisions — don't).
2. **Brier prob source**: `predicted` (explicit 0-1) when given, else `confidence/100`. `predicted` + `confidence` are distinct fields (sureness vs P(thesis true)); Brier degrades to confidence when predicted absent. — to change: make predicted required, or drop it and always use confidence.
3. **Bias thresholds**: min-n=4, wrong-rate>0.60 (strict). Defaults, env-tunable later. — to change: tune per real data volume (raise min-n as the corpus grows).
4. **Stats over the FILTERED set**: GET with `?domain=` computes Brier/bands/bias over just that domain (matches journal behavior; arguably useful for per-domain calibration). — to change: always compute over the full set + filter only `entries`.

## A1c — FE wiki finish · (pending — appended after frontend lands + architect review)
