"""tests/test_projects_dev_activity.py — PROJECTS-UNIFY T1 (#112): per-project dev-activity slug-join.

projects id = slug(folder) (lowercase); dev_activity stores repo = basename RAW-case. The join key =
slug(dev_activity.repo) == project_id, at the READ layer ONLY. The load-bearing teeth:
  - slug(dev_activity-repo) == project slug → the join returns the REAL aggregated commits/locNet;
  - 🔴 a project NOT in the dev_activity scan → found:false + commits:0 + reason (HONEST, NOT a fake 0);
  - slug-COLLISION (2 different repos, same basename → same slug) → BOTH returned + warning (not merged silently);
  - case-insensitive project_id (the #105 lookup convention);
  - REST GET /projects/{id}/dev-activity ≡ MCP project_dev_activity (#24).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from modules.dev_activity import service as dev_service
from modules.dev_activity import store as dev_store
from modules.projects import service as svc


def _vn_day(offset: int = 0) -> str:
    d = dev_service._now().astimezone(dev_service.VN_TZ).date() + timedelta(days=offset)
    return d.strftime("%Y-%m-%d")


@pytest.fixture
def db(isolated_paths):
    dev_store.init_dev_activity_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


# --------------------------------------------------------------------------- #
# slug-join — RAW-case dev_activity repo matches the lowercase project slug      #
# --------------------------------------------------------------------------- #
def test_slug_join_matches_raw_case_repo(db):
    """dev_activity stores 'OutboundOS' (raw case); a project_id 'outboundos' (slug) must JOIN to it
    (slug('OutboundOS')=='outboundos') and return the REAL aggregated commits."""
    dev_store.upsert_day(date=_vn_day(0), repo="OutboundOS", source="you", commits=3,
                         loc_added=100, loc_deleted=40, first_ts=None, last_ts=None)
    dev_store.upsert_day(date=_vn_day(-1), repo="OutboundOS", source="you", commits=2,
                         loc_added=20, loc_deleted=5, first_ts=None, last_ts=None)
    stat = svc.dev_stat_for_project("outboundos", days=30)
    assert stat.found is True
    assert stat.commits == 5  # 3 + 2
    assert stat.locNet == (100 - 40) + (20 - 5)  # 75
    assert stat.lastActiveDay == _vn_day(0)
    assert stat.activeDays == 2
    assert stat.reason is None and stat.warning is None


def test_join_aggregates_multiple_sources_same_repo(db):
    """Both 'you' + 'other' source rows for the same repo+day sum into the project's commits."""
    dev_store.upsert_day(date=_vn_day(0), repo="DevCrew", source="you", commits=4,
                         loc_added=10, loc_deleted=0, first_ts=None, last_ts=None)
    dev_store.upsert_day(date=_vn_day(0), repo="DevCrew", source="other", commits=6,
                         loc_added=30, loc_deleted=10, first_ts=None, last_ts=None)
    stat = svc.dev_stat_for_project("devcrew", days=7)
    assert stat.found is True and stat.commits == 10  # 4 + 6
    assert stat.activeDays == 1  # same day


# --------------------------------------------------------------------------- #
# 🔴 honest not-found — registered/queried project NOT in the scan → found:false  #
# --------------------------------------------------------------------------- #
def test_unscanned_project_is_found_false_not_fake_zero(db):
    """THE DISTINGUISHING case: a project whose repo is NOT in the dev_activity scan → found:false +
    commits:0 + a reason — NOT a silent 0-as-if-real."""
    dev_store.upsert_day(date=_vn_day(0), repo="OutboundOS", source="you", commits=3,
                         loc_added=1, loc_deleted=0, first_ts=None, last_ts=None)
    stat = svc.dev_stat_for_project("not-scanned-project", days=30)
    assert stat.found is False
    assert stat.commits == 0 and stat.locNet == 0 and stat.lastActiveDay is None
    assert stat.reason and "scan" in stat.reason.lower()  # honest WHY
    assert stat.matches == []


