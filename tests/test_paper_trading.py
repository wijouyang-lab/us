# -*- coding: utf-8 -*-
"""Paper Trading 纯逻辑回归测试，不依赖 Yahoo 网络或真实账本。"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.paper_trading import (
    _candidate_tickers,
    _create_signal_orders,
    _fill_pending_orders,
    close_positions,
    execution_window_enabled,
    buy_execution_price,
    commission,
    next_open_bar,
    net_trade_pnl,
    observation_eligible,
    observation_data_ready,
    load_prices,
    PRICE_SCHEMA_VERSION,
    record_observation,
    sell_execution_price,
)


def test_next_open_uses_exact_first_post_signal_bar():
    series = [
        {"date": "2026-10-19", "open": 49.0, "close": 50.0},
        {"date": "2026-10-20", "open": 48.5, "close": 49.0},
        {"date": "2026-10-21", "open": 52.0, "close": 53.0},
    ]
    bar = next_open_bar(series, "2026-10-19")
    assert bar is series[1], bar


def test_missing_next_open_fails_closed():
    series = [{"date": "2026-10-19", "open": 49.0, "close": 50.0}]
    assert next_open_bar(series, "2026-10-19") is None


def test_asof_date_blocks_future_bar():
    series = [
        {"date": "2026-10-19", "open": 49.0, "close": 50.0},
        {"date": "2026-10-20", "open": 48.5, "close": 49.0},
    ]
    assert next_open_bar(series, "2026-10-19", asof_date="2026-10-19") is None
    assert next_open_bar(series, "2026-10-19", asof_date="2026-10-20") is series[1]


def test_void_row_does_not_block_corrected_signal():
    import csv
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "us_stocks_pending_20261019.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["Ticker", "Status"])
            w.writeheader()
            w.writerow({"Ticker": "APA", "Status": "pending"})
        rows = [{
            "Txn_ID": "APA|2026-10-19|BUY|VOID", "Ticker": "APA",
            "Action": "VOID", "Entry_Date": "2026-10-19",
        }]
        created = _create_signal_orders(rows, [path], "2026-10-19")
        assert created == 1
        assert rows[-1]["Action"] == "PENDING"
        assert rows[-1]["Txn_ID"] == "APA|2026-10-19|BUY"
        assert len({row["Txn_ID"] for row in rows}) == len(rows)


def test_stale_pending_expires_even_if_history_has_next_open():
    rows = [{
        "Txn_ID": "AAA|2026-10-19|BUY", "Signal_Date": "2026-10-19",
        "Ticker": "AAA", "Action": "PENDING", "Entry_Date": "",
        "Entry_Price": "", "Shares": "", "Entry_Commission": "",
        "Exit_Date": "", "Mode": "PAPER",
    }]
    prices = {"AAA": [
        {"date": "2026-10-19", "open": 49.0, "high": 51.0, "low": 48.0, "close": 50.0},
        {"date": "2026-10-20", "open": 48.5, "high": 50.0, "low": 47.0, "close": 49.0},
    ]}
    filled, expired = _fill_pending_orders(rows, prices, today="2026-10-25")
    assert (filled, expired) == (0, 1)
    assert rows[0]["Action"] == "EXPIRED"
    assert rows[0]["Reason"] == "SIGNAL_TOO_OLD_TO_FILL"


def test_missed_expected_session_expires_instead_of_backfilling_open():
    rows = [{
        "Txn_ID": "AAA|2026-10-19|BUY", "Signal_Date": "2026-10-19",
        "Ticker": "AAA", "Action": "PENDING", "Entry_Date": "",
        "Entry_Price": "", "Shares": "", "Entry_Commission": "",
        "Exit_Date": "", "Mode": "PAPER",
    }]
    prices = {"AAA": [
        {"date": "2026-10-19", "open": 49.0, "high": 51.0, "low": 48.0, "close": 50.0},
        {"date": "2026-10-20", "open": 48.5, "high": 50.0, "low": 47.0, "close": 49.0},
        {"date": "2026-10-21", "open": 52.0, "high": 54.0, "low": 51.0, "close": 53.0},
    ]}
    filled, expired = _fill_pending_orders(rows, prices, today="2026-10-21")
    assert (filled, expired) == (0, 1)
    assert rows[0]["Action"] == "EXPIRED"
    assert rows[0]["Entry_Source_Date"] == "2026-10-20"
    assert rows[0]["Reason"] == "MISSED_EXPECTED_SESSION_EXECUTION_WINDOW"


def test_missing_first_open_expires_order_instead_of_late_fill():
    rows = [{
        "Txn_ID": "AAA|2026-10-19|BUY", "Signal_Date": "2026-10-19",
        "Ticker": "AAA", "Action": "PENDING", "Entry_Date": "",
        "Entry_Price": "", "Shares": "", "Entry_Commission": "",
        "Exit_Date": "", "Mode": "PAPER",
    }]
    prices = {"AAA": [
        {"date": "2026-10-19", "open": 49.0, "high": 51.0, "low": 48.0, "close": 50.0},
        {"date": "2026-10-20", "open": None, "high": 51.0, "low": 47.0, "close": 49.0},
        {"date": "2026-10-21", "open": 52.0, "high": 54.0, "low": 51.0, "close": 53.0},
    ]}
    filled, expired = _fill_pending_orders(rows, prices, today="2026-10-20")
    assert (filled, expired) == (0, 1)
    assert rows[0]["Action"] == "EXPIRED"
    assert rows[0]["Reason"] == "MISSING_TICKER_BAR_OR_OPEN_ON_FIRST_POST_SIGNAL_SESSION"


def test_buy_sell_slippage_is_adverse():
    reference = 100.0
    assert buy_execution_price(reference) > reference
    assert sell_execution_price(reference) < reference
    assert math.isclose(buy_execution_price(reference), 100.05, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(sell_execution_price(reference), 99.95, rel_tol=0, abs_tol=1e-9)


def test_commission_and_net_pnl_include_both_sides():
    entry = buy_execution_price(100.0)
    exit_ = sell_execution_price(110.0)
    shares = 100.0
    buy_fee = commission(entry * shares)
    sell_fee = commission(exit_ * shares)
    gross, net, pct = net_trade_pnl(entry, exit_, shares, buy_fee, sell_fee)
    assert math.isclose(gross, (exit_ - entry) * shares, abs_tol=1e-9)
    assert math.isclose(net, gross - buy_fee - sell_fee, abs_tol=1e-9)
    assert net < gross
    assert pct > 0


def test_fill_pending_uses_next_real_open_and_records_costs():
    rows = [{
        "Txn_ID": "APA|2026-10-19|BUY", "Signal_Date": "2026-10-19",
        "Ticker": "APA", "Action": "PENDING", "Entry_Date": "",
        "Entry_Price": "", "Shares": "", "Entry_Commission": "",
        "Exit_Date": "", "Mode": "PAPER",
    }]
    prices = {"APA": [
        {"date": "2026-10-19", "open": 49.0, "high": 51.0, "low": 48.0, "close": 50.0},
        {"date": "2026-10-20", "open": 48.5, "high": 50.0, "low": 47.0, "close": 49.0},
    ]}
    filled, expired = _fill_pending_orders(rows, prices, today="2026-10-20")
    assert (filled, expired) == (1, 0)
    row = rows[0]
    assert row["Action"] == "BUY"
    assert row["Entry_Date"] == "2026-10-20"
    assert row["Entry_Source_Date"] == "2026-10-20"
    assert math.isclose(float(row["Reference_Entry_Price"]), 48.5, abs_tol=1e-9)
    assert float(row["Entry_Price"]) > 48.5
    assert float(row["Entry_Commission"]) > 0


def test_pending_order_stays_pending_without_future_bar():
    rows = [{
        "Txn_ID": "APA|2026-10-19|BUY", "Signal_Date": "2026-10-19",
        "Ticker": "APA", "Action": "PENDING", "Entry_Date": "",
        "Entry_Price": "", "Shares": "", "Entry_Commission": "",
        "Exit_Date": "", "Mode": "PAPER",
    }]
    prices = {"APA": [
        {"date": "2026-10-19", "open": 49.0, "high": 51.0, "low": 48.0, "close": 50.0},
    ]}
    filled, expired = _fill_pending_orders(rows, prices)
    assert (filled, expired) == (0, 0)
    assert rows[0]["Action"] == "PENDING"


def test_missing_ticker_session_expires_instead_of_late_fill():
    rows = [{
        "Txn_ID": "AAA|2026-10-19|BUY", "Signal_Date": "2026-10-19",
        "Ticker": "AAA", "Action": "PENDING", "Entry_Date": "",
        "Entry_Price": "", "Shares": "", "Entry_Commission": "",
        "Exit_Date": "", "Mode": "PAPER",
    }]
    # SPY proves 2026-10-20 was a market session; AAA has a later bar but is missing that session.
    prices = {
        "SPY": [
            {"date": "2026-10-19", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
            {"date": "2026-10-20", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5},
        ],
        "AAA": [
            {"date": "2026-10-19", "open": 49.0, "high": 51.0, "low": 48.0, "close": 50.0},
            {"date": "2026-10-21", "open": 52.0, "high": 54.0, "low": 51.0, "close": 53.0},
        ],
    }
    filled, expired = _fill_pending_orders(rows, prices, today="2026-10-21")
    assert (filled, expired) == (0, 1)
    assert rows[0]["Action"] == "EXPIRED"
    assert rows[0]["Entry_Source_Date"] == "2026-10-20"


def test_execution_window_defaults_to_non_executing_scan_mode():
    import os
    previous = os.environ.get("PAPER_EXECUTION_WINDOW")
    try:
        os.environ.pop("PAPER_EXECUTION_WINDOW", None)
        assert execution_window_enabled() is False
        os.environ["PAPER_EXECUTION_WINDOW"] = "SCAN"
        assert execution_window_enabled() is False
        os.environ["PAPER_EXECUTION_WINDOW"] = "EOD"
        assert execution_window_enabled() is True
    finally:
        if previous is None:
            os.environ.pop("PAPER_EXECUTION_WINDOW", None)
        else:
            os.environ["PAPER_EXECUTION_WINDOW"] = previous


def test_exit_does_not_backdate_trigger_to_old_close():
    rows = [{
        "Ticker": "AAA", "Action": "BUY", "Signal_Date": "2026-10-16",
        "Entry_Date": "2026-10-19", "Entry_Price": "100.0", "Shares": "10",
        "Entry_Commission": "0.50", "Exit_Date": "",
    }]
    prices = {"AAA": [
        {"date": "2026-10-16", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
        {"date": "2026-10-19", "open": 100.0, "high": 101.0, "low": 89.0, "close": 90.0},
        {"date": "2026-10-20", "open": 96.0, "high": 99.0, "low": 95.0, "close": 98.0},
    ]}
    closed = close_positions(rows, prices, today="2026-10-20")
    assert closed == 1
    assert rows[0]["Exit_Date"] == "2026-10-20"
    assert rows[0]["Exit_Source_Date"] == "2026-10-20"
    assert rows[0]["Reason"] == "Delayed_Stop_Loss_Close_Trigger_2026-10-19"
    assert float(rows[0]["Exit_Reference_Price"]) == 98.0
    assert rows[0]["Hold_Days"] == "2"


def test_exit_waits_when_no_current_completed_bar_exists():
    rows = [{
        "Ticker": "AAA", "Action": "BUY", "Signal_Date": "2026-10-16",
        "Entry_Date": "2026-10-19", "Entry_Price": "100.0", "Shares": "10",
        "Entry_Commission": "0.50", "Exit_Date": "",
    }]
    prices = {"AAA": [
        {"date": "2026-10-19", "open": 100.0, "high": 101.0, "low": 89.0, "close": 90.0},
    ]}
    closed = close_positions(rows, prices, today="2026-10-20")
    assert closed == 0
    assert rows[0]["Action"] == "BUY"
    assert rows[0]["Exit_Date"] == ""


def test_observation_requires_recent_completed_price_bar():
    assert observation_data_ready({}, "2026-10-20") is False

    # A single ticker with a fresh bar must not pass the breadth guard.
    one_ticker = {
        "AAA": [{"date": "2026-10-19", "open": 10.0, "close": 11.0}]
    }
    assert observation_data_ready(one_ticker, "2026-10-20") is False

    # Premarket scan can only consume the previous session's completed close.
    fresh_30 = {
        f"T{i:03d}": [{"date": "2026-10-19", "open": 10.0, "close": 11.0}]
        for i in range(30)
    }
    assert observation_data_ready(fresh_30, "2026-10-20") is True

    # A four-calendar-day gap allows a long weekend plus a Monday market holiday.
    holiday_gap = {
        f"T{i:03d}": [{"date": "2026-10-16", "open": 10.0, "close": 11.0}]
        for i in range(30)
    }
    assert observation_data_ready(holiday_gap, "2026-10-20") is True

    stale = {
        f"T{i:03d}": [{"date": "2026-10-15", "open": 10.0, "close": 11.0}]
        for i in range(30)
    }
    assert observation_data_ready(stale, "2026-10-20") is False

    # Future-dated data must not establish readiness for an earlier run date.
    future = {
        f"T{i:03d}": [{"date": "2026-10-21", "open": 12.0, "close": 13.0}]
        for i in range(30)
    }
    assert observation_data_ready(future, "2026-10-20") is False

    # Mixed coverage: only one fresh ticker is insufficient even when many are stale.
    mixed = {
        "FRESH": [{"date": "2026-10-19", "open": 10.0, "close": 11.0}],
        **{
            f"OLD{i:03d}": [{"date": "2026-10-15", "open": 10.0, "close": 11.0}]
            for i in range(50)
        },
    }
    assert observation_data_ready(mixed, "2026-10-20") is False


def test_manual_runs_do_not_advance_observation_gate(monkeypatch=None):
    import os
    previous = os.environ.get("PAPER_RECORD_OBSERVATION")
    try:
        os.environ.pop("PAPER_RECORD_OBSERVATION", None)
        assert observation_eligible() is False
        os.environ["PAPER_RECORD_OBSERVATION"] = "0"
        assert observation_eligible() is False
        os.environ["PAPER_RECORD_OBSERVATION"] = "1"
        assert observation_eligible() is True
    finally:
        if previous is None:
            os.environ.pop("PAPER_RECORD_OBSERVATION", None)
        else:
            os.environ["PAPER_RECORD_OBSERVATION"] = previous


def test_observation_log_counts_zero_signal_days_and_is_idempotent():
    import csv
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "observations.csv"
        prices = {"SPY": [{"date": "2026-10-19", "open": 100.0, "close": 101.0}]}
        record_observation("2026-10-19", prices, "", 0, 0, 0, 0, 0, 0, path=path)
        # Repeat run the same ET date: update that date's row rather than duplicating it.
        record_observation("2026-10-19", prices, "us_stocks_pending_20261019.csv", 1, 0, 0, 0, 0, 1, path=path)
        record_observation("2026-10-20", prices, "", 0, 0, 0, 0, 0, 0, path=path)
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 2
        assert rows[0]["Run_Date"] == "2026-10-19"
        assert rows[0]["Signals_Queued"] == "1"
        assert rows[1]["Run_Date"] == "2026-10-20"
        assert rows[1]["Signals_Queued"] == "0"


def test_stale_pending_file_does_not_create_backdated_order():
    import csv
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "us_stocks_pending_20261019.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["Ticker", "Status"])
            w.writeheader()
            w.writerow({"Ticker": "APA", "Status": "pending"})
        rows = []
        created = _create_signal_orders(rows, [path], "2026-10-20")
        assert created == 0
        assert rows == []


def test_pending_order_expires_when_corrected_history_is_delayed_too_long():
    rows = [{
        "Txn_ID": "APA|2026-10-19|BUY", "Signal_Date": "2026-10-19",
        "Ticker": "APA", "Action": "PENDING", "Entry_Date": "",
        "Entry_Price": "", "Shares": "", "Entry_Commission": "",
        "Exit_Date": "", "Mode": "PAPER",
    }]
    # Schema guard makes prices empty until the full history rebuild is published.
    filled, expired = _fill_pending_orders(rows, {}, today="2026-10-24")
    assert (filled, expired) == (0, 1)
    assert rows[0]["Action"] == "EXPIRED"
    assert rows[0]["Reason"] == "SIGNAL_TOO_OLD_TO_FILL"


def test_legacy_or_mixed_price_schema_fails_closed():
    import csv
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "prices.csv"
        fields = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]
        rows = [
            {"Date": "2026-10-19", "Ticker": "AAA", "Open": "49", "High": "51",
             "Low": "48", "Close": "50", "Volume": "1000", "schema_version": "phase2b.v1"},
            {"Date": "2026-10-20", "Ticker": "AAA", "Open": "50", "High": "52",
             "Low": "49", "Close": "51", "Volume": "1100", "schema_version": PRICE_SCHEMA_VERSION},
        ]
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        assert load_prices(path) == {}


def test_corrected_price_schema_is_accepted():
    import csv
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "prices.csv"
        fields = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]
        row = {"Date": "2026-10-20", "Ticker": "AAA", "Open": "50", "High": "52",
               "Low": "49", "Close": "51", "Volume": "1100", "schema_version": PRICE_SCHEMA_VERSION}
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerow(row)
        prices = load_prices(path)
        assert prices["AAA"][0]["date"] == "2026-10-20"
        assert prices["AAA"][0]["open"] == 50.0


def test_candidate_ticker_filter_honors_status():
    rows = [
        {"Ticker": "APA", "Status": "pending"},
        {"Ticker": "XOM", "Status": "rejected"},
        {"Ticker": "APA", "Status": "pending"},
        {"Ticker": "CVX", "Status": ""},
    ]
    assert _candidate_tickers(rows) == ["APA", "CVX"]


def main():
    tests = [
        test_next_open_uses_exact_first_post_signal_bar,
        test_missing_next_open_fails_closed,
        test_asof_date_blocks_future_bar,
        test_void_row_does_not_block_corrected_signal,
        test_missing_first_open_expires_order_instead_of_late_fill,
        test_missed_expected_session_expires_instead_of_backfilling_open,
        test_stale_pending_expires_even_if_history_has_next_open,
        test_buy_sell_slippage_is_adverse,
        test_commission_and_net_pnl_include_both_sides,
        test_fill_pending_uses_next_real_open_and_records_costs,
        test_pending_order_stays_pending_without_future_bar,
        test_missing_ticker_session_expires_instead_of_late_fill,
        test_observation_log_counts_zero_signal_days_and_is_idempotent,
        test_manual_runs_do_not_advance_observation_gate,
        test_observation_requires_recent_completed_price_bar,
        test_execution_window_defaults_to_non_executing_scan_mode,
        test_exit_does_not_backdate_trigger_to_old_close,
        test_exit_waits_when_no_current_completed_bar_exists,
        test_stale_pending_file_does_not_create_backdated_order,
        test_pending_order_expires_when_corrected_history_is_delayed_too_long,
        test_legacy_or_mixed_price_schema_fails_closed,
        test_corrected_price_schema_is_accepted,
        test_candidate_ticker_filter_honors_status,
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
