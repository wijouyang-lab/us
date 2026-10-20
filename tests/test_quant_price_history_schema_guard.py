# -*- coding: utf-8 -*-
"""Standalone Phase 2 entry must not backtest shifted legacy/mixed price dates."""
import csv
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_factor_backtest import run_backtest_from_history


def test_direct_backtest_refuses_legacy_or_mixed_history():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        snapshot = root / "snapshot.csv"
        prices = root / "prices.csv"
        backtest = root / "backtest.csv"
        summary = root / "summary.csv"
        pd.DataFrame([{
            "Scan_Date": "2026-10-20", "Technical_Date": "2026-10-19",
            "Ticker": "AAA", "Name": "AAA", "Price": "10",
            "Momentum_20D_Pct": "2",
        }]).to_csv(snapshot, index=False)

        fields = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]
        rows = [
            {"Date": "2026-10-19", "Ticker": "AAA", "Open": "9.5", "High": "10.5",
             "Low": "9.0", "Close": "10", "Volume": "1000", "schema_version": "phase2b.v1"},
            {"Date": "2026-10-20", "Ticker": "AAA", "Open": "10", "High": "11",
             "Low": "9.8", "Close": "10.5", "Volume": "1100", "schema_version": "phase2b.v2"},
        ]
        with prices.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        result = run_backtest_from_history(
            snapshot_path=str(snapshot), price_history_path=str(prices),
            backtest_path=str(backtest), summary_path=str(summary),
        )
        assert result["status"] == "NOT_ENOUGH_DATA"
        assert "Rebuild Quant Price History" in result["reason"]
        assert result["written"] is False
        assert not backtest.exists()
        assert not summary.exists()


def main():
    test_direct_backtest_refuses_legacy_or_mixed_history()
    print("[PASS] test_direct_backtest_refuses_legacy_or_mixed_history")
    print("\n结果：通过 1/1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
