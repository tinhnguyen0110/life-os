"""modules/alerts/schema.py — alert severity + the notify() result shape (ALERT-ROUTING, #33).

FROZEN: ``notify(severity, title, body)`` returns ``{discord, mail, severity}`` where discord ∈
{"sent","skipped"}, mail ∈ {"sent","skipped","n/a"}, severity is the (validated) severity. The shape
is what the caller/test asserts which channels fired; "n/a" mail = severity below the threshold so mail
wasn't attempted (NOT a failure).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "normal", "high"]

# severity ordering for the threshold compare (high ≥ normal ≥ low). The mail threshold knob
# (alertMailThreshold) compares against this — a severity at/above the threshold rank gets mail.
SEVERITY_RANK: dict[str, int] = {"low": 0, "normal": 1, "high": 2}


class NotifyResult(BaseModel):
    """The notify() return — which channels fired. FROZEN #33."""

    discord: Literal["sent", "skipped"] = Field(..., description="Discord always attempted; sent on success else skipped")
    mail: Literal["sent", "skipped", "n/a"] = Field(..., description="n/a = below threshold (not attempted); else sent/skipped")
    severity: Severity = Field(..., description="the validated severity the alert routed at")
