"""tests/test_alerts.py — ALERT-ROUTING (#33): the shared notify() engine.

notify(severity, title, body) routes by severity: low/normal → Discord only; high → Discord + Mail.
Threshold = the alertMailThreshold knob (default "high"). FAIL-SOFT: a Discord/SMTP bounce or a missing
credential never crashes the caller; the return reports honestly which channels fired.

EVERYTHING IS MOCKED — no test ever posts a real Discord message or sends a real mail. The two channel
primitives (_post_discord / _send_mail) and the .env reader (_env_value) are the seams; we patch them to
record calls + simulate success / failure / missing-config. We also test the REAL fail-soft paths by
making urlopen / SMTP_SSL raise (the channel must swallow it → return False, never propagate).
"""

from __future__ import annotations

import pytest

import modules.alerts.service as alerts


@pytest.fixture
def caps(monkeypatch):
    """Capture channel calls without real I/O. Discord + mail both 'succeed' by default; .env has all
    creds. Individual tests override a seam to simulate failure / missing-config / threshold."""
    calls = {"discord": [], "mail": []}
    monkeypatch.setattr(alerts, "_post_discord",
                        lambda message: (calls["discord"].append(message) or True))
    monkeypatch.setattr(alerts, "_send_mail",
                        lambda subject, body: (calls["mail"].append((subject, body)) or True))
    # default threshold = high (the shipped default); tests that need another set it explicitly
    monkeypatch.setattr(alerts, "_mail_threshold", lambda: "high")
    return calls


# --------------------------------------------------------------------------- #
# routing by severity                                                            #
# --------------------------------------------------------------------------- #
def test_low_routes_discord_only(caps):
    r = alerts.notify("low", "t", "b")
    assert r == {"discord": "sent", "mail": "n/a", "severity": "low"}
    assert len(caps["discord"]) == 1 and len(caps["mail"]) == 0  # mail NOT attempted


def test_normal_routes_discord_only(caps):
    r = alerts.notify("normal", "t", "b")
    assert r == {"discord": "sent", "mail": "n/a", "severity": "normal"}
    assert len(caps["mail"]) == 0


def test_high_routes_discord_and_mail(caps):
    r = alerts.notify("high", "Big", "body")
    assert r == {"discord": "sent", "mail": "sent", "severity": "high"}
    assert len(caps["discord"]) == 1 and len(caps["mail"]) == 1


def test_discord_message_format(caps):
    alerts.notify("high", "Title here", "the body")
    assert caps["discord"][0] == "[high] Title here\nthe body"  # [{severity}] {title}\n{body}


def test_mail_subject_format(caps):
    alerts.notify("high", "Title here", "the body")
    subject, body = caps["mail"][0]
    assert subject == "[life-os high] Title here" and body == "the body"


# --------------------------------------------------------------------------- #
# threshold knob — lowering it to 'normal' makes normal also mail                #
# --------------------------------------------------------------------------- #
def test_threshold_normal_makes_normal_mail(caps, monkeypatch):
    monkeypatch.setattr(alerts, "_mail_threshold", lambda: "normal")
    r = alerts.notify("normal", "t", "b")
    assert r["mail"] == "sent"  # normal >= normal threshold → mail attempted + sent
    # but low stays below the lowered threshold
    r2 = alerts.notify("low", "t", "b")
    assert r2["mail"] == "n/a"


def test_threshold_high_keeps_normal_mail_na(caps):
    # default threshold high → normal below it → mail n/a
    assert alerts.notify("normal", "t", "b")["mail"] == "n/a"


# --------------------------------------------------------------------------- #
# FAIL-SOFT — a channel error/skip never crashes notify(); honest return        #
# --------------------------------------------------------------------------- #
def test_discord_skipped_when_post_fails(monkeypatch):
    monkeypatch.setattr(alerts, "_post_discord", lambda message: False)  # post failed/skipped
    monkeypatch.setattr(alerts, "_send_mail", lambda s, b: True)
    monkeypatch.setattr(alerts, "_mail_threshold", lambda: "high")
    r = alerts.notify("high", "t", "b")
    assert r["discord"] == "skipped" and r["mail"] == "sent"  # honest: discord skipped, mail still sent


