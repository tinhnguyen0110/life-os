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
    # read-only and NEVER write into them (ARCH §6). Populated later (Sprint 1).
    project_repos: dict[str, str] = Field(default_factory=dict)

    # --- App ----------------------------------------------------------------
    app_name: str = "life-os"
    # Scheduler can be disabled (e.g. in tests) without touching module code.
    scheduler_enabled: bool = True

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
