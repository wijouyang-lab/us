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


def test_generated_death_autopsy_has_real_markdown_line_breaks_and_daily_ic():
    old_values = (ta.BT, ta.SECTOR_HISTORY, ta.FUND, ta.OUT)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ta.BT = root / "backtest.csv"
            ta.SECTOR_HISTORY = root / "missing_sector_history.csv"
            ta.FUND = root / "missing_fundamentals.csv"
            ta.OUT = root / "report.md"
            rows = []
            for date in ["2025-01-02", "2025-01-03"]:
                for i in range(12):
                    rows.append({
                        "Scan_Date": date, "Ticker": f"T{i:02d}",
                        "Momentum_20D_Pct": float(i), "BP": float(i) / 10,
                        "Forward_Return_5D": float(i) / 100,
                        "Forward_Return_10D": float(i % 5) / 100,
                        "Forward_Return_20D": float(11-i) / 100,
                    })
            pd.DataFrame(rows).to_csv(ta.BT, index=False)
            assert ta.main() == 0
            text = ta.OUT.read_text(encoding="utf-8")
            assert "\\n" not in text
            lines = text.splitlines()
            assert "## 2. IC 衰减（数据受限）" in lines
            assert "## 3. BP 归因回归（必须有真实 PIT 市值与 PIT 行业）" in lines
            assert "| 5D |" in text
    finally:
        ta.BT, ta.SECTOR_HISTORY, ta.FUND, ta.OUT = old_values


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
        test_generated_death_autopsy_has_real_markdown_line_breaks_and_daily_ic,
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
