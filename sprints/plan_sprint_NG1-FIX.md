# Sprint NG1-FIX — claude_usage.pct overflow at the SOURCE (the M6 that survived 3 rounds) + NG4

> Consumer-agent round-3 (memory `consumer-agent-round3-gaps-2026-06-15`, Rule#0-verified).
> Reactive — dispatched AFTER OKX-FINANCE lands (no file overlap: NG1=claude_usage/read_server, OKX=finance).

## Kickoff — 2026-06-15 (architect)

### The bug — and why it survived M6 (dissolved) → G6 (scoped too narrow) → now (round-3 caught it)
- **SOURCE:** `claude_usage/service.py:293` `pct = round(used/cap*100, 1)` where `used` = today's TOKEN count (~8.9M) and `cap` = 200000 (a context-window allowance, NOT a token-quota) → **~4500% garbage.** This is the orphan field I dissolved at M6.
- **The `ClaudeUsage` object carries this broken `pct`** → so EVERY consumer that reads `.pct` leaks it.
- **G6 fixed only ONE consumer** (`daily_brief._quota_pct` → uses pct5h). It did NOT fix the SOURCE, so:
  - **Leak 1 (HIGH):** the raw `claude_usage` tool → `pct=4499` (verified live).
  - **Leak 2 (HIGH):** `_brief_claude()` (read_server.py:622) dumps `"pct": u.pct` → `life_brief.brief.claude.pct=4501` (verified live). **This is in the SYNTH code I just shipped** — I dumped the whole object including the broken field.
- **costUSD note (correction to team-lead's flag):** costUSD is computed via `pricing.compute_cost` (real per-token pricing), NOT off the cap — the ~$50k is the REAL cost of 8.9M tokens, legit, not a bug. The bug is PURELY the `pct` field.

### MY repeated miss (owning it — the lesson)
I dissolved this at M6 ("no consumer reads raw pct" — wrong, missed brief), then at G6 I fixed the SYMPTOM at `daily_brief._quota_pct` instead of the SOURCE, leaving the raw tool + `_brief_claude` (which I then SHIPPED reading `.pct` in SYNTH). **A "fixed pct" must be fixed at the SOURCE and verified at EVERY consumer, not one.** Logged to memory `dissolved-finding-recheck-all-consumers` (this is the 3rd instance — strengthen it: fix-at-source > patch-one-consumer).

### The fix — at the SOURCE (so all consumers are correct)
- `service.py:293`: the headline `pct` must NOT be `used/cap`. Derive it from the sane snapshot window: **`pct = pct5h if not None else (weekly/pctWeek) if not None else None`** (the same correct field daily_brief now uses), clamped 0-100. NEVER `used/cap`.
- Then the `ClaudeUsage.pct` field is sane → the raw tool AND `_brief_claude`'s `u.pct` dump AND any other consumer are all correct automatically (the source fix propagates).
- (Optionally keep `used`/`cap`/`remaining` as-is — those are real token counts, just don't compute the headline % off them. If `remaining = cap - used` is also nonsensical for the same reason, set it null/omit; check what consumes `remaining`.)

### NG4 (LOW, bundle in) — check_proposal_status raw ValueError
- `check_proposal_status('nope123')` raises a raw ValueError (leaked traceback) → coerce/validate the id → return `{found: false}` (honest not-found, not a 500). Small.

### Final task list (single backend lane, AFTER OKX-FINANCE)
- **NG1 [backend]** — fix `claude_usage.pct` at the SOURCE (pct5h→weekly→None, ≤100/null, never used/cap). Verify ALL THREE surfaces: raw claude_usage.pct ≤100/null, life_brief.brief.claude.pct ≤100/null, daily_brief still sane. Distinguishing case: assert life_brief.claude.pct is NOT 4500.
- **NG4 [backend]** — check_proposal_status bad-id → {found:false}, no raw ValueError.

### Deferred (logged, round-4 / write-loop pivot): NG2 (propose_wiki_note undiscoverable), NG5 (stale /tinhdev/ repo paths → stderr noise = round-1 G9), + the agent's PIVOT: exercise the WRITE/propose loop e2e (propose→accept→row lands) + data-feeds (macro-FRED). The read surface is now solid — next high-value is the write loop, not more read-gap rounds.

## Assumptions (user-review)
- claude_usage headline `pct` derives from pct5h/weekly (the sane quota window), clamped ≤100, null when no snapshot — NEVER used/cap (which is tokens÷context-window = garbage). Fixed at the SOURCE so all consumers (raw tool, life_brief, daily_brief) are correct.
- NG4: check_proposal_status(bad-id) → {found:false}, not a raw 500.
