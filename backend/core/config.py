"""core/config.py — settings & paths (ARCH §3/§6).

Single source of truth for filesystem locations and the read-only pointers to
external project repos. No-auth, single-user — no secrets beyond optional repo
pointers; everything is local.

Override any field via environment variables prefixed ``LIFEOS_`` (e.g.
``LIFEOS_DATA_DIR=/tmp/x``) or a ``.env`` file at the backend root.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ root = parent of this file's parent (core/ -> backend/)
BACKEND_ROOT = Path(__file__).resolve().parent.parent
# The repo lives at <tinhdev_root>/life-os/backend, so tinhdev_root is two up from
# BACKEND_ROOT (backend -> life-os -> tinhdev_root). The shortlist repos are
# siblings of life-os under tinhdev_root. Derived (not hardcoded) so it works on
# any machine where the repos sit beside life-os; override via LIFEOS_TINHDEV_ROOT
# or the whole map via LIFEOS_PROJECT_REPOS.
TINHDEV_ROOT = BACKEND_ROOT.parent.parent

# Shortlist of projects tracked by default (Sprint 1, ARCH §9 / memory
# trackable-repos-inventory). id (slug) -> repo folder name under tinhdev_root.
# life-os points at its own repo root (dogfood). Folder casing matches disk.
_SHORTLIST_FOLDERS: dict[str, str] = {
    "devcrew": "DevCrew",
    "outboundos": "OutboundOS",
    "crewly": "crewly",
    "claudemanager": "ClaudeManager",
    "groundwork": "Groundwork",
    "life-os": "life-os",
}


def _default_project_repos() -> dict[str, str]:
    """Resolve the shortlist to absolute paths under TINHDEV_ROOT.

    Only includes a project if its repo dir actually exists on this machine, so a
    missing sibling repo never registers a dead pointer at import. (The reader is
    fail-open anyway, but this keeps the default map honest per host.)
    Override entirely via the LIFEOS_PROJECT_REPOS env var (JSON dict).
    """
    out: dict[str, str] = {}
    for slug, folder in _SHORTLIST_FOLDERS.items():
        path = (TINHDEV_ROOT / folder).resolve()
        if path.is_dir():
            out[slug] = str(path)
    return out


class Settings(BaseSettings):
    """Runtime configuration. Paths default relative to ``backend/``."""

    model_config = SettingsConfigDict(
        env_prefix="LIFEOS_",
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Paths --------------------------------------------------------------
    # DATA_DIR is its OWN git repo (md_store commits land here), distinct from
    # the source repo. ARCH §6: every markdown write = one git commit.
    data_dir: Path = Field(default=BACKEND_ROOT / "data")
    # SQLite time-series store (price_history / run_log / claude_usage_history).
    db_path: Path = Field(default=BACKEND_ROOT / "store" / "life_os.db")

    # --- External project repo pointers (read-only ground truth) ------------
    # Maps project id -> absolute path of its git repo. Readers read these
    # read-only and NEVER write into them (ARCH §6). Defaults to the Sprint 1
    # shortlist resolved under TINHDEV_ROOT (machine-portable — derived, not
    # hardcoded). Override the whole map via LIFEOS_PROJECT_REPOS (JSON dict).
    project_repos: dict[str, str] = Field(default_factory=_default_project_repos)

    # --- App ----------------------------------------------------------------
    app_name: str = "life-os"
    # Scheduler can be disabled (e.g. in tests) without touching module code.
    scheduler_enabled: bool = True

    # Browser origins allowed to call the API. Single-user localhost no-auth
    # (CLAUDE.md §2) — CORS here is a browser-functionality enabler, NOT a
    # security boundary. Default covers the FE dev server (:3010) + Next default
    # (:3000). Override via LIFEOS_CORS_ORIGINS (JSON list).
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3010", "http://localhost:3000"]
    )

    # --- Derived paths (always under data_dir) ------------------------------
    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def notes_dir(self) -> Path:
        return self.data_dir / "notes"

    @property
    def journal_dir(self) -> Path:
        return self.data_dir / "journal"


# Module-level singleton — import this everywhere.
settings = Settings()

# --- Dispatch-locked convenience exports (ARCH/Sprint-0 Exports) ------------
# The architect's Sprint 0 contract names DATA_DIR / DB_PATH as importable
# module-level paths. They mirror settings.* (the live, env-overridable source of
# truth). Prefer ``settings.data_dir`` in code that must respect runtime/test
# overrides; these constants are the snapshot at import time for simple callers.
DATA_DIR = settings.data_dir
DB_PATH = settings.db_path
