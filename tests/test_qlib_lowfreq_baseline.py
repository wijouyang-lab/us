# -*- coding: utf-8 -*-
"""Optional Qlib contract test; skips when the research dependency is absent."""

import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("qlib")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
import qlib_lowfreq_baseline as mod  # noqa: E402


def _snapshot(path, days=80, tickers=20):
    rows = []
    dates = pd.bdate_range("2025-01-02", periods=days)
    for t in range(tickers):
        ticker = f"T{t:02d}"
        price = 100 + t
        for d in dates:
            row = {"Scan_Date": d.date().isoformat(), "Technical_Date": d.date().isoformat(),
                   "Ticker": ticker, "Price": price, "schema_version": "phase1.v1"}
            for f in mod.FEATURES:
                row[f] = 1.0 + t * 0.01
            rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_prepare_and_handler_keep_time_order(tmp_path):
    path = _snapshot(tmp_path / "snap.csv")
    df = mod.prepare(path)
    assert df.Date.is_monotonic_increasing is False  # sorted by ticker first
    assert df.groupby("Ticker")["Date"].apply(lambda s: s.is_monotonic_increasing).all()
    handler = mod.to_handler(df)
    assert handler is not None
    assert df["label"].notna().all()
    assert len(df) == 80 * 20 - 20 * 20
