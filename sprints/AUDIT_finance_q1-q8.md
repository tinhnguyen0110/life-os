# Finance-assistant audit — 8 dogfood questions, live-grounded answers

> Architect audit-answer pass (2026-06-16). Each Q: LIVE evidence + verdict (REAL-BUG / DESIGN-CHOICE / NEEDS-DECISION) + (if bug) a 1-line fix sketch. **No build yet** — team-lead prioritizes the bugs into fix-sprints.

---

## Q1 + Q3 — freshness rewards MOCK, punishes REAL data → **REAL BUG** (root pinned, reproduced live)
**Evidence (live `confidence_q`):** REAL CPI (FRED, obs date 46d ago, source=fred) → confidence **0.2148**; MOCK DXY (stamped "today", source=mock) → **0.9952**. **Mock is rewarded 4.6× over real data.**
**Root:** the mock generator (`macro/reader.py:_mock_points` L70) stamps its latest point at `_today()` ≈ now → freshness `exp(-0/τ) ≈ 1.0`. Real FRED data carries the TRUE observation date — and a monthly indicator (CPI/M2) is *inherently* ~30-46d old at publication. The freshness formula `exp(-age/τ)` measures **ABSOLUTE age**, so it punishes a naturally-lagged real indicator exactly like stale data, while a mock that lies about being current scores ~1.0. The user's framing is correct.
**The two-tool inconsistency the user caught (real):** `macro_overview` COUNTS a mock indicator (confidence ~0.99) while `macro_cycle` marks the same mock `present:false` (via `mock_is_present=False`) — opposite handling of the same mock. So the SAME mock is high-confidence in one tool and excluded in another.
**Verdict: REAL BUG — the highest-value fix.** It corrupts the q-engine's whole premise (data quality), and it's load-bearing (every tower layer multiplies q).
**Fix sketch (likely ONE fix, two parts):** (a) **cadence-aware freshness** — measure lag vs the indicator's *publication cadence*, not absolute age (CPI 46d-old = on-time → freshness high, not 0.21); i.e. `age_effective = max(0, age − expected_cadence_lag)`. AND (b) **mock must NOT score high** — either force mock freshness/confidence LOW (a mock is NOT real current data) or exclude it consistently (make `macro_overview` use `mock_is_present=False` like `macro_cycle` — fixing the two-tool inconsistency in the same stroke). Recommend (a)+(b) together: cadence-aware freshness for real, mock forced-low + consistently-excluded.

## Q2 — per-indicator vs group τ → **NEEDS-DECISION (becomes a real gap IF Q1's cadence model is adopted)**
**Evidence:** all macro indicators share `TAU_DAYS["macro"] = 30.0` (a single group τ). M2 (monthly, but FRED publishes with a ~6-week lag) and CPI (monthly, ~2-week lag) have DIFFERENT real cadences.
**Verdict:** today a shared τ is a defensible simplification (all "monthly macro"). BUT if Q1's fix adopts cadence-aware freshness, the cadence is per-indicator → a shared τ can't express it. **Decision: if we fix Q1 with cadence-awareness, τ (or the cadence-lag) must become per-indicator.** Otherwise leave the group τ. So this rides on the Q1 decision — not independent.

## Q4 — nav cron: 17 morning-pulls but 1 snapshot point (the user's #1 worry) → **NOT A BUG (verified live)**
**Evidence (live):** `portfolio_snapshot` had 1 row (06-15). I ran `take_snapshot()` live → **OK, persisted a NEW row (06-16, $10641.66)**, rows 1→2. The writer WORKS. run_log shows 17 morning-pull runs across **9 distinct days (06-06 … 06-15)**, but the snapshot step was **built-but-not-wired until recently** (the D2 comment: "take_snapshot was built but never scheduled" — wired in LATER). So the early runs (06-06…06-14) predate the wiring → no snapshot; only 06-15 (post-wiring) captured; my live run added 06-16.
**Verdict: NOT the feared lost-a-point-every-day bug.** The snapshot upserts by UTC `day` (PK, idempotent) and now runs daily via morning_pull — from the wiring date forward it captures 1 row/day correctly. The 06-06…06-14 "gap" is pre-wiring history (not recoverable, but not an ongoing loss). **The user's ongoing-loss worry is unfounded going forward.** (Minor watch-item: confirm the morning_pull cron is actually ENABLED + firing daily on the live container so a row lands each day — but the writer itself is proven correct.)

