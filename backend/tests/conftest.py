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
    db.close_db()
    yield tmp_path
    db.close_db()
