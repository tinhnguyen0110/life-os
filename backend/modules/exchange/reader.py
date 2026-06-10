"""modules/exchange/reader.py — OKX REST client (read-only, HMAC-SHA256 auth)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

from core.config import settings

logger = logging.getLogger("life-os.exchange.reader")

OKX_BASE = "https://www.okx.com"
_TIMEOUT = 10.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _sign(timestamp: str, method: str, path: str, body: str = "") -> str:
    """HMAC-SHA256 signature: timestamp + method + path + body → Base64."""
    msg = f"{timestamp}{method}{path}{body}"
    mac = hmac.new(
        settings.okx_api_secret.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    )
    return base64.b64encode(mac.digest()).decode()


def _headers(method: str, path: str, body: str = "") -> dict:
    ts = _now_iso()
    return {
        "OK-ACCESS-KEY": settings.okx_api_key,
        "OK-ACCESS-SIGN": _sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": settings.okx_api_passphrase,
        "Content-Type": "application/json",
    }


def _get(path: str) -> dict:
    """Authenticated GET. Returns parsed body. Raises on HTTP/network error."""
    url = OKX_BASE + path
    resp = httpx.get(url, headers=_headers("GET", path), timeout=_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != "0":
        raise ValueError(f"OKX error {body.get('code')}: {body.get('msg')}")
    return body


def fetch_balances() -> list[dict]:
    """GET /api/v5/account/balance — returns list of raw balance dicts."""
    body = _get("/api/v5/account/balance")
    details = body.get("data", [{}])[0].get("details", [])
    return details


def fetch_positions() -> list[dict]:
    """GET /api/v5/account/positions — returns list of raw position dicts."""
    body = _get("/api/v5/account/positions")
    return body.get("data", [])


def fetch_orders(inst_type: str = "SPOT", limit: int = 50) -> list[dict]:
    """GET /api/v5/trade/orders-history — recent completed orders."""
    path = f"/api/v5/trade/orders-history?instType={inst_type}&limit={limit}"
    body = _get(path)
    return body.get("data", [])
