# -*- coding: utf-8 -*-
"""Regression tests for point-in-time sector and market-cap fail-closed rules."""
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.research import turnover_and_cost_analysis as ta


def test_mean_ic_is_cross_sectional_per_date_not_pooled():
    rows = []
    values = list(range(10))
    for i, value in enumerate(values):
        rows.append({
            "Scan_Date": "2025-01-02", "Factor": value, "Ret": value / 100.0,
        })
        rows.append({
            "Scan_Date": "2025-01-03", "Factor": value, "Ret": (9 - value) / 100.0,
        })
    result = ta.mean_daily_ic(pd.DataFrame(rows), "Factor", "Ret", min_cross_section=10)
    assert result["status"] == "OK", result
    assert result["n_dates"] == 2
    assert abs(result["mean_ic"]) < 1e-9, result
    assert abs(result["median_ic"]) < 1e-9, result
    assert abs(result["positive_date_pct"] - 50.0) < 1e-9, result


def test_missing_pit_sector_file_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        history, reason = ta.load_pit_sector_history(Path(tmp) / "missing.csv")
    assert history is None
    assert "PIT" in reason


def test_pit_sector_intervals_attach_by_effective_date():
    history = pd.DataFrame([
        {"Ticker": "AAA", "Effective_From": "2025-01-01", "Effective_To": "2025-12-31", "Sector": "Old"},
        {"Ticker": "AAA", "Effective_From": "2026-01-01", "Effective_To": "", "Sector": "New"},
    ])
    history["Effective_From"] = pd.to_datetime(history["Effective_From"])
    history["Effective_To"] = pd.to_datetime(history["Effective_To"], errors="coerce").fillna(pd.Timestamp.max)
    d = pd.DataFrame({
        "Scan_Date": ["2025-06-01", "2026-04-01"],
        "Ticker": ["AAA", "AAA"],
        "Momentum_20D_Pct": [2.0, 3.0],
    })
    got = ta.attach_pit_sectors(d, history)
    assert got["Sector"].tolist() == ["Old", "New"]


def test_part1_computes_gross_and_cost_from_input_not_hardcoded_result():
    rows = []
    sectors = ["S0", "S1", "S2", "S3", "S4", "S5"]
    for date in ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]:
        for rank, sector in enumerate(sectors):
            rows.append({
                "Scan_Date": date, "Sector": sector,
                "Momentum_20D_Pct": float(rank),
                "Forward_Return_20D": float(rank) / 100.0,
            })
    result = ta.part1_turnover(pd.DataFrame(rows))
    assert result
    assert abs(result["gross20_pct"] - 3.0) < 1e-9
    assert abs(result["cost20_pct"]) < 1e-9
    assert abs(result["net20_pct"] - 3.0) < 1e-9


def test_bp_attribution_skips_without_market_cap_in_fundamentals():
    old_fund = ta.FUND
    try:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "fund.csv"
            pd.DataFrame([{
                "Date": "2025-01-01", "Ticker": "AAA", "BP": "0.1", "Price": "10",
            }]).to_csv(p, index=False)
            ta.FUND = p
            d = pd.DataFrame([{
                "Scan_Date": "2025-01-01", "Ticker": "AAA", "Sector": "Tech",
                "Forward_Return_20D": 0.02,
            }])
            result = ta.part3_attribution(d)
            assert result["status"] == "SKIPPED"
            assert "Market_Cap" in result["reason"]
    finally:
        ta.FUND = old_fund


def main():
    tests = [
        test_mean_ic_is_cross_sectional_per_date_not_pooled,
        test_missing_pit_sector_file_fails_closed,
        test_pit_sector_intervals_attach_by_effective_date,
        test_part1_computes_gross_and_cost_from_input_not_hardcoded_result,
        test_bp_attribution_skips_without_market_cap_in_fundamentals,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {test.__name__}: {exc}")
    print(f"\n结果：通过 {len(tests) - failures}/{len(tests)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