## Q5 — the NAV_POINTS_FOR_TREND ≈ 30 constant → **DESIGN-CHOICE (documented, tunable)**
**Evidence:** nav confidence = compute_q coverage = `points / NAV_POINTS_FOR_TREND` (=30). A ~monthly series is treated as "enough" for a trend.
**Verdict: DESIGN-CHOICE, already logged** (§Assumptions, P4). 30 ≈ a month of daily points; a short series → honest-low confidence. Tunable via the one constant. Rationale is sound (a 3-point NAV series can't support a CAGR/drawdown claim). No fix needed; could be revisited once a real long series exists.

## Q6 + Q7 — s_asset=0 (empty watchlist) zeroes the WHOLE tower (W=∏q=0) → **DESIGN-CHOICE (deliberate-for-now, with a real revisit trigger)**
**Evidence (live):** `watchlist_data()` returns **0 items** → `_s_asset` coverage 0 → q=0 → `W = q_cycle × q_macro × q_flow × s_asset = 0`. The code comment explicitly cites "the §484 watchlist-gap is real."
**Verdict: DELIBERATE-FOR-NOW.** P2 explicitly scoped OUT holdings→watchlist auto-sync as over-engineering (north-star) — a thin/empty asset layer → low q → honest low W is the SPEC's intended behavior ("weak data = don't bet blindly"). W=0 with a blind layer is *correct*, not broken. BUT the user's observation is sharp: a permanently-empty watchlist permanently zeroes the tower, so the tower can NEVER light up. **The revisit trigger (honest answer):** auto-sync the user's actual HOLDINGS into the watchlist (or feed s_asset from the held assets' RSI/trend directly) so s_asset reflects real positions — that's the §484 fix. It was deferred, but if the user wants W to ever be non-zero, this is the unblock. **Recommend: a small "s_asset reads held assets' technicals" sprint** (NOT full watchlist auto-sync — just point s_asset at the holdings the user already has, which DO have market data). This is the most impactful non-bug follow-up.

## Q8 — finance_analytics uses STATIC golden-path while allocation_target is DYNAMIC → **DESIGN-CHOICE (both intentional, different purposes)**
**Evidence:** `finance_analytics` drift = actual-vs-`get_golden_path()` (the static `golden_path.md` / BASELINE_TARGETS 38/24/18/20). `allocation_target` = dynamic phase+capital reference weighting.
**Verdict: DESIGN-CHOICE, intentional.** They answer DIFFERENT questions: analytics.drift = "am I off MY chosen plan?" (the user's own golden-path is the reference — stable, user-set); allocation_target = "what would the classic-clock + my capital imply?" (a dynamic what-if reference). Both are valid references for different purposes; conflating them would lose the "vs my own plan" signal. NOT a bug. (If the user WANTS analytics drift measured vs the dynamic allocation_target instead of the static golden-path, that's a NEEDS-DECISION preference — but the current split is coherent.)

---

## Summary for prioritization
| Q | Verdict | Action |
|---|---|---|
| **Q1/Q3 freshness rewards mock** | **REAL BUG** | **Fix-sprint** — cadence-aware freshness + mock-forced-low + the two-tool consistency. Highest value (corrupts the q-engine premise). |
| Q2 per-indicator τ | NEEDS-DECISION | Rides on Q1 — if cadence-aware adopted, make τ/cadence per-indicator. |
| **Q4 nav cron** | **NOT A BUG** | Verified live (writer works, idempotent-by-day, the gap was pre-wiring). Watch-item: confirm the cron is enabled+firing daily on the live container. |
| Q5 ~30 constant | DESIGN-CHOICE | None (documented, tunable). |
| **Q6/Q7 s_asset→W=0** | DESIGN-CHOICE (deliberate) | **Recommend a small sprint:** point s_asset at the user's HELD assets' technicals (the §484 unblock) so the tower can light up. Most impactful non-bug. |
| Q8 static vs dynamic | DESIGN-CHOICE | None (intentional; the split is coherent). |

**The 2 real fix candidates:** Q1 (freshness — REAL BUG, highest value) + Q6/Q7 (s_asset reads held assets — DESIGN-gap with a clear unblock). Q4 is reassuring (not the feared bug). The rest are sound design choices.
