"""modules/claude_usage/pricing.py — model rate table (Sprint 7).

USD per 1M tokens (input/output), copied from ClaudeManager `lib/pricing.ts`
(read-only ref, architect-ruled: opus 15/75). Cache tokens ARE priced (architect
adopted the fuller formula): cache-read 0.1× input rate, cache-create 1.25× input
rate. Unknown model → FALLBACK sonnet rate. Cost is DERIVED (stats-cache costUSD
is often 0) and tagged provenance "derived:pricing-table".
"""

from __future__ import annotations

# USD per 1,000,000 tokens, (input, output).
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-haiku-3-5": (0.8, 4.0),
}

# Used when the model is unknown to the table.
FALLBACK: tuple[float, float] = (3.0, 15.0)  # sonnet


def _rate_for(model: str) -> tuple[float, float]:
    """Rate for a model: exact match first, then longest-prefix match, else fallback.

    e.g. "claude-sonnet-4-5-20250929" has no exact entry → prefix-matches
    "claude-sonnet-4-5" → (3, 15).
    """
    if model in PRICING:
        return PRICING[model]
    # longest known key that is a prefix of the model id
    candidates = [k for k in PRICING if model.startswith(k)]
    if candidates:
        return PRICING[max(candidates, key=len)]
    return FALLBACK


CACHE_READ_MULT = 0.1    # cache-read tokens cost 0.1× the input rate
CACHE_CREATE_MULT = 1.25  # cache-create (write) tokens cost 1.25× the input rate


def compute_cost(
    tokens_in: int,
    tokens_out: int,
    model: str | None,
    cache_read: int = 0,
    cache_create: int = 0,
) -> float:
    """USD cost for a model's tokens at its rate. 0 if all token counts are zero.

    Includes cache cost (architect-adopted): cache-read at 0.1× input rate,
    cache-create at 1.25× input rate. Unknown model → sonnet fallback.
    """
    if not (tokens_in or tokens_out or cache_read or cache_create):
        return 0.0
    rate_in, rate_out = _rate_for(model) if model else FALLBACK
    cost = (
        tokens_in * rate_in
        + tokens_out * rate_out
        + cache_read * CACHE_READ_MULT * rate_in
        + cache_create * CACHE_CREATE_MULT * rate_in
    ) / 1_000_000
    return round(cost, 4)
