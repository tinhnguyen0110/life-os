# end_sprint_79-SUITE-ISOLATION — fix the exchange _last_snapshot reorder-leak (Cairn #79)

> Result. The pre-existing reorder-isolation bug (the #73 reorder-gate finding) is fixed — root cause was NOT crypto_basis.md (the bug-name's hypothesis) but the exchange `_last_snapshot` process-global cache leaking per-coin basis across tests. Test-only conftest reset → FULL suite green in BOTH orders (forward + reverse). Commit `<hash>` `fix(sprint-79-suite-isolation)`. Status: ✅ all gates pass. backend-w3 BUILT (diagnosed-first, test-only); architect 4-step + committed (§3). Unblocks #78 (session-scope <60s).

## ROOT CAUSE (diagnosed-first — NOT the bug-name's crypto_basis.md hypothesis)
backend binary-searched the leaker→victim pair: the leak is `modules/exchange/service.py::_last_snapshot` (module-level process-global). `exchange.get_overview()` returns it VERBATIM when set. Chain:
- A prior OKX-configured test's `sync()` leaves `_last_snapshot` populated with per-coin balances carrying `accAvgPx` (a cost basis).
- `test_overview_with_okx_uses_basis_as_cost` monkeypatches only `_okx_crypto_value` (the TOTAL) — NOT `_okx_crypto_holdings()` → the unpatched fn calls the REAL exchange get_overview() → stale per-coin holdings WITH basis → `_basis_unknown()` returns False → `basisUnknown` flips True→False, `pnl.abs` 0.0 instead of None → AssertionError.
- In-order: `_last_snapshot` empty → basisUnknown=True (correct). The leaker file = test_mcp_read.py. (So the dispatch's crypto_basis.md hypothesis was a red herring — the real leak was the exchange cache; diagnose-first caught it.)

## FIX (test-only — NO prod change; the feature is correct, the test isolation leaked)
`tests/conftest.py::isolated_paths`: `monkeypatch.setattr(_ex_service, "_last_snapshot", None)` — alongside the existing `_FEED_CACHE.clear()` / `_STATUS_CACHE.clear()` / `DB_PATH=None` resets (the established per-test global-reset pattern). Auto-undone (clean at setup AND teardown). So each test re-syncs from its own isolated/unconfigured state — no cross-test basis leak.

## What shipped (2 files — both test-only)
| File | Change |
|---|---|
| `tests/conftest.py` | + the `_last_snapshot` reset in isolated_paths (with the leak-chain comment). |
| `tests/test_suite_isolation.py` | +2 distinguishing tests (the RED-proven pair). |
| `modules/finance/service.py` + `modules/exchange/service.py` | CLEAN (no prod diff — `git status --porcelain` confirms). |

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full):** the _last_snapshot reset (correct global, the established pattern, comment explains the chain) ✅; the isolation test (leaker SETS the global directly — not monkeypatch, so only the conftest reset cleans it — + victim asserts clean) ✅; test-only (2 files, modules clean) ✅; **my own minimal-repro-pair run** (test_mcp_read + test_overview_with_okx + test_suite_isolation) → 104 passed (was 1-failed before the fix — confirms the fix) ✅.
- **backend-w3 evidence:** RED-proven (disable the conftest reset → victim FAILS 1/4; restore → 5 passed). FULL suite BOTH orders: FORWARD 2073/6/0; **REVERSE (`ls tests/test_*.py | tac`) — the #79 gate — 2073/6/0 ✅ (the reorder leak GONE)**. crypto_basis FEATURE tests 119 passed (feature unaffected). The minimal repro pair (was 1-failed) → 99 passed.

## 3 Gates — ALL PASS
- **Gate 2 (Function):** INCLUSIVE 2073/0 in BOTH orders (the reversed-green is the proof — the leak fixed under reorder); the RED-proven isolation test; the feature unaffected (119 green); no over-reset. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + backend both-order-green + my minimal-repro-pair verify; test-only (no prod, no live-container needed); 2-file surgical stage (no #81/FE leak); commit format. ✅

## Assumptions (user-review)
- The exchange `_last_snapshot` process-global is reset per-test in isolated_paths (the established pattern, alongside _FEED_CACHE/_STATUS_CACHE/DB_PATH). Test-only — the exchange/finance/basis FEATURE is unchanged + correct. **How to change:** the isolated_paths reset list.

## Notes
- Cairn #79. The pre-existing reorder-isolation bug (surfaced by #73's reorder-gate, proven pre-existing). DIAGNOSE-FIRST found the real root (the exchange _last_snapshot cache, NOT crypto_basis.md the bug-name implied) — the diagnose-before-fix discipline. backend BUILT (test-only); architect committed (§3). Committed from an intermixed tree (#81 FE committed just before) — 2-file BE surgical stage. **Unblocks #78** (session-scope <60s — which needs real per-test isolation; this reorder-clean is the prerequisite). Next: #78 → #64-P3 → dogfood/user-direction.
