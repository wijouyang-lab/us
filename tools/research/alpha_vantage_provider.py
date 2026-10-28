#!/usr/bin/env python3
"""Minimal Alpha Vantage daily-OHLCV adapter for research-only probes.

Design constraints:
- API key only from ALPHA_VANTAGE_API_KEY.
- Never include the key in logs, cache names, exceptions, or reports.
- Cache every successful response and count requests per UTC day.
- Free tier is rate-limited; this adapter is intentionally conservative.
- Adjusted and unadjusted data are not silently mixed.

This module is not imported by production scan/review/portfolio code.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

BASE_URL = "https://www.alphavantage.co/query"
DEFAULT_CACHE_DIR = Path(".research_cache") / "alpha_vantage"
DAILY_LIMIT = 25
MIN_INTERVAL_SECONDS = 12.0
OUTPUT_COLUMNS = ["Date", "Ticker", "Open", "High", "Low", "Close", "Adj_Close", "Volume", "Source"]


class ProviderError(RuntimeError):
    pass


class MissingApiKey(ProviderError):
    pass


class RateLimitExceeded(ProviderError):
    pass


@dataclass
class ProviderConfig:
    cache_dir: Path = DEFAULT_CACHE_DIR
    daily_limit: int = DAILY_LIMIT
    min_interval_seconds: float = MIN_INTERVAL_SECONDS
    timeout_seconds: float = 20.0
    allow_unadjusted_fallback: bool = False


class AlphaVantageProvider:
    def __init__(self, api_key: str | None = None, config: ProviderConfig | None = None,
                 session: requests.Session | None = None, sleeper=time.sleep,
                 now=None):
        self._api_key = (api_key if api_key is not None else os.environ.get("ALPHA_VANTAGE_API_KEY", "")).strip()
        self.config = config or ProviderConfig()
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.sleeper = sleeper
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._last_request = 0.0

    @property
    def has_key(self) -> bool:
        return bool(self._api_key)

    def _redact(self, text: str) -> str:
        return text.replace(self._api_key, "[REDACTED]") if self._api_key else text

    def _state_path(self) -> Path:
        return self.config.cache_dir / "request_state.json"

    def _state(self) -> dict:
        try:
            state = json.loads(self._state_path().read_text(encoding="utf-8"))
        except Exception:
            state = {}
        today = self._now().date().isoformat()
        if state.get("date") != today:
            state = {"date": today, "count": 0}
        return state

    def _write_state(self, state: dict) -> None:
        self._state_path().write_text(json.dumps(state), encoding="utf-8")

    def _cache_path(self, ticker: str) -> Path:
        safe = re.sub(r"[^A-Z0-9_.-]", "_", ticker.upper())
        return self.config.cache_dir / f"{safe}.json"

    def _request(self, ticker: str) -> dict:
        if not self._api_key:
            raise MissingApiKey("ALPHA_VANTAGE_API_KEY is not configured")
        state = self._state()
        if state["count"] >= self.config.daily_limit:
            raise RateLimitExceeded("Alpha Vantage daily request limit reached; use cache or wait")
        wait = self.config.min_interval_seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            self.sleeper(wait)
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker.upper(),
            "outputsize": "full",
            "apikey": self._api_key,
        }
        try:
            response = self.session.get(BASE_URL, params=params, timeout=self.config.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise ProviderError(self._redact(f"request failed: {type(exc).__name__}")) from None
        self._last_request = time.monotonic()
        state["count"] += 1
        self._write_state(state)
        if "Error Message" in payload or "Information" in payload or "Note" in payload:
            msg = str(payload.get("Error Message") or payload.get("Information") or payload.get("Note"))
            raise ProviderError(self._redact(msg))
        if "Time Series (Daily)" not in payload:
            raise ProviderError("Alpha Vantage response has no daily time series")
        self._cache_path(ticker).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def fetch_daily(self, ticker: str, force: bool = False) -> pd.DataFrame:
        ticker = str(ticker).upper().strip()
        if not ticker:
            raise ValueError("ticker is required")
        cache = self._cache_path(ticker)
        if cache.exists() and not force:
            payload = json.loads(cache.read_text(encoding="utf-8"))
            cached = True
        else:
            payload = self._request(ticker)
            cached = False
        ts = payload.get("Time Series (Daily)", {})
        rows = []
        for day, values in ts.items():
            try:
                close = float(values["4. close"])
                adj = float(values.get("5. adjusted close", "nan"))
                volume = float(values.get("6. volume", "nan"))
                open_ = float(values["1. open"])
                high = float(values["2. high"])
                low = float(values["3. low"])
            except (KeyError, TypeError, ValueError):
                continue
            if close <= 0 or open_ <= 0 or high <= 0 or low <= 0 or high < low:
                continue
            rows.append({
                "Date": pd.to_datetime(day, errors="coerce"),
                "Ticker": ticker,
                "Open": open_, "High": high, "Low": low, "Close": close,
                "Adj_Close": adj if pd.notna(adj) and adj > 0 else None,
                "Volume": volume,
                "Source": "alpha_vantage_adjusted" if pd.notna(adj) and adj > 0 else "alpha_vantage_unadjusted",
            })
        out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
        out = out.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
        if not self.config.allow_unadjusted_fallback and (out["Adj_Close"].isna()).any():
            raise ProviderError(
                "adjusted close is missing; unadjusted fallback is disabled (set allow_unadjusted_fallback explicitly)"
            )
        return out


def probe(provider: AlphaVantageProvider, ticker: str) -> dict:
    """Return an auditable result without exposing credentials."""
    try:
        df = provider.fetch_daily(ticker)
        return {
            "ticker": ticker.upper(),
            "status": "OK" if not df.empty else "EMPTY",
            "rows": int(len(df)),
            "date_min": str(df["Date"].min().date()) if not df.empty else None,
            "date_max": str(df["Date"].max().date()) if not df.empty else None,
            "adjusted_available": bool(df["Adj_Close"].notna().all()) if not df.empty else False,
            "source": "alpha_vantage",
        }
    except MissingApiKey as exc:
        return {"ticker": ticker.upper(), "status": "SKIPPED_NO_API_KEY", "error": str(exc)}
    except Exception as exc:
        return {"ticker": ticker.upper(), "status": "FAILED", "error": provider._redact(str(exc))}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", required=True, help="Comma-separated sample tickers")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args(argv)
    provider = AlphaVantageProvider(config=ProviderConfig(cache_dir=Path(args.cache_dir)))
    results = [probe(provider, t.strip()) for t in args.tickers.split(",") if t.strip()]
    payload = {
        "research_only": True,
        "api_key_present": provider.has_key,
        "rate_limit": {"daily_limit": provider.config.daily_limit,
                       "min_interval_seconds": provider.config.min_interval_seconds},
        "results": results,
        "note": "No key is printed. Without a key, all probes are SKIPPED_NO_API_KEY.",
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0 if any(r["status"] == "OK" for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
