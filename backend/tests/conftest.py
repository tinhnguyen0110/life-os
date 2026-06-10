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
    # Isolate the Claude-usage host-file sources too — else a test leaks into the
    # real ~/.claude/{stats-cache,quota-snapshot}.json on the dev machine and its
    # live values (e.g. quota resetIn='15m') break stub-expecting assertions.
    monkeypatch.setattr(settings, "claude_stats_path", tmp_path / "absent-stats.json")
    monkeypatch.setattr(settings, "claude_quota_path", tmp_path / "absent-quota.json")
    # Transcripts (.jsonl) are the PRIMARY token source now — point at an empty tmp
    # dir so the real ~/.claude/projects (live, 100M+ tokens) can't override a test's
    # stats-cache fixture. Also clear the module's process-global incremental mtime
    # cache between tests, else a prior test's parse leaks into the next.
    monkeypatch.setattr(settings, "claude_projects_dir", tmp_path / "absent-projects")
    from modules.claude_usage import transcripts
    transcripts._CACHE.clear()
    # projects read_one cache is process-global too — clear so a prior test's
    # ProjectStatus can't be served for a same-id project in a fresh tmp repo.
    from modules.projects import service as _proj_service
    _proj_service._STATUS_CACHE.clear()
    # market CoinGecko TTL cache is process-global — clear so a prior test's feed
    # can't leak into a test that monkeypatches httpx.get differently.
    from modules.market import reader as _mkt_reader
    _mkt_reader._FEED_CACHE.clear()
    # Reset the module-level DB_PATH override so settings.db_path takes effect.
    # init_db(path) (e.g. test_db.py) sets this global and never clears it; it
    # wins over settings.db_path in _db_path(), so without this reset a prior
    # test's DB path leaks into every later isolated_paths test (cross-test bleed).
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    yield tmp_path
    db.close_db()
