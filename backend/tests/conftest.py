"""Shared fixtures — isolate DATA_DIR and DB_PATH into a tmp dir per test."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def isolated_paths(tmp_path: Path, monkeypatch):
    """Point settings.data_dir + settings.db_path at a fresh tmp dir.

    Also resets the db module's cached connection so each test gets its own DB.
    """
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    # Reset the module-level DB_PATH override so settings.db_path takes effect.
    # init_db(path) (e.g. test_db.py) sets this global and never clears it; it
    # wins over settings.db_path in _db_path(), so without this reset a prior
    # test's DB path leaks into every later isolated_paths test (cross-test bleed).
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    yield tmp_path
    db.close_db()
