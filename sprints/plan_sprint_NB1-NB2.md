# Sprint NB1+NB2 — brief_history read-time sanitize (clamp overflow claudePct + guard netWorth outliers)

> Blank-context dogfood (memory `blank-context-dogfood-2026-06-15`), team-lead Rule#0-verified.
> Backend-only. READ-TIME clamp/guard — NO data mutation (the brief store is gitignored; rows may be historical snapshots; purge = user decision).

## Kickoff — 2026-06-15 (architect)

### The data ON DISK (kickoff — I read every row; corrects the memory's stale dates)
`data/brief/<date>.md`, 9 rows. claudePct + netWorth:
```
2026-06-06: claudePct 18.9   netWorth 63204     ← netWorth OUTLIER
2026-06-07: claudePct 18.9   netWorth 63236     ← netWorth OUTLIER
2026-06-08: claudePct 18.9   netWorth 65695     ← netWorth OUTLIER
2026-06-09: claudePct 18.9   netWorth 10633
2026-06-10: claudePct 466.1  netWorth 10626     ← claudePct OVERFLOW
2026-06-11: claudePct 95.8   netWorth 10622
2026-06-12: claudePct 367.7  netWorth 10622     ← claudePct OVERFLOW
2026-06-13: claudePct 370.2  netWorth 10639     ← claudePct OVERFLOW
2026-06-15: claudePct 95.0   netWorth 10644
```
- **claudePct overflow rows: 06-10 (466.1), 06-12 (367.7), 06-13 (370.2)** — pre-NG1 `used/cap` garbage. (The memory said 06-07; the real overflow rows are 10/12/13.)
- **netWorth outlier rows: 06-06/07/08 (~63-65k)** vs the real ~10.6k baseline (06-09 onward). ~6× — almost certainly BTC-price-in-USD (BTC ≈ $63k) mislabeled as netWorth in those early rows. (The memory said 2026-04-17; no such file exists — that store snapshot is superseded. The real outliers are 06-06/07/08.)

### Read path (where the sanitize goes)
`modules/brief/service.py:285` `get_history(limit=30)` — loads `brief/<date>.md` newest-first, `briefs.append(Brief(**data))` (L316). Called by `brief/router.py:35` (`GET /brief/history`) AND `read_server.py:91` (`brief_history` MCP tool). **The sanitize applies right after `Brief(**data)`** so BOTH consumers get clean rows. `BriefSummary.claudePct` and `.netWorth` are already `float | None` → nulling is schema-legal.

### 🔑 DECISIONS (architect calls — decide-and-log)

**NB1 — claudePct clamp: `claudePct > 100 → None`** (not 100).
- Rationale: a quota % CANNOT exceed 100; an overflow row is corrupt, not "maxed out." None = honest "this historical row's quota is unknown/stale" — better than a fake 100 that reads as a real "you were at 100%". (Same honest-null-over-fabricated principle as the live NG1 fix.) The clean rows (18.9 / 95.8 / 95.0) are ≤100 → untouched.
- Edge: `claudePct is None` → stays None (no-op). `0 ≤ claudePct ≤ 100` → untouched.

**NB2 — netWorth outlier guard: `netWorth > 3× median(all loaded netWorths) → None`** (robust-median rule).
- Rationale: median (not mean) is robust — the 3 outliers don't pull it (median sits at 10638 in the good cluster; outliers are ~6× = far past 3×). A mean would be corrupted BY the outliers. 3× is a conservative threshold (real rows are 1.0×; outliers 5.9-6.2× — huge separation, no borderline).
- **Compute the median over the netWorth values that are present (not None) in the loaded window**, then null any row > 3× that median. Single pass: collect non-None netWorths → median → second pass nulls outliers.
- **Honest limitation (logged):** this is a HISTORICAL-data cleanup heuristic, not a live write-guard. It can't distinguish "net worth genuinely 3×'d and STAYED" from "spiked then reverted" — but the corruption signature here IS spike-then-revert (65k→10.6k), and real personal net worth doesn't 6× in a day then drop back. If the user's net worth ever legitimately grows past 3× the trailing median, this would wrongly null it → revisit the rule then (user-review §Assumptions). Guard rows ≥4 needed for a meaningful median; with <4 loaded rows, SKIP the netWorth guard (too few to establish a baseline — don't null on a 1-2 row sample).
- Edge: `netWorth is None` → excluded from the median calc + stays None. All-None or <4 present → no guard (return as-is).

**Both:** a small pure helper `_sanitize_brief_history(briefs: list[Brief]) -> list[Brief]` (claudePct per-row clamp + netWorth median-guard over the list), applied to the `briefs` list before `get_history` returns. Pure, testable, no I/O.

### Read-only invariant (HARD)
- `get_history` must NOT write/mutate the `.md` files (it already only reads). **Assert the `.md` files are byte-unchanged after a `brief_history` call** (mtime + content) — the sanitize is in-memory on the loaded Brief objects only. NO purge, NO rewrite.

### Final task list (single backend lane)
- **NB1+NB2 [backend]** — add `_sanitize_brief_history(briefs)` in `brief/service.py`; clamp `claudePct > 100 → None`; null `netWorth > 3× median` (≥4 present rows, else skip); apply in `get_history` before return. Tests: overflow row → None, clean row untouched (distinguishing case: 95.0 stays 95.0, 466.1 → None); outlier netWorth → None, baseline untouched (63204 → None, 10644 stays); <4 rows → no netWorth guard; None-safe; **disk-unchanged assertion** (read-only). Full suite green.

## Assumptions (user-review)
- **NB1 claudePct:** historical brief rows with `claudePct > 100` (pre-NG1 `used/cap` overflow: 466/367/370%) are clamped to None at READ time (honest "stale/unknown", not a fake 100). Clean rows (≤100) untouched. No disk mutation.
- **NB2 netWorth:** historical rows with `netWorth > 3× median` of the loaded series are nulled at READ time (the 06-06/07/08 ~63-65k rows = BTC-price mislabeled, ~6× the real ~10.6k). Robust-median rule, ≥4 rows required (else skip). HEURISTIC limitation: can't tell legitimate 3×-growth-that-stays from spike-then-revert — revisit if the user's net worth ever legitimately exceeds 3× its trailing median. No disk mutation (clamp on read; purge would be a user decision).
- Both applied in a pure `_sanitize_brief_history` helper in `get_history`; both `brief_history` (MCP) and `GET /brief/history` get clean rows.
