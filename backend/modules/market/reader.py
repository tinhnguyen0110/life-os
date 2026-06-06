"""modules/market/reader.py — quote reader (Sprint 3, SPEC §S8).

Branch by assetClass — NO plugin framework (single dev, simple impl):
  - crypto → CoinGecko free `/simple/price` (httpx, 8s timeout, batched).
  - etf/vn → deterministic mock (fixed realistic seed + deterministic jitter).

FAIL-OPEN (this is the build's FIRST external network call): any CoinGecko
failure (timeout / 429 / non-200 / network error / malformed body) → fall back to
last-known price from price_history, else mock — with a warning. NEVER raises;
the poll + endpoint must never crash on a flaky feed.

changePct is NOT taken blindly from the feed — the service derives it from
price_history (we own the series). The feed's `usd_24h_change` is only a fallback
when our series is too short, and the reader surfaces it via `feed_change_pct`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from core.config import settings
from store import db

from .schema import AssetQuote

logger = logging.getLogger("life-os.market.reader")

COINGECKO_TIMEOUT_S = 8.0
_MOCK_BASE_DEFAULT = 100.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deterministic_jitter(symbol: str, base: float) -> float:
    """A small ±0.5% nudge seeded by ``symbol + UTC date`` — NOT random.

    Same symbol on the same UTC day → same price (tests stable within a day), but
    the value drifts day-to-day so it looks live. No ``random`` → fully reproducible.
    """
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    h = sum(ord(c) for c in f"{symbol}{day}")
    frac = ((h % 1000) / 1000.0 - 0.5) * 0.01  # in [-0.5%, +0.5%)
    return round(base * (1.0 + frac), 2)


def _mock_base(asset: dict) -> float:
    """Mock seed = asset['mock'] field; else the default."""
    val = asset.get("mock")
    return float(val) if isinstance(val, (int, float)) else _MOCK_BASE_DEFAULT


def _mock_quote(asset: dict, *, warning: str | None = None) -> tuple[AssetQuote, str | None]:
    """Build a deterministic mock quote for an etf/vn asset (or unknown fallback)."""
    symbol = asset["symbol"]
    price = _deterministic_jitter(symbol, _mock_base(asset))
    return (
        AssetQuote(
            symbol=symbol,
            name=asset.get("name", symbol),
            assetClass=asset.get("assetClass", "etf"),
            price=price,
            changePct=None,  # service derives from price_history
            currency="USD",
            ts=_now_iso(),
            source="mock",
        ),
        warning,
    )


def _last_known_quote(asset: dict, warning: str) -> tuple[AssetQuote, str]:
    """Fail-open: last price from price_history, else mock. Always returns + warns."""
    row = db.latest_price(asset["symbol"])
    if row is not None:
        return (
            AssetQuote(
                symbol=asset["symbol"],
                name=asset.get("name", asset["symbol"]),
                assetClass=asset.get("assetClass", "crypto"),
                price=float(row["price"]),
                changePct=None,
                currency=row["currency"] or "USD",
                ts=row["ts"],
                source="last-known",
            ),
            warning,
        )
    quote, _ = _mock_quote(asset, warning=warning)
    return quote, warning


def _fetch_coingecko(cg_ids: list[str]) -> dict:
    """ONE batched CoinGecko /simple/price call for all crypto ids. Raises on failure.

    Returns the raw mapping {cg_id: {"usd": float, "usd_24h_change": float}}.
    """
    url = f"{settings.coingecko_base}/simple/price"
    params = {
        "ids": ",".join(cg_ids),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    resp = httpx.get(url, params=params, timeout=COINGECKO_TIMEOUT_S)
    resp.raise_for_status()
    body = resp.json()
    if not isinstance(body, dict):
        raise ValueError(f"unexpected CoinGecko body type: {type(body).__name__}")
    return body


def read_quotes(assets: list[dict]) -> tuple[list[AssetQuote], list[str]]:
    """Read quotes for many assets. ONE CoinGecko call for all crypto; mock the rest.

    Returns (quotes, warnings). Fail-open: a CoinGecko failure degrades every
    crypto asset to last-known/mock with a warning — never raises, never crashes
    the caller (poll/endpoint). Also carries the feed's usd_24h_change on the
    quote object attribute ``feed_change_pct`` for the service's fallback.
    """
    quotes: list[AssetQuote] = []
    warnings: list[str] = []

    crypto = [a for a in assets if a.get("assetClass") == "crypto" and a.get("cgId")]
    others = [a for a in assets if a.get("assetClass") != "crypto"]
    unknown = [a for a in assets if a.get("assetClass") == "crypto" and not a.get("cgId")]

    for a in unknown:
        warnings.append(f"{a.get('symbol','?')}: crypto asset missing cgId — skipped")

    # --- crypto: one batched CoinGecko call, fail-open as a group ---
    feed: dict = {}
    feed_ok = True
    if crypto:
        cg_ids = [a["cgId"] for a in crypto]
        try:
            feed = _fetch_coingecko(cg_ids)
        except Exception as exc:  # timeout/429/non-200/network/malformed — fail-open
            feed_ok = False
            logger.warning("CoinGecko fetch failed (fail-open to last-known/mock): %s", exc)
            warnings.append(f"CoinGecko unavailable ({type(exc).__name__}) — using last-known/mock")

    for a in crypto:
        entry = feed.get(a["cgId"]) if feed_ok else None
        if entry and isinstance(entry.get("usd"), (int, float)):
            q = AssetQuote(
                symbol=a["symbol"],
                name=a.get("name", a["symbol"]),
                assetClass="crypto",
                price=float(entry["usd"]),
                changePct=None,  # service derives from price_history
                currency="USD",
                ts=_now_iso(),
                source="coingecko",
            )
            # Stash the feed's 24h change for the service's fallback (not a schema field).
            object.__setattr__(q, "_feed_change_pct", entry.get("usd_24h_change"))
            quotes.append(q)
        else:
            reason = "feed missing this asset" if feed_ok else "feed unavailable"
            q, _ = _last_known_quote(a, f"{a['symbol']}: {reason} — fail-open")
            warnings.append(f"{a['symbol']}: {reason} — used {q.source}")
            quotes.append(q)

    # --- etf/vn (and any unknown non-crypto class): deterministic mock ---
    for a in others:
        if a.get("assetClass") not in ("etf", "vn"):
            warnings.append(f"{a.get('symbol','?')}: unknown assetClass {a.get('assetClass')!r} — mocked")
        q, _ = _mock_quote(a)
        quotes.append(q)

    return quotes, warnings


def read_quote(asset: dict) -> AssetQuote:
    """Single-asset convenience wrapper around read_quotes (fail-open, never raises)."""
    quotes, _ = read_quotes([asset])
    return quotes[0]
