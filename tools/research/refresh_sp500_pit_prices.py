#!/usr/bin/env python3
"""Refresh research prices with raw feature OHLC plus adjusted return levels.

Raw OHLC is kept for factor engineering. Adjusted Close and same-session adjusted
OHLC are used only for forward-return labels and execution-timing research.
This script never reads or writes production price history or transaction ledgers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import date, datetime, time as clock_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote

import pandas as pd

from pit_membership import (
    active_tickers_on,
    approximate_date_counts,
    load_membership_history_with_aliases,
    tickers_overlapping,
)
from wayback_delisted_prices import fetch_wayback_yahoo_csv_history
from multi_index_membership import load_multi_index_membership

REPO = Path(__file__).resolve().parents[2]
DEFAULT_HISTORY = REPO / "tools" / "research" / "data" / "sp500_components_history.csv"
DEFAULT_TICKER_ALIASES = REPO / "tools" / "research" / "data" / "sp500_ticker_aliases.csv"
DEFAULT_STOCKS = REPO / "research_price_history_sp500_10y.csv"
DEFAULT_SPY = REPO / "research_spy_sp500_10y.csv"
DEFAULT_AUDIT = REPO / "research_pit_price_refresh_audit.json"
TZ = ZoneInfo("America/New_York")
PRICE_COLUMNS = ["Date", "Ticker", "Open", "High", "Low", "Close", "Adj Open", "Adj High", "Adj Low", "Adj Close", "Volume", "Price_Basis"]
BATCH_SIZE = 30
WARMUP_DAYS = 120
MIN_VALID_TICKER_SESSION_COVERAGE = 0.90
PINNED_MEMBERSHIP_COMMIT = "2d0556e4ca01dc9203231c8b60d503a227be4512"
PINNED_MEMBERSHIP_BLOB_SHA = "c025e09a6bbb2e12310a3f9fcef9114a0b59df90"
PINNED_TICKER_ALIAS_BLOB_SHA = "2ffa0f7bb24c9219d7247c7a7c043a8985515ac2"


def last_completed_session_cutoff(now: datetime | None = None) -> date:
    """Use today's date after the regular close; otherwise use the prior calendar date.

    The SPY trading-session calendar is used separately for coverage. The calendar-day
    cutoff here excludes a potentially incomplete current-session daily bar.
    """
    local_now = (now or datetime.now(TZ)).astimezone(TZ)
    return local_now.date() if local_now.time() >= clock_time(16, 0) else local_now.date() - timedelta(days=1)


def subtract_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # Feb 29 -> Feb 28 in the target year.
        return day.replace(year=day.year - years, day=28)


def yahoo_symbol(ticker: str) -> str:
    """Map canonical S&P source symbols to Yahoo's common US ticker notation."""
    return str(ticker).strip().upper().replace(".", "-")


def fetch_yahoo_chart_history(session, symbol: str, start: date, end_exclusive: date) -> pd.DataFrame:
    """Read Yahoo chart data directly, without yfinance's preliminary timezone lookup.

    yfinance can raise YFTzMissingError before it requests the historical window. Some
    valid historical chart responses still contain epoch timestamps and OHLC values
    even when that preliminary metadata lookup fails. This path accepts only chart
    payloads with timestamps, OHLCV fields, and adjusted close; normal OHLC validation
    remains downstream in _records_for_symbol.
    """
    period1 = int(datetime.combine(start, clock_time.min, tzinfo=TZ).timestamp())
    period2 = int(datetime.combine(end_exclusive, clock_time.min, tzinfo=TZ).timestamp())
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "div,splits",
        "includePrePost": "false",
    }
    last_error = None
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{quote(str(symbol), safe='.-^=')}"
        try:
            response = session.get(url, params=params, timeout=8)
            response.raise_for_status()
            payload = response.json()
            chart = payload.get("chart") or {}
            if chart.get("error"):
                raise RuntimeError(f"Yahoo chart error: {chart['error']}")
            results = chart.get("result") or []
            if not results:
                raise RuntimeError("Yahoo chart response contains no result")
            result = results[0]
            timestamps = result.get("timestamp") or []
            indicators = result.get("indicators") or {}
            quote_rows = indicators.get("quote") or []
            adjusted_rows = indicators.get("adjclose") or []
            if not timestamps or not quote_rows or not adjusted_rows:
                raise RuntimeError("Yahoo chart response lacks timestamps, OHLC, or adjusted close")
            quote_row = quote_rows[0]
            adjusted_row = adjusted_rows[0]
            index = pd.to_datetime(timestamps, unit="s", utc=True, errors="coerce")
            frame = pd.DataFrame(
                {
                    "Open": quote_row.get("open", []),
                    "High": quote_row.get("high", []),
                    "Low": quote_row.get("low", []),
                    "Close": quote_row.get("close", []),
                    "Adj Close": adjusted_row.get("adjclose", []),
                    "Volume": quote_row.get("volume", []),
                },
                index=index,
            )
            if frame.empty or frame["Close"].notna().sum() == 0:
                raise RuntimeError("Yahoo chart response contains no close prices")
            return frame
        except Exception as exc:
            last_error = f"{host} {type(exc).__name__}: {exc}"
            error_text = f"{type(exc).__name__}: {exc}".lower()
            # A timeout on one Yahoo host usually means the endpoint is unreachable;
            # do not double the wait by retrying the mirror for the same ticker.
            if "timeout" in error_text or "timed out" in error_text:
                break
    raise RuntimeError(f"direct Yahoo chart fallback failed: {last_error}")


