"""modules/alerts/service.py — the shared alert-routing engine (ALERT-ROUTING, #33).

ONE ``notify(severity, title, body)`` that every alert in life-os routes through (the reminders-notify
scan now; future alerts later), so the per-module notification code is de-duplicated. Routes by severity:

  - ``low`` / ``normal`` → Discord ONLY (mail not attempted → "n/a")
  - ``high``             → Discord + Mail

The threshold is the config knob ``alertMailThreshold`` (default "high"; the user can lower it to
"normal" to also get mail on normal alerts). A severity at-or-above the threshold gets mail.

FAIL-SOFT (memory fail-closed-write-fail-soft-addon): a notification is a SECONDARY add-on, never a
primary write — a Discord/SMTP bounce or a missing credential must NEVER crash the caller. Each channel
is independently try/excepted; the return reports HONESTLY which channels fired
(``{discord, mail, severity}``) so a skip is visible, not silently swallowed. notify() itself never
raises.

No new dependency: Discord via stdlib urllib (lifted from the #29 reminders poster); mail via stdlib
smtplib SMTP_SSL. Single-user: mail is a SELF-SEND (To = the configured SMTP user). Credentials come from
the repo-root ``.env`` (``discord=``, ``LIFEOS_SMTP_USER=``, ``LIFEOS_SMTP_APP_PASSWORD=``) — the same
.env the #29 poster + .claude/process/notify.py read. If a credential is absent, that channel honestly
"skipped" (never a crash) — verify on the CONTAINER that .env is readable (host-file-source-must-mount).
"""

from __future__ import annotations

import json
import logging
import pathlib
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from typing import Any

from .schema import SEVERITY_RANK, Severity

logger = logging.getLogger(__name__)

# the repo-root .env (parents[2] = backend/ -> repo root, matching reminders._discord_webhook +
# .claude/process/notify.py). Single-user, no secret store.
_ENV = pathlib.Path(__file__).resolve().parents[2] / ".env"


def _env_value(key: str) -> str:
    """Read ``key=`` from the repo-root .env. Missing .env / missing key → "" (→ the channel
    honest-skips). Never raises (a missing env must not crash a notify)."""
    try:
        if not _ENV.exists():
            return ""
        for line in _ENV.read_text().splitlines():
            s = line.strip()
            if s.startswith(f"{key}="):
                return s.split("=", 1)[1].strip()
    except Exception as exc:  # noqa: BLE001 — reading config must never crash a notify
        logger.warning("alerts: .env read failed for %s (treating as absent): %s", key, exc)
    return ""


def _mail_threshold() -> Severity:
    """The configured ``alertMailThreshold`` (default "high"). Read from settings; fail-safe to
    "high" (the most conservative — mail only on the most severe) if settings is unreadable."""
    try:
        from modules.settings.service import get_config
        thr = get_config().alertMailThreshold
        if thr in SEVERITY_RANK:
            return thr
    except Exception as exc:  # noqa: BLE001 — settings read must not crash a notify
        logger.warning("alerts: alertMailThreshold read failed — defaulting 'high': %s", exc)
    return "high"


def _post_discord(message: str) -> bool:
    """Post to the Discord webhook (.env ``discord=``). Lifted from the #29 reminders poster:
    urllib, 10s timeout, no new dep. FAIL-SOFT: no webhook or a post error → log + return False
    (never raises). Returns True only on a successful post."""
    url = _env_value("discord")
    if not url or not message:
        return False
    try:
        req = urllib.request.Request(
            url, data=json.dumps({"content": message}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "life-os-alerts/1.0"},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as exc:  # noqa: BLE001 — a webhook bounce must not crash the caller
        logger.warning("alerts: Discord post skipped (webhook fail): %s", exc)
        return False


def _send_mail(subject: str, body: str) -> bool:
    """Self-send mail via Gmail SMTP_SSL (stdlib smtplib, no new dep). Creds from .env
    (LIFEOS_SMTP_USER + LIFEOS_SMTP_APP_PASSWORD — a Gmail APP password). To = the SMTP user
    (single-user self-send only; no arbitrary outbound). FAIL-SOFT: missing creds or an SMTP error
    → log + return False (NEVER raises). Returns True only on a successful send."""
    user = _env_value("LIFEOS_SMTP_USER")
    app_password = _env_value("LIFEOS_SMTP_APP_PASSWORD")
    if not user or not app_password:
        return False
    try:
        msg = EmailMessage()
        msg["From"] = user
        msg["To"] = user  # self-send
        msg["Subject"] = subject
        msg.set_content(body)
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=15) as smtp:
            smtp.login(user, app_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — an SMTP bounce must not crash the caller
        logger.warning("alerts: mail send skipped (SMTP fail): %s", exc)
        return False


def notify(severity: Severity, title: str, body: str) -> dict[str, Any]:
    """Route an alert by severity (the shared engine — see module docstring). FAIL-SOFT: never
    raises; reports honestly which channels fired.

    Returns ``{discord: "sent"|"skipped", mail: "sent"|"skipped"|"n/a", severity}``:
      - discord: always ATTEMPTED → "sent" on success, "skipped" on no-webhook/error.
      - mail: "n/a" if severity is BELOW the alertMailThreshold (mail not attempted); else
        "sent"/"skipped" (attempted; "skipped" on no-creds/error).
    """
    sev: Severity = severity if severity in SEVERITY_RANK else "normal"  # defensive default
    discord_ok = _post_discord(f"[{sev}] {title}\n{body}")

    # mail only at/above the threshold.
    threshold = _mail_threshold()
    mail_result: str
    if SEVERITY_RANK[sev] >= SEVERITY_RANK[threshold]:
        mail_result = "sent" if _send_mail(f"[life-os {sev}] {title}", body) else "skipped"
    else:
        mail_result = "n/a"  # below threshold — mail not attempted (not a failure)

    return {
        "discord": "sent" if discord_ok else "skipped",
        "mail": mail_result,
        "severity": sev,
    }