def test_mail_skipped_when_send_fails(monkeypatch):
    monkeypatch.setattr(alerts, "_post_discord", lambda message: True)
    monkeypatch.setattr(alerts, "_send_mail", lambda s, b: False)  # mail failed/skipped
    monkeypatch.setattr(alerts, "_mail_threshold", lambda: "high")
    r = alerts.notify("high", "t", "b")
    assert r["discord"] == "sent" and r["mail"] == "skipped"


def test_notify_never_raises_even_if_channel_raises(monkeypatch):
    """A channel primitive that RAISES must be swallowed inside the channel (fail-soft) — but even
    if one slipped through, notify must not propagate. Here _post_discord itself is the real one,
    with urlopen raising → it returns False, notify returns skipped (no exception)."""
    import urllib.request
    monkeypatch.setattr(alerts, "_env_value",
                        lambda key: "http://fake.invalid/hook" if key == "discord" else "")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network down")))
    monkeypatch.setattr(alerts, "_mail_threshold", lambda: "high")
    r = alerts.notify("high", "t", "b")  # must NOT raise
    assert r["discord"] == "skipped"  # the raising post was swallowed → skipped


def test_real_discord_fail_soft_returns_false(monkeypatch):
    """_post_discord with a webhook but a raising urlopen → False (never raises)."""
    import urllib.request
    monkeypatch.setattr(alerts, "_env_value", lambda key: "http://fake.invalid/hook" if key == "discord" else "")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert alerts._post_discord("hi") is False


def test_real_mail_fail_soft_returns_false(monkeypatch):
    """_send_mail with creds but a raising SMTP_SSL → False (never raises)."""
    import smtplib
    monkeypatch.setattr(alerts, "_env_value", lambda key: "user@gmail.com" if "SMTP" in key else "")
    monkeypatch.setattr(smtplib, "SMTP_SSL",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("smtp down")))
    assert alerts._send_mail("subj", "body") is False


# --------------------------------------------------------------------------- #
# missing-env — honest skip, never a crash                                       #
# --------------------------------------------------------------------------- #
def test_missing_discord_webhook_skips(monkeypatch):
    monkeypatch.setattr(alerts, "_env_value", lambda key: "")  # no discord, no SMTP
    monkeypatch.setattr(alerts, "_mail_threshold", lambda: "high")
    r = alerts.notify("high", "t", "b")
    assert r["discord"] == "skipped" and r["mail"] == "skipped"  # both honest-skip, no crash


def test_missing_smtp_creds_mail_skips(monkeypatch):
    monkeypatch.setattr(alerts, "_env_value",
                        lambda key: "http://hook" if key == "discord" else "")  # discord ok, no SMTP
    monkeypatch.setattr(alerts, "_post_discord", lambda m: True)
    monkeypatch.setattr(alerts, "_mail_threshold", lambda: "high")
    r = alerts.notify("high", "t", "b")
    assert r["mail"] == "skipped"  # no creds → honest skip


def test_real_post_discord_no_webhook_returns_false(monkeypatch):
    monkeypatch.setattr(alerts, "_env_value", lambda key: "")
    assert alerts._post_discord("hi") is False


def test_real_send_mail_no_creds_returns_false(monkeypatch):
    monkeypatch.setattr(alerts, "_env_value", lambda key: "")
    assert alerts._send_mail("s", "b") is False


# --------------------------------------------------------------------------- #
# defensive — an unknown severity defaults to 'normal' (never crashes)           #
# --------------------------------------------------------------------------- #
def test_unknown_severity_defaults_normal(caps):
    r = alerts.notify("EMERGENCY", "t", "b")  # type: ignore[arg-type]
    assert r["severity"] == "normal" and r["mail"] == "n/a"


