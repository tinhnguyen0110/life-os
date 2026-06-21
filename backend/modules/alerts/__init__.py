"""modules/alerts — the shared alert-routing engine (ALERT-ROUTING, #33).

ONE ``notify(severity, title, body)`` that all life-os alerts route through (the reminders-notify scan
now; future alerts later), de-duplicating the per-module notification code. Routes by severity: Discord
always; Mail at/above the ``alertMailThreshold`` knob (default "high"). Discord = stdlib urllib (lifted
from #29); Mail = stdlib smtplib SMTP_SSL self-send. FAIL-SOFT — a bounce/missing-credential never
crashes the caller; the return reports honestly which channels fired.

Single-user, no auth, no new dependency (north-star). The registry discovers MODULE from router.py.
"""

from .router import MODULE
from .service import notify

__all__ = ["MODULE", "notify"]
