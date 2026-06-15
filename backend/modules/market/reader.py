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
import time
from datetime import datetime, timezone

import httpx

from core.config import settings
from store import db

from .schema import AssetQuote

logger = logging.getLogger("life-os.market.reader")

COINGECKO_TIMEOUT_S = 8.0
_MOCK_BASE_DEFAULT = 100.0

# CoinGecko TTL cache (perf): /market hits CoinGecko on every request; a 5-min poll
# already keeps prices warm, so a fresh live call per page-view is wasted network
# (measured /market ~134ms, all of it the HTTP round-trip). Cache the raw feed for
# COINGECKO_TTL_S keyed by the requested id set, so repeated GET /market (and the
# per-holding /finance quotes that flow through here) serve the last good feed.
# Also de-risks the external dep: a 429/outage inside the TTL window reuses the
# last good response instead of failing open to mock. monotonic clock = immune to
# wall-clock jumps. Single entry per id-set is plenty (one user, few id sets).
COINGECKO_TTL_S = 30.0
_FEED_CACHE: dict[str, tuple[float, dict]] = {}  # key → (monotonic_ts, raw feed)


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

    TTL-cached for COINGECKO_TTL_S keyed by the sorted id set: a repeat call within
    the window returns the last good feed (no network). A fresh fetch refreshes the
    cache; a fetch FAILURE inside the window falls back to the cached feed (if any)
    rather than propagating — only raises when there's nothing cached to reuse.
    """
    key = ",".join(sorted(cg_ids))
    now = time.monotonic()
    cached = _FEED_CACHE.get(key)
    if cached is not None and (now - cached[0]) < COINGECKO_TTL_S:
        return cached[1]  # warm within TTL — no network

    url = f"{settings.coingecko_base}/simple/price"
    params = {
        "ids": ",".join(cg_ids),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    try:
        resp = httpx.get(url, params=params, timeout=COINGECKO_TIMEOUT_S)
        resp.raise_for_status()
        body = resp.json()
        if not isinstance(body, dict):
            raise ValueError(f"unexpected CoinGecko body type: {type(body).__name__}")
    except Exception:
        # network/HTTP/parse failure → reuse the last good feed if the cache has one
        # (stale-but-good beats failing open to mock); else propagate to the caller.
        if cached is not None:
            logger.warning("CoinGecko fetch failed — serving cached feed (%.0fs old)", now - cached[0])
            return cached[1]
        raise
    _FEED_CACHE[key] = (now, body)
    return body


def fetch_market_chart(cg_id: str, days: int = 365) -> list[tuple[str, float]]:
    """Fetch HISTORICAL daily prices for one CoinGecko id — free, no-key backfill source.

    Calls ``/coins/{id}/market_chart?vs_currency=usd&days=N&interval=daily`` (the same
    free CoinGecko API, no key) and returns ``[(iso_ts_utc, usd_price), ...]`` oldest→
    newest. This is what fixes the "only 9 days of history" gap — the 5-min poller only
    accumulates forward from when it started, so deep windows (30/200-day indicators,
    long correlations) had no data. Backfill seeds the past.

    Raises on any failure (timeout / 429 / non-200 / malformed) — the backfill engine
    catches per-symbol and fails open (a missing backfill never crashes anything). NOT
    TTL-cached (one-shot historical pull, not a hot path). ``days`` is clamped to
    [1, 3650]; CoinGecko's free tier serves daily granularity for days>1.
    """
    days = max(1, min(int(days), 3650))
    url = f"{settings.coingecko_base}/coins/{cg_id}/market_chart"
    params = {"vs_currency": "usd", "days": str(days), "interval": "daily"}
    resp = httpx.get(url, params=params, timeout=COINGECKO_TIMEOUT_S)
    resp.raise_for_status()
    body = resp.json()
    if not isinstance(body, dict) or not isinstance(body.get("prices"), list):
        raise ValueError(f"unexpected market_chart body for {cg_id!r}")
    out: list[tuple[str, float]] = []
    for point in body["prices"]:
        # each point is [ms_epoch, usd_price]; skip anything malformed (defensive).
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        ms, price = point[0], point[1]
        if not isinstance(ms, (int, float)) or not isinstance(price, (int, float)):
            continue
        ts_iso = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()
        out.append((ts_iso, float(price)))
    return out


def _fetch_gold(cg_ids: list[str]) -> dict:
    """Fetch spot-gold quote(s) for the ``gold`` asset class — REAL, free, no-key.

    Source = CoinGecko's PAX Gold (PAXG, ``cgId='pax-gold'``): a token redeemable 1:1
    for one troy ounce of LBMA-accredited physical gold, so its USD price tracks spot
    gold within ~0.1%. This is a genuine market price (NOT a mock) obtained from the
    same free CoinGecko `/simple/price` endpoint the crypto path uses — so it inherits
    the proven fail-open + TTL-cache behavior. We keep it a SEPARATE function (parallel
    to ``_fetch_coingecko``) so the gold source can later swap to a dedicated metals
    feed without touching the crypto path. Raises on failure (caller fails open).

    Returns the raw mapping {cg_id: {"usd": float, "usd_24h_change": float}} — same
    shape as ``_fetch_coingecko`` so ``read_quotes`` consumes both identically.
    """
    return _fetch_coingecko(cg_ids)  # PAXG lives on the same free CoinGecko endpoint


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
    gold = [a for a in assets if a.get("assetClass") == "gold"]
    others = [a for a in assets if a.get("assetClass") not in ("crypto", "gold")]
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

    # --- gold (XAU): REAL price via CoinGecko PAXG, fail-open to last-known/mock ---
    if gold:
        gold_with_id = [a for a in gold if a.get("cgId")]
        gold_no_id = [a for a in gold if not a.get("cgId")]
        for a in gold_no_id:  # a gold asset without a cgId can only be mocked
            warnings.append(f"{a.get('symbol','?')}: gold asset missing cgId — mocked")
            q, _ = _mock_quote(a)
            quotes.append(q)

        gold_feed: dict = {}
        gold_ok = True
        if gold_with_id:
            try:
                gold_feed = _fetch_gold([a["cgId"] for a in gold_with_id])
            except Exception as exc:  # feed down → fail-open per asset (never crash)
                gold_ok = False
                logger.warning("gold (PAXG) fetch failed (fail-open to last-known/mock): %s", exc)
                warnings.append(f"gold source unavailable ({type(exc).__name__}) — using last-known/mock")

        for a in gold_with_id:
            entry = gold_feed.get(a["cgId"]) if gold_ok else None
            if entry and isinstance(entry.get("usd"), (int, float)):
                q = AssetQuote(
                    symbol=a["symbol"],
                    name=a.get("name", a["symbol"]),
                    assetClass="gold",
                    price=float(entry["usd"]),
                    changePct=None,  # service derives from price_history
                    currency="USD",
                    # honest provenance: real spot-tracking price, via the PAXG proxy.
                    source="coingecko:pax-gold",
                    ts=_now_iso(),
                )
                object.__setattr__(q, "_feed_change_pct", entry.get("usd_24h_change"))
                quotes.append(q)
            else:
                reason = "gold feed missing this asset" if gold_ok else "gold feed unavailable"
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
