"""tests/test_agent_errors.py — AGENT-ERROR Phase-1 (#46): the agent_error helper + closed enum.

agent_error(code, message, hint, retryable) → {"error":{code,message,hint,retryable}} — a structured,
agent-readable error so an AI agent branches on a CLOSED code + a retryable bool instead of parsing
free text. THE invariant: deterministic codes (NOT_FOUND/INVALID_INPUT/CONFLICT) are ALWAYS
retryable=False (retrying loops forever); transient codes (UPSTREAM_DOWN/RATE_LIMITED) MAY be True.
"""

from __future__ import annotations

from typing import get_args

import pytest

from core.agent_errors import ErrorCode, agent_error

ALL_CODES = list(get_args(ErrorCode))
DETERMINISTIC = {"NOT_FOUND", "INVALID_INPUT", "CONFLICT"}
TRANSIENT = {"UPSTREAM_DOWN", "RATE_LIMITED"}


# --------------------------------------------------------------------------- #
# shape                                                                          #
# --------------------------------------------------------------------------- #
def test_shape_is_error_wrapper_with_four_fields():
    e = agent_error("NOT_FOUND", "no such note 99", hint="pass a valid note id")
    assert set(e) == {"error"}
    inner = e["error"]
    assert set(inner) == {"code", "message", "hint", "retryable"}
    assert inner["code"] == "NOT_FOUND"
    assert inner["message"] == "no such note 99"
    assert inner["hint"] == "pass a valid note id"
    assert isinstance(inner["retryable"], bool)


def test_hint_defaults_to_empty_string():
    assert agent_error("INVALID_INPUT", "bad value")["error"]["hint"] == ""


# --------------------------------------------------------------------------- #
# the closed enum — exactly 6 codes, each builds                                 #
# --------------------------------------------------------------------------- #
def test_enum_is_exactly_the_closed_six():
    assert set(ALL_CODES) == {
        "NOT_FOUND", "INVALID_INPUT", "AMBIGUOUS",
        "UPSTREAM_DOWN", "RATE_LIMITED", "CONFLICT",
    }
    assert len(ALL_CODES) == 6


@pytest.mark.parametrize("code", ALL_CODES, ids=ALL_CODES)
def test_each_code_builds_with_its_code_echoed(code):
    e = agent_error(code, "msg")  # type: ignore[arg-type]
    assert e["error"]["code"] == code


def test_unknown_code_raises():
    with pytest.raises(ValueError):
        agent_error("KABOOM", "nope")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# retryable — the invariant (the heart of #46-P1)                                #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("code", sorted(DETERMINISTIC), ids=sorted(DETERMINISTIC))
def test_deterministic_codes_default_not_retryable(code):
    """NOT_FOUND / INVALID_INPUT / CONFLICT default retryable=False (retrying is useless)."""
    assert agent_error(code, "m")["error"]["retryable"] is False  # type: ignore[arg-type]


@pytest.mark.parametrize("code", sorted(DETERMINISTIC), ids=sorted(DETERMINISTIC))
def test_deterministic_codes_REJECT_retryable_true(code):
    """The enforced invariant: passing retryable=True for a deterministic code RAISES (a deterministic
    failure marked retryable would loop forever — it's a programming error, not a silent bad-flag)."""
    with pytest.raises(ValueError):
        agent_error(code, "m", retryable=True)  # type: ignore[arg-type]


@pytest.mark.parametrize("code", sorted(TRANSIENT), ids=sorted(TRANSIENT))
def test_transient_codes_default_retryable_true(code):
    """UPSTREAM_DOWN / RATE_LIMITED default retryable=True (a retry may succeed)."""
    assert agent_error(code, "m")["error"]["retryable"] is True  # type: ignore[arg-type]


@pytest.mark.parametrize("code", sorted(TRANSIENT), ids=sorted(TRANSIENT))
def test_transient_codes_can_be_overridden_false(code):
    """A transient code MAY be set retryable=False explicitly (the caller decides) — allowed, no raise."""
    assert agent_error(code, "m", retryable=False)["error"]["retryable"] is False  # type: ignore[arg-type]


def test_ambiguous_defaults_not_retryable():
    """AMBIGUOUS is not transient — same ambiguous input → same ambiguity → default retryable=False
    (the agent must DISAMBIGUATE, not retry). But it MAY be set True (not in the never-retryable set)."""
    assert agent_error("AMBIGUOUS", "matched 3 notes")["error"]["retryable"] is False
    # not deterministic-locked → True is allowed without raising
    assert agent_error("AMBIGUOUS", "m", retryable=True)["error"]["retryable"] is True


def test_no_code_is_both_in_never_retryable_and_transient():
    """Sanity: the deterministic (never-retryable) set and the transient set are disjoint."""
    assert DETERMINISTIC.isdisjoint(TRANSIENT)