def fetch_eodhd_history(session, symbol: str, start: date, end_exclusive: date, api_token: str) -> pd.DataFrame:
    """Fetch adjusted daily OHLCV from EODHD, including historical delisted listings.

    EODHD supplies raw OHLCV and an adjusted close (split/dividend adjusted); the
    existing validator derives same-session adjusted OHLC from the adjusted-close
    factor. For symbols reused by another issuer, EODHD may expose the older listing
    with an _old suffix, so that code is tried when the current code is empty or 404.
    """
    token = str(api_token or "").strip()
    if not token:
        raise RuntimeError("EODHD_API_TOKEN is not configured")

    base_symbol = yahoo_symbol(symbol)
    candidate_symbols = [f"{base_symbol}.US", f"{base_symbol}_old.US"]
    errors: list[str] = []
    end_inclusive = end_exclusive - timedelta(days=1)

    for provider_symbol in dict.fromkeys(candidate_symbols):
        url = f"https://eodhd.com/api/eod/{quote(provider_symbol, safe='.-_')}"
        params = {
            "api_token": token,
            "from": start.isoformat(),
            "to": end_inclusive.isoformat(),
            "fmt": "json",
        }
        try:
            response = session.get(url, params=params, timeout=20)
        except Exception as exc:
            # Never include the request exception or URL: its query string contains the API token.
            raise RuntimeError(f"EODHD request failed ({type(exc).__name__})") from None

        status_code = int(getattr(response, "status_code", 200))
        if status_code == 404:
            errors.append("HTTP 404")
            continue
        if status_code >= 400:
            raise RuntimeError(f"EODHD HTTP {status_code}")

        try:
            payload = response.json()
        except Exception:
            raise RuntimeError("EODHD response was not valid JSON") from None
        if not isinstance(payload, list):
            raise RuntimeError("EODHD returned a non-list response")
        if not payload:
            errors.append("empty history")
            continue

        rows = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            adjusted_close = item.get("adjusted_close", item.get("adjustedClose", item.get("adjusted close")))
            rows.append({
                "Date": item.get("date"),
                "Open": item.get("open"),
                "High": item.get("high"),
                "Low": item.get("low"),
                "Close": item.get("close"),
                "Adj Close": adjusted_close,
                "Volume": item.get("volume"),
            })
        frame = pd.DataFrame(rows)
        if frame.empty or frame["Adj Close"].notna().sum() == 0:
            errors.append("no usable OHLC and adjusted-close rows")
            continue
        frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
        frame = frame.dropna(subset=["Date"]).set_index("Date")
        return frame[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].sort_index()

    raise RuntimeError(
        f"EODHD returned no usable history for {symbol}: {', '.join(errors) or 'empty history'}"
    )

def _symbol_frame(data: pd.DataFrame, symbol: str, batch_len: int) -> pd.DataFrame | None:
    if data is None or data.empty:
        return None
    if isinstance(data.columns, pd.MultiIndex):
        for level in range(data.columns.nlevels):
            if symbol in data.columns.get_level_values(level):
                try:
                    candidate = data.xs(symbol, axis=1, level=level, drop_level=True)
                    if isinstance(candidate, pd.DataFrame) and not candidate.empty:
                        return candidate
                except (KeyError, ValueError):
                    continue
        return None
    return data if batch_len == 1 else None


