"""tests/test_activity.py — activity feed reader + GET /activity + stats (Sprint 10B, SPEC §S14).

BEHAVIOR-TESTED (not field-read): seed run_log rows → call get_feed() → assert computed
stats match the hand-calc against the REAL schema.

Key schema facts (from schema.py + service.py + router.py — FROZEN):
  - successRate = round(ok/count*100, 1) — PERCENTAGE (0–100), None when count==0
  - get_feed(routine, status, range) — param is `range` (not range_key)
  - RoutineBreakdown.routine = routine id (NOT routineId)
  - byRoutine sorted DESC by count (most runs first)
  - cap: count = FULL filtered total; runs[] = newest-100 slice
  - runsToday = unfiltered all-runs today count (independent of active filter)
  - Filters LENIENT: unknown status/range → ignored (returns all), NOT 422 (router.py)
  - GET /activity?status=garbage → 200 (lenient, no 422)
  - GET /activity/{int} → 200/404; non-int → FastAPI 422

DISTINGUISHING CASE (memory: verify-with-the-distinguishing-case):
  Fixture A (warn-heavy):  3 ok + 2 warn  → successRate=60.0, warnCount=2, errorCount=0
  Fixture B (error-heavy): 3 ok + 2 error → successRate=60.0, warnCount=0, errorCount=2
  SAME successRate but DIFFERENT breakdown — proves successRate=ok/total*100 AND
  breakdown composition is tracked independently.

Baseline: pytest 575/575, vitest 310/310.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modules.activity import service as activity_service
from modules.activity.schema import ActivityFeed, ActivityRun, RoutineBreakdown

# =========================================================================== #
# Helpers                                                                       #
# =========================================================================== #

def _iso(offset_seconds: int = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return dt.isoformat()


def _seed(routine_id: str, status: str, *, started_offset: int = 0,
          finished_offset: int | None = None, detail: str = "") -> None:
    """Insert one run_log row via db.record_run."""
    from store import db
    started = _iso(started_offset)
    finished = _iso(finished_offset) if finished_offset is not None else None
    db.record_run(routine_id, status, started, finished_at=finished, detail=detail)


# =========================================================================== #
# SECTION A — SERVICE (isolated_paths, pure unit)                               #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Shape + newest-first order                                                    #
# --------------------------------------------------------------------------- #

def test_feed_shape_and_newest_first(isolated_paths):
    """ActivityFeed shape + runs are newest-first (startedAt desc)."""
    _seed("idle-hunter",   "ok",    started_offset=-30, finished_offset=-25)
    _seed("pattern-check", "warn",  started_offset=-20, finished_offset=-15)
    _seed("idle-hunter",   "error", started_offset=-10, finished_offset=-5)

    feed = activity_service.get_feed()
    assert isinstance(feed, ActivityFeed)
    assert feed.count == 3
    assert len(feed.runs) == 3
    # Newest-first
    assert feed.runs[0].startedAt > feed.runs[1].startedAt > feed.runs[2].startedAt

    run = feed.runs[0]
    assert isinstance(run, ActivityRun)
    assert run.routineId in ("idle-hunter", "pattern-check")
    assert run.status in ("ok", "warn", "error")
    assert isinstance(run.id, int)
    assert run.startedAt


def test_feed_activityrun_fields(isolated_paths):
    """ActivityRun carries routineName (from catalog), durationMs when finished, detail."""
    _seed("idle-hunter", "warn",
          started_offset=-10, finished_offset=-8, detail="2 idle projects")
    feed = activity_service.get_feed()
    run = feed.runs[0]
    assert run.routineId == "idle-hunter"
    assert run.routineName == "Idle Hunter"
    assert run.detail == "2 idle projects"
    assert run.durationMs is not None and run.durationMs >= 0


def test_feed_null_finished_gives_null_duration(isolated_paths):
    """Run with null finished_at → durationMs=None, excluded from avgDurationMs."""
    _seed("market-poll", "ok", started_offset=-20, finished_offset=-15)  # ~5000ms
    _seed("market-poll", "ok", started_offset=-5,  finished_offset=None)  # no finish

    feed = activity_service.get_feed()
    unfinished = next(r for r in feed.runs if r.finishedAt is None)
    assert unfinished.durationMs is None
    assert feed.avgDurationMs is not None and feed.avgDurationMs > 0


# --------------------------------------------------------------------------- #
# Stats math — hand-calc on a known fixture                                     #
# --------------------------------------------------------------------------- #

def test_stats_handcalc_ok_warn_error(isolated_paths):
    """Hand-calc: 2 ok, 1 warn, 1 error → count=4, successRate=round(2/4*100,1)=50.0,
    okCount=2, warnCount=1, errorCount=1."""
    _seed("idle-hunter",   "ok",    started_offset=-40, finished_offset=-38)
    _seed("idle-hunter",   "ok",    started_offset=-30, finished_offset=-28)
    _seed("pattern-check", "warn",  started_offset=-20, finished_offset=-18)
    _seed("pattern-check", "error", started_offset=-10, finished_offset=-8)

    feed = activity_service.get_feed()
    assert feed.count == 4
    assert feed.okCount == 2
    assert feed.warnCount == 1
    assert feed.errorCount == 1
    # successRate = round(2/4*100, 1) = 50.0 (PERCENTAGE)
    assert feed.successRate == 50.0


def test_avgduration_handcalc(isolated_paths):
    """avgDurationMs = int(round(mean of finished durations)), in ms."""
    from store import db
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    def _ts(secs): return (t0 + timedelta(seconds=secs)).isoformat()
    db.record_run("idle-hunter", "ok", _ts(0),  finished_at=_ts(2),  detail="")  # 2000ms
    db.record_run("idle-hunter", "ok", _ts(10), finished_at=_ts(16), detail="")  # 6000ms
    db.record_run("idle-hunter", "ok", _ts(20), finished_at=None,    detail="")  # excluded

    feed = activity_service.get_feed()
    # avg = int(round((2000 + 6000) / 2)) = 4000
    assert feed.avgDurationMs == 4000


def test_byRoutine_grouping_sorted_by_count(isolated_paths):
    """byRoutine groups by routineId, fields use 'routine' key, sorted DESC by count."""
    _seed("idle-hunter",   "ok",   started_offset=-50)
    _seed("idle-hunter",   "warn", started_offset=-40)
    _seed("idle-hunter",   "ok",   started_offset=-30)
    _seed("pattern-check", "ok",   started_offset=-20)

    feed = activity_service.get_feed()
    # idle-hunter has 3 runs, pattern-check has 1 → idle-hunter first (sorted DESC)
    assert feed.byRoutine[0].routine == "idle-hunter"

    by_r = {g.routine: g for g in feed.byRoutine}
    assert by_r["idle-hunter"].count == 3
    assert by_r["idle-hunter"].okCount == 2
    assert by_r["idle-hunter"].warnCount == 1
    assert by_r["idle-hunter"].routineName == "Idle Hunter"
    assert by_r["pattern-check"].count == 1


# --------------------------------------------------------------------------- #
# DISTINGUISHING CASE — successRate=percentage; breakdown is separate           #
# (memory: verify-with-the-distinguishing-case)                                 #
# --------------------------------------------------------------------------- #

def test_successrate_DISTINGUISHING_warn_heavy_vs_error_heavy(isolated_paths):
    """DISTINGUISHING CASE: two fixtures with identical successRate (60.0) but
    different warn/error composition. Proves successRate=round(ok/total*100,1) AND
    the breakdown (warnCount/errorCount) is tracked independently.

    Fixture A (warn-heavy):  3 ok + 2 warn  → successRate=60.0, warnCount=2, errorCount=0
    Fixture B (error-heavy): 3 ok + 2 error → successRate=60.0, warnCount=0, errorCount=2

    TEETH: if successRate included warns (ok+warn)/total → A=100.0 not 60.0.
           if breakdown not independent → A and B would look identical.
    """
    from store import db
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    def _ts(secs): return (t0 + timedelta(seconds=secs)).isoformat()

    # -- Fixture A: 3 ok + 2 warn --
    for i in range(3):
        db.record_run("idle-hunter", "ok",   _ts(i*10), finished_at=_ts(i*10+2), detail="")
    for i in range(2):
        db.record_run("idle-hunter", "warn", _ts(30+i*10), finished_at=_ts(30+i*10+2), detail="")

    feed_a = activity_service.get_feed()
    assert feed_a.count == 5
    assert feed_a.okCount == 3 and feed_a.warnCount == 2 and feed_a.errorCount == 0
    assert feed_a.successRate == 60.0, \
        f"Fixture A successRate wrong: {feed_a.successRate!r} (expected 60.0)"

    # -- Reset run_log, seed Fixture B: 3 ok + 2 error --
    # close_db() drops the connection but NOT the data; DELETE the rows to start fresh.
    conn = db.get_conn()
    conn.execute("DELETE FROM run_log")
    conn.commit()

    for i in range(3):
        db.record_run("idle-hunter", "ok",    _ts(i*10), finished_at=_ts(i*10+2), detail="")
    for i in range(2):
        db.record_run("idle-hunter", "error", _ts(30+i*10), finished_at=_ts(30+i*10+2), detail="")

    feed_b = activity_service.get_feed()
    assert feed_b.count == 5
    assert feed_b.okCount == 3 and feed_b.warnCount == 0 and feed_b.errorCount == 2
    assert feed_b.successRate == 60.0, \
        f"Fixture B successRate wrong: {feed_b.successRate!r} (expected 60.0)"

    # THE DISTINGUISHING ASSERTIONS
    assert feed_a.successRate == feed_b.successRate, \
        "successRate must be identical (both 60.0) — same ok/total ratio"
    assert feed_a.warnCount != feed_b.warnCount, \
        f"warnCount must DIFFER: A={feed_a.warnCount}, B={feed_b.warnCount}"
    assert feed_a.errorCount != feed_b.errorCount, \
        f"errorCount must DIFFER: A={feed_a.errorCount}, B={feed_b.errorCount}"


# --------------------------------------------------------------------------- #
# Empty run_log                                                                  #
# --------------------------------------------------------------------------- #

def test_empty_feed(isolated_paths):
    """Empty run_log → all-null/zero stats, never raises."""
    feed = activity_service.get_feed()
    assert feed.count == 0 and feed.runs == []
    assert feed.okCount == 0 and feed.warnCount == 0 and feed.errorCount == 0
    assert feed.successRate is None   # None, NOT 0.0
    assert feed.avgDurationMs is None
    assert feed.runsToday == 0
    assert feed.byRoutine == []


def test_successrate_none_when_no_runs(isolated_paths):
    """successRate must be None (not 0.0) for empty feed."""
    assert activity_service.get_feed().successRate is None


# --------------------------------------------------------------------------- #
# Cap: runs[] capped at 100 (newest); count = FULL filtered total               #
# --------------------------------------------------------------------------- #

def test_cap_100_runs_count_is_full_total(isolated_paths):
    """Seed 110 rows. runs[] = newest-100; count = 110 (full total, not capped)."""
    for i in range(110):
        _seed("market-poll", "ok", started_offset=-(110 - i))
    feed = activity_service.get_feed()
    assert feed.count == 110, f"count should be full total 110, got {feed.count}"
    assert len(feed.runs) == 100, f"runs[] capped at 100, got {len(feed.runs)}"
    # Capped runs are the NEWEST 100
    assert feed.runs[0].startedAt > feed.runs[-1].startedAt


# --------------------------------------------------------------------------- #
# Filters: routine, status, range                                               #
# --------------------------------------------------------------------------- #

def test_filter_by_routine(isolated_paths):
    """routine='idle-hunter' returns only idle-hunter rows."""
    _seed("idle-hunter",   "ok",   started_offset=-30)
    _seed("pattern-check", "warn", started_offset=-20)
    _seed("idle-hunter",   "warn", started_offset=-10)

    feed = activity_service.get_feed(routine="idle-hunter")
    assert all(r.routineId == "idle-hunter" for r in feed.runs)
    assert feed.count == 2


def test_filter_by_status_ok(isolated_paths):
    """status='ok' returns only ok rows (affects runs and count)."""
    _seed("idle-hunter",   "ok",    started_offset=-30)
    _seed("pattern-check", "warn",  started_offset=-20)
    _seed("idle-hunter",   "error", started_offset=-10)

    feed = activity_service.get_feed(status="ok")
    assert all(r.status == "ok" for r in feed.runs)
    assert feed.count == 1


def test_filter_by_status_garbage_returns_all(isolated_paths):
    """status='garbage' → IGNORED (lenient), returns all rows, NOT 422."""
    _seed("idle-hunter", "ok",   started_offset=-20)
    _seed("idle-hunter", "warn", started_offset=-10)

    feed = activity_service.get_feed(status="garbage-invalid")
    assert feed.count == 2, \
        f"invalid status should be ignored (lenient), got count={feed.count}"


def test_filter_range_today(isolated_paths):
    """range='today' returns only rows started today (UTC)."""
    from store import db
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=2)
    db.record_run("idle-hunter", "ok", now.isoformat(), finished_at=None, detail="today")
    db.record_run("idle-hunter", "ok", old.isoformat(), finished_at=None, detail="old")

    feed = activity_service.get_feed(range="today")
    assert feed.count == 1
    assert feed.runs[0].detail == "today"


def test_filter_range_7d(isolated_paths):
    """range='7d' returns rows within last 7 days."""
    from store import db
    now = datetime.now(timezone.utc)
    db.record_run("idle-hunter", "ok", now.isoformat(), finished_at=None, detail="now")
    db.record_run("idle-hunter", "ok", (now - timedelta(days=5)).isoformat(),
                  finished_at=None, detail="5d")
    db.record_run("idle-hunter", "ok", (now - timedelta(days=10)).isoformat(),
                  finished_at=None, detail="10d")

    feed = activity_service.get_feed(range="7d")
    assert feed.count == 2
    assert "10d" not in {r.detail for r in feed.runs}


def test_filter_range_week(isolated_paths):
    """range='week' is also 7 days (alias)."""
    from store import db
    now = datetime.now(timezone.utc)
    db.record_run("idle-hunter", "ok", now.isoformat(), finished_at=None, detail="now")
    db.record_run("idle-hunter", "ok", (now - timedelta(days=10)).isoformat(),
                  finished_at=None, detail="10d")

    feed = activity_service.get_feed(range="week")
    assert feed.count == 1
    assert feed.runs[0].detail == "now"


def test_filter_range_all_returns_everything(isolated_paths):
    """range='all' returns all rows regardless of date."""
    from store import db
    now = datetime.now(timezone.utc)
    db.record_run("idle-hunter", "ok",
                  (now - timedelta(days=100)).isoformat(), finished_at=None, detail="old")
    db.record_run("idle-hunter", "ok", now.isoformat(), finished_at=None, detail="new")

    feed = activity_service.get_feed(range="all")
    assert feed.count == 2


def test_filter_range_garbage_returns_all(isolated_paths):
    """range='garbage' → IGNORED (lenient), returns all rows, NOT 422."""
    _seed("idle-hunter", "ok", started_offset=-20)
    _seed("idle-hunter", "ok", started_offset=-10)

    feed = activity_service.get_feed(range="garbage")
    assert feed.count == 2, f"invalid range should be ignored, got count={feed.count}"


def test_filter_combined_routine_and_status(isolated_paths):
    """routine + status filters are AND-combined."""
    _seed("idle-hunter",   "ok",   started_offset=-40)
    _seed("idle-hunter",   "warn", started_offset=-30)
    _seed("pattern-check", "ok",   started_offset=-20)

    feed = activity_service.get_feed(routine="idle-hunter", status="ok")
    assert feed.count == 1
    assert feed.runs[0].routineId == "idle-hunter"
    assert feed.runs[0].status == "ok"


# --------------------------------------------------------------------------- #
# runsToday is unfiltered (independent of active filter)                        #
# --------------------------------------------------------------------------- #

def test_runs_today_is_unfiltered(isolated_paths):
    """runsToday = today's total across ALL routines/statuses regardless of filter."""
    from store import db
    now = datetime.now(timezone.utc)
    db.record_run("idle-hunter",   "ok",   now.isoformat(), finished_at=None, detail="")
    db.record_run("idle-hunter",   "warn", now.isoformat(), finished_at=None, detail="")
    db.record_run("pattern-check", "ok",   now.isoformat(), finished_at=None, detail="")

    # Filter to only idle-hunter ok (1 row) — but runsToday should still be 3
    feed = activity_service.get_feed(routine="idle-hunter", status="ok")
    assert feed.count == 1              # filtered count
    assert feed.runsToday == 3         # UNFILTERED today total


