"""modules/settings/service.py — global AppConfig persistence (S12).

Reads/writes md_store `settings/config.md` (YAML front-matter, one commit per write —
the Notes/toggles pattern). Fail-OPEN read (absent/malformed config.md → defaults, the
current hardcoded behavior — never 500). Fail-CLOSED write (a persist failure raises —
a lost config write must be visible).

The runtime-config readers (idle_hunter / scheduler gate / morning-pull cron) call
get_config() so a PATCH takes effect at the next routine run without a code edit. A
helper get_config() is the single read entry-point; set_config() merges a partial
patch onto the current config + persists.
"""

from __future__ import annotations

import logging

import yaml

from store import md_store

from .schema import AppConfig, AppConfigPatch

logger = logging.getLogger("life-os.settings.service")

CONFIG_MD = "settings/config.md"


def _render(config: AppConfig) -> str:
    """AppConfig → `---\\n<front-matter>\\n---\\n` document (no body — config is all FM)."""
    block = yaml.safe_dump(config.model_dump(), sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n"


def get_config() -> AppConfig:
    """The resolved global config. Fail-OPEN: absent/malformed config.md → defaults (the
    current hardcoded behavior). Never raises — readers depend on this at runtime."""
    try:
        content = md_store.read(CONFIG_MD)
    except Exception as exc:
        logger.warning("settings config.md read failed — using defaults: %s", exc)
        return AppConfig()
    if not content:
        return AppConfig()
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return AppConfig()
    block = text[len("---"):].split("\n---", 1)[0]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        logger.warning("settings config.md malformed — using defaults: %s", exc)
        return AppConfig()
    if not isinstance(data, dict):
        return AppConfig()
    try:
        # Validate against the schema. A corrupt/out-of-range file → full defaults
        # (honest: we couldn't trust the file), never a partial mix.
        return AppConfig.model_validate(data)
    except Exception as exc:
        logger.warning("settings config.md invalid — using defaults: %s", exc)
        return AppConfig()


def set_config(patch: AppConfigPatch) -> AppConfig:
    """Merge a partial patch onto the current config + persist (one commit). Returns the
    new full config. Fail-CLOSED write (md_store failure raises). Validation already
    happened at the boundary (router → AppConfigPatch); this merges validated fields."""
    current = get_config()
    updates = patch.model_dump(exclude_none=True)
    merged = current.model_copy(update=updates)
    md_store.write_file(CONFIG_MD, _render(merged), "update settings")
    return merged