def _normalise_daily_index(index, cutoff: date, start: date) -> list[str | None]:
    parsed = pd.to_datetime(index, errors="coerce")
    if isinstance(parsed, pd.DatetimeIndex) and parsed.tz is not None:
        parsed = parsed.tz_convert(TZ).tz_localize(None)
    values: list[str | None] = []
    for value in parsed:
        if pd.isna(value):
            values.append(None)
            continue
        day = value.date()
        values.append(day.isoformat() if start <= day <= cutoff else None)
    return values


def _valid_number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _records_for_symbol(frame: pd.DataFrame, ticker: str, cutoff: date, start: date) -> list[dict]:
    if frame is None or frame.empty or not {"Close", "Adj Close"}.issubset(frame.columns):
        return []
    dates = _normalise_daily_index(frame.index, cutoff, start)
    records = []
    for pos, day in enumerate(dates):
        if day is None:
            continue
        row = frame.iloc[pos]
        close = _valid_number(row.get("Close"))
        adj_close = _valid_number(row.get("Adj Close"))
        high = _valid_number(row.get("High"))
        low = _valid_number(row.get("Low"))
        if (
            close is None or close <= 0
            or adj_close is None or adj_close <= 0
            or high is None or high <= 0
            or low is None or low <= 0
            or high < low
            or not low <= close <= high
        ):
            continue
        adjustment_factor = adj_close / close
        record = {"Date": day, "Ticker": ticker}
        for field in ("Open", "High", "Low"):
            value = _valid_number(row.get(field))
            valid_raw = value is not None and value > 0
            if field in ("High", "Low") and not valid_raw:
                record = {}
                break
            if valid_raw and not low <= value <= high:
                valid_raw = False
            record[field] = round(value, 6) if valid_raw else ""
            record[f"Adj {field}"] = round(value * adjustment_factor, 6) if valid_raw else ""
        if not record:
            continue
        volume = _valid_number(row.get("Volume"))
        record["Volume"] = int(round(volume)) if volume is not None and volume >= 0 else ""
        record["Close"] = round(close, 6)
        record["Adj Close"] = round(adj_close, 6)
        record["Price_Basis"] = "raw_ohlc_adj_close"
        records.append(record)
    return records