# --------------------------------------------------------------------------- #
# get_run — found / not found                                                   #
# --------------------------------------------------------------------------- #

def test_get_run_by_id_found(isolated_paths):
    """get_run(id) returns the ActivityRun for a known run_log row."""
    _seed("idle-hunter", "warn", started_offset=-10, finished_offset=-8,
          detail="2 idle projects")
    feed = activity_service.get_feed()
    run_id = feed.runs[0].id  # db.all_runs selects id column

    fetched = activity_service.get_run(run_id)
    assert fetched is not None
    assert fetched.id == run_id
    assert fetched.routineId == "idle-hunter"
    assert fetched.status == "warn"
    assert fetched.detail == "2 idle projects"


def test_get_run_unknown_returns_none(isolated_paths):
    """get_run(999999) returns None (router → 404)."""
    assert activity_service.get_run(999999) is None


# =========================================================================== #
# SECTION B — API (skip-guarded: server at :8001 WITH activity module loaded)   #
# =========================================================================== #

requests = pytest.importorskip("requests", reason="requests not installed")

BASE = "http://localhost:8001"


def _server_up() -> bool:
    try:
        return requests.get(f"{BASE}/health", timeout=2).status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def server():
    """Skip API section if server not up OR pre-T1 (activity module not registered)."""
    if not _server_up():
        pytest.skip("BE server not running at :8001 — API tests skipped")
    try:
        r = requests.get(f"{BASE}/health", timeout=2)
        modules = r.json()["data"].get("modules", [])
        if "activity" not in modules:
            pytest.skip("Server predates S10B-T1 — restart needed for /activity")
    except Exception:
        pytest.skip("Could not determine server module list")


