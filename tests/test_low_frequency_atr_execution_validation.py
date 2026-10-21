from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "research"))
from low_frequency_atr_execution_validation import (
    attach_execution_returns,
    load_inputs,
    render_report,
    run_research,
)


def small_inputs(n_dates=260, n_tickers=40):
    dates = pd.bdate_range("2024-01-02", periods=n_dates + 25)
    price_rows = []
    snapshot_rows = []
    for ti in range(n_tickers):
        ticker = f"T{ti:03d}"
        base = 20.0 + ti
        drift = (ti - n_tickers / 2) * 0.00005
        for di, date in enumerate(dates):
            open_px = base * (1 + drift) ** di
            close_px = open_px * (1 + (ti + 1) * 0.00005)
            price_rows.append({"Date": date, "Ticker": ticker, "Open": open_px, "Close": close_px})
        for di in range(1, n_dates + 1):
            snapshot_rows.append({
                "Ticker": ticker,
                "Scan_Date": dates[di],
                "Technical_Date": dates[di - 1],
                "ATR_Pct": float(ti),
            })
    return pd.DataFrame(snapshot_rows), pd.DataFrame(price_rows)


def test_execution_return_enters_scan_date_open_and_exits_after_twenty_sessions():
    snapshot, prices = small_inputs(n_dates=2, n_tickers=30)
    clean, by_ticker = load_inputs(snapshot, prices)
    actual, audit = attach_execution_returns(clean, by_ticker)
    row = actual.iloc[0]
    bars = by_ticker[row["Ticker"]]
    pos = bars.index[bars["Date"] == row["Scan_Date"]][0]
    expected = bars.iloc[pos + 19]["Close"] / bars.iloc[pos]["Open"] - 1
    assert row["Execution_Return"] == pytest.approx(expected)
    assert audit["rows_valid"] == len(snapshot)


def test_duplicate_snapshot_keys_fail_closed():
    snapshot, prices = small_inputs(n_dates=2, n_tickers=30)
    snapshot = pd.concat([snapshot, snapshot.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate snapshot"):
        load_inputs(snapshot, prices)


def test_report_discloses_survivorship_and_unadjusted_prices():
    snapshot, prices = small_inputs(n_dates=260, n_tickers=40)
    result = run_research(snapshot, prices)
    report = render_report(result, membership_has_removals=False)
    assert "幸存者偏差" in report
    assert "未复权 OHLC" in report
    assert "不接生产" in report


def test_alignment_mismatch_is_not_silently_shifted():
    snapshot, prices = small_inputs(n_dates=2, n_tickers=30)
    snapshot.loc[0, "Scan_Date"] = pd.Timestamp("2030-01-01")
    clean, by_ticker = load_inputs(snapshot, prices)
    _, audit = attach_execution_returns(clean, by_ticker)
    assert audit["date_alignment_mismatch"] >= 1
