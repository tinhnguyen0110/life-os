"""modules/claude_usage/pricing.py — model rate table + cost formula.

Rates VERIFIED against the official Anthropic pricing docs (platform.claude.com/
docs/en/about-claude/pricing, fetched 2026-06-10), NOT the old ClaudeManager copy
which had Opus 4.5–4.8 at the deprecated 15/75 (the 4.0/4.1 rate). Current line:

  USD per 1M tokens (input / output):
    Opus 4.5–4.8 .... 5 / 25     (NEW tier — was wrongly 15/75)
    Opus 4.0/4.1 .... 15 / 75    (deprecated, still 15/75)
    3-opus .......... 15 / 75
    Sonnet 4.x/3.5/3.7  3 / 15
    Haiku 4.5 ....... 1 / 5
    Haiku 3.5 ....... 0.8 / 4
    Haiku 3 ......... 0.25 / 1.25
    Fable/Mythos 5 .. 10 / 50

Prompt-cache multipliers (official):
    cache READ (hit) ........ 0.1× base input  (same for 5m & 1h)
    cache WRITE 5-minute .... 1.25× base input
    cache WRITE 1-hour ...... 2.0× base input

Cost is DERIVED (the on-disk costUSD is usually 0). NOTE: this is the API-equivalent
price; a Claude subscription (Pro/Max) is a flat fee, so this figure is "what it
WOULD cost on the API", not an actual charge — the UI labels it as such.
"""

from __future__ import annotations

# USD per 1,000,000 tokens, (input, output). Exact ids + bare family-prefix keys
# (longest-prefix match catches dated variants like -20251001 and future point
# releases). Opus 4.5+ is the NEW 5/25 tier; only the deprecated 4.0/4.1 stay 15/75.
PRICING: dict[str, tuple[float, float]] = {
    # --- Opus 4.5–4.8 : NEW tier 5 / 25 ---
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    # --- Opus 4.0 / 4.1 (deprecated) + 3-opus : OLD tier 15 / 75 ---
    # NOTE: keys are the FULL deprecated ids — NOT a bare "claude-opus-4" (that would
    # prefix-match a future "claude-opus-4-9" and wrongly price it at the old tier).
    "claude-opus-4-1": (15.0, 75.0),
    "claude-opus-4-0": (15.0, 75.0),
    "claude-3-opus": (15.0, 75.0),
    # bare "claude-opus" family fallback — default a brand-new opus (incl. an
    # unrecognised 4.x point release) to the CURRENT 5/25 tier; only the exact
    # deprecated ids above stay 15/75.
    "claude-opus": (5.0, 25.0),
    # --- Sonnet (3 / 15) ---
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-3-7-sonnet": (3.0, 15.0),
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-sonnet": (3.0, 15.0),
    "claude-sonnet": (3.0, 15.0),  # bare-family fallback prefix
    # --- Haiku (4.5: 1/5 · 3.5: 0.8/4 · 3: 0.25/1.25) ---
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-haiku-4": (1.0, 5.0),
    "claude-3-5-haiku": (0.8, 4.0),
    "claude-haiku-3-5": (0.8, 4.0),
    "claude-3-haiku": (0.25, 1.25),
    "claude-haiku": (1.0, 5.0),  # bare-family fallback prefix
    # --- Fable / Mythos 5 : 10 / 50 (premium experimental tier) ---
    "claude-fable-5": (10.0, 50.0),
    "claude-fable": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-mythos": (10.0, 50.0),
}

# Used when the model is unknown to the table (non-Claude or an id whose family
# prefix isn't listed). Sonnet tier — a safe middle.
FALLBACK: tuple[float, float] = (3.0, 15.0)  # sonnet


def _rate_for(model: str) -> tuple[float, float]:
    """Rate for a model: exact match first, then longest-prefix match, else fallback.

    e.g. "claude-sonnet-4-5-20250929" has no exact entry → prefix-matches
    "claude-sonnet-4-5" → (3, 15). "claude-opus-4-9-future" → "claude-opus" → (5, 25).
    """
    if model in PRICING:
        return PRICING[model]
    candidates = [k for k in PRICING if model.startswith(k)]
    if candidates:
        return PRICING[max(candidates, key=len)]
    return FALLBACK


# Official prompt-cache multipliers (× base INPUT rate).
CACHE_READ_MULT = 0.1        # cache hit/refresh — same for 5m & 1h
CACHE_WRITE_5M_MULT = 1.25   # 5-minute cache write
CACHE_WRITE_1H_MULT = 2.0    # 1-hour cache write


def compute_cost(
    tokens_in: int,
    tokens_out: int,
    model: str | None,
    cache_read: int = 0,
    cache_create: int = 0,
    cache_create_1h: int = 0,
) -> float:
    """USD cost for a model's tokens at its rate. 0 if all token counts are zero.

    Cache pricing per the official docs:
      cache_read        → 0.1× input rate
      cache_create      → total cache-write tokens. ``cache_create_1h`` is the
                          subset written with the 1-hour TTL (2.0× input); the
                          remainder (``cache_create - cache_create_1h``) is the
                          5-minute TTL (1.25× input). When the 1h split is unknown
                          (0), ALL cache-create is priced at the 5-minute rate —
                          the conservative/common case.
      unknown model     → sonnet fallback.
    """
    if not (tokens_in or tokens_out or cache_read or cache_create):
        return 0.0
    rate_in, rate_out = _rate_for(model) if model else FALLBACK
    cc_1h = min(max(cache_create_1h, 0), cache_create)  # clamp to [0, cache_create]
    cc_5m = cache_create - cc_1h
    cost = (
        tokens_in * rate_in
        + tokens_out * rate_out
        + cache_read * CACHE_READ_MULT * rate_in
        + cc_5m * CACHE_WRITE_5M_MULT * rate_in
        + cc_1h * CACHE_WRITE_1H_MULT * rate_in
    ) / 1_000_000
    return round(cost, 4)