def test_api_health_includes_activity(server):
    """GET /health lists 'activity' in loaded modules."""
    modules = requests.get(f"{BASE}/health", timeout=5).json()["data"].get("modules", [])
    assert "activity" in modules, f"'activity' not in modules: {modules}"


def test_api_get_activity_envelope(server):
    """GET /activity → {success:true, data:{runs[], count, runsToday, okCount, warnCount,
    errorCount, successRate, avgDurationMs, byRoutine[]}}."""
    r = requests.get(f"{BASE}/activity", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    d = body["data"]
    for field in ("runs", "count", "runsToday", "okCount", "warnCount", "errorCount",
                  "successRate", "avgDurationMs", "byRoutine"):
        assert field in d, f"missing field '{field}'"
    assert isinstance(d["runs"], list) and isinstance(d["count"], int)


def test_api_get_activity_real_s10a_rows(server):
    """LIVE value-by-value: GET /activity contains real S10A run_log rows.
    At minimum: market-poll ok and idle-hunter warn rows exist from S10A verification."""
    runs = requests.get(f"{BASE}/activity", timeout=5).json()["data"]["runs"]
    assert len(runs) > 0, "Expected S10A runs in run_log, got empty feed"

    routine_ids = {run["routineId"] for run in runs}
    assert "market-poll" in routine_ids or "idle-hunter" in routine_ids, \
        f"Expected S10A routine ids, got: {routine_ids}"

    # ActivityRun shape
    run = runs[0]
    for field in ("id", "routineId", "routineName", "status", "detail",
                  "startedAt", "finishedAt", "durationMs"):
        assert field in run, f"ActivityRun missing field '{field}'"
    assert run["status"] in ("ok", "warn", "error")
    assert run["routineName"]


def test_api_successrate_is_percentage(server):
    """LIVE: successRate is a percentage (0–100), not a fraction."""
    d = requests.get(f"{BASE}/activity", timeout=5).json()["data"]
    sr = d["successRate"]
    if sr is not None:
        assert 0.0 <= sr <= 100.0, \
            f"successRate should be 0-100 (percentage), got {sr}"
        # Extra sanity: if all runs are ok, should be 100.0
        if d["okCount"] == d["count"] and d["count"] > 0:
            assert sr == 100.0


def test_api_filter_by_routine(server):
    """GET /activity?routine=market-poll returns only market-poll rows."""
    runs = requests.get(f"{BASE}/activity?routine=market-poll", timeout=5).json()["data"]["runs"]
    if runs:
        assert all(r["routineId"] == "market-poll" for r in runs)


def test_api_filter_status_warn(server):
    """GET /activity?status=warn returns only warn rows."""
    runs = requests.get(f"{BASE}/activity?status=warn", timeout=5).json()["data"]["runs"]
    if runs:
        assert all(r["status"] == "warn" for r in runs)


def test_api_filter_status_garbage_is_200_lenient(server):
    """GET /activity?status=garbage → 200 (lenient — ignored, NOT 422)."""
    r = requests.get(f"{BASE}/activity?status=garbage", timeout=5)
    assert r.status_code == 200, \
        f"invalid status should return 200 (lenient), got {r.status_code}"
    assert r.json()["success"] is True


def test_api_filter_range_today_200(server):
    """GET /activity?range=today → 200."""
    r = requests.get(f"{BASE}/activity?range=today", timeout=5)
    assert r.status_code == 200


def test_api_filter_range_7d_200(server):
    """GET /activity?range=7d → 200."""
    assert requests.get(f"{BASE}/activity?range=7d", timeout=5).status_code == 200


def test_api_filter_range_garbage_is_200_lenient(server):
    """GET /activity?range=garbage → 200 (lenient — ignored, NOT 422)."""
    r = requests.get(f"{BASE}/activity?range=garbage", timeout=5)
    assert r.status_code == 200, \
        f"invalid range should return 200 (lenient), got {r.status_code}"


def test_api_byRoutine_fields(server):
    """GET /activity byRoutine entries have all RoutineBreakdown fields.
    Field is 'routine' (id), NOT 'routineId'."""
    by = requests.get(f"{BASE}/activity", timeout=5).json()["data"]["byRoutine"]
    if by:
        entry = by[0]
        for field in ("routine", "routineName", "count", "okCount",
                      "warnCount", "errorCount", "lastRun"):
            assert field in entry, f"byRoutine entry missing '{field}'"
        assert "routineId" not in entry, \
            "byRoutine must use 'routine' (not 'routineId') per schema"


def test_api_get_run_by_id(server):
    """GET /activity/{id} for a real row → 200 + ActivityRun shape."""
    runs = requests.get(f"{BASE}/activity", timeout=5).json()["data"]["runs"]
    if not runs:
        pytest.skip("No runs in feed")
    run_id = runs[0]["id"]

    r = requests.get(f"{BASE}/activity/{run_id}", timeout=5)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == run_id
    assert data["routineId"] == runs[0]["routineId"]
    assert data["status"] == runs[0]["status"]


def test_api_get_run_unknown_404(server):
    """GET /activity/999999999 → 404."""
    assert requests.get(f"{BASE}/activity/999999999", timeout=5).status_code == 404


def test_api_get_run_non_int_422(server):
    """GET /activity/not-an-int → 422 (FastAPI auto-validates int path param)."""
    assert requests.get(f"{BASE}/activity/not-an-int", timeout=5).status_code == 422


def test_api_idle_hunter_warn_has_detail(server):
    """LIVE: idle-hunter warn row has non-empty detail mentioning idle projects (S10A)."""
    runs = requests.get(
        f"{BASE}/activity?routine=idle-hunter&status=warn", timeout=5
    ).json()["data"]["runs"]
    if runs:
        assert runs[0]["detail"], "idle-hunter warn row should have non-empty detail"


# =========================================================================== #
# SECTION C — CHROME STUBS (skip-guarded, after T3 FE lands)                   #
# =========================================================================== #

@pytest.mark.skip(reason="Chrome UI verify pending T3 FE (Sprint 10B)")
def test_chrome_activity_screen_real_runs():
    """[STUB] /activity renders S10A's real runs value-by-value vs GET /activity.
    Status chips: ✓ok / ⚠warn / ✗error. routineName + relative time visible."""
    pass


@pytest.mark.skip(reason="Chrome UI verify pending T3 FE (Sprint 10B)")
def test_chrome_click_row_shows_detail():
    """[STUB] Click a run row → detail panel shows the full detail text."""
    pass


@pytest.mark.skip(reason="Chrome UI verify pending T3 FE (Sprint 10B)")
def test_chrome_filter_tabs():
    """[STUB] Filter tabs all/ok/err filter displayed rows correctly."""
    pass


@pytest.mark.skip(reason="Chrome UI verify pending T3 FE (Sprint 10B)")
def test_chrome_cap_banner():
    """[STUB] When count>100: cap banner shows "100 gần nhất / tổng N"."""
    pass


@pytest.mark.skip(reason="Chrome UI verify pending T3 FE (Sprint 10B)")
def test_chrome_home_activity_widget_live():
    """[STUB] /home Activity widget is live (not stub) — shows real recent runs."""
    pass


@pytest.mark.skip(reason="Chrome UI verify pending T3 FE (Sprint 10B)")
def test_chrome_console_clean():
    """[STUB] Console 0 errors, 0 warnings, 0 unhandled on /activity."""
    pass
