"""tests/test_claude_usage.py — claude-usage schema + reader + service (Sprint 7).

Behavior-test math against a KNOWN fixture stats-cache (hand-calc today/series/
avg/peak/byModel/cost). Fail-open on missing/malformed. Reader path points at a
fixture, NEVER the real ~/.claude. mock-free (no network).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from modules.claude_usage import pricing, reader, service
from modules.claude_usage.schema import ClaudeUsage, ManualOverride


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


@pytest.fixture
def stats_file(tmp_path, monkeypatch):
    """Write a known stats-cache fixture + point config at it (NOT real ~/.claude)."""
    def _write(data: dict):
        p = tmp_path / "stats-cache.json"
        p.write_text(json.dumps(data))
        monkeypatch.setattr(service.settings, "claude_stats_path", p)
        return p
    return _write


# --------------------------------------------------------------------------- #
# pricing                                                                       #
# --------------------------------------------------------------------------- #
def test_pricing_exact_match():
    # opus 15/75: 1M in + 1M out = 15 + 75 = 90
    assert pricing.compute_cost(1_000_000, 1_000_000, "claude-opus-4-7") == 90.0
    # sonnet 3/15
    assert pricing.compute_cost(1_000_000, 0, "claude-sonnet-4-6") == 3.0
    # haiku 1/5
    assert pricing.compute_cost(0, 1_000_000, "claude-haiku-4-5") == 5.0


def test_pricing_prefix_match():
    # dated variant prefix-matches the base rate
    assert pricing.compute_cost(1_000_000, 0, "claude-sonnet-4-5-20250929") == 3.0


def test_pricing_unknown_fallback_sonnet():
    assert pricing.compute_cost(1_000_000, 0, "some-unknown-model") == 3.0
    assert pricing.compute_cost(1_000_000, 0, None) == 3.0


def test_pricing_zero_tokens():
    assert pricing.compute_cost(0, 0, "claude-opus-4-7") == 0.0
    assert pricing.compute_cost(0, 0, "claude-opus-4-7", cache_read=0, cache_create=0) == 0.0


def test_pricing_includes_cache():
    # cache-read 0.1× input, cache-create 1.25× input (sonnet input rate = 3/1M)
    # 1M cache_read = 1M*0.1*3/1e6 = 0.3 ; 1M cache_create = 1M*1.25*3/1e6 = 3.75
    assert pricing.compute_cost(0, 0, "claude-sonnet-4-6", cache_read=1_000_000) == 0.3
    assert pricing.compute_cost(0, 0, "claude-sonnet-4-6", cache_create=1_000_000) == 3.75
    # cache-only tokens still produce a cost (not zero)
    assert pricing.compute_cost(0, 0, "claude-opus-4-7", cache_read=1_000_000) > 0


# --------------------------------------------------------------------------- #
# reader fail-open                                                              #
# --------------------------------------------------------------------------- #
def test_reader_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(service.settings, "claude_stats_path", tmp_path / "nope.json")
    assert reader.read_stats() is None


def test_reader_malformed_json_returns_none(tmp_path, monkeypatch):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json")
    monkeypatch.setattr(service.settings, "claude_stats_path", p)
    assert reader.read_stats() is None


def test_reader_non_object_returns_none(tmp_path, monkeypatch):
    p = tmp_path / "arr.json"
    p.write_text("[1,2,3]")
    monkeypatch.setattr(service.settings, "claude_stats_path", p)
    assert reader.read_stats() is None


# --------------------------------------------------------------------------- #
# service — fail-open manual mode                                               #
# --------------------------------------------------------------------------- #
def test_get_usage_no_stats_cache_manual_mode(tmp_path, monkeypatch, isolated_paths):
    monkeypatch.setattr(service.settings, "claude_stats_path", tmp_path / "absent.json")
    u = service.get_usage()
    assert isinstance(u, ClaudeUsage)
    assert u.source == "manual"
    assert u.used == 0 and u.today == 0 and u.byModel == [] and u.series == []
    assert u.costUSD == 0.0
    assert u.stale is False  # manual mode: asOf=today, not stale
    assert u.peak.tokens == 0  # zero-day


# --------------------------------------------------------------------------- #
# service — real fixture, hand-calc math                                        #
# --------------------------------------------------------------------------- #
def test_get_usage_handcalc(stats_file, isolated_paths):
    today = _iso(0)
    stats_file({
        "lastComputedDate": today,
        "dailyModelTokens": [
            {"date": _iso(2), "tokensByModel": {"claude-opus-4-7": 100, "claude-sonnet-4-6": 50}},  # 150
            {"date": _iso(1), "tokensByModel": {"claude-opus-4-7": 300}},  # 300 (peak)
            {"date": _iso(0), "tokensByModel": {"claude-sonnet-4-6": 200}},  # 200 (today)
        ],
        "modelUsage": {
            "claude-opus-4-7": {"inputTokens": 1_000_000, "outputTokens": 1_000_000,
                                "cacheReadInputTokens": 5, "cacheCreationInputTokens": 3, "costUSD": 0},
            "claude-sonnet-4-6": {"inputTokens": 2_000_000, "outputTokens": 0,
                                  "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0, "costUSD": 0},
        },
    })
    u = service.get_usage()
    # today = latest entry sum = 200
    assert u.today == 200 and u.used == 200
    # series 3 entries, sums 150/300/200 → avg = round(650/3) = 217
    assert len(u.series) == 3
    assert u.avgPerDay == round(650 / 3)  # 217
    # peak = 300 day
    assert u.peak.tokens == 300
    # byModel: opus total 2M (cost 90), sonnet total 2M (cost 6) → sorted by total desc (tie → insertion/stable)
    by = {b.model: b for b in u.byModel}
    # opus: (1M*15 + 1M*75)/1e6 = 90 + negligible cache dust (5 read, 3 create)
    assert by["claude-opus-4-7"].costUSD == pytest.approx(90.0, abs=0.01)
    assert by["claude-sonnet-4-6"].costUSD == 6.0  # 2M*3/1e6 (no cache)
    assert by["claude-opus-4-7"].total == 2_000_000
    assert by["claude-opus-4-7"].cacheReadTokens == 5
    # top-level cost = 90 + 6 = 96 (+ cache dust)
    assert u.costUSD == pytest.approx(96.0, abs=0.01)
    # model (top-level) = highest total; tie 2M each → first after sort
    assert u.model in ("claude-opus-4-7", "claude-sonnet-4-6")
    assert u.source == "stats-cache"
    # cap default 200_000, pct = round(200/200000*100,1) = 0.1
    assert u.cap == 200_000
    assert u.pct == round(200 / 200_000 * 100, 1)


def test_pct_carries_used_and_cap(stats_file, isolated_paths):
    """pct is verifiable from used + cap on the payload (self-describing)."""
    stats_file({"lastComputedDate": _iso(0),
                "dailyModelTokens": [{"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 50_000}}],
                "modelUsage": {}})
    u = service.get_usage()
    assert u.pct == round(u.used / u.cap * 100, 1)  # checkable from the same payload


def test_stale_flag_when_lastcomputed_old(stats_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(30),  # 30 days behind
                "dailyModelTokens": [{"date": _iso(30), "tokensByModel": {"claude-opus-4-7": 100}}],
                "modelUsage": {}})
    u = service.get_usage()
    assert u.stale is True
    assert u.asOf == _iso(30)


def test_not_stale_when_lastcomputed_today(stats_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0),
                "dailyModelTokens": [{"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 100}}],
                "modelUsage": {}})
    assert service.get_usage().stale is False


def test_stale_grace_yesterday_is_fresh(stats_file, isolated_paths):
    """1-day grace: a cache computed YESTERDAY is still fresh (not stale)."""
    stats_file({"lastComputedDate": _iso(1),  # yesterday
                "dailyModelTokens": [{"date": _iso(1), "tokensByModel": {"claude-opus-4-7": 100}}],
                "modelUsage": {}})
    assert service.get_usage().stale is False


def test_stale_two_days_ago_is_stale(stats_file, isolated_paths):
    """Older than yesterday → stale."""
    stats_file({"lastComputedDate": _iso(2),  # 2 days ago
                "dailyModelTokens": [{"date": _iso(2), "tokensByModel": {"claude-opus-4-7": 100}}],
                "modelUsage": {}})
    assert service.get_usage().stale is True


# --------------------------------------------------------------------------- #
# service — defensive edges                                                     #
# --------------------------------------------------------------------------- #
def test_empty_daily_model_tokens(stats_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    u = service.get_usage()
    assert u.series == [] and u.today == 0 and u.avgPerDay == 0 and u.peak.tokens == 0


def test_malformed_section_skipped(stats_file, isolated_paths):
    # dailyModelTokens has a junk entry + a good one; modelUsage has a junk value
    stats_file({
        "lastComputedDate": _iso(0),
        "dailyModelTokens": ["not a dict", {"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 10}}],
        "modelUsage": {"claude-opus-4-7": {"inputTokens": 100, "outputTokens": 0},
                       "bad-model": "not a dict"},
    })
    u = service.get_usage()
    assert len(u.series) == 1 and u.today == 10  # junk entry skipped
    assert len(u.byModel) == 1  # junk model skipped


def test_unknown_model_uses_fallback(stats_file, isolated_paths):
    # unknown CLAUDE model (a non-claude one would be excluded entirely)
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [],
                "modelUsage": {"claude-future-x": {"inputTokens": 1_000_000, "outputTokens": 0}}})
    u = service.get_usage()
    assert u.byModel[0].costUSD == 3.0  # sonnet fallback rate, no crash


def test_cap_zero_no_div_by_zero(stats_file, monkeypatch, isolated_paths):
    monkeypatch.setattr(service.settings, "claude_usage_cap", 0)
    stats_file({"lastComputedDate": _iso(0),
                "dailyModelTokens": [{"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 100}}],
                "modelUsage": {}})
    u = service.get_usage()
    assert u.pct == 0.0  # guarded, no ZeroDivisionError
    assert u.remaining == 0


# --------------------------------------------------------------------------- #
# service — Claude-only filter (the real-cache bug: non-Claude models excluded) #
# --------------------------------------------------------------------------- #
def test_non_claude_models_excluded_from_everything(stats_file, isolated_paths):
    """REAL-cache bug: stats-cache has non-Claude models (MiniMax 4.66B tokens).
    They must be excluded from byModel/used/today/series/cost — else MiniMax priced
    at the sonnet fallback headlines a $55K garbage cost on the CLAUDE screen.
    RED without the is_claude() filter (MiniMax would dominate)."""
    today = _iso(0)
    stats_file({
        "lastComputedDate": today,
        "dailyModelTokens": [{"date": today, "tokensByModel": {
            "claude-opus-4-7": 100_000,
            "MiniMax-M2.7": 4_660_000_000,   # 4.66B — must NOT count
            "glm-5.1": 50_000_000,           # must NOT count
        }}],
        "modelUsage": {
            "claude-opus-4-7": {"inputTokens": 1_000_000, "outputTokens": 0,
                                "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0},
            "MiniMax-M2.7": {"inputTokens": 4_660_000_000, "outputTokens": 1_000_000_000,
                             "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0},
            "glm-5.1": {"inputTokens": 50_000_000, "outputTokens": 0,
                        "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0},
        },
    })
    u = service.get_usage()
    # byModel: ONLY claude
    assert [b.model for b in u.byModel] == ["claude-opus-4-7"]
    assert all(b.model.startswith("claude-") for b in u.byModel)
    # today/used: only the 100k claude tokens, NOT the billions of MiniMax
    assert u.today == 100_000 and u.used == 100_000
    assert u.series[-1].tokens == 100_000
    # cost: only opus 1M input @ 15 = $15, NOT $55K from MiniMax at sonnet rates
    assert u.costUSD == 15.0
    assert u.model == "claude-opus-4-7"  # top claude model, not MiniMax


def test_unknown_claude_model_uses_fallback_but_non_claude_excluded(stats_file, isolated_paths):
    """Fallback catches an UNKNOWN claude model (future opus), never a non-Claude one."""
    stats_file({
        "lastComputedDate": _iso(0), "dailyModelTokens": [],
        "modelUsage": {
            "claude-opus-4-9-future": {"inputTokens": 1_000_000, "outputTokens": 0},  # unknown CLAUDE
            "MiniMax-M2.7": {"inputTokens": 9_999_999_999, "outputTokens": 0},        # non-Claude
        },
    })
    u = service.get_usage()
    assert [b.model for b in u.byModel] == ["claude-opus-4-9-future"]  # MiniMax dropped
    assert u.byModel[0].costUSD == 3.0  # unknown CLAUDE → sonnet fallback (1M*3/1e6)


# --------------------------------------------------------------------------- #
# service — manual override                                                     #
# --------------------------------------------------------------------------- #
def test_set_override_cap_and_stubs(stats_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0),
                "dailyModelTokens": [{"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 100}}],
                "modelUsage": {}})
    u = service.set_override(ManualOverride(cap=500, resetIn="3h 12m", weekly=80_000))
    assert u.cap == 500
    assert u.resetIn == "3h 12m"  # stub now set via override
    assert u.weekly == 80_000
    assert u.pct == round(100 / 500 * 100, 1)
    # persisted: a fresh get_usage reflects it
    assert service.get_usage().cap == 500


def test_override_absent_uses_defaults(stats_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    u = service.get_usage()
    assert u.cap == 200_000 and u.resetIn is None and u.weekly is None


# --------------------------------------------------------------------------- #
# stub fields are honestly None                                                 #
# --------------------------------------------------------------------------- #
def test_stub_fields_none_without_override(stats_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    u = service.get_usage()
    assert u.resetIn is None and u.weekly is None and u.byProject is None
