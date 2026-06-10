"""core/config.py — settings & paths (ARCH §3/§6).

Single source of truth for filesystem locations and the read-only pointers to
external project repos. No-auth, single-user — no secrets beyond optional repo
pointers; everything is local.

Override any field via environment variables prefixed ``LIFEOS_`` (e.g.
``LIFEOS_DATA_DIR=/tmp/x``) or a ``.env`` file at the backend root.
"""

from __future__ import annotations

import os
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
#
# Read the env override DIRECTLY (os.environ, not a pydantic field) because
# _default_project_repos() runs at import time, before Settings() is constructed.
# In a container BACKEND_ROOT=/app so parent.parent=/ resolves no repos — the
# compose mount sets LIFEOS_TINHDEV_ROOT=/repos to point at the read-only repo mount.
TINHDEV_ROOT = Path(os.environ.get("LIFEOS_TINHDEV_ROOT", str(BACKEND_ROOT.parent.parent)))

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


def _default_market_assets() -> list[dict]:
    """Sprint 3 tracked-asset shortlist (SPEC §S8). crypto→CoinGecko, etf/vn→mock."""
    return [
        {"symbol": "BTC", "name": "Bitcoin", "assetClass": "crypto", "cgId": "bitcoin"},
        {"symbol": "ETH", "name": "Ethereum", "assetClass": "crypto", "cgId": "ethereum"},
        {"symbol": "SOL", "name": "Solana", "assetClass": "crypto", "cgId": "solana"},
        {"symbol": "VNINDEX", "name": "VN-Index", "assetClass": "vn", "mock": 1283.5},
        {"symbol": "FUEVFVND", "name": "ETF VFVND", "assetClass": "etf", "mock": 24.8},
    ]


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

    # --- Market (Sprint 3, SPEC §S8) ---------------------------------------
    # Tracked assets as a flat list (no asset-mgmt API — single dev). Each entry:
    # {symbol, name, assetClass, cgId?(crypto), mock?(etf/vn)}. crypto → CoinGecko
    # (cgId required); etf/vn → deterministic mock seed. Override LIFEOS_MARKET_ASSETS.
    market_assets: list[dict] = Field(default_factory=lambda: _default_market_assets())
    # CoinGecko free API base (no key). Override for tests/proxy via LIFEOS_COINGECKO_BASE.
    coingecko_base: str = "https://api.coingecko.com/api/v3"

    # --- Claude usage (Sprint 7, SPEC §S9) ----------------------------------
    # Path to Claude Code's stats-cache.json (real token-usage source). Default
    # ~/.claude/stats-cache.json; override via LIFEOS_CLAUDE_STATS_PATH (tests
    # point this at a fixture, NOT the real ~/.claude). Machine-portable (3B lesson).
    claude_stats_path: Path = Field(default_factory=lambda: Path.home() / ".claude" / "stats-cache.json")
    # Path to the live quota snapshot tee'd by the statusline command (real 5h/7d
    # rate-limit % + reset timestamps + context %). Claude Code pushes rate_limits
    # ONLY via the statusline stdin; statusline-command.sh tee's it here so the
    # backend can read it. Default ~/.claude/quota-snapshot.json; override via
    # LIFEOS_CLAUDE_QUOTA_PATH (tests point at a fixture). Fail-open if absent.
    claude_quota_path: Path = Field(default_factory=lambda: Path.home() / ".claude" / "quota-snapshot.json")
    # Dir holding Claude Code session transcripts (~/.claude/projects/<slug>/*.jsonl).
    # The LIVE token/cost/byProject source — each assistant message carries a real
    # `usage` block + cwd + model + timestamp (stats-cache.json died 2026-04-17).
    # Parsed incrementally (mtime cache). Override via LIFEOS_CLAUDE_PROJECTS_DIR
    # (tests point at a fixture). Fail-open: missing dir → empty, never raises.
    claude_projects_dir: Path = Field(default_factory=lambda: Path.home() / ".claude" / "projects")
    # Default token cap for the active window (no rate-limit ceiling on disk —
    # manual-override via PUT). Matches the mock's 200K.
    claude_usage_cap: int = 200_000

    # --- OKX exchange (read-only API key, optional) -------------------------
    # Set via .env or env vars. Left empty → exchange module returns stub/empty.
    okx_api_key: str = Field(default="", description="OKX API key")
    okx_api_secret: str = Field(default="", description="OKX API secret")
    okx_api_passphrase: str = Field(default="", description="OKX API passphrase")

    # Browser origins allowed to call the API. Single-user localhost no-auth
    # (CLAUDE.md §2) — CORS here is a browser-functionality enabler, NOT a
    # security boundary. Default covers the FE dev server (:3010) + Next default
    # (:3000). Override via LIFEOS_CORS_ORIGINS (JSON list).
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"]
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
