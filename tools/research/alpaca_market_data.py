#!/usr/bin/env python3
"""Read-only Alpaca Stock Bars adapter; credentials must come from env.

No key/secret is logged or serialized. This module does not write any panel.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from typing import Any, Mapping

import requests

BASE = "https://data.alpaca.markets"


class AlpacaError(RuntimeError):
    pass


class MissingCredentials(AlpacaError):
    pass


def _creds(env: Mapping[str, str]) -> tuple[str, str]:
    key = env.get("APCA_API_KEY_ID") or env.get("ALPACA_API_KEY")
    secret = env.get("APCA_API_SECRET_KEY") or env.get("ALPACA_API_SECRET")
    if not key or not secret:
        raise MissingCredentials("Alpaca credentials absent from environment")
    return key, secret


def fetch_daily_bars(symbols: list[str], start: date, end: date, *,
                     feed: str = "iex", adjustment: str = "raw",
                     env: Mapping[str, str] | None = None,
                     session: requests.Session | None = None,
                     limit: int = 1000) -> dict[str, Any]:
    """Fetch daily bars, following next_page_token. Returns normalized rows + provenance."""
    env = env if env is not None else os.environ
    key, secret = _creds(env)
    sess = session or requests.Session()
    url = f"{BASE}/v2/stocks/bars"
    params = {
        "symbols": ",".join(sorted(s.upper() for s in symbols)),
        "timeframe": "1Day",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "feed": feed,
        "adjustment": adjustment,
        "limit": limit,
    }
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    all_bars: dict[str, list[dict[str, Any]]] = {}
    pages = []
    token = None
    while True:
        if token:
            params["page_token"] = token
        resp = sess.get(url, params=params, headers=headers, timeout=30)
        body = resp.content
        if resp.status_code == 429:
            raise AlpacaError("Alpaca rate limited (HTTP 429)")
        if resp.status_code in (401, 403):
            raise AlpacaError(f"Alpaca authentication/permission error (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            raise AlpacaError(f"Alpaca HTTP {resp.status_code}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise AlpacaError("Alpaca returned non-JSON") from exc
        pages.append({"sha256": hashlib.sha256(body).hexdigest(), "status": resp.status_code})
        for symbol, bars in (payload.get("bars") or {}).items():
            all_bars.setdefault(symbol.upper(), []).extend(bars)
        token = payload.get("next_page_token")
        if not token:
            break
    rows = []
    for symbol, bars in all_bars.items():
        for b in bars:
            rows.append({
                "Ticker": symbol,
                "Date": str(b.get("t", ""))[:10],
                "Open": b.get("o"), "High": b.get("h"), "Low": b.get("l"),
                "Close": b.get("c"), "Volume": b.get("v"),
                "provider": "alpaca_market_data",
                "feed": feed,
                "adjustment": adjustment,
            })
    return {
        "rows": rows,
        "pages": pages,
        "request": {"endpoint": url, "feed": feed, "adjustment": adjustment,
                    "start": start.isoformat(), "end": end.isoformat()},
        "has_adjusted_close_field": False,
    }
