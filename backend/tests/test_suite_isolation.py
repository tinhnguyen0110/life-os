"""tests/test_suite_isolation.py — SUITE-REFACTOR (#73): prove per-test DB isolation is REAL.

#73 sped up the suite by SKIPPING the MCP build in create_app (LIFEOS_SKIP_MCP_MOUNTS) — each test
still builds a FRESH isolated app (isolated_paths reset db.DB_PATH + clears process-global caches),
so per-test DB isolation is UNCHANGED. This file is the distinguishing PROOF the dispatch requires:
a row written in one test must NOT be visible in another (no cross-test leak), AND it must hold under
REORDER (a leak often only shows reordered). The two tests are symmetric — each writes a UNIQUE
marker + asserts NO foreign marker is present — so they prove isolation in EITHER run order.
"""

from __future__ import annotations

import pytest

from modules.exchange import schema as ex_schema
from modules.exchange import service as ex_service
from modules.reminders import schema as rem_schema
from modules.reminders import service as rem
from modules.reminders import store as rem_store


def _marker_titles() -> set[str]:
    """All reminder titles currently in the store (the cross-test leak probe)."""
    view, _ = rem.list_reminders("all")
    return {r.title for r in view.reminders}


@pytest.fixture
def db(isolated_paths):
    rem_store.init_reminders_tables()
    return isolated_paths


def test_isolation_alpha_writes_its_own_marker_only(db):
    """Write the ALPHA marker; assert the BETA marker (written by the sibling test) is ABSENT —
    i.e. this test's store is fresh, no row leaked in from test B (in either run order)."""
    titles = _marker_titles()
    assert "ISO-MARKER-BETA" not in titles, f"LEAK: beta's row bled into alpha's store — {titles}"
    rem.create(rem_schema.ReminderInput(title="ISO-MARKER-ALPHA", due_at=rem_schema.now_iso()))
    assert _marker_titles() == {"ISO-MARKER-ALPHA"}  # only my own row, fresh store


def test_isolation_beta_writes_its_own_marker_only(db):
    """Symmetric to alpha: write BETA, assert ALPHA absent. Together the pair proves no cross-test
    leak regardless of which runs first (the reorder-safe isolation distinguishing)."""
    titles = _marker_titles()
    assert "ISO-MARKER-ALPHA" not in titles, f"LEAK: alpha's row bled into beta's store — {titles}"
    rem.create(rem_schema.ReminderInput(title="ISO-MARKER-BETA", due_at=rem_schema.now_iso()))
    assert _marker_titles() == {"ISO-MARKER-BETA"}  # only my own row, fresh store


def test_isolation_fresh_store_starts_empty(db):
    """A third test seeing NEITHER marker — the fresh-per-test store invariant (no accumulation)."""
    assert _marker_titles() == set(), "store must start empty each test (per-test DB isolation)"


# --------------------------------------------------------------------------- #
# #79 — exchange `_last_snapshot` process-global leak (the crypto_basis reorder bug).      #
# exchange_service.get_overview() returns the module-global _last_snapshot verbatim when   #
# set, so a prior OKX-configured test's per-coin holdings (carrying avgCost) leaked into   #
# finance._okx_crypto_holdings() and flipped a value-only channel's basisUnknown True→False#
# under reorder. The pair below is the DISTINGUISHING proof: the leaker SETS the global     #
# directly (as a real prod sync() leaves it — NOT via monkeypatch, so ONLY the conftest     #
# isolated_paths reset can clean it); the victim asserts it sees a CLEAN (None→re-synced,    #
# unconfigured-empty) snapshot. Without the conftest `_last_snapshot=None` reset the victim  #
# reads the leaker's balances → FAIL (RED-proves the fix). Order-independent: the seeded      #
# global persists across tests, so whichever runs first, the other must still be clean.        #
# --------------------------------------------------------------------------- #
_LEAK_SNAPSHOT = ex_schema.ExchangeOverview(  # type: ignore[call-arg]
    totalUsdValue=12345.0,
    balances=[
        ex_schema.OkxBalance(
            symbol="BTC", available=1.0, frozen=0.0, total=1.0,
            usdValue=12345.0, accAvgPx=9000.0,  # HAS a basis → would flip basisUnknown
        )
    ],
    configured=True,
)


def test_isolation_exchange_snapshot_leaker_seeds_global(db):
    """LEAKER: stamp a stale OKX snapshot onto the process-global `_last_snapshot` the way a
    real OKX-configured test's sync() would leave it (direct set, no monkeypatch). The sibling
    victim test must NOT see these balances — the conftest reset is the only thing that clears it."""
    ex_service._last_snapshot = _LEAK_SNAPSHOT
    snap, _ = ex_service.get_overview()
    assert snap.balances and snap.balances[0].symbol == "BTC"  # leaker DID seed the global


def test_isolation_exchange_snapshot_does_not_leak(db):
    """VICTIM: relies on isolated_paths (conftest) resetting `_last_snapshot=None`. Assert the OKX
    overview is CLEAN — no leaked balances from the leaker's seeded global. RED without the fix."""
    snap, _ = ex_service.get_overview()
    assert not any(b.symbol == "BTC" and b.accAvgPx for b in snap.balances), (
        f"LEAK: a prior test's _last_snapshot bled in — basisUnknown would flip wrongly. "
        f"balances={snap.balances}"
    )
    assert snap.totalUsdValue != 12345.0, "LEAK: stale total leaked from the seeded global"
