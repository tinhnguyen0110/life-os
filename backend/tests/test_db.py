"""tests/test_db.py — unit tests for store/db.py (SQLite store).

Sprint 0 Gate 2. API:
  init_db(path: Path | str | None = None) -> sqlite3.Connection
  get_conn() -> sqlite3.Connection
  close_db() -> None

Verifies:
- Tables created on first boot (price_history, run_log, claude_usage_history)
- Second init_db call is idempotent
- WAL mode enabled
- Insert helpers (record_price, record_run, record_usage) work
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import store.db as db_mod


EXPECTED_TABLES = {"price_history", "run_log", "claude_usage_history"}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _journal_mode(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA journal_mode").fetchone()
    return row[0] if row else ""


@pytest.fixture(autouse=True)
def fresh_db(tmp_path: Path):
    """Each test gets a fresh DB — close any existing connection first."""
    db_mod.close_db()
    yield tmp_path / "test_life_os.db"
    db_mod.close_db()


# ---------------------------------------------------------------------------
# Table creation (first boot)
# ---------------------------------------------------------------------------

class TestDbInit:
    def test_tables_created_on_init(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        assert fresh_db.exists(), "SQLite file must exist after init_db"
        conn = db_mod.get_conn()
        missing = EXPECTED_TABLES - _table_names(conn)
        assert not missing, f"Tables missing: {missing}"

    def test_all_three_tables_present(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        conn = db_mod.get_conn()
        assert _table_names(conn) >= EXPECTED_TABLES

    def test_wal_mode_enabled(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        conn = db_mod.get_conn()
        mode = _journal_mode(conn)
        assert mode == "wal", f"Expected WAL journal mode, got {mode!r}"

    def test_price_history_table_exists(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        assert "price_history" in _table_names(db_mod.get_conn())

    def test_run_log_table_exists(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        assert "run_log" in _table_names(db_mod.get_conn())

    def test_claude_usage_history_table_exists(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        assert "claude_usage_history" in _table_names(db_mod.get_conn())


# ---------------------------------------------------------------------------
# Idempotency (second boot)
# ---------------------------------------------------------------------------

class TestDbIdempotent:
    def test_second_init_does_not_raise(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        db_mod.close_db()
        db_mod.init_db(fresh_db)  # must not raise

    def test_second_init_same_tables(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        tables_before = _table_names(db_mod.get_conn())
        db_mod.close_db()
        db_mod.init_db(fresh_db)
        tables_after = _table_names(db_mod.get_conn())
        assert tables_before == tables_after

    def test_no_duplicate_tables(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        db_mod.close_db()
        db_mod.init_db(fresh_db)
        conn = db_mod.get_conn()
        rows = conn.execute(
            "SELECT name, COUNT(*) FROM sqlite_master WHERE type='table' GROUP BY name"
        ).fetchall()
        for name, count in rows:
            assert count == 1, f"Table {name!r} appears {count} times in sqlite_master"


# ---------------------------------------------------------------------------
# DB path resolution
# ---------------------------------------------------------------------------

class TestDbPath:
    def test_db_file_at_given_path(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        assert fresh_db.exists()

    def test_creates_parent_dir_if_missing(self, tmp_path: Path):
        nested = tmp_path / "deep" / "nested" / "life.db"
        db_mod.init_db(nested)
        assert nested.exists()


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------

class TestDbInserts:
    def test_record_price_returns_row_id(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        row_id = db_mod.record_price("BTC", 65000.0, "2026-06-06T00:00:00Z")
        assert isinstance(row_id, int) and row_id > 0

    def test_record_price_stored(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        db_mod.record_price("ETH", 3200.0, "2026-06-06T01:00:00Z", currency="USD")
        conn = db_mod.get_conn()
        row = conn.execute("SELECT * FROM price_history WHERE asset='ETH'").fetchone()
        assert row is not None
        assert abs(row["price"] - 3200.0) < 0.01

    def test_record_run_ok(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        row_id = db_mod.record_run("market-poll", "ok", "2026-06-06T00:00:00Z")
        assert isinstance(row_id, int) and row_id > 0

    def test_record_run_invalid_status_raises(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        with pytest.raises(ValueError, match="ok|warn|error"):
            db_mod.record_run("x", "unknown", "2026-06-06T00:00:00Z")

    def test_record_usage(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        row_id = db_mod.record_usage(
            "2026-06-06T00:00:00Z", input_tokens=100, output_tokens=200, cost_usd=0.003
        )
        assert isinstance(row_id, int) and row_id > 0

    def test_record_usage_stored(self, fresh_db: Path):
        db_mod.init_db(fresh_db)
        db_mod.record_usage("2026-06-06T00:00:00Z", input_tokens=50, output_tokens=75, cost_usd=0.001)
        conn = db_mod.get_conn()
        row = conn.execute("SELECT * FROM claude_usage_history ORDER BY id DESC LIMIT 1").fetchone()
        assert row is not None
        assert row["input_tokens"] == 50
        assert row["output_tokens"] == 75