def download_historical_prices(
    tickers: list[str],
    start: date,
    end_exclusive: date,
    *,
    batch_size: int = BATCH_SIZE,
    retries: int = 3,
    sleeper=time.sleep,
    downloader=None,
    history_fetcher=None,
    chart_fetcher=None,
    wayback_fetcher=None,
    eodhd_fetcher=None,
) -> tuple[pd.DataFrame, list[dict]]:
    """Batch-download raw OHLC plus adjusted close; derive adjusted OHLC for returns.

    downloader is injectable for regression tests. It should behave like yf.download.
    """
    download_session = None
    if downloader is None:
        import yfinance as yf
        downloader = yf.download
        try:
            # Explicit browser-impersonating session helps avoid intermittent Yahoo
            # chart/timezone failures seen when requesting many symbols in one run.
            from curl_cffi import requests as curl_requests
            download_session = curl_requests.Session(impersonate="chrome")
        except Exception:
            # yfinance can still create its own default session if curl_cffi is unavailable.
            download_session = None
        if history_fetcher is None:
            def fetch_history(ticker, start, end):
                ticker_kwargs = {"session": download_session} if download_session is not None else {}
                return yf.Ticker(ticker, **ticker_kwargs).history(
                    start=start.isoformat(),
                    end=end.isoformat(),
                    auto_adjust=False,
                    actions=False,
                    repair=False,
                    raise_errors=True,
                )
            history_fetcher = fetch_history
        if chart_fetcher is None and download_session is not None:
            chart_fetcher = lambda ticker, start, end: fetch_yahoo_chart_history(
                download_session, ticker, start, end
            )
        if wayback_fetcher is None:
            wayback_session = download_session
            if wayback_session is None:
                import requests
                wayback_session = requests.Session()
            wayback_fetcher = lambda ticker, start, end: fetch_wayback_yahoo_csv_history(
                wayback_session, ticker, start, end
            )
        eodhd_token = os.environ.get("EODHD_API_TOKEN", "").strip()
        if eodhd_fetcher is None and eodhd_token:
            eodhd_session = download_session
            if eodhd_session is None:
                import requests
                eodhd_session = requests.Session()
            eodhd_fetcher = lambda ticker, start, end: fetch_eodhd_history(
                eodhd_session, ticker, start, end, eodhd_token
            )

    def run_download(**kwargs):
        if download_session is not None:
            kwargs["session"] = download_session
        return downloader(**kwargs)

    symbols = list(dict.fromkeys(str(t).strip().upper() for t in tickers if str(t).strip()))
    requests: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for ticker in symbols:
        yahoo = yahoo_symbol(ticker)
        if yahoo in reverse and reverse[yahoo] != ticker:
            raise ValueError(f"Yahoo symbol collision: {reverse[yahoo]} and {ticker} both map to {yahoo}")
        requests[ticker] = yahoo
        reverse[yahoo] = ticker

    all_records: list[dict] = []
    ticker_bulk_errors: dict[str, str] = {}
    download_diagnostics: list[dict] = []
    record_cutoff = end_exclusive - timedelta(days=1)

    for offset in range(0, len(symbols), batch_size):
        canonical_batch = symbols[offset:offset + batch_size]
        yahoo_batch = [requests[t] for t in canonical_batch]
        raw = None
        error = None
        for attempt in range(1, retries + 1):
            try:
                raw = run_download(
                    tickers=yahoo_batch,
                    start=start.isoformat(),
                    end=end_exclusive.isoformat(),
                    auto_adjust=False,
                    actions=False,
                    group_by="ticker",
                    # Bound per-ticker concurrency to reduce Yahoo throttling while avoiding
                    # the very slow all-serial path across the historical universe.
                    threads=4,
                    progress=False,
                    ignore_tz=True,
                    repair=True,
                )
                if raw is not None and not raw.empty:
                    error = None
                    break
                error = "empty batch response"
            except Exception as exc:  # retries are bounded; audit preserves final cause.
                error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                sleeper(float(attempt * 2))

        if raw is None or raw.empty:
            for ticker in canonical_batch:
                ticker_bulk_errors[ticker] = error or "empty batch response"
            continue

        for ticker in canonical_batch:
            frame = _symbol_frame(raw, requests[ticker], len(canonical_batch))
            if frame is None or frame.empty:
                ticker_bulk_errors[ticker] = "no ticker-level frame in bulk response"
                continue
            ticker_records = _records_for_symbol(frame, ticker, record_cutoff, start)
            if ticker_records:
                all_records.extend(ticker_records)
            else:
                ticker_bulk_errors[ticker] = (
                    "ticker frame returned no valid raw/adjusted OHLC rows"
                )

    # Bulk yfinance calls can omit individual symbols even when neighbouring symbols
    # succeed. Retry only tickers with zero usable rows, one at a time and without
    # yfinance internal threading, so a failed group does not masquerade as success.
    recovered_tickers: list[dict] = []
    unresolved_failures: list[dict] = []
    eodhd_disabled = False
    eodhd_disabled_error = None
    for ticker, bulk_error in ticker_bulk_errors.items():
        fallback_error = None
        recovered_rows = []
        eodhd_attempted = False
        for attempt in range(1, 3):
            try:
                raw_single = run_download(
                    tickers=[requests[ticker]],
                    start=start.isoformat(),
                    end=end_exclusive.isoformat(),
                    auto_adjust=False,
                    actions=False,
                    group_by="ticker",
                    threads=False,
                    progress=False,
                    ignore_tz=True,
                    repair=False,
                )
                frame = _symbol_frame(raw_single, requests[ticker], 1)
                recovered_rows = (
                    _records_for_symbol(frame, ticker, record_cutoff, start)
                    if frame is not None and not frame.empty else []
                )
                if recovered_rows:
                    break
                fallback_error = "single-ticker response contained no valid raw/adjusted OHLC rows"
            except Exception as exc:
                fallback_error = f"{type(exc).__name__}: {exc}"
            if attempt < 2:
                sleeper(1.0)

        recovery_method = "single_ticker_download"
        history_attempted = False
        chart_attempted = False
        wayback_attempted = False
        if not recovered_rows and history_fetcher is not None:
            history_attempted = True
            try:
                history_frame = history_fetcher(
                    requests[ticker], start, end_exclusive
                )
                recovered_rows = _records_for_symbol(
                    history_frame, ticker, record_cutoff, start
                ) if history_frame is not None and not history_frame.empty else []
                if recovered_rows:
                    recovery_method = "ticker_history"
                else:
                    fallback_error = (
                        (fallback_error + "; ") if fallback_error else ""
                    ) + "Ticker.history returned no valid raw/adjusted OHLC rows"
            except Exception as exc:
                fallback_error = (
                    (fallback_error + "; ") if fallback_error else ""
                ) + f"Ticker.history {type(exc).__name__}: {exc}"

        if not recovered_rows and chart_fetcher is not None:
            chart_attempted = True
            try:
                chart_frame = chart_fetcher(requests[ticker], start, end_exclusive)
                recovered_rows = _records_for_symbol(
                    chart_frame, ticker, record_cutoff, start
                ) if chart_frame is not None and not chart_frame.empty else []
                if recovered_rows:
                    recovery_method = "direct_yahoo_chart"
                else:
                    fallback_error = (
                        (fallback_error + "; ") if fallback_error else ""
                    ) + "direct Yahoo chart returned no valid raw/adjusted OHLC rows"
            except Exception as exc:
                fallback_error = (
                    (fallback_error + "; ") if fallback_error else ""
                ) + f"direct Yahoo chart {type(exc).__name__}: {exc}"

        # Free, unauthenticated Internet Archive recovery comes before any optional
        # paid provider. Use a conservative delay because the public archive is rate-limited.
        if not recovered_rows and wayback_fetcher is not None:
            wayback_attempted = True
            sleeper(1.0)
            try:
                wayback_frame = wayback_fetcher(ticker, start, end_exclusive)
                recovered_rows = (
                    _records_for_symbol(wayback_frame, ticker, record_cutoff, start)
                    if wayback_frame is not None and not wayback_frame.empty else []
                )
                if recovered_rows:
                    recovery_method = "wayback_yahoo_csv"
                else:
                    fallback_error = ((fallback_error + "; ") if fallback_error else "") + "Wayback returned no valid raw/adjusted OHLC rows"
            except Exception as exc:
                fallback_error = ((fallback_error + "; ") if fallback_error else "") + f"Wayback {type(exc).__name__}: {exc}"

        if not recovered_rows and eodhd_fetcher is not None and not eodhd_disabled:
            eodhd_attempted = True
            try:
                eodhd_frame = eodhd_fetcher(ticker, start, end_exclusive)
                recovered_rows = (
                    _records_for_symbol(eodhd_frame, ticker, record_cutoff, start)
                    if eodhd_frame is not None and not eodhd_frame.empty else []
                )
                if recovered_rows:
                    recovery_method = "eodhd_history"
                else:
                    fallback_error = ((fallback_error + "; ") if fallback_error else "") + "EODHD returned no valid raw/adjusted OHLC rows"
            except Exception as exc:
                safe_error = f"{type(exc).__name__}: {exc}"
                fallback_error = ((fallback_error + "; ") if fallback_error else "") + f"EODHD {safe_error}"
                if safe_error in {"RuntimeError: EODHD HTTP 401", "RuntimeError: EODHD HTTP 403"}:
                    eodhd_disabled = True
                    eodhd_disabled_error = safe_error.replace("RuntimeError: ", "")

        if recovered_rows:
            all_records.extend(recovered_rows)
            fallback_attempts = (
                attempt if recovery_method == "single_ticker_download"
                else 3 if recovery_method == "ticker_history"
                else 4 if recovery_method == "direct_yahoo_chart"
                else 5 + int(wayback_attempted)
            )
            recovered_entry = {
                "ticker": ticker,
                "status": "recovered",
                "bulk_error": bulk_error,
                "fallback_attempts": fallback_attempts,
                "recovery_method": recovery_method,
                "rows": len(recovered_rows),
            }
            if wayback_attempted:
                recovered_entry["wayback_attempted"] = True
            if eodhd_fetcher is not None:
                recovered_entry["eodhd_attempted"] = eodhd_attempted
            recovered_tickers.append(recovered_entry)
        else:
            failure_entry = {
                "ticker": ticker,
                "status": "failed",
                "bulk_error": bulk_error,
                "fallback_error": fallback_error or "single-ticker request returned no data",
                "fallback_attempts": 2 + int(history_attempted) + int(chart_attempted) + int(wayback_attempted) + int(eodhd_attempted),
                "recovery_method": (
                    "eodhd_history_failed" if eodhd_attempted
                    else "wayback_yahoo_csv_failed" if wayback_attempted
                    else "direct_yahoo_chart_failed" if chart_attempted
                    else "ticker_history_failed" if history_attempted
                    else "single_ticker_download_failed"
                ),
            }
            if wayback_attempted:
                failure_entry["wayback_attempted"] = True
            if eodhd_fetcher is not None:
                failure_entry["eodhd_attempted"] = eodhd_attempted
                if eodhd_disabled_error:
                    failure_entry["eodhd_error"] = eodhd_disabled_error
            unresolved_failures.append(failure_entry)

    if not all_records:
        return pd.DataFrame(columns=PRICE_COLUMNS), recovered_tickers + unresolved_failures
    output = pd.DataFrame(all_records, columns=PRICE_COLUMNS)
    output = output.drop_duplicates(["Date", "Ticker"], keep="last")
    output = output.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    return output, recovered_tickers + unresolved_failures


