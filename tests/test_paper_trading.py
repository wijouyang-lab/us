# -*- coding: utf-8 -*-
"""Paper Trading 纯逻辑回归测试，不依赖 Yahoo 网络或真实账本。"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.paper_trading import (
    _candidate_tickers,
    _fill_pending_orders,
    buy_execution_price,
    commission,
    next_open_bar,
    net_trade_pnl,
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
    filled, expired = _fill_pending_orders(rows, prices)
    assert (filled, expired) == (0, 1)
    assert rows[0]["Action"] == "EXPIRED"
    assert rows[0]["Reason"] == "MISSING_OPEN_ON_FIRST_POST_SIGNAL_BAR"


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
    filled, expired = _fill_pending_orders(rows, prices)
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
        test_missing_first_open_expires_order_instead_of_late_fill,
        test_missing_next_open_fails_closed,
        test_buy_sell_slippage_is_adverse,
        test_commission_and_net_pnl_include_both_sides,
        test_fill_pending_uses_next_real_open_and_records_costs,
        test_pending_order_stays_pending_without_future_bar,
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
