from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "research"))

from etf_history_backfill import build_manifest, normalize_history


def make_history(n=260):
    dates = pd.bdate_range("2024-01-02", periods=n, tz="America/New_York")
    frame = pd.DataFrame({
        "Open": [100.0 + i * 0.01 for i in range(n)],
        "High": [100.2 + i * 0.01 for i in range(n)],
        "Low": [99.8 + i * 0.01 for i in range(n)],
        "Close": [100.1 + i * 0.01 for i in range(n)],
        "Adj Close": [100.0 + i * 0.01 for i in range(n)],
        "Volume": [100000] * n,
        "Dividends": [0.0] * n,
        "Stock Splits": [0.0] * n,
    }, index=dates)
    frame.iloc[100, frame.columns.get_loc("Dividends")] = 0.25
    return frame


def test_normalize_history_removes_timezone_and_preserves_actions():
    result = normalize_history(make_history(), "BIL")
    assert result.Ticker.nunique() == 1
    assert result.Ticker.iloc[0] == "BIL"
    assert pd.api.types.is_datetime64_any_dtype(result.Date.dtype)
    assert result.Date.dt.tz is None
    assert result.Date.is_monotonic_increasing
    assert result.Dividends.sum() == pytest.approx(0.25)
    assert int(result.Dividends.ne(0).sum()) == 1
    assert len(result) == 260


def test_normalize_history_fails_closed_on_missing_adjusted_close():
    frame = make_history().drop(columns=["Adj Close"])
    with pytest.raises(ValueError, match="missing required columns"):
        normalize_history(frame, "SGOV")


def test_normalize_history_fails_closed_on_duplicate_sessions():
    frame = make_history()
    frame = pd.concat([frame, frame.iloc[[0]]])
    with pytest.raises(ValueError, match="duplicate Date/Ticker"):
        normalize_history(frame, "SHV")


def test_normalize_history_fails_closed_on_short_history():
    with pytest.raises(ValueError, match="fewer than 252 sessions"):
        normalize_history(make_history(n=200), "SGOV")


def test_manifest_captures_coverage_and_distribution_actions():
    frame = normalize_history(make_history(), "BIL")
    manifest = build_manifest(
        {"BIL": frame},
        downloaded_at="2026-11-02T00:00:00+00:00",
        yfinance_version="1.7.0",
    )
    assert manifest["status"] == "RESEARCH_ONLY_PROVIDER_DOWNLOAD"
    assert manifest["symbols"]["BIL"]["rows"] == 260
    assert manifest["symbols"]["BIL"]["dividend_event_rows"] == 1
    assert manifest["symbols"]["BIL"]["first_date"] == "2024-01-02"
    assert "closed/liquidated ETF histories are not reconstructed." in manifest["limitations"][1]