# --------------------------------------------------------------------------- #
# the config endpoint (read-only, no secrets)                                    #
# --------------------------------------------------------------------------- #
def test_config_endpoint_no_secrets(monkeypatch):
    from fastapi.testclient import TestClient
    from main import create_app
    monkeypatch.setattr(alerts, "_env_value",
                        lambda key: "http://secret-hook" if key == "discord" else "creds")
    client = TestClient(create_app())
    r = client.get("/alerts/config")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["discordConfigured"] is True and d["mailConfigured"] is True
    assert d["mailThreshold"] in ("low", "normal", "high")
    # NEVER leak the actual webhook/password value
    assert "secret-hook" not in str(d) and "creds" not in str(d)


# --------------------------------------------------------------------------- #
# TRACING-UX T3 (#111) — the additive channels= override (does NOT alter the     #
# existing severity routing when omitted; routes to EXACTLY the given channels    #
# when given, severity-independent).                                              #
# --------------------------------------------------------------------------- #
def test_111_channels_omitted_is_byte_identical_severity_route(caps):
    """🔴 NO REGRESSION: with channels= OMITTED, notify routes by SEVERITY exactly as before — the
    #33 reminders-scan's notify('normal',...) is UNCHANGED. normal → discord only; high → +mail."""
    assert alerts.notify("normal", "t", "b") == {"discord": "sent", "mail": "n/a", "severity": "normal"}
    assert len(caps["mail"]) == 0  # severity-mode: normal does NOT mail
    assert alerts.notify("high", "t", "b") == {"discord": "sent", "mail": "sent", "severity": "high"}


def test_111_channels_discord_only_routes_discord_regardless_of_severity(caps):
    """channels=['discord'] → discord fires, mail is 'n/a' (NOT attempted) — even at 'normal' (which
    in severity-mode also = discord-only, so test it doesn't accidentally mail) AND the override is
    severity-INDEPENDENT (a 'low' with channels=['discord'] still fires discord)."""
    r = alerts.notify("low", "Reminder", "due now", channels=["discord"])
    assert r == {"discord": "sent", "mail": "n/a", "severity": "low"}
    assert len(caps["discord"]) == 1 and len(caps["mail"]) == 0


def test_111_channels_email_only_routes_mail_regardless_of_severity(caps):
    """channels=['email'] → MAIL fires even at 'normal'/'low' severity (which in severity-mode would
    NOT mail). Proves the override ignores the severity threshold — routes to EXACTLY email."""
    r = alerts.notify("normal", "Reminder", "due now", channels=["email"])
    assert r == {"discord": "n/a", "mail": "sent", "severity": "normal"}
    assert len(caps["mail"]) == 1 and len(caps["discord"]) == 0  # discord NOT attempted


def test_111_channels_override_fail_soft_on_no_creds(caps, monkeypatch):
    """A given channel with no creds → 'skipped' (fail-soft, no crash), the other channel n/a."""
    monkeypatch.setattr(alerts, "_send_mail", lambda subject, body: False)  # simulate no creds/bounce
    r = alerts.notify("high", "t", "b", channels=["email"])
    assert r == {"discord": "n/a", "mail": "skipped", "severity": "high"}


def test_111_channels_empty_list_routes_nothing(caps):
    """channels=[] (explicit empty) → neither channel attempted (both n/a) — distinct from None
    (severity-mode). An explicit 'no channels' is honest no-op."""
    r = alerts.notify("high", "t", "b", channels=[])
    assert r == {"discord": "n/a", "mail": "n/a", "severity": "high"}
    assert len(caps["discord"]) == 0 and len(caps["mail"]) == 0


def test_111_configured_helpers_reflect_env(monkeypatch):
    """discord_configured/mail_configured (the shared single-source detection #111 reuses) reflect
    the .env: present creds → True; absent → False."""
    monkeypatch.setattr(alerts, "_env_value",
                        lambda k: {"discord": "hook", "LIFEOS_SMTP_USER": "u",
                                   "LIFEOS_SMTP_APP_PASSWORD": "p"}.get(k, ""))
    assert alerts.discord_configured() is True and alerts.mail_configured() is True
    monkeypatch.setattr(alerts, "_env_value", lambda k: "")  # nothing configured
    assert alerts.discord_configured() is False and alerts.mail_configured() is False
