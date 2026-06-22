# end_sprint_116-OKX-MOCK-ISOLATION — fix the test_finance OKX reverse-order isolation leak (Cairn #116)

> Result. `test_overview_with_okx_uses_basis_as_cost` flaked in full/reverse runs (live-OKX handshake timeout). Root: it mocked `_okx_crypto_value` but NOT `_okx_crypto_holdings` (the 2nd OKX call) → fell to live OKX. Fixed: mock `_okx_crypto_holdings` too — with a VALUE-ONLY entry (not None) that reproduces the real shape driving `basisUnknown=True` — plus a fail-loud guard. Commit `<hash>` `fix(sprint-116-okx-mock-isolation)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT determinism + isolated + mypy). Cairn #116 — be-only test-only fix, CLOSES on this commit. The pre-existing reverse-order leak logged during the #109 stretch.

## The bug + fix (the subtle catch)
- **Root:** the test mocked `service._okx_crypto_value` (channel value) but `get_overview` ALSO calls `service._okx_crypto_holdings` (per-coin balances, L752) → that hit the LIVE OKX network → handshake-timeout flake (intermittent, worst in full/reverse/parallel runs where it ran after an OKX-touching predecessor).
- **🔴 The subtle part:** mocking `_okx_crypto_holdings → None` FAILED the assertion — None routes to manual-fallback → `basisUnknown=False`, but the test asserts `True`. The test DEPENDED on the live OKX holdings RETURN (a value-only entry, avgCost=None) to drive `basisUnknown=True` via `_basis_unknown`'s value-weighted-majority. So the correct mock is a VALUE-ONLY entry (qty + value, avgCost=None) that REPRODUCES that shape deterministically — NOT a None stub.
- **Guard:** `monkeypatch.setattr(service.exchange_service, "get_overview", raise)` → if any path slips back to live OKX, it fails LOUD (AssertionError) instead of flaking.

## What shipped
| File | Change |
|---|---|
| `tests/test_finance.py` (+23, test-only) | `_fake_okx_holdings` returns one value-only Holding (channel=crypto, qty=0.2, avgCost=None, value=tracks the mocked channel value across both get_overview calls); `monkeypatch.setattr(service, "_okx_crypto_holdings", ...)`; the fail-loud `_no_live_okx` guard on `exchange_service.get_overview`. |

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** the value-only mock (avgCost=None drives basisUnknown=True via value-weighted-majority — the behavior the None-stub would have silently broken); the guard set on the real OKX boundary; test-only (the staged diff is ONLY test_finance.py +23, NO product code — verified). ✅
- **🔴 determinism (the flake was INTERMITTENT — single pass ≠ proof):** ran the previously-flaky test **5×** → 5/5 passed (was intermittently timing out on live OKX); isolated PASS; full test_finance **71 passed**. The mocks + guard make live-OKX structurally unreachable → deterministic any order. ✅
- **mypy --no-incremental** finance clean. backend: FORWARD 2358/0 == REVERSE 2358/0 (reverse = the worst case where the flake hit → GONE both directions). ✅

## 3 Gates
- **Gate 2 (Function):** the value-only mock reproduces basisUnknown=True (not a None-stub that silently flips it) + the fail-loud guard + 5× determinism + isolated + 71 + fwd==reverse 2358/0. NOT self-confirming (the guard would fail loud on a regression). ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent determinism; staged EXACTLY test_finance.py (test-only, NO product/FE/data leak); commit format. ✅

## Assumptions (user-review)
- **the test mocks BOTH OKX calls** (value + holdings) with a value-only holdings entry reproducing the real basisUnknown=True shape + a fail-loud guard. **How to change:** n/a — pure test-isolation, no product behavior change.

## Notes
- Cairn #116 — be-only TEST-ONLY fix (the pre-existing reverse-order OKX isolation leak I diagnosed during the #109 stretch + logged non-blocking). backend-w3 built; architect committed (§3 sole-committer). 🔴 **The reusable lesson (the [[reverse-order-only-failure-is-isolation-leak]] companion — backend logged it):** a test that PASSES isolated but FLAKES in full/reverse may DEPEND on a live call's RETURN VALUE — so the fix is to mock a REPRODUCING value, NOT stub None (a None stub silently changes the pinned behavior the test asserts, here basisUnknown True→False). Always check what the live call RETURNS that the assertion depends on before mocking it away. + a fail-loud guard (raise if the live boundary is reached) turns a future silent re-flake into a loud failure. This was the LAST known BE lane → BE backlog clear (only #95 parked). No product change, no restart.
