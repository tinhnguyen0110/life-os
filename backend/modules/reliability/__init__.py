"""modules/reliability — Agent Reliability Harness (Sprint W8 A3).

ONE module that RUNS + MEASURES the reliability of life-os's OWN agents — it does
NOT reinvent grounding, it builds the HARNESS that PROVES the grounding works. The
"supervise + trust the AI" thesis made a tool.

Targets (life-os's own, deterministic — no LLM, no live-agent calls):
  - the wiki citation-verify (A1b, `modules/wiki/citations.verify_citations`) — run an
    ADVERSARIAL corpus of fabricated + real citations through it, assert each lands
    the expected status (a fabricated span MUST be rejected).
  - the MCP no-write/no-mutate gates (read_server / write_server) — re-assert the
    capability separation programmatically.

THE central constraint (verify-with-the-distinguishing-case): a wrong harness is
worse than none, so the harness has its OWN teeth — a deliberately-broken checker
(always "verified") run through it REPORTS FAIL; the real checker REPORTS PASS. The
runner takes the checker fn via dependency injection so both can be exercised.

NEW auto-discovered module (router exports MODULE) — no core/main.py edit.
"""
