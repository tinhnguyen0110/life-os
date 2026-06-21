"""modules/exchange/service.py — OKX account aggregation + sync cache."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.config import settings

from . import reader
from .schema import ExchangeOverview, OkxBalance, OkxPosition

logger = logging.getLogger("life-os.exchange.service")

# In-memory cache of last successful sync (single-user, no DB needed for this)
_last_snapshot: ExchangeOverview | None = None

# DUST-FOLD (#17): sub-$1 balances are folded into ONE ·dust summary row for DISPLAY (value
# preserved, total unchanged) — same philosophy as finance's holdings fold. The threshold is the
# SAME concept as modules.finance.service.DUST_USD_THRESHOLD; mirrored here (NOT imported)
# because finance.service imports exchange.service at top-level → a top-level import back would be
# circular. Single conceptual source = finance; keep these in sync if it ever changes.
DUST_USD_THRESHOLD = 1.00          # mirror of finance.service.DUST_USD_THRESHOLD (circular-import safe)
DUST_SYMBOL = "·dust"              # mirror of finance.service.DUST_SYMBOL


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_configured() -> bool:
    return bool(settings.okx_api_key and settings.okx_api_secret and settings.okx_api_passphrase)


def _opt_float(value: object) -> float | None:
    """FINANCE-ASSISTANT P1 (#52): parse an OKX string field → float, or None when it's
    empty/absent/unparseable. OKX sends '' for a coin it has no cost-basis for (stablecoins,
    pre-history coins) — that must become None (honest-null), NEVER a fabricated 0 (a 0 basis
    would read as +∞% gain). 0-as-a-real-value is impossible for accAvgPx (a price), so
    treating '' → None is unambiguous."""
    if value in (None, ""):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _parse_balances(raw: list[dict]) -> tuple[list[OkxBalance], float]:
    """Parse OKX balance details into OkxBalance list + total USD value."""
    balances: list[OkxBalance] = []
    total_usd = 0.0
    for item in raw:
        try:
            available = float(item.get("availBal") or 0)
            frozen = float(item.get("frozenBal") or 0)
            usd_val = item.get("eqUsd")
            # #57: narrow for mypy (a `not in (None,...)` check doesn't narrow Any|None) — only
            # float() a present, non-empty, non-zero value; else honest None.
            usd_float = float(usd_val) if usd_val and usd_val != "0" else None
            bal = OkxBalance(  # type: ignore[call-arg]  # DUST-FOLD #17: isDust/count have defaults; no pydantic mypy plugin in env → mypy reads defaulted fields as required (known gotcha)
                symbol=item.get("ccy", "?"),
                available=available,
                frozen=frozen,
                total=available + frozen,
                usdValue=usd_float,
                # FINANCE-ASSISTANT P1 (#52): carry the per-coin cost-basis + OKX's own P&L.
                # '' (no basis) → None, not 0 — honest-null.
                accAvgPx=_opt_float(item.get("accAvgPx")),
                spotUpl=_opt_float(item.get("spotUpl")),
                spotUplRatio=_opt_float(item.get("spotUplRatio")),
            )
            balances.append(bal)
            if usd_float:
                total_usd += usd_float
        except Exception as exc:
            logger.warning("balance parse error: %s — item=%s", exc, item)
    # Sort by USD value descending (most valuable first)
    balances.sort(key=lambda b: b.usdValue or 0, reverse=True)
    return balances, total_usd


def _is_dust_balance(b: OkxBalance) -> bool:
    """DUST-FOLD (#17) dust predicate for an OkxBalance (the flat-list analogue of finance's
    _is_dust). A balance is dust when it has a KNOWN usdValue (not None) STRICTLY BELOW $1 —
    INCLUDING a usdValue that rounds to 0.0 (a true-zero coin OKX still values, e.g. ETH/LINK/
    DOGE at 1e-7 qty). Differs from finance's predicate: OkxBalance has NO ``price`` field, so
    usdValue is the sole value signal (the price clause is dropped per the dispatch). A
    null-usdValue balance is UNKNOWN, not small → NOT dust (stays VISIBLE — the finance lock).
    ``< threshold`` is STRICT: exactly $1.00 stays visible."""
    return b.usdValue is not None and b.usdValue < DUST_USD_THRESHOLD


def _fold_dust_balances(balances: list[OkxBalance]) -> list[OkxBalance]:
    """DUST-FOLD (#17): collapse the sub-$1 balances (see _is_dust_balance) into ONE flat ·dust
    summary OkxBalance so dust doesn't clutter the list. Exchange has NO channel grouping (one
    flat list), so this is a single fold (vs finance's per-channel). Kept individual: usdValue
    ≥ $1, AND any null-usdValue balance (unknown ≠ small — stays visible). 0 dust → no dust row.
    DISPLAY-only: the caller computed total_usd from the FULL set before folding, and the ·dust
    summary carries usdValue=Σ(dust), so Σ(folded incl ·dust) == the pre-fold total. The summary
    preserves the sorted order's tail position (appended last = smallest, like the real dust)."""
    kept: list[OkxBalance] = []
    dust: list[OkxBalance] = []
    for b in balances:
        (dust if _is_dust_balance(b) else kept).append(b)
    if not dust:
        return kept
    dust_value = round(sum(float(b.usdValue or 0.0) for b in dust), 2)
    kept.append(OkxBalance(
        symbol=DUST_SYMBOL,
        available=0.0, frozen=0.0, total=0.0,
        usdValue=dust_value,
        accAvgPx=None, spotUpl=None, spotUplRatio=None,
        isDust=True, count=len(dust),
    ))
    return kept


def _parse_positions(raw: list[dict]) -> list[OkxPosition]:
    positions: list[OkxPosition] = []
    for item in raw:
        try:
            pos = OkxPosition(
                instId=item.get("instId", "?"),
                side=item.get("posSide", "?"),
                qty=float(item.get("pos") or 0),
                avgOpenPrice=float(item.get("avgPx") or 0),
                unrealizedPnl=float(item.get("upl") or 0),
                margin=float(item.get("margin") or 0),
                lever=str(item.get("lever", "1")),
            )
            positions.append(pos)
        except Exception as exc:
            logger.warning("position parse error: %s — item=%s", exc, item)
    return positions


def sync() -> tuple[ExchangeOverview, str | None]:
    """Pull fresh data from OKX and update the in-memory cache.

    Returns (snapshot, warning). Never raises — fails soft with a warning.
    """
    global _last_snapshot

    if not is_configured():
        # #57: syncedAt has a default (None) — the [call-arg] is the no-pydantic-mypy-plugin gotcha
        # (mypy reads defaulted fields as required), same as the OkxBalance ignore above. NOT a bug.
        snap = ExchangeOverview(totalUsdValue=0.0, configured=False)  # type: ignore[call-arg]
        _last_snapshot = snap
        return snap, None

    warnings: list[str] = []
    balances: list[OkxBalance] = []
    positions: list[OkxPosition] = []
    total_usd = 0.0

    try:
        raw_bal = reader.fetch_balances()
        balances, total_usd = _parse_balances(raw_bal)
        # DUST-FOLD (#17): fold sub-$1 balances into one ·dust summary — AFTER total_usd is
        # computed from the full set, so this is DISPLAY-only (total unchanged; Σ folded == total).
        balances = _fold_dust_balances(balances)
    except Exception as exc:
        logger.warning("OKX balance fetch failed: %s", exc)
        warnings.append(f"balance fetch failed: {type(exc).__name__}")

    try:
        raw_pos = reader.fetch_positions()
        positions = _parse_positions(raw_pos)
    except Exception as exc:
        logger.warning("OKX position fetch failed: %s", exc)
        warnings.append(f"position fetch failed: {type(exc).__name__}")

    snap = ExchangeOverview(
        totalUsdValue=total_usd,
        balances=balances,
        positions=positions,
        syncedAt=_now_iso(),
        configured=True,
    )
    _last_snapshot = snap
    warning = "; ".join(warnings) if warnings else None
    return snap, warning


def get_overview() -> tuple[ExchangeOverview, str | None]:
    """Return cached snapshot, or sync if none yet. Never raises."""
    global _last_snapshot
    if _last_snapshot is None:
        return sync()
    return _last_snapshot, None
