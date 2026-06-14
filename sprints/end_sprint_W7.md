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

### A2-fix (W7-A2-fix, reactive) — partial-resolve PUT (the gap team-lead's gate caught pre-push)
The first cut bound `DecisionInput` (required decision+confidence+domain) on PUT → the NATURAL resolve `PUT {status, outcome}` 422'd; only a full-resend worked. Every unit test called `compute_stats` on hand-built objects, so the HTTP resolve→stats path was never exercised (built-but-not-wired). **Fix:** new all-optional `DecisionUpdate` schema; `update_entry` merges field-by-field (None=keep). + 2 end-to-end tests (POST→natural-PUT-resolve→GET→brier). Re-verified by architect with the CONSUMER's natural call (memory `review-live-roundtrip-consumer-call-shape`): `PUT {status:"resolved", outcome:"right"}` → **200** (was 422), core fields kept, e2e brier correct. pytest 985→987.

## Assumptions (user-review) — A2
1. **A2 = NEW `modules/decision_journal/`**, separate from the trade `modules/journal/` (cohesion + different stats surface). Reuses journal's calibration-band/thesis-axis math. — to change: merge the two modules (would force trade fields onto general decisions — don't).
2. **Brier prob source**: `predicted` (explicit 0-1) when given, else `confidence/100`. `predicted` + `confidence` are distinct fields (sureness vs P(thesis true)); Brier degrades to confidence when predicted absent. — to change: make predicted required, or drop it and always use confidence.
3. **Bias thresholds**: min-n=4, wrong-rate>0.60 (strict). Defaults, env-tunable later. — to change: tune per real data volume (raise min-n as the corpus grows).
4. **Stats over the FILTERED set**: GET with `?domain=` computes Brier/bands/bias over just that domain (matches journal behavior; arguably useful for per-domain calibration). — to change: always compute over the full set + filter only `entries`.

## A1c — FE wiki finish · ✅ SHIPPED + verified live (Rule#0 — architect; incl. the conflict round-trip FE couldn't seed)

**Commit:** `feat(sprint-W7): A1c FE wiki finish — citation-verify + conflict UI + graph/backlink polish` (hash at commit).

### What shipped — the wiki backend made user-visible
The wiki backend (M1+M4+A1a+A1b) had no FE surface for A1a/A1b. A1c adds them, on the REAL loaded corpus (mining track: ~10 notes + 1 MOC). Per SPEC L257 there is NO in-app chat — so the citation work is a verify DISPLAY surface, not a chatbox.

### Files
- NEW `app/wiki/sync/page.tsx` (+ `__tests__/sync.test.tsx`, 7) — ONE consolidated `/wiki/sync` screen with two integrity surfaces: ConflictsSection + CitationSection.
- MOD `lib/types.ts` (WikiCitation*/WikiConflict* mirroring the live shapes), `lib/api.ts` (verifyWikiCitations/getWikiConflicts/resolveWikiConflict), `lib/useWiki.ts` (useWikiConflicts), `app/wiki/graph/page.tsx` (+status filter + orphan-highlight, +2 tests), `lib/nav.ts` (Tri thức + Sync), Sidebar/nav tests.

### The 4 parts
1. **Citation-verify surface** (A1b, NOT a chatbox — SPEC L257): paste cites (JSON or `claim | noteId | span`) → `POST /wiki/citations/verify` → per-claim verified/weak/rejected/ungrounded + summary → click a verified/weak cite → jump to `/wiki/[resolvedNoteId ?? noteId]` (D6-aware); rejected/ungrounded NOT clickable.
2. **Conflict-resolution UI** (A1a, deferred here): `GET /wiki/sync/conflicts` → cards showing EVERY version (device/content/ts, 0-data-loss) → pick winner → `POST .../{id}/resolve {noteId, content}` (through the single-writer) → refetch. Fail-closed.
3. **Ego-graph polish** (W4): status filter (dims non-matching, center always shown) + orphan-highlight toggle.
4. **Backlink panel** (W2): verified the existing BacklinksPanel already renders outbound + linked + unlinked mentions — complete.

### Verified LIVE (architect, Rule#0 — incl. closing FE's flagged gap)
- **tsc clean · vitest 519/519 (+9)**, 0 unhandled, console clean.
- **The conflict round-trip FE couldn't seed via REST — I seeded it via the backend merge layer + verified end-to-end:** `merge_and_record` two divergent same-block edits → `GET /wiki/sync/conflicts` returns it (both versions) → **Chrome live**: `/wiki/sync` renders the conflict card (note #1 block 2, deskA vs phoneB, both versions + pick buttons) → `POST /wiki/sync/conflicts/{id}/resolve` → **HTTP 200 {resolved}** → conflict closed (0 open). The resolve path is live-proven, not just unit-proven.
- **Chrome live**: both sections render on the real corpus, citation surface framed "answered via MCP" (no chatbox), nav "Tri thức" = Home·Inbox·Graph·Proposals·MOC·Sync. Console clean.
- Test conflicts cleaned up; runtime `backend/data` is gitignored (never committed).

## Assumptions (user-review) — A1c
5. **One consolidated `/wiki/sync` screen** (conflicts + citations) rather than two screens — both are integrity/sync surfaces, keeps nav lean. — to change: split into `/wiki/citations` + `/wiki/conflicts` (trivial).
6. **Citation-verify input is paste-based** (JSON or `claim|noteId|span` lines) — the agent's cites are pasted/inspected, since there's no in-app chat to capture them automatically (SPEC L257). — to change: only if an MCP round-trip ever auto-feeds cites (not this build).
7. **Graph polish kept the existing custom SVG, sigma.js deferred** — the dispatch *suggested* sigma.js, but the existing deterministic radial ego-graph already does node-size=degree / color=status / typed-edges / depth and meets the 200-note <1s gate with NO heavy dep. Adding sigma.js for the same result violates single-dev-no-overengineering (cut technical complexity, not value). Frontend correctly surfaced the deviation (not a silent swap) and I accepted it. — to change: add sigma.js only if the vault graph exceeds ~5k nodes (Phase-2 territory anyway, per the wiki spec's global-graph deferral).