def calculate_member_session_coverage(
    history: dict,
    prices: pd.DataFrame,
    market_dates: list[date],
    analysis_start: date,
    cutoff: date,
    *,
    per_ticker_threshold: float = MIN_VALID_TICKER_SESSION_COVERAGE,
) -> dict:
    """Measure actual OHLC rows against the historical-member × SPY-session panel."""
    sessions = sorted({d for d in market_dates if analysis_start <= d <= cutoff})
    price_dates_by_ticker: dict[str, set[date]] = {}
    if not prices.empty:
        for ticker, group in prices.groupby("Ticker", sort=False):
            parsed = pd.to_datetime(group["Date"], errors="coerce").dropna()
            price_dates_by_ticker[str(ticker).upper()] = {x.date() for x in parsed}

    expected = Counter()
    observed = Counter()
    for session in sessions:
        for ticker in active_tickers_on(session, history):
            expected[ticker] += 1
            if session in price_dates_by_ticker.get(ticker, set()):
                observed[ticker] += 1

    expected_total = sum(expected.values())
    observed_total = sum(observed.values())
    symbol_fractions = {
        ticker: (observed[ticker] / count) if count else 0.0
        for ticker, count in expected.items()
    }
    covered_tickers = sorted(
        ticker for ticker, fraction in symbol_fractions.items()
        if fraction >= per_ticker_threshold
    )
    low_coverage = sorted(
        (
            {"ticker": ticker, "observed_sessions": observed[ticker],
             "expected_sessions": expected[ticker], "coverage": round(symbol_fractions[ticker], 6)}
            for ticker in symbol_fractions
            if symbol_fractions[ticker] < per_ticker_threshold
        ),
        key=lambda row: (row["coverage"], row["ticker"]),
    )
    return {
        "market_sessions": len(sessions),
        "expected_member_session_bars": expected_total,
        "observed_member_session_bars": observed_total,
        "member_bar_coverage": (observed_total / expected_total) if expected_total else 0.0,
        "expected_member_tickers": len(expected),
        "tickers_with_coverage_at_least_threshold": len(covered_tickers),
        "ticker_coverage": (len(covered_tickers) / len(expected)) if expected else 0.0,
        "per_ticker_coverage_threshold": per_ticker_threshold,
        "low_coverage_ticker_count": len(low_coverage),
        "low_coverage_tickers": low_coverage[:100],
    }


