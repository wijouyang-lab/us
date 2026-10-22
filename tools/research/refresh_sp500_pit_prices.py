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

import pandas as pd

from pit_membership import (
    active_tickers_on,
    approximate_date_counts,
    load_membership_history,
    tickers_overlapping,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_HISTORY = REPO / "tools" / "research" / "data" / "sp500_components_history.csv"
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
) -> tuple[pd.DataFrame, list[dict]]:
    """Batch-download raw OHLC plus adjusted close; derive adjusted OHLC for returns.

    downloader is injectable for regression tests. It should behave like yf.download.
    """
    if downloader is None:
        import yfinance as yf
        downloader = yf.download

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
    batch_failures: list[dict] = []
    for offset in range(0, len(symbols), batch_size):
        canonical_batch = symbols[offset:offset + batch_size]
        yahoo_batch = [requests[t] for t in canonical_batch]
        raw = None
        error = None
        for attempt in range(1, retries + 1):
            try:
                raw = downloader(
                    tickers=yahoo_batch,
                    start=start.isoformat(),
                    end=end_exclusive.isoformat(),
                    auto_adjust=False,
                    actions=False,
                    group_by="ticker",
                    threads=True,
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
            batch_failures.append({"tickers": canonical_batch, "error": error or "empty batch response"})
            continue
        for ticker in canonical_batch:
            frame = _symbol_frame(raw, requests[ticker], len(canonical_batch))
            if frame is None or frame.empty:
                batch_failures.append({"tickers": [ticker], "error": "no ticker-level frame in response"})
                continue
            all_records.extend(_records_for_symbol(frame, ticker, end_exclusive - timedelta(days=1), start))

    if not all_records:
        return pd.DataFrame(columns=PRICE_COLUMNS), batch_failures
    output = pd.DataFrame(all_records, columns=PRICE_COLUMNS)
    output = output.drop_duplicates(["Date", "Ticker"], keep="last")
    output = output.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    return output, batch_failures


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
    actual_membership_blob_sha = git_blob_sha(args.history)
    using_vendored_source = args.history.resolve() == DEFAULT_HISTORY.resolve()
    if using_vendored_source and actual_membership_blob_sha != PINNED_MEMBERSHIP_BLOB_SHA:
        raise SystemExit(
            "Vendored membership history hash does not match its pinned source; "
            "review provenance and update the pin before refreshing prices."
        )
    history = load_membership_history(args.history)
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

    stocks, failures = download_historical_prices(
        requested, fetch_start, end_exclusive, batch_size=args.batch_size
    )
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
        "membership_source_commit": PINNED_MEMBERSHIP_COMMIT if using_vendored_source else None,
        "membership_source_blob_sha": actual_membership_blob_sha,
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
        "download_failures": failures[:100],
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

    # Never replace prior input files unless both source freshness and membership coverage pass.
    if issues:
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
    args = parser.parse_args(argv)
    if not 0 < args.min_member_bar_coverage <= 1 or not 0 < args.min_ticker_coverage <= 1:
        parser.error("coverage thresholds must be in the interval (0, 1]")
    if args.warmup_days < 60:
        parser.error("--warmup-days must be at least 60")
    refresh(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
