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
