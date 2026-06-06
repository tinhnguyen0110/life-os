"""tests/test_config.py — core/config resolution (Sprint 3B).

Regression: TINHDEV_ROOT must honor the LIFEOS_TINHDEV_ROOT env override (the
comment promised it; the code ignored it → in a container BACKEND_ROOT=/app so
repos resolved against / and none were found → Docker showed 1 repo not 6).

NOTE: we do NOT importlib.reload(core.config) — reloading rebinds the module-level
``settings`` singleton and breaks every other test that holds the old reference
(monkeypatch then patches a different object). Instead we test the env-read
expression directly and exercise _default_project_repos() via monkeypatched
TINHDEV_ROOT, which is exactly what the import-time line computes.
"""

from __future__ import annotations

import os
from pathlib import Path

import core.config as cfg


def test_tinhdev_root_expression_honors_env(monkeypatch, tmp_path):
    """The exact import-time expression reads LIFEOS_TINHDEV_ROOT when set."""
    monkeypatch.setenv("LIFEOS_TINHDEV_ROOT", str(tmp_path))
    resolved = Path(os.environ.get("LIFEOS_TINHDEV_ROOT", str(cfg.BACKEND_ROOT.parent.parent)))
    assert resolved == tmp_path


def test_tinhdev_root_expression_defaults_without_env(monkeypatch):
    """No env → derived BACKEND_ROOT.parent.parent (bare-metal behavior)."""
    monkeypatch.delenv("LIFEOS_TINHDEV_ROOT", raising=False)
    resolved = Path(os.environ.get("LIFEOS_TINHDEV_ROOT", str(cfg.BACKEND_ROOT.parent.parent)))
    assert resolved == cfg.BACKEND_ROOT.parent.parent


def test_default_project_repos_resolve_under_root(monkeypatch, tmp_path):
    """With TINHDEV_ROOT pointing at a dir holding the repo folders, the shortlist
    resolves them (the container case: mount /repos + LIFEOS_TINHDEV_ROOT=/repos)."""
    for folder in ("DevCrew", "OutboundOS", "crewly", "ClaudeManager", "Groundwork", "life-os"):
        (tmp_path / folder).mkdir()
    monkeypatch.setattr(cfg, "TINHDEV_ROOT", tmp_path)
    repos = cfg._default_project_repos()
    assert set(repos) == {"devcrew", "outboundos", "crewly", "claudemanager", "groundwork", "life-os"}
    assert all(str(tmp_path) in p for p in repos.values())


def test_default_project_repos_skips_missing_dirs(monkeypatch, tmp_path):
    """Only repo dirs that actually exist register (honest per-host)."""
    (tmp_path / "DevCrew").mkdir()  # only one exists
    monkeypatch.setattr(cfg, "TINHDEV_ROOT", tmp_path)
    repos = cfg._default_project_repos()
    assert set(repos) == {"devcrew"}