def test_empty_dev_activity_is_found_false(db):
    """No dev_activity rows at all → any project → found:false honest (no fabricated commits)."""
    stat = svc.dev_stat_for_project("anything", days=30)
    assert stat.found is False and stat.commits == 0


# --------------------------------------------------------------------------- #
# slug-collision — 2 different repos, same basename/slug → BOTH + warning         #
# --------------------------------------------------------------------------- #
def test_slug_collision_returns_both_with_warning(db):
    """Two repos that slug to the SAME id (e.g. 'My-App' + 'my_app' → 'my-app') → found:true, summed,
    matches[] lists BOTH (distinguished by raw repo), + a warning (honest, not silently merged)."""
    dev_store.upsert_day(date=_vn_day(0), repo="My-App", source="you", commits=2,
                         loc_added=10, loc_deleted=0, first_ts=None, last_ts=None)
    dev_store.upsert_day(date=_vn_day(0), repo="my_app", source="you", commits=3,
                         loc_added=5, loc_deleted=1, first_ts=None, last_ts=None)
    # both slug to 'my-app'
    from modules.projects.reader import slug
    assert slug("My-App") == "my-app" == slug("my_app")
    stat = svc.dev_stat_for_project("my-app", days=7)
    assert stat.found is True
    assert stat.commits == 5  # 2 + 3 summed
    assert len(stat.matches) == 2
    assert {m.repo for m in stat.matches} == {"My-App", "my_app"}  # both, distinguished by raw repo
    assert stat.warning and "collision" in stat.warning.lower()  # honest, not silent


# --------------------------------------------------------------------------- #
# case-insensitive project_id + days clamp                                       #
# --------------------------------------------------------------------------- #
def test_case_insensitive_project_id(db):
    dev_store.upsert_day(date=_vn_day(0), repo="OutboundOS", source="you", commits=1,
                         loc_added=1, loc_deleted=0, first_ts=None, last_ts=None)
    for variant in ("outboundos", "OutboundOS", "OUTBOUNDOS"):
        assert svc.dev_stat_for_project(variant, days=7).found is True


def test_days_clamped_to_at_least_one(db):
    dev_store.upsert_day(date=_vn_day(0), repo="X", source="you", commits=1,
                         loc_added=0, loc_deleted=0, first_ts=None, last_ts=None)
    stat = svc.dev_stat_for_project("x", days=0)  # clamped to ≥1
    assert stat.days == 1


def test_window_excludes_rows_before_since(db):
    """A commit OLDER than the window must NOT count (the join respects the days window)."""
    dev_store.upsert_day(date=_vn_day(-10), repo="OutboundOS", source="you", commits=9,
                         loc_added=0, loc_deleted=0, first_ts=None, last_ts=None)
    stat = svc.dev_stat_for_project("outboundos", days=3)  # window = last 3 days, excludes day -10
    assert stat.found is False or stat.commits == 0  # the old commit is out of the window


# --------------------------------------------------------------------------- #
# REST + MCP parity (#24)                                                        #
# --------------------------------------------------------------------------- #
def test_rest_endpoint_real_join(api):
    dev_store.upsert_day(date=_vn_day(0), repo="OutboundOS", source="you", commits=3,
                         loc_added=10, loc_deleted=2, first_ts=None, last_ts=None)
    r = api.get("/projects/outboundos/dev-activity?days=30")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["found"] is True and d["commits"] == 3 and d["projectId"] == "outboundos"


def test_rest_unscanned_is_200_found_false(api):
    """found:false is a valid HONEST answer → 200, not a 404."""
    r = api.get("/projects/ghost-project/dev-activity")
    assert r.status_code == 200
    assert r.json()["data"]["found"] is False


def test_mcp_matches_rest(api):
    from mcp_servers import read_server as rs
    dev_store.upsert_day(date=_vn_day(0), repo="DevCrew", source="you", commits=4,
                         loc_added=5, loc_deleted=1, first_ts=None, last_ts=None)
    rest = api.get("/projects/devcrew/dev-activity?days=30").json()["data"]
    mcp = rs.project_dev_activity("devcrew", days=30)
    assert mcp == rest, "MCP project_dev_activity must be byte-identical to REST"
