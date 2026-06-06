"""modules/brief — the daily brief generator (S11, SPEC §S11).

Template-based (NO AI this build — the in-app brief is a deterministic roll-up of
the other modules; an external Claude Code generates a richer brief later, ARCH §11).
Reads projects/finance/market/claude/alerts (fail-soft per source, mirroring the
morning-pull cross-module pull), runs 5 deterministic priority rules, and emits a
numbered priority list ordered by severity. The router auto-mounts at ``/brief``.
"""

from .router import MODULE

__all__ = ["MODULE"]
