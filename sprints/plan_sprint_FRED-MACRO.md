# Sprint FRED-MACRO — real Fed-funds + CPI via FRED public CSV (no key); DXY stays mock-labeled

> Answer-quality audit D5: "macro all mock → any macro answer untrustworthy." team-lead verified the FRED public CSV needs NO key (I re-confirmed: FEDFUNDS 3.63 / CPIAUCSL 333.979) AND that the CONTAINER has egress (status 200 from inside). So Fed+CPI go REAL now — removes "macro all mock" from the most-asked questions. Backend-only.

## Kickoff — 2026-06-15 (architect)

### Verified on disk — the gap is precise (the reader uses the KEYED API, not the no-key CSV)
- `modules/macro/reader.py` ALREADY has the full fail-open machinery: `fetch_latest(indicator)` → real fetch if `settings.fred_api_key` set, else mock; deterministic mock tagged `source='mock'`; never raises. The source-tagging + overview aggregation (`service.py:128` source='fred' if any live) + store + schema all EXIST.
- **THE GAP:** `_fetch_fred_series` (reader.py) hits the **keyed JSON API** (`api.stlouisfed.org/fred/series/observations` + `api_key`). With `settings.fred_api_key=""` (default, and it IS empty), `fetch_latest` short-circuits to MOCK for ALL indicators (reader.py: `if not settings.fred_api_key: return _mock_points(...)`). So Fed/CPI mock NOT because FRED is unreachable, but because the code only knows the keyed path.
- **The fix is a no-key CSV path.** The public CSV `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>` needs no key (verified, container egress confirmed by team-lead). Config already maps the series: `fed_funds_rate→FEDFUNDS`, `cpi→CPIAUCSL`, `dxy→DTWEXBGS` (`config.py:162`).
- DXY's `DTWEXBGS` returns EMPTY from FRED (verified both of us) → the existing "no usable points → mock" branch handles it honestly (stays source='mock').

### 🔑 THE DECISION (architect call — add a no-key CSV fetch as the PRIMARY path)
- Add `_fetch_fred_csv(series_id) -> list[{date, value}]` — GET `{settings.fred_csv_base}/graph/fredgraph.csv?id=<series_id>` (no key), parse CSV (header `observation_date,<SERIES>` then `YYYY-MM-DD,<value>` rows; skip `.`/empty values like the JSON path does), oldest→newest. Raises on failure (caller fails open).
- Rewire `fetch_latest`: **try the no-key CSV FIRST** (works for Fed/CPI without a key). Keep the keyed JSON API as an optional upgrade ONLY if `fred_api_key` is set AND you want it (simplest: CSV is the primary, drop the key-gate short-circuit to mock). On CSV success → `source='fred'`. On CSV failure/empty → the EXISTING fail-soft (mock + warning). So:
  - Fed/CPI → real `source='fred'` (CSV returns data).
  - DXY (`DTWEXBGS` empty) → existing "no usable points → mock" → `source='mock'` honestly.
  - FRED unreachable → existing except → mock + warning, no 500.
- **`settings.fred_csv_base = "https://fred.stlouisfed.org"`** new config (the CSV host differs from `fred_base` = the API host). Default it; env-overridable.
- **DXY decision (logged):** keep DXY mock-labeled (NOT a renamed trade-weighted proxy). Rationale: `DTWEXBGS` (FRED's trade-weighted broad dollar) returned empty in both our tests, and even if it returned data, presenting it AS "dxy" would mislead (it's a different index than ICE DXY). Honest-mock-labeled > a near-miss proxy the user reads as DXY. (If the user later wants the trade-weighted dollar as its OWN clearly-named indicator, that's a separate add.)

### Network-egress note (the host-file-source-must-mount sibling)
FRED is an outbound HTTPS call → the CONTAINER must reach `fred.stlouisfed.org`. **team-lead VERIFIED this from inside the container (status 200, Fed 3.63)** — no egress blocker. The fail-soft to mock (existing) covers a transient network blip. Verify on the CONTAINER (canonical stack), not just the host.

### Scope boundary
- Do NOT remove the mock machinery (it's the fail-soft floor + DXY's honest source). Do NOT touch the schema/store/overview-aggregation (they already handle source tags). The change is localized to `reader.py` (+ one config line).
- NEUTRAL/honest unchanged: real where real (Fed/CPI source='fred'), mock-labeled where mock (DXY).

### Final task list (single backend lane)
- **FRED-MACRO [backend]** — add `_fetch_fred_csv` (no-key CSV) + rewire `fetch_latest` to use it as the primary path (CSV first → fred; fail-soft → mock). Add `settings.fred_csv_base`. Fed/CPI → real source='fred'; DXY → mock-labeled. Tests: CSV-parse (mock the httpx CSV response → fred points); DXY empty → mock; FRED-down → fail-soft mock no-raise; overview source aggregation reflects fred when Fed/CPI live.

## Verification (distinguishing cases — locked)
- **Real Fed/CPI:** live `macro_overview` → `fed_funds_rate` + `cpi` carry `source='fred'` + real values (~3.63 / ~333.98) + asOf the real FRED date. (Distinguishing: these are NOT the mock baselines 5.33 / 314.0 — a mock-vs-real divergent check.)
- **DXY honest-mock:** `dxy` stays `source='mock'` (DTWEXBGS empty).
- **Overview source:** `source='fred'` (since Fed/CPI are live) — the "macro all mock" blanket caveat no longer fires for the whole overview; only DXY is mock-flagged.
- **Fail-soft:** mock the CSV fetch to RAISE → `fetch_latest` returns mock + warning, NO 500 (existing pattern preserved).
- Container egress confirmed (re-verify on the container at test time). Full suite ≥1504, 0 errors/unhandled. NEUTRAL.

## Assumptions (user-review)
- Fed funds (FEDFUNDS) + CPI (CPIAUCSL) are now REAL via the FRED public CSV (`fredgraph.csv?id=`, no key). source='fred'. Mock is the fail-soft floor only (FRED down → mock-labeled + warning, no 500).
- DXY stays mock-labeled (FRED's DTWEXBGS empty + it's not ICE DXY anyway). To get a real dollar index: add the trade-weighted dollar as its OWN clearly-named indicator (not relabeled "dxy"), or a real DXY feed (proprietary). Deferred.
- New config `fred_csv_base="https://fred.stlouisfed.org"` (CSV host ≠ the keyed API host). The keyed API path may stay as an optional upgrade but is no longer required for real data.
