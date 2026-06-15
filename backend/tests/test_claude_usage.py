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
    # opus 4.5+ NEW tier 5/25: 1M in + 1M out = 5 + 25 = 30 (verified vs official docs)
    assert pricing.compute_cost(1_000_000, 1_000_000, "claude-opus-4-7") == 30.0
    # deprecated opus 4.1 stays 15/75
    assert pricing.compute_cost(1_000_000, 1_000_000, "claude-opus-4-1") == 90.0
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
def test_get_usage_no_sources_empty_mode(tmp_path, monkeypatch, isolated_paths):
    # both transcripts (isolated absent by conftest) AND stats-cache absent → empty mode
    monkeypatch.setattr(service.settings, "claude_stats_path", tmp_path / "absent.json")
    u = service.get_usage()
    assert isinstance(u, ClaudeUsage)
    assert u.source == "none" and u.tokenSource == "none"
    assert u.used == 0 and u.today == 0 and u.byModel == [] and u.series == []
    assert u.byProject == [] and u.costUSD == 0.0
    assert u.stale is False  # empty mode: asOf=today, not stale
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
    # byModel: opus 4.7 NEW tier 5/25 → total 2M = 30 ; sonnet 2M = 6
    by = {b.model: b for b in u.byModel}
    # opus 4.7: (1M*5 + 1M*25)/1e6 = 30 + negligible cache dust (5 read, 3 create)
    assert by["claude-opus-4-7"].costUSD == pytest.approx(30.0, abs=0.01)
    assert by["claude-sonnet-4-6"].costUSD == 6.0  # 2M*3/1e6 (no cache)
    assert by["claude-opus-4-7"].total == 2_000_000
    assert by["claude-opus-4-7"].cacheReadTokens == 5
    # top-level cost = 30 + 6 = 36 (+ cache dust)
    assert u.costUSD == pytest.approx(36.0, abs=0.01)
    # model (top-level) = highest total; tie 2M each → first after sort
    assert u.model in ("claude-opus-4-7", "claude-sonnet-4-6")
    assert u.source == "stats-cache"
    # cap default 200_000. NG1: pct is the QUOTA-window % (pct5h/weekly), NOT used/cap.
    # No quota snapshot in this fixture → pct is honest-None (never the used/cap garbage).
    assert u.cap == 200_000
    assert u.pct is None


