"""modules/settings — global app-config (S12, SPEC §S12).

The system config the Settings screen edits: master automation switch, routine timing
(briefHour), thresholds (idleThresholdDays), per-routine enables, error channel, timezone,
display name. Persisted to md_store `settings/config.md` (one commit per write — the Notes
pattern). Readers (idle_hunter / scheduler / morning-pull) read this at runtime so a config
change takes effect without code edits. The router auto-mounts at ``/settings``.
"""

from .router import MODULE

__all__ = ["MODULE"]
