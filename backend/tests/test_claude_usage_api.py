"""tests/test_claude_usage_api.py — Claude Usage router integration (Sprint 7 T2).

Real app via TestClient, claude-usage auto-mounted. Stats-cache points at a
fixture (NEVER real ~/.claude). Envelope + /health discovery + override PUT.
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)

    # stats-cache fixture (NOT real ~/.claude)
    fix = tmp_path / "stats-cache.json"
    fix.write_text(json.dumps({
        "lastComputedDate": _today(),
        "dailyModelTokens": [{"date": _today(), "tokensByModel": {"claude-opus-4-7": 50_000}}],
        "modelUsage": {"claude-opus-4-7": {"inputTokens": 1_000_000, "outputTokens": 0,
                                           "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0}},
    }))
    monkeypatch.setattr(settings, "claude_stats_path", fix)
    # Isolate the live sources so these tests exercise the stats-cache fixture, not
    # the dev machine's real ~/.claude (transcripts is PRIMARY now; quota is live).
    monkeypatch.setattr(settings, "claude_quota_path", tmp_path / "absent-quota.json")
    monkeypatch.setattr(settings, "claude_projects_dir", tmp_path / "absent-projects")
    from modules.claude_usage import transcripts
    transcripts._CACHE.clear()

    db.close_db()
    import main as main_mod
    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        c._stats_fixture = fix  # type: ignore[attr-defined]
        yield c
    db.close_db()


# --- discovery ---
def test_health_lists_claude_usage_module(app_client):
    assert "claude-usage" in app_client.get("/health").json()["data"]["modules"]


def test_health_no_skipped_modules(app_client):
    assert not app_client.get("/health").json().get("warning")


# --- GET /claude-usage ---
def test_get_usage_envelope(app_client):
    body = app_client.get("/claude-usage").json()
    assert body["success"] is True
    d = body["data"]
    required = {"model", "used", "cap", "pct", "remaining", "resetIn", "weekly", "series",
                "today", "avgPerDay", "peak", "byModel", "costUSD", "byProject", "asOf",
                "stale", "source"}
    assert not (required - set(d)), f"missing keys: {required - set(d)}"
    assert d["source"] == "stats-cache"
    assert d["used"] == 50_000 and d["today"] == 50_000
    assert d["byModel"][0]["costUSD"] == 5.0  # 1M opus-4-7 input @ 5/1M (NEW 4.5+ tier)


def test_get_usage_pct_is_quota_window_not_used_cap(app_client):
    # NG1: pct is the quota-window % (pct5h/weekly) or None — NEVER used/cap. So it's
    # either None (no snapshot) or a sane 0-100, but NOT the used/cap ratio.
    d = app_client.get("/claude-usage").json()["data"]
    assert d["pct"] is None or (0.0 <= d["pct"] <= 100.0)
    if d["used"] > d["cap"]:
        # the old bug would headline >100% here; now it's None or ≤100.
        assert d["pct"] is None or d["pct"] <= 100.0


# --- fail-open empty mode (200, not 500) when NO token source at all ---
def test_get_usage_empty_mode_when_no_sources(app_client, monkeypatch, tmp_path):
    from core.config import settings
    monkeypatch.setattr(settings, "claude_stats_path", tmp_path / "gone.json")
    # projects dir already isolated-absent by app_client fixture → no transcripts either
    resp = app_client.get("/claude-usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["source"] == "none" and body["data"]["tokenSource"] == "none"
    assert body.get("warning") and "no token data" in body["warning"]


# --- PUT /claude-usage/override ---
def test_put_override(app_client):
    r = app_client.put("/claude-usage/override", json={"cap": 500_000, "resetIn": "2h 30m", "weekly": 1_000_000})
    assert r.status_code == 200 and r.json()["success"] is True
    d = r.json()["data"]
    assert d["cap"] == 500_000 and d["resetIn"] == "2h 30m" and d["weekly"] == 1_000_000
    # persisted: a fresh GET reflects it
    g = app_client.get("/claude-usage").json()["data"]
    assert g["cap"] == 500_000 and g["resetIn"] == "2h 30m"


def test_put_override_422_negative_cap(app_client):
    assert app_client.put("/claude-usage/override", json={"cap": -1}).status_code == 422


def test_put_override_empty_ok(app_client):
    # all-None override is valid (clears nothing, uses defaults)
    assert app_client.put("/claude-usage/override", json={}).status_code == 200


# ---------------------------------------------------------------------------
# A4 — edge cases / error paths not previously covered at the API layer
# ---------------------------------------------------------------------------

def test_get_usage_stale_surfaced_as_warning(app_client):
    """When the stats-cache is stale (lastComputedDate is old), GET /claude-usage
    returns a warning string mentioning the stale date — NOT just a silent stale flag."""
    import json
    from core.config import settings

    stale_date = "2026-01-01"
    fix = app_client._stats_fixture  # type: ignore[attr-defined]
    fix.write_text(json.dumps({
        "lastComputedDate": stale_date,
        "dailyModelTokens": [{"date": stale_date, "tokensByModel": {"claude-sonnet-4-6": 10_000}}],
        "modelUsage": {"claude-sonnet-4-6": {"inputTokens": 10_000, "outputTokens": 0,
                                              "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0}},
    }))

    resp = app_client.get("/claude-usage")
    assert resp.status_code == 200
    body = resp.json()
    # stale path → warning in the envelope
    assert body.get("warning") is not None
    assert "stale" in body["warning"]
    assert stale_date in body["warning"]
    # data.stale flag is also set
    assert body["data"]["stale"] is True
    assert body["data"]["asOf"] == stale_date


def test_get_usage_non_claude_model_excluded_from_by_model_api(app_client):
    """A non-Claude model in stats-cache is excluded from byModel at the API layer
    (not just unit-level). Only claude-* keys surface in the response."""
    import json

    today = _today()
    fix = app_client._stats_fixture  # type: ignore[attr-defined]
    fix.write_text(json.dumps({
        "lastComputedDate": today,
        "dailyModelTokens": [{"date": today, "tokensByModel": {
            "claude-opus-4-7": 100_000,
            "MiniMax-Text-01": 4_660_000_000,   # garbage non-Claude model
        }}],
        "modelUsage": {
            "claude-opus-4-7": {"inputTokens": 100_000, "outputTokens": 0,
                                "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0},
            "MiniMax-Text-01": {"inputTokens": 4_660_000_000, "outputTokens": 0,
                                "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0},
        },
    }))

    resp = app_client.get("/claude-usage")
    assert resp.status_code == 200
    by_model = resp.json()["data"]["byModel"]
    model_names = [b["model"] for b in by_model]
    assert all(m.startswith("claude-") for m in model_names), \
        f"Non-Claude models leaked into byModel: {model_names}"
    assert "MiniMax-Text-01" not in model_names
    # cost must NOT include MiniMax's garbage tokens — costUSD at sonnet fallback
    # for 4.66B tokens would be ~$14k; the real cost for 100k opus tokens is ~$0.50
    cost_usd = resp.json()["data"]["costUSD"]
    assert cost_usd < 10.0, f"Non-Claude cost leaked: costUSD={cost_usd}"


def test_get_usage_cost_usd_derived_when_zero_in_cache(app_client):
    """costUSD=0 in the raw cache → service DERIVES it from the pricing table.
    We can't inject a raw 'costUSD' field since the service computes it; verify
    that a known token count produces a non-zero derived cost."""
    import json

    today = _today()
    fix = app_client._stats_fixture  # type: ignore[attr-defined]
    fix.write_text(json.dumps({
        "lastComputedDate": today,
        "dailyModelTokens": [{"date": today, "tokensByModel": {"claude-sonnet-4-6": 1_000_000}}],
        "modelUsage": {
            "claude-sonnet-4-6": {
                "inputTokens": 1_000_000, "outputTokens": 0,
                "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0,
                # note: no explicit costUSD key — service derives it
            }
        },
    }))

    resp = app_client.get("/claude-usage")
    assert resp.status_code == 200
    d = resp.json()["data"]
    # 1M sonnet input @ $3/1M = $3.00
    assert d["costUSD"] == pytest.approx(3.0, abs=0.01)
    assert d["byModel"][0]["costUSD"] == pytest.approx(3.0, abs=0.01)


def test_get_usage_pct_zero_when_no_tokens(app_client):
    """An empty stats-cache (no token data) → pct=0, used=0, source='none'."""
    from core.config import settings

    # Remove the stats-cache so there's truly no source
    import json
    fix = app_client._stats_fixture  # type: ignore[attr-defined]
    fix.unlink()

    resp = app_client.get("/claude-usage")
    assert resp.status_code == 200
    d = resp.json()["data"]
    assert d["used"] == 0
    # NG1: pct is the quota-window % — no snapshot here → None (honest), not 0.0/used·cap.
    assert d["pct"] is None
    assert d["source"] == "none"
