"""tests/test_responses.py — unit tests for core/responses (C4 envelope helper)."""

from __future__ import annotations

from core.responses import err, ok


def test_ok_omits_warning_when_none():
    assert ok({"x": 1}) == {"success": True, "data": {"x": 1}}


def test_ok_includes_warning_when_given():
    assert ok([], warning="partial") == {"success": True, "data": [], "warning": "partial"}


def test_ok_default_data_is_none():
    assert ok() == {"success": True, "data": None}


def test_err_shape():
    body = err("boom", data={"id": 7})
    assert body == {"success": False, "data": {"id": 7}, "warning": "boom"}