def test_NG1_pct_is_none_without_quota_snapshot(stats_file, isolated_paths):
    """NG1 (source fix): pct is the quota-window % (pct5h/weekly), NOT used/cap. With
    no quota snapshot, pct is None (honest) — NEVER the absurd used/cap ratio that
    leaked ~4500% to every consumer."""
    stats_file({"lastComputedDate": _iso(0),
                "dailyModelTokens": [{"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 50_000}}],
                "modelUsage": {}})
    u = service.get_usage()
    assert u.pct is None  # no snapshot → None, not 25.0 (used/cap), not 4500


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
    # NG1: pct no longer divides by cap (it's pct5h/weelky/None) → no ZeroDivisionError
    # regardless of cap; with no snapshot here, pct is None.
    assert u.pct is None
    # used(100) > cap(0) → remaining is honest-None (token quota unknown), not 0.
    assert u.remaining is None


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
    # cost: only opus-4-7 1M input @ 5 (NEW tier) = $5, NOT $55K from MiniMax
    assert u.costUSD == 5.0
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
    # a future opus id prefix-matches the "claude-opus" family → opus rate (15/1M),
    # NOT the sonnet catch-all. Only a model with no claude family prefix hits fallback.
    assert u.byModel[0].costUSD == 5.0  # unknown OPUS → opus family rate, NEW tier (1M*5/1e6)


# --------------------------------------------------------------------------- #
# service — manual override                                                     #
# --------------------------------------------------------------------------- #
def test_set_override_cap_and_stubs(stats_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0),
                "dailyModelTokens": [{"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 100}}],
                "modelUsage": {}})
    u = service.set_override(ManualOverride(cap=500, resetIn="3h 12m", weekly=80))
    assert u.cap == 500
    assert u.resetIn == "3h 12m"  # stub now set via override
    assert u.weekly == 80
    # NG1: pct now derives from the weekly window % (no pct5h snapshot here), NOT used/cap.
    assert u.pct == 80.0
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
    # stats-cache fallback path (no transcripts): byProject is [] (empty, not None)
    assert u.resetIn is None and u.weekly is None and u.byProject == []


# --------------------------------------------------------------------------- #
# LIVE quota snapshot (statusline tee) — 5h/7d/context + reset countdown        #
# --------------------------------------------------------------------------- #
@pytest.fixture
def quota_file(tmp_path, monkeypatch):
    """Write a known quota-snapshot fixture + point config at it (NOT real ~/.claude)."""
    def _write(data: dict):
        p = tmp_path / "quota-snapshot.json"
        p.write_text(json.dumps(data))
        monkeypatch.setattr(service.settings, "claude_quota_path", p)
        return p
    return _write


def _epoch_in(minutes: int) -> int:
    """Unix epoch `minutes` from now (for resets_at). +5s pad so the floor-based
    countdown lands on the whole `minutes` despite test wall-clock drift."""
    return int((datetime.now(timezone.utc) + timedelta(minutes=minutes, seconds=5)).timestamp())


def test_quota_snapshot_live_fields(stats_file, quota_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    quota_file({
        "five_hour": {"used_percentage": 6, "resets_at": _epoch_in(75)},   # 1h 15m
        "seven_day": {"used_percentage": 42, "resets_at": _epoch_in(200)},
        "context": {"used_percentage": 54},
    })
    u = service.get_usage()
    assert u.quotaSource == "snapshot"
    assert u.pct5h == 6.0
    assert u.weekly == 42            # 7d used % → weekly
    assert u.ctxPct == 54.0
    assert u.resetIn == "1h 15m"     # 5h reset countdown from resets_at
    assert u.resetWeek == "3h 20m"
    # NG1: pct = the quota-window % = pct5h (preferred), NOT used/cap.
    assert u.pct == 6.0


def test_NG1_pct_falls_back_to_weekly_when_no_pct5h(stats_file, quota_file, isolated_paths):
    """NG1: pct5h absent but weekly present → pct = weekly (still a sane window %),
    never used/cap."""
    stats_file({"lastComputedDate": _iso(0),
                "dailyModelTokens": [{"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 9_000_000}}],
                "modelUsage": {}})
    quota_file({  # NO five_hour → pct5h None; seven_day present → weekly drives pct
        "seven_day": {"used_percentage": 71, "resets_at": _epoch_in(200)},
    })
    u = service.get_usage()
    assert u.pct5h is None and u.weekly == 71
    assert u.pct == 71.0           # falls back to weekly, NOT used/cap (~4500%)
    assert u.pct <= 100.0


def test_quota_reset_minutes_only(stats_file, quota_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    quota_file({"five_hour": {"used_percentage": 10, "resets_at": _epoch_in(24)}})
    u = service.get_usage()
    assert u.resetIn == "24m"        # < 1h → minutes only


def test_quota_reset_rolls_hours_into_days(stats_file, quota_file, isolated_paths):
    # a 7-day reset (≥ 24h) reads as "Xd Yh", not "147h 25m"
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    quota_file({
        "five_hour": {"used_percentage": 5, "resets_at": _epoch_in(90)},       # 1h 30m
        "seven_day": {"used_percentage": 6, "resets_at": _epoch_in(6 * 1440 + 3 * 60)},  # 6d 3h
    })
    u = service.get_usage()
    assert u.resetIn == "1h 30m"     # < 24h still h+m
    assert u.resetWeek == "6d 3h"    # ≥ 24h → days + hours (minutes dropped)


def test_quota_past_reset_is_none(stats_file, quota_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    quota_file({"five_hour": {"used_percentage": 10, "resets_at": _epoch_in(-30)}})  # already past
    u = service.get_usage()
    assert u.resetIn is None         # past reset → no fake countdown


def test_quota_absent_is_stub(stats_file, isolated_paths):
    # no quota_file → snapshot absent → quotaSource stub, live fields None
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    u = service.get_usage()
    assert u.quotaSource == "stub"
    assert u.pct5h is None and u.resetWeek is None and u.ctxPct is None


def test_manual_override_beats_snapshot(stats_file, quota_file, isolated_paths):
    # override resetIn/weekly must win over the live snapshot (priority: manual > snapshot)
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    quota_file({"five_hour": {"used_percentage": 6, "resets_at": _epoch_in(75)},
                "seven_day": {"used_percentage": 42}})
    service.set_override(ManualOverride(resetIn="9h 9m", weekly=99))
    u = service.get_usage()
    assert u.quotaSource == "manual"
    assert u.resetIn == "9h 9m" and u.weekly == 99
    # but raw live fields still surface for transparency
    assert u.pct5h == 6.0


def test_malformed_quota_snapshot_no_crash(stats_file, quota_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    quota_file({"five_hour": "not-a-dict", "seven_day": None, "context": 123})
    u = service.get_usage()
    assert u.quotaSource == "stub"   # nothing parseable → stub, never raises
    assert u.pct5h is None


# --------------------------------------------------------------------------- #
# LIVE transcripts (.jsonl) — primary token source + byProject                  #
# --------------------------------------------------------------------------- #
from modules.claude_usage import transcripts as _tx


def _asst_line(model: str, cwd: str, date: str, out: int, in_: int = 0, cr: int = 0, cc: int = 0) -> str:
    """One assistant-message JSONL line with a usage block."""
    return json.dumps({
        "type": "assistant", "timestamp": f"{date}T12:00:00.000Z", "cwd": cwd,
        "message": {"model": model, "usage": {
            "input_tokens": in_, "output_tokens": out,
            "cache_read_input_tokens": cr, "cache_creation_input_tokens": cc,
        }},
    })


@pytest.fixture
def projects_dir(tmp_path, monkeypatch):
    """Build a fake ~/.claude/projects with given {slug: [lines]} + point config at it."""
    def _write(layout: dict[str, list[str]]):
        base = tmp_path / "projects"
        base.mkdir(exist_ok=True)
        for slug, lines in layout.items():
            d = base / slug
            d.mkdir(exist_ok=True)
            (d / "sess.jsonl").write_text("\n".join(lines) + "\n")
        monkeypatch.setattr(service.settings, "claude_projects_dir", base)
        _tx._CACHE.clear()
        return base
    return _write


def test_transcripts_is_primary_source(projects_dir, isolated_paths):
    today = _iso(0)
    projects_dir({
        "-home-x-OutboundOS": [
            _asst_line("claude-opus-4-8", "/home/x/OutboundOS", today, out=1000, in_=10),
            _asst_line("claude-opus-4-8", "/home/x/OutboundOS", today, out=2000, in_=20),
        ],
        "-home-x-life-os": [
            _asst_line("claude-sonnet-4-6", "/home/x/life-os", today, out=500, in_=5),
        ],
    })
    u = service.get_usage()
    assert u.tokenSource == "transcripts" and u.source == "transcripts"
    assert u.today == 3500           # 1000+2000 (OutboundOS) + 500 (life-os), same day
    assert u.stale is False          # today's data
    assert u.model == "claude-opus-4-8"  # top model by tokens


def test_transcripts_byproject_priced_per_model(projects_dir, isolated_paths):
    today = _iso(0)
    projects_dir({
        "-a": [_asst_line("claude-opus-4-8", "/home/x/OutboundOS", today, out=1_000_000, in_=1_000_000)],
        "-b": [_asst_line("claude-sonnet-4-6", "/home/x/life-os", today, out=1_000_000, in_=1_000_000)],
    })
    u = service.get_usage()
    projects = {p.project: p for p in u.byProject}
    assert set(projects) == {"OutboundOS", "life-os"}
    # opus 4.8 NEW 5/25: 1M in + 1M out = 30 ; sonnet 3/15: = 18 → priced per project's OWN model
    assert projects["OutboundOS"].costUSD == 30.0
    assert projects["life-os"].costUSD == 18.0
    # sorted total desc — equal totals, stable; both present
    assert projects["OutboundOS"].msgs == 1


def test_transcripts_excludes_non_claude_and_tmp(projects_dir, isolated_paths):
    today = _iso(0)
    projects_dir({
        "-real": [
            _asst_line("claude-opus-4-8", "/home/x/real", today, out=1000),
            _asst_line("MiniMax-M2.7", "/home/x/real", today, out=9_999_999),  # non-claude → excluded
        ],
        "-tmp": [_asst_line("claude-opus-4-8", "/tmp/scratch", today, out=5000)],  # -tmp slug skipped
    })
    u = service.get_usage()
    assert u.today == 1000  # only the claude line in -real; MiniMax + -tmp excluded
    assert all(b.model.startswith("claude-") for b in u.byModel)


def test_transcripts_incremental_cache(projects_dir, isolated_paths):
    today = _iso(0)
    base = projects_dir({"-a": [_asst_line("claude-opus-4-8", "/home/x/a", today, out=100)]})
    a1 = service.get_usage().today
    assert a1 == 100
    # second call hits the mtime cache (no error, same result)
    assert service.get_usage().today == 100


def test_transcripts_malformed_lines_skipped(projects_dir, isolated_paths):
    today = _iso(0)
    projects_dir({"-a": [
        "{not valid json",
        _asst_line("claude-opus-4-8", "/home/x/a", today, out=777),
        '{"type":"user","message":{}}',  # no usage
    ]})
    u = service.get_usage()
    assert u.today == 777  # only the one good assistant line counted, no crash


def test_transcripts_empty_dir_falls_back_to_stats(projects_dir, stats_file, isolated_paths):
    # empty projects dir → transcripts None → stats-cache fallback
    projects_dir({})  # no project subdirs
    stats_file({"lastComputedDate": _iso(0),
                "dailyModelTokens": [{"date": _iso(0), "tokensByModel": {"claude-opus-4-7": 42}}],
                "modelUsage": {}})
    u = service.get_usage()
    assert u.tokenSource == "stats-cache"
    assert u.today == 42


# --------------------------------------------------------------------------- #
# pricing — full Claude line + family-prefix fallback                           #
# --------------------------------------------------------------------------- #
def test_pricing_full_model_line():
    # every family priced at its tier (1M input only → input rate), verified vs docs
    assert pricing.compute_cost(1_000_000, 0, "claude-opus-4-8") == 5.0   # NEW 4.5+ tier
    assert pricing.compute_cost(1_000_000, 0, "claude-opus-4-5") == 5.0
    assert pricing.compute_cost(1_000_000, 0, "claude-opus-4-1") == 15.0  # deprecated tier
    assert pricing.compute_cost(1_000_000, 0, "claude-3-opus") == 15.0
    assert pricing.compute_cost(1_000_000, 0, "claude-sonnet-4-6") == 3.0
    assert pricing.compute_cost(1_000_000, 0, "claude-3-5-sonnet") == 3.0
    assert pricing.compute_cost(1_000_000, 0, "claude-haiku-4-5") == 1.0
    assert pricing.compute_cost(1_000_000, 0, "claude-3-haiku") == 0.25
    # Fable 5 premium tier (10/50, not the sonnet fallback)
    assert pricing.compute_cost(1_000_000, 0, "claude-fable-5") == 10.0


def test_pricing_family_prefix_for_unknown_dated_variant():
    # a brand-new dated opus id prefix-matches the opus family → CURRENT 5/25 tier
    assert pricing.compute_cost(1_000_000, 0, "claude-opus-4-9-20270101") == 5.0
    # a non-claude model still hits the fallback (sonnet)
    assert pricing.compute_cost(1_000_000, 0, "gpt-5.4") == 3.0


def test_pricing_cache_write_5m_vs_1h():
    # cache-create split: 5m = 1.25× input, 1h = 2× input (sonnet input 3/MTok)
    # 1M all-5m: 1M * 1.25 * 3 / 1e6 = 3.75
    assert pricing.compute_cost(0, 0, "claude-sonnet-4-6", cache_create=1_000_000) == 3.75
    # 1M all-1h: 1M * 2.0 * 3 / 1e6 = 6.0
    assert pricing.compute_cost(0, 0, "claude-sonnet-4-6", cache_create=1_000_000, cache_create_1h=1_000_000) == 6.0
    # mixed 50/50: 0.5M*1.25*3 + 0.5M*2*3 all /1e6 = 1.875 + 3.0 = 4.875
    assert pricing.compute_cost(0, 0, "claude-sonnet-4-6", cache_create=1_000_000, cache_create_1h=500_000) == 4.875


# --------------------------------------------------------------------------- #
# context (current-session window — model-dependent, NOT a quota)               #
# --------------------------------------------------------------------------- #
def test_context_session_fields_from_snapshot(stats_file, quota_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    quota_file({
        "five_hour": {"used_percentage": 0},
        "context": {"used_percentage": 32, "total_input_tokens": 323_106, "context_window_size": 1_000_000},
        "model": "Opus 4.8 (1M context)",
    })
    u = service.get_usage()
    assert u.ctxUsed == 323_106
    assert u.ctxMax == 1_000_000      # opus 1M window (sonnet would be 200k)
    assert u.ctxPct == 32.0
    assert u.ctxModel == "Opus 4.8 (1M context)"


def test_context_absent_when_no_snapshot(stats_file, isolated_paths):
    stats_file({"lastComputedDate": _iso(0), "dailyModelTokens": [], "modelUsage": {}})
    u = service.get_usage()
    assert u.ctxUsed is None and u.ctxMax is None and u.ctxModel is None
