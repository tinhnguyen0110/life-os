"""tests/test_journal.py — journal schema + service + stats (Sprint 9, SPEC §S7).

Behavior + hand-calc: pnl-parse fail-soft, winRate/avgPnl/ladderDiscipline/thisMonth/
calibration math on a known fixture, write-failure FAIL-CLOSED teeth, empty journal,
sparse-calibration → []. Mirrors Notes; writes = 1 git commit.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from modules.journal import service
from modules.journal.schema import JournalInput


def _now_month_date(day: int = 15) -> str:
    return datetime.now(timezone.utc).strftime(f"%Y-%m-{day:02d}T00:00:00+00:00")


# --------------------------------------------------------------------------- #
# pnl parse (fail-soft)                                                         #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw,expected", [
    ("+5.5%", 5.5), ("-4.1%", -4.1), ("18%", 18.0), ("+18", 18.0),
    ("0%", 0.0), (None, None), ("", None), ("open", None), ("n/a", None), ("garbage", None),
])
def test_parse_pnl(raw, expected):
    assert service.parse_pnl(raw) == expected


# --------------------------------------------------------------------------- #
# id / slug                                                                     #
# --------------------------------------------------------------------------- #
def test_new_id_slug_plus_hex():
    nid = service._new_id("BTC")
    assert nid.startswith("btc-") and len(nid.rsplit("-", 1)[1]) == 6


def test_new_id_fallback():
    assert service._new_id("!!!").startswith("entry-")


# --------------------------------------------------------------------------- #
# CRUD round-trip (writes = 1 commit)                                           #
# --------------------------------------------------------------------------- #
def test_create_read_round_trip(isolated_paths):
    e = service.create_entry(JournalInput(
        action="BUY", asset="BTC", size="$2,000", px="$68,240", tag="ladder",
        reason="DCA into weakness", channel="crypto", thesis="cycle bottom", confidence=70))
    assert e.id.startswith("btc-") and e.outcome == "open"
    got = service.get_entry(e.id)
    assert got is not None
    assert got.asset == "BTC" and got.reason == "DCA into weakness"
    assert got.confidence == 70 and got.thesis == "cycle bottom" and got.tag == "ladder"


def test_create_commits_to_git(isolated_paths):
    import subprocess
    e = service.create_entry(JournalInput(action="BUY", asset="ETH", reason="x"))
    log = subprocess.run(["git", "-C", str(isolated_paths / "data"), "log", "--oneline"],
                         capture_output=True, text=True).stdout
    assert f"create journal {e.id}" in log


def test_update_closes_trade_sets_outcome(isolated_paths):
    e = service.create_entry(JournalInput(action="BUY", asset="BTC", reason="x"))
    assert e.outcome == "open"
    # close with a winning pnl → outcome auto right
    closed = service.update_entry(e.id, JournalInput(action="BUY", asset="BTC", reason="x", pnl="+12%"))
    assert closed.outcome == "right" and closed.pnl == "+12%"
    assert closed.createdAt == e.createdAt  # preserved
    # losing pnl → wrong
    e2 = service.create_entry(JournalInput(action="SELL", asset="ETH", reason="y"))
    closed2 = service.update_entry(e2.id, JournalInput(action="SELL", asset="ETH", reason="y", pnl="-8%"))
    assert closed2.outcome == "wrong"


def test_update_explicit_outcome_overrides(isolated_paths):
    e = service.create_entry(JournalInput(action="BUY", asset="BTC", reason="x"))
    closed = service.update_entry(e.id, JournalInput(action="BUY", asset="BTC", reason="x", pnl="+5%", outcome="wrong"))
    assert closed.outcome == "wrong"  # user override wins despite pnl>0


def test_delete(isolated_paths):
    e = service.create_entry(JournalInput(action="BUY", asset="BTC", reason="x"))
    assert service.delete_entry(e.id) is True
    assert service.get_entry(e.id) is None
    assert service.delete_entry(e.id) is False


def test_update_unknown_returns_none(isolated_paths):
    assert service.update_entry("nope-000000", JournalInput(action="BUY", asset="X", reason="x")) is None


# --------------------------------------------------------------------------- #
# WRITE FAIL-CLOSED (the teeth — a lost entry must NOT look successful)          #
# --------------------------------------------------------------------------- #
def test_create_fail_closed_on_write_error(isolated_paths, monkeypatch):
    """md_store.write_file raising must PROPAGATE (no silent success)."""
    from store import md_store
    def boom(*a, **k):
        raise md_store.MdStoreError("disk full")
    monkeypatch.setattr(service.md_store, "write_file", boom)
    with pytest.raises(md_store.MdStoreError):
        service.create_entry(JournalInput(action="BUY", asset="BTC", reason="x"))
    # Nothing was persisted — the read path doesn't touch write_file, so list still
    # works under the (still-active) boom patch and finds zero entries. Do NOT
    # monkeypatch.undo() here: it would also undo isolated_paths' data_dir/DB_PATH
    # patches and make list_entries read the REAL backend/data (cross-test bleed).
    assert service.list_entries()[0].count == 0


def test_update_fail_closed_on_write_error(isolated_paths, monkeypatch):
    e = service.create_entry(JournalInput(action="BUY", asset="BTC", reason="x"))
    from store import md_store
    monkeypatch.setattr(service.md_store, "write_file",
                        lambda *a, **k: (_ for _ in ()).throw(md_store.MdStoreError("fail")))
    with pytest.raises(md_store.MdStoreError):
        service.update_entry(e.id, JournalInput(action="BUY", asset="BTC", reason="x", pnl="+5%"))


# --------------------------------------------------------------------------- #
# stats math (hand-calc)                                                        #
# --------------------------------------------------------------------------- #
def _seed(asset, action="BUY", tag="", pnl=None, confidence=None, date=None, reason="r"):
    return service.create_entry(JournalInput(
        action=action, asset=asset, tag=tag, pnl=pnl, confidence=confidence,
        date=date or _now_month_date(), reason=reason))


def test_stats_winrate_avgpnl_handcalc(isolated_paths):
    _seed("A", pnl="+10%")   # closed win
    _seed("B", pnl="+20%")   # closed win
    _seed("C", pnl="-5%")    # closed loss
    _seed("D", pnl=None)     # open (excluded from closed stats)
    st, _ = service.list_entries()
    assert st.count == 4
    # closed = 3 (A,B,C); wins = 2 → winRate = 2/3*100 = 66.7
    assert st.winRate == round(2 / 3 * 100, 1)
    # avgPnl = (10+20-5)/3 = 8.33
    assert st.avgPnl == round((10 + 20 - 5) / 3, 2)


def test_stats_null_when_no_closed(isolated_paths):
    _seed("A", pnl=None)
    _seed("B", pnl="open")  # unparseable → open
    st, _ = service.list_entries()
    assert st.winRate is None and st.avgPnl is None  # 0 closed → None, NOT 0


def test_ladder_discipline(isolated_paths):
    _seed("A", tag="ladder")
    _seed("B", tag="ladder")
    _seed("C", tag="dca")
    _seed("D", tag="")
    st, _ = service.list_entries()
    # 2 ladder / 4 total = 50.0
    assert st.ladderDiscipline == 50.0


def test_this_month_split(isolated_paths):
    _seed("A", action="BUY", tag="ladder", date=_now_month_date(1))
    _seed("B", action="SELL", date=_now_month_date(2))
    _seed("C", action="BUY", date="2020-01-01T00:00:00+00:00")  # old month — excluded
    st, _ = service.list_entries()
    assert st.thisMonth["total"] == 2  # A, B (C is old)
    assert st.thisMonth["buy"] == 1 and st.thisMonth["sell"] == 1 and st.thisMonth["ladder"] == 1


# --------------------------------------------------------------------------- #
# calibration (the domain stat)                                                 #
# --------------------------------------------------------------------------- #
def test_calibration_buckets_handcalc(isolated_paths):
    # actual = %(outcome=="right"). pnl>0 → outcome auto "right"; pnl<0 → "wrong".
    # band 70-79: conf 70 (right), conf 75 (wrong) → actual 50, predicted 74.5, n2
    _seed("A", pnl="+5%", confidence=70)   # outcome auto right
    _seed("B", pnl="-3%", confidence=75)   # outcome auto wrong
    # band 90-100: conf 95 (right) → actual 100, predicted 95.0, n1
    _seed("C", pnl="+8%", confidence=95)
    # open+confident → NOT closed → excluded
    _seed("D", pnl=None, confidence=82)
    # confidence < 50 → DROPPED (not a confidence claim)
    _seed("E", pnl="+1%", confidence=30)
    st, _ = service.list_entries()
    bands = {b.band: b for b in st.calibration}
    assert set(bands) == {"70-79", "90-100"}  # D open (excluded), E <50 (dropped)
    assert bands["70-79"].predicted == 74.5 and bands["70-79"].actual == 50.0 and bands["70-79"].n == 2
    assert bands["90-100"].predicted == 95.0 and bands["90-100"].actual == 100.0 and bands["90-100"].n == 1


def test_calibration_scores_THESIS_not_pnl(isolated_paths):
    """LOCKED two-axes: actual = %(outcome=='right'), NOT pnl sign. A lucky profit on a
    WRONG thesis is a calibration MISS. TEETH: RED if calibration uses pnl>0."""
    # profit (+20%) but thesis WRONG (user override) → calibration miss (actual 0, not 100)
    e1 = service.create_entry(JournalInput(action="BUY", asset="A", reason="r",
                                           date=_now_month_date(), confidence=85, pnl="+20%", outcome="wrong"))
    # loss (-10%) but thesis RIGHT → calibration hit (actual 100, not 0)
    e2 = service.create_entry(JournalInput(action="BUY", asset="B", reason="r",
                                           date=_now_month_date(), confidence=75, pnl="-10%", outcome="right"))
    st, _ = service.list_entries()
    bands = {b.band: b for b in st.calibration}
    assert bands["80-89"].actual == 0.0, "profit+wrong-thesis must be a calibration MISS (0%, not 100%)"
    assert bands["70-79"].actual == 100.0, "loss+right-thesis must be a calibration HIT (100%, not 0%)"
    # meanwhile the MONEY axis (winRate) still uses pnl: 1 win (+20%) of 2 closed = 50%
    assert st.winRate == 50.0  # money axis unchanged — two distinct axes


def test_calibration_empty_when_no_confidence(isolated_paths):
    """SPARSE-calibration edge: closed entries but ZERO confidence → [] (honest)."""
    _seed("A", pnl="+5%")  # closed, no confidence
    _seed("B", pnl="-2%")  # closed, no confidence
    st, _ = service.list_entries()
    assert st.calibration == []  # not a fabricated curve


# --------------------------------------------------------------------------- #
# empty + filters + fail-open read                                              #
# --------------------------------------------------------------------------- #
def test_empty_journal(isolated_paths):
    st, warnings = service.list_entries()
    assert st.count == 0 and st.entries == []
    assert st.winRate is None and st.avgPnl is None and st.ladderDiscipline is None
    assert st.thisMonth == {"total": 0, "buy": 0, "sell": 0, "ladder": 0}
    assert st.calibration == []


def test_filters(isolated_paths):
    _seed("BTC", action="BUY", tag="ladder")
    _seed("ETH", action="SELL", tag="dca")
    assert [e.asset for e in service.list_entries(action="BUY")[0].entries] == ["BTC"]
    assert [e.asset for e in service.list_entries(tag="dca")[0].entries] == ["ETH"]
    assert [e.asset for e in service.list_entries(asset="btc")[0].entries] == ["BTC"]  # ci


def test_malformed_entry_skipped(isolated_paths):
    good = service.create_entry(JournalInput(action="BUY", asset="BTC", reason="x"))
    from store import md_store
    md_store.write_file("journal/broken.md", "not front-matter", "junk")
    st, warnings = service.list_entries()
    assert any(e.id == good.id for e in st.entries)
    assert all(e.id != "broken" for e in st.entries)
    assert warnings


# --------------------------------------------------------------------------- #
# schema validation                                                             #
# --------------------------------------------------------------------------- #
def test_confidence_out_of_range_rejected():
    with pytest.raises(Exception):
        JournalInput(action="BUY", asset="X", reason="x", confidence=150)


def test_empty_asset_reason_rejected():
    with pytest.raises(Exception):
        JournalInput(action="BUY", asset="", reason="x")
    with pytest.raises(Exception):
        JournalInput(action="BUY", asset="X", reason="")


def test_action_must_be_buy_sell():
    with pytest.raises(Exception):
        JournalInput(action="HOLD", asset="X", reason="x")
