# Sprint W7 — A1c (FE wiki finish) + A2 (Decision Journal + Calibration) · PARALLEL · PLAN

> Maps to DISPATCH "Sprint 2". Two independent tracks: frontend (A1c) ∥ backend+FE-view (A2).
> Approved by team-lead 2026-06-14.

## Objective
- **A1c [frontend]** — finish the FE wiki: citation-verify surface (consumes A1b), ego-graph polish, complete backlink panel, the `/wiki/sync/conflicts` conflict-resolution UI (makes A1a user-visible). Real corpus already loaded (team-lead's mining track: 10 notes + 1 MOC via the proposal queue) → render against REAL data.
- **A2 [backend + FE view]** — Decision Journal + Calibration module (general decision learning-loop: log decision + prediction → on resolve, measure calibration → detect repeated bias). The "self-improve" thesis applied to the user.

---

## Kickoff — 2026-06-14

### Spot-checked the actual code + spec (the decisive findings)

**FINDING 1 (A1c reframe — SPEC drift in the DISPATCH):** The DISPATCH says A1c = "chat UI". The SPEC is
explicit (`WIKI-SCREENS-FEATURES.md` L5 + L257): **"KHÔNG có chat box trong app"** — there is NO chat
screen; grounded Q&A = Claude Code via MCP. What L257 actually wants is a small surface: *"answered via
MCP, N citations verified"* + **citation-click → jump to note + span**. So A1c task-1 is a **citation-
verify display surface** (consumes the A1b `POST /wiki/citations/verify` endpoint + renders verified/
rejected/ungrounded per claim, click→note+span), NOT a chatbox. This is the correct, spec-faithful read
and AVOIDS building a chat box the SPEC explicitly rejects.

**FINDING 2 (A2 architecture call — RESOLVED here, the key kickoff deliverable):** `modules/journal/`
ALREADY EXISTS and already has decision-fields: `thesis`, `negationCondition` (= falsification_condition),
`confidence%` (0-100, 422 out of range), `outcome` (open/right/wrong on the **thesis axis, separated from
P&L** — "a lucky profit on a wrong thesis is a calibration MISS"), `lesson`, AND confidence-band
calibration already computed in `JournalStats` (the `verify-with-the-distinguishing-case` lesson is baked
in). BUT it is **trade-shaped**: `action` BUY/SELL, `asset`, `px`, `pnl%`, `channel` crypto/etf/vn.

**DECISION: NEW `modules/decision_journal/` (do NOT fold into `modules/journal/`).** Reasons:
1. **Cohesion** — the existing journal is a *trade* log; A2 is *general decisions* (investment AND project,
   per DISPATCH). Overloading the trade journal would force every general decision to carry irrelevant
   trade fields (action/asset/px/pnl), violating the module's clean trade-shape. The SPEC keeps S7
   (trade journal) distinct from a general decision-learning loop.
2. **Different stats surface** — A2 wants **Brier score** + **bias-clustering by domain/pattern**; the
   trade journal computes win-rate/avgPnl/ladder-discipline. Different derived metrics, different module.
3. **REUSE the math, not the module** — the existing `_BANDS` + thesis-axis calibration logic in
   `journal/service.py` is excellent prior art. decision_journal will REUSE the calibration approach
   (confidence-band, thesis-outcome axis) + ADD Brier + domain bias-clustering. I'll point backend at it.
4. **Finance as outcome source** — A2 links to `modules/finance/` for investment-decision outcomes; that
   cross-module link is cleaner from a dedicated module than from the trade journal.

This keeps both modules simple + full-featured (north-star: simplest impl, full feature). Logged to
§Assumptions in end_sprint_W7.md.

**A2 entry minimal fields (DISPATCH-locked):** `decision · thesis · falsification_condition · confidence%
· date · domain · status(open/resolved) · outcome`. + `predicted` (the probabilistic prediction for Brier).
**Calibration:** Brier score (mean squared error of confidence-as-probability vs outcome) + confidence-band
predicted-vs-actual (reuse journal's band approach). **Bias detection: RULE-BASED** (DISPATCH: "ưu tiên
rule, rẻ + deterministic" — NOT LLM): cluster resolved-wrong decisions by domain/tag, flag a domain where
wrong-rate exceeds a threshold over a min sample (no false-positive on sparse data — min-n gate).

### Drift summary
- A1c "chat UI" → **citation-verify surface** (no chatbox — SPEC L257). Conflict UI is NEW (A1a deferred it here).
- A2 → **new `modules/decision_journal/`**, reusing journal's calibration math, adding Brier + rule-based bias-cluster.

### Final task list (W7)
- **A1c [frontend]** — citation-verify surface + ego-graph polish + backlink panel + `/wiki/sync/conflicts` UI. Chrome self-verify against the REAL loaded corpus.
- **A2 [backend]** — new `modules/decision_journal/` (router/schema/service): CRUD + Brier + calibration-bands + rule-based bias-cluster. Full §3.3b dispatch with the Logic/Algorithm block I'll write.
- **A2-FE [frontend, after A2 schema freezes]** — the decision-journal view (log decision, resolve, calibration display). May slip to a follow-on if A1c fills the FE sprint.

Parallel: frontend on A1c, backend on A2. Tester verifies each. Independent — no cross-dep.

---

## Assumptions (user-review) — finalized in end_sprint_W7.md
- A1c task-1 = citation-verify surface (consumes A1b), NOT a chat box (SPEC L257 "no chat box in app").
- A2 = new `modules/decision_journal/`, not folded into the trade `modules/journal/` (cohesion + different stats + Brier/bias-cluster). Reuses journal's calibration-band + thesis-axis math.
- A2 bias detection = rule-based domain-cluster with a min-n gate (no LLM, no false-positive on sparse data).
