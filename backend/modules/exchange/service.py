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
            usd_float = float(usd_val) if usd_val not in (None, "", "0") else None
            bal = OkxBalance(
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
        snap = ExchangeOverview(totalUsdValue=0.0, configured=False)
        _last_snapshot = snap
        return snap, None

    warnings: list[str] = []
    balances: list[OkxBalance] = []
    positions: list[OkxPosition] = []
    total_usd = 0.0

    try:
        raw_bal = reader.fetch_balances()
        balances, total_usd = _parse_balances(raw_bal)
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
