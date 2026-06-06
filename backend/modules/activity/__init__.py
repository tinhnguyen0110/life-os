"""modules/activity — the run_log activity feed (S10B).

Read-only over the SQLite run_log: a cross-routine timeline + roll-up stats.
``recent_runs`` (automation) is per-routine; this module is the unified feed every
screen + the Home widget read. The router is auto-mounted at ``/activity`` by the
registry via ``MODULE``.
"""

from .router import MODULE

__all__ = ["MODULE"]
