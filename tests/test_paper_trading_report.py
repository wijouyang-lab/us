# -*- coding: utf-8 -*-
"""Paper Trading report must not mark holdings from legacy/mixed price-history schemas."""
import csv
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import paper_trading_report as report
from scripts.paper_trading import PRICE_SCHEMA_VERSION
from scripts.paper_trading_report import drawdown_gate_pass


def _write_price_file(path: Path, versions):
    fields = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for i, version in enumerate(versions):
            writer.writerow({
                "Date": f"2026-10-{19+i:02d}", "Ticker": "AAA",
                "Open": "10", "High": "11", "Low": "9", "Close": str(10+i),
                "Volume": "1000", "schema_version": version,
            })


def test_generated_report_uses_real_markdown_line_breaks():
    old_values = (report.OUT, report.LEDGER, report.PRICE_FILE, report.OBSERVATIONS_FILE)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report.OUT = root / "report.md"
            report.LEDGER = root / "ledger.csv"
            report.PRICE_FILE = root / "prices.csv"
            report.OBSERVATIONS_FILE = root / "observations.csv"
            with report.LEDGER.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "Txn_ID", "Signal_Date", "Ticker", "Action", "Shares",
                        "Entry_Price", "Entry_Date", "Exit_Date", "PnL", "PnL_Pct",
                    ],
                )
                writer.writeheader()
            report.main()
            text = report.OUT.read_text(encoding="utf-8")
            assert "\\n" not in text
            assert "## 已平仓净绩效" in text.splitlines()
            assert "## 已平仓明细" in text.splitlines()
            assert "## 数据质量提示" in text.splitlines()
    finally:
        report.OUT, report.LEDGER, report.PRICE_FILE, report.OBSERVATIONS_FILE = old_values


def test_drawdown_gate_fails_closed_without_closed_trades():
    assert drawdown_gate_pass(0, 0.0) is False
    assert drawdown_gate_pass(0, -10.0) is False
    assert drawdown_gate_pass(1, -4.9) is True
    assert drawdown_gate_pass(1, -5.1) is False


def test_report_refuses_legacy_and_mixed_prices():
    old = report.PRICE_FILE
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prices.csv"
            report.PRICE_FILE = path
            _write_price_file(path, ["phase2b.v1"])
            prices, dates = report.read_prices("2026-10-20")
            assert prices == {}
            assert dates == []
            _write_price_file(path, ["phase2b.v1", PRICE_SCHEMA_VERSION])
            prices, dates = report.read_prices("2026-10-20")
            assert prices == {}
            assert dates == []
    finally:
        report.PRICE_FILE = old


def test_observation_dates_are_actual_logged_runs_and_deduplicated():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "observations.csv"
        fields = [
            "Run_Date", "Data_AsOf_Date", "Candidate_File", "Signals_Queued",
            "Fills", "Closes", "Orders_Expired", "Open_Positions", "Pending_Orders",
        ]
        rows = [
            {"Run_Date": "2026-10-19"},
            {"Run_Date": "2026-10-19"},
            {"Run_Date": "2026-10-20"},
            {"Run_Date": "2026-10-21"},
            {"Run_Date": "not-a-date"},
        ]
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        got = report.read_observation_dates("2026-10-20", path=path)
        assert got == ["2026-10-19", "2026-10-20"]


def test_report_accepts_only_rebuilt_v2_prices():
    old = report.PRICE_FILE
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prices.csv"
            report.PRICE_FILE = path
            _write_price_file(path, [PRICE_SCHEMA_VERSION, PRICE_SCHEMA_VERSION])
            prices, dates = report.read_prices("2026-10-20")
            assert prices["AAA"] == [("2026-10-19", 10.0), ("2026-10-20", 11.0)]
            assert dates == ["2026-10-19", "2026-10-20"]
    finally:
        report.PRICE_FILE = old


def main():
    tests = [
        test_drawdown_gate_fails_closed_without_closed_trades,
        test_generated_report_uses_real_markdown_line_breaks,
        test_report_refuses_legacy_and_mixed_prices,
        test_report_accepts_only_rebuilt_v2_prices,
        test_observation_dates_are_actual_logged_runs_and_deduplicated,
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
