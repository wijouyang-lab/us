from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pending_merge import unseen_pending_items


def test_new_file_keeps_unique_candidates():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pending.csv"
        items = [{"Ticker": "aapl"}, {"Ticker": "MSFT"}, {"Ticker": "AAPL"}, {"Ticker": ""}]
        assert unseen_pending_items(path, items) == items[:2]


def test_rerun_does_not_rewrite_existing_tickers():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pending.csv"
        path.write_text("Ticker,Status\nAAPL,bought\nMSFT,pending\n", encoding="utf-8")
        items = [{"Ticker": "AAPL", "Status": "pending"}, {"Ticker": "NVDA"}, {"Ticker": "nvda"}]
        assert unseen_pending_items(path, items) == [items[1]]
        # Existing rows and statuses remain byte-for-byte untouched by the helper.
        assert path.read_text(encoding="utf-8") == "Ticker,Status\nAAPL,bought\nMSFT,pending\n"


def test_malformed_existing_file_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pending.csv"
        path.write_text("Symbol,Status\nAAPL,pending\n", encoding="utf-8")
        try:
            unseen_pending_items(path, [{"Ticker": "NVDA"}])
        except ValueError as exc:
            assert "Ticker column" in str(exc)
        else:
            raise AssertionError("Expected malformed pending file to fail closed")


if __name__ == "__main__":
    tests = [
        test_new_file_keeps_unique_candidates,
        test_rerun_does_not_rewrite_existing_tickers,
        test_malformed_existing_file_fails_closed,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Result: {len(tests)}/{len(tests)} passed")