def git_blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def refresh(args) -> dict:
    aliases_path = Path(getattr(args, "aliases", DEFAULT_TICKER_ALIASES))
    actual_membership_blob_sha = git_blob_sha(args.history)
    actual_alias_blob_sha = git_blob_sha(aliases_path)
    using_vendored_source = args.history.resolve() == DEFAULT_HISTORY.resolve()
    using_vendored_aliases = aliases_path.resolve() == DEFAULT_TICKER_ALIASES.resolve()
    if using_vendored_source and actual_membership_blob_sha != PINNED_MEMBERSHIP_BLOB_SHA:
        raise SystemExit(
            "Vendored membership history hash does not match its pinned source; "
            "review provenance and update the pin before refreshing prices."
        )
    if using_vendored_aliases and actual_alias_blob_sha != PINNED_TICKER_ALIAS_BLOB_SHA:
        raise SystemExit(
            "Vendored ticker alias registry hash does not match its pin; "
            "review registry provenance and update the pin before refreshing prices."
        )
    alias_usage: dict = {}
    nasdaq_path = getattr(args, "nasdaq100_membership", None)
    dow_path = getattr(args, "dow30_membership", None)
    if bool(nasdaq_path) != bool(dow_path):
        raise ValueError("Nasdaq-100 and Dow membership paths must be supplied together")
    if nasdaq_path and dow_path:
        history = load_multi_index_membership(
            args.history, aliases_path, Path(nasdaq_path), Path(dow_path)
        )
        membership_scope = ["S&P 500", "Nasdaq-100", "Dow Jones 30"]
    else:
        history = load_membership_history_with_aliases(
            args.history, aliases_path, alias_usage=alias_usage
        )
        membership_scope = ["S&P 500"]
    cutoff = args.cutoff_date or last_completed_session_cutoff()
    analysis_start = args.analysis_start or subtract_years(cutoff, 10)
    if analysis_start > cutoff:
        raise ValueError("analysis start must not be after the completed-session cutoff")
    fetch_start = analysis_start - timedelta(days=args.warmup_days)
    end_exclusive = cutoff + timedelta(days=1)

    in_scope = tickers_overlapping(analysis_start, cutoff, history)
    if not in_scope:
        raise ValueError("no historical member tickers overlap the requested analysis window")
    requested = sorted(in_scope | {"SPY"})
    print(
        f"[PIT prices] analysis={analysis_start}..{cutoff}; warmup from={fetch_start}; "
        f"historical member tickers={len(in_scope)}; requested with SPY={len(requested)}"
    )

    stocks, download_diagnostics = download_historical_prices(
        requested, fetch_start, end_exclusive, batch_size=args.batch_size
    )
    recovered_tickers = [item for item in download_diagnostics if item.get("status") == "recovered"]
    failures = [item for item in download_diagnostics if item.get("status") == "failed"]
    spy = stocks[stocks["Ticker"] == "SPY"].copy() if not stocks.empty else pd.DataFrame(columns=PRICE_COLUMNS)
    stock_rows = stocks[stocks["Ticker"] != "SPY"].copy() if not stocks.empty else pd.DataFrame(columns=PRICE_COLUMNS)
    market_dates = sorted(pd.to_datetime(spy["Date"], errors="coerce").dropna().dt.date.unique().tolist()) if not spy.empty else []
    latest_spy = max(market_dates).isoformat() if market_dates else None
    stale_days = (cutoff - date.fromisoformat(latest_spy)).days if latest_spy else None

    coverage = calculate_member_session_coverage(
        history, stock_rows, market_dates, analysis_start, cutoff
    )
    source_stats = approximate_date_counts(history)
    issues = []
    if not latest_spy:
        issues.append("SPY history is empty; no valid market-session calendar")
    elif stale_days is not None and stale_days > args.max_spy_staleness_days:
        issues.append(
            f"SPY latest completed date {latest_spy} is {stale_days} calendar days behind cutoff {cutoff}"
        )
    if coverage["market_sessions"] < 100:
        issues.append(f"only {coverage['market_sessions']} market sessions in analysis window")
    if coverage["member_bar_coverage"] < args.min_member_bar_coverage:
        issues.append(
            f"member-session bar coverage {coverage['member_bar_coverage']:.2%} "
            f"is below required {args.min_member_bar_coverage:.2%}"
        )
    if coverage["ticker_coverage"] < args.min_ticker_coverage:
        issues.append(
            f"ticker coverage {coverage['ticker_coverage']:.2%} "
            f"is below required {args.min_ticker_coverage:.2%}"
        )
    # Individual ticker gaps are accounted for by the session-coverage gates below.
    # Preserve them as diagnostics; do not fail solely because an isolated symbol is unavailable.

    report = {
        "status": "FAIL" if issues else "PASS",
        "research_only": True,
        "analysis_start": analysis_start.isoformat(),
        "price_fetch_start": fetch_start.isoformat(),
        "cutoff_date": cutoff.isoformat(),
        "yfinance_end_exclusive": end_exclusive.isoformat(),
        "price_basis": "raw OHLC for factor features; Adj Close and same-session-adjusted OHLC for research return labels",
        "membership_source": str(args.history.relative_to(REPO) if args.history.is_relative_to(REPO) else args.history),
        "membership_scope": membership_scope,
        "nasdaq100_membership_source": str(Path(nasdaq_path).relative_to(REPO) if nasdaq_path and Path(nasdaq_path).is_relative_to(REPO) else nasdaq_path),
        "dow30_membership_source": str(Path(dow_path).relative_to(REPO) if dow_path and Path(dow_path).is_relative_to(REPO) else dow_path),
        "membership_source_commit": PINNED_MEMBERSHIP_COMMIT if using_vendored_source else None,
        "membership_source_blob_sha": actual_membership_blob_sha,
        "ticker_alias_registry": str(aliases_path.relative_to(REPO) if aliases_path.is_relative_to(REPO) else aliases_path),
        "ticker_alias_registry_blob_sha": actual_alias_blob_sha,
        "ticker_alias_usage": alias_usage,
        "membership_ticker_count_all_spans": len(history),
        "membership_tickers_overlapping_window": len(in_scope),
        "membership_date_quality": source_stats,
        "requested_tickers_including_spy": len(requested),
        "downloaded_price_rows": len(stock_rows),
        "downloaded_unique_tickers": int(stock_rows["Ticker"].nunique()) if not stock_rows.empty else 0,
        "spy_rows": len(spy),
        "latest_spy_date": latest_spy,
        "spy_staleness_calendar_days": stale_days,
        "coverage": coverage,
        "download_failure_count": len(failures),
        "download_failures": failures[:200],
        "fallback_recovered_ticker_count": len(recovered_tickers),
        "fallback_recovered_tickers": recovered_tickers[:200],
        "free_secondary_price_provider": {
            "name": "Internet Archive legacy Yahoo CSV snapshots",
            "configured": True,
            "attempted_ticker_count": sum(1 for item in download_diagnostics if item.get("wayback_attempted")),
            "recovered_ticker_count": sum(1 for item in recovered_tickers if item.get("recovery_method") == "wayback_yahoo_csv"),
            "limitations": "Only archived legacy CSV snapshots are searched; coverage is partial and adjusted prices reflect the snapshot date.",
        },
        "secondary_price_provider": {
            "name": "EOD Historical Data (EODHD), optional paid fallback",
            "configured": bool(os.environ.get("EODHD_API_TOKEN", "").strip()),
            "attempted_ticker_count": sum(1 for item in download_diagnostics if item.get("eodhd_attempted")),
            "recovered_ticker_count": sum(1 for item in recovered_tickers if item.get("recovery_method") == "eodhd_history"),
            "first_provider_error": next((item.get("eodhd_error") for item in download_diagnostics if item.get("eodhd_error")), None),
        },
        "requirements": {
            "min_member_bar_coverage": args.min_member_bar_coverage,
            "min_ticker_coverage": args.min_ticker_coverage,
            "max_spy_staleness_calendar_days": args.max_spy_staleness_days,
        },
        "issues": issues,
        "limitations": [
            "Membership dates are community-maintained and some upstream dates are explicitly approximate.",
            "Raw OHLC is used for signal features; adjusted price levels are used only for labels and execution validation. Provider corporate-action and delisted-ticker history must still be audited.",
            "Corporate actions, symbol changes, and delisted ticker availability must still be audited before promotion.",
        ],
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # By default, never replace prior input files unless source freshness and membership
    # coverage pass. Partial outputs are permitted only with explicit opt-in AND isolated
    # non-default output paths; the audit retains status=FAIL and the normal inputs remain safe.
    if issues and not getattr(args, "allow_partial_output", False):
        raise SystemExit("PIT price refresh blocked; existing research price inputs were preserved. See audit JSON.")

    args.stocks.parent.mkdir(parents=True, exist_ok=True)
    stock_tmp = args.stocks.with_suffix(args.stocks.suffix + ".tmp")
    spy_tmp = args.spy.with_suffix(args.spy.suffix + ".tmp")
    stock_rows.to_csv(stock_tmp, index=False, encoding="utf-8")
    spy.to_csv(spy_tmp, index=False, encoding="utf-8")
    os.replace(stock_tmp, args.stocks)
    os.replace(spy_tmp, args.spy)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--aliases", type=Path, default=DEFAULT_TICKER_ALIASES)
    parser.add_argument("--nasdaq100-membership", type=Path, default=None)
    parser.add_argument("--dow30-membership", type=Path, default=None)
    parser.add_argument("--stocks", type=Path, default=DEFAULT_STOCKS)
    parser.add_argument("--spy", type=Path, default=DEFAULT_SPY)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--analysis-start", type=date.fromisoformat, default=None)
    parser.add_argument("--cutoff-date", type=date.fromisoformat, default=None, help="test-only override for the latest completed date")
    parser.add_argument("--warmup-days", type=int, default=WARMUP_DAYS)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--min-member-bar-coverage", type=float, default=0.95)
    parser.add_argument("--min-ticker-coverage", type=float, default=0.98)
    parser.add_argument("--max-spy-staleness-days", type=int, default=4)
    parser.add_argument(
        "--allow-partial-output",
        action="store_true",
        help=(
            "Research-only escape hatch: write partial prices despite failed coverage/freshness "
            "gates. Requires both --stocks and --spy to be non-default isolated paths; the audit "
            "remains FAIL and default research inputs are never overwritten."
        ),
    )
    args = parser.parse_args(argv)
    if args.allow_partial_output and (
        args.stocks.resolve() == DEFAULT_STOCKS.resolve()
        or args.spy.resolve() == DEFAULT_SPY.resolve()
    ):
        parser.error(
            "--allow-partial-output requires both --stocks and --spy to use isolated non-default paths"
        )
    if not 0 < args.min_member_bar_coverage <= 1 or not 0 < args.min_ticker_coverage <= 1:
        parser.error("coverage thresholds must be in the interval (0, 1]")
    if args.warmup_days < 60:
        parser.error("--warmup-days must be at least 60")
    refresh(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
