"""modules/alerts/router.py — alerts REST surface (ALERT-ROUTING, #33).

Mounts at ``/alerts`` via the registry (``MODULE`` below). Adding this folder is the ONLY wiring needed
(the registry auto-discovers ``MODULE`` — no edit to core/ or main.py).

The alert ENGINE is service.notify() — called in-process by other modules (the reminders-notify scan,
future alerts). This router exposes a small READ-ONLY status surface so the user/agent can see how alerts
are configured + which channels are available, WITHOUT leaking secrets (booleans only, never the webhook
URL or the app-password).
"""

from __future__ import annotations

from fastapi import APIRouter

from core.base import BaseModule
from core.responses import ok

from . import service

router = APIRouter()


@router.get("/config")
def alerts_config():
    """Alert routing config (READ-ONLY, no secrets): the mail threshold + whether each channel is
    CONFIGURED (a credential is present). Booleans only — never the webhook/app-password value."""
    return ok(data={
        "mailThreshold": service._mail_threshold(),
        "discordConfigured": bool(service._env_value("discord")),
        "mailConfigured": bool(service._env_value("LIFEOS_SMTP_USER")
                               and service._env_value("LIFEOS_SMTP_APP_PASSWORD")),
        "routing": {
            "low": "discord",
            "normal": "discord",
            "high": "discord + mail",
        },
    })


MODULE = BaseModule(name="alerts", router=router)
