# end_sprint_DXY-HONEST — revert the DTWEXBGS-as-DXY mislabel + back out q_macro inflation + surface the honest warning (Cairn #15 corrective)

> Result. CORRECTIVE for the honest-mirror INCIDENT in 5b380d4 (#15). Commit: `<hash>`. Status: ✅ all 3 gates pass (after the T1b warning-gap was caught + fixed).

## The incident (closed by this commit)
#15's never-persist-mock fix (5b380d4) un-shadowed a pre-existing config mislabel `dxy→DTWEXBGS` (core/config.py:177), so `/macro/overview` dxy flipped to source='fred', val 119.5073, label "DXY" — presenting FRED's **DTWEXBGS (broad TRADE-WEIGHTED dollar)** AS the **ICE DXY index** (a DIFFERENT instrument). VIOLATED honest-mirror + reversed plan_sprint_FRED-MACRO.md:20 ("honest-mock > near-miss proxy") + the user's ruling (real DXY needs a dedicated API, not built → PARK it). AND because q_macro = mean of ALL indicators' confidence, dxy's fake 0.77 INFLATED q_macro 0.5108→0.6211 (the "synergy" #15 over-credited).

## What shipped (T1 + T1b in one commit)
| File | Change |
|---|---|
| `core/config.py` | Removed the `dxy→DTWEXBGS` fred_series mapping (+ a comment why: DTWEXBGS ≠ ICE DXY; parked). |
| `modules/macro/service.py` | `_FEEDLESS_INDICATORS=("dxy",)` (tracked + displayed but no live feed); `tracked_indicators()` includes them; `_indicator_view` sets a per-view `warning` for feedless (honest reason, real → None); `get_history` accepts feedless (no spurious 404/refresh). |
| `modules/macro/reader.py` | `fetch_latest` for a KNOWN-but-feedless indicator (in `_MOCK_BASE`) → honest mock + "no live {indicator} feed (needs a dedicated API, not built) — mock"; truly-unknown stays the empty path. |
| `modules/macro/schema.py` | `MacroIndicatorView` + `warning: str|None=None` (additive/nullable). |
| `modules/decision/service.py` | q_macro `macro_qs = [v.confidence for v in indicators if v.source != "mock"]` — EXCLUDE mock (S1: mock = absence, never counts). All-mock → 0.0 guard intact. macro_note shows "N/total REAL (mock excluded)". |
| `tests/test_macro.py` + `tests/test_decision.py` | dxy=mock+warning teeth-test (asserts warning present + cpi.warning=None feedless-specific), q_macro 0.596-vs-0.511 distinguishing, all-mock-no-divzero. |

## The gate gap caught mid-corrective (the 4-step review working)
T1 shipped dxy=mock + q_macro=0.5955 — BUT the honest "no live feed" warning was DROPPED (reader produced it; get_overview reads the store, never fetch_latest; MacroIndicatorView had no warning field → live dxy.warning=None). AND the warning-test under-asserted (named for the warning, only checked source — false-green class). **BLOCKED commit.** T1b fixed both: warning field + _indicator_view sets it for feedless + the test gained teeth (asserts warning + cpi=None distinguishing).

## Verification (Rule #0 — 3-way, both the headline + the warning)
- **architect Rule#0 (direct):** cpi → source='fred', warning=None; dxy → source='mock', warning="no live US Dollar Index (DXY) feed (dedicated API not built) — mock". q_macro 0.5955 ("6/7 REAL, mock excluded"). 99 macro+decision pass, 0 failed.
- **team-lead live (both T1 + T1b):** dxy=mock + the agent-readable warning on the indicator object; cpi warning=None (feedless-specific); q_macro 0.5954; 6 real fred; purged 12 stale mislabeled dxy rows (84 other untouched); get_history feed-less fix (recheck-all-consumers catch). 1688 pytest.
- **tester:** the 0.596 gate + dxy=mock+warning + cpi=None + hardening intact (see tester report).
- **distinguishing:** q_macro 0.596 (exclude) ≠ 0.511 (count-mock-as-0) ≠ 0.62 (inflated mislabel); dxy.warning present ≠ cpi.warning None.

## 3 Gates — ALL PASS
- **Gate 1 (API):** /macro/overview shape additive (MacroIndicatorView +warning); dxy source='mock' + honest warning surfaced; integration green. ✅
- **Gate 2 (Function):** q_macro mock-exclude with the 0.596≠0.511 distinguishing; the warning teeth-test (asserts warning + cpi-None); all-mock guard; #15 hardening tests green; no self-confirming/under-asserting test. ✅
- **Gate 3 (Sprint):** end-doc + corrected #15 end-doc; full-function spot-check (incl. the T1b warning-drop trace); team-lead live + architect Rule#0; counts ↑; commit format. ✅

## Assumptions (user-review)
- **dxy honest source='mock' (NEVER 'fred') + an agent-visible warning** — DTWEXBGS (broad trade-weighted dollar) ≠ ICE DXY; real DXY PARKED until the user builds a dedicated API. **How to change:** wire a real DXY feed as 'dxy', or add DTWEXBGS as its OWN clearly-named indicator (not 'dxy').
- **q_macro EXCLUDES mock indicators from its mean** (S1-consistent: mock = absence, neither inflates nor drags) → honest 0.596 (the real indicators only). **How to change:** the predicate `v.source != 'mock'` in decision/service.py.
- **`_FEEDLESS_INDICATORS`** = indicators tracked+displayed-as-honest-mock with no live feed (currently `("dxy",)`). **How to change:** add/remove from the tuple; each surfaces a per-view warning + is excluded from q_macro.

## The arc (the immune system, on the record)
mislabel (DTWEXBGS-as-DXY) → q_macro inflation → dropped-warning → toothless-test — EACH caught by a gate / Rule#0 / the 4-step review BEFORE final land. The never-persist-mock hardening (#15, 5b380d4) was the genuine win + is kept; this corrective reverted the mislabel, backed out the fake lift, and made the honest state agent-visible.
