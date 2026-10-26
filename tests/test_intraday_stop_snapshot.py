# -*- coding: utf-8 -*-
"""盘中止损必须同时落「权益快照」：否则 Dashboard 会读到上一日的 Cash。

回归线上事故：2026-10-22 APA 盘中止损只写了 transactions/positions，
history.csv 仍停在 10-20，Dashboard 把卖回笼的 $9,628 当成蒸发，
Total PnL 显示 -$9,503.63。本测试锁死：
  · transactions 里新卖出行的 Cash_After 被回填；
  · history 追加/覆盖当日快照（Cash / Total_Equity / Open_Positions 正确）；
  · 持仓被置为 CLOSED、股数 0；
  · 成交时刻侧车写入该笔（供前端显示几点几分）。
"""
import csv
import importlib.util
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("pf_mod", REPO / "portfolio_50000.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def test_intraday_sell_writes_equity_snapshot(tmp_path, monkeypatch):
    pf = _load()

    (tmp_path / "portfolio_50000_meta.json").write_text(
        '{"portfolio_id":"US-50000-001","initial_capital":"50000.00",'
        '"start_date":"2026-10-06","unit_dollars":"10000.00","max_open_positions":4}',
        encoding="utf-8")

    _write(tmp_path / "portfolio_50000_positions.csv", pf.POSITION_COLUMNS, [{
        "Portfolio_ID": "US-50000-001", "Unit_ID": "U001", "Ticker": "APA",
        "Shares": "200", "Entry_Price": "49.76", "Entry_Date": "2026-10-19",
        "Cost_Basis": "9952.00", "Current_Price": "49.76", "Market_Value": "9952.00",
        "Unrealized_PnL": "0.00", "Unrealized_PnL_Pct": "0.00", "Weight_Pct": "19.74",
        "Status": "OPEN", "Stop_Loss": "48.27",
        "Recommendation_ID": "APA|2026-10-19|Core_Dragon", "Last_Update": "2026-10-21",
    }])

    # 完整流水（现金由 INITIAL_CAPITAL + 流水推导，必须包含账户此前所有成交）
    _write(tmp_path / "portfolio_50000_transactions.csv", pf.TRANSACTION_COLUMNS, [
        {"Txn_ID": "ADSK|2026-10-07|Core_Dragon|BUY", "Date": "2026-10-07", "Ticker": "ADSK",
         "Action": "BUY", "Shares": "43", "Price": "231.42", "Amount": "9951.06",
         "Realized_PnL": "0.00", "Cash_After": "40048.94", "Reason": "Core",
         "Scan_Date": "2026-10-07", "Portfolio_ID": "US-50000-001", "Unit_ID": "U001"},
        {"Txn_ID": "ANET|2026-10-07|Core_Dragon|BUY", "Date": "2026-10-07", "Ticker": "ANET",
         "Action": "BUY", "Shares": "47", "Price": "211.30", "Amount": "9931.10",
         "Realized_PnL": "0.00", "Cash_After": "30117.84", "Reason": "Core",
         "Scan_Date": "2026-10-07", "Portfolio_ID": "US-50000-001", "Unit_ID": "U002"},
        {"Txn_ID": "ISRG|2026-10-07|Core_Dragon|BUY", "Date": "2026-10-07", "Ticker": "ISRG",
         "Action": "BUY", "Shares": "24", "Price": "405.07", "Amount": "9721.68",
         "Realized_PnL": "0.00", "Cash_After": "20396.16", "Reason": "Core",
         "Scan_Date": "2026-10-07", "Portfolio_ID": "US-50000-001", "Unit_ID": "U003"},
        {"Txn_ID": "KR|2026-10-07|Core_Dragon|BUY", "Date": "2026-10-07", "Ticker": "KR",
         "Action": "BUY", "Shares": "168", "Price": "59.27", "Amount": "9957.36",
         "Realized_PnL": "0.00", "Cash_After": "10438.80", "Reason": "Core",
         "Scan_Date": "2026-10-07", "Portfolio_ID": "US-50000-001", "Unit_ID": "U004"},
        {"Txn_ID": "ANET|2026-10-07|Core_Dragon|SELL|2026-10-13", "Date": "2026-10-13",
         "Ticker": "ANET", "Action": "SELL", "Shares": "47", "Price": "204.98",
         "Amount": "9634.06", "Realized_PnL": "-297.04", "Cash_After": "20072.86",
         "Reason": "Review exit: Stop_Loss_Hit", "Scan_Date": "2026-10-07",
         "Portfolio_ID": "US-50000-001", "Unit_ID": "U002"},
        {"Txn_ID": "KR|2026-10-07|Core_Dragon|SELL|2026-10-13", "Date": "2026-10-13",
         "Ticker": "KR", "Action": "SELL", "Shares": "168", "Price": "60.68",
         "Amount": "10194.24", "Realized_PnL": "236.88", "Cash_After": "30267.10",
         "Reason": "Review exit: Stop_Loss_Hit", "Scan_Date": "2026-10-07",
         "Portfolio_ID": "US-50000-001", "Unit_ID": "U004"},
        {"Txn_ID": "ISRG|2026-10-07|Core_Dragon|SELL|2026-10-14", "Date": "2026-10-14",
         "Ticker": "ISRG", "Action": "SELL", "Shares": "24", "Price": "414.81",
         "Amount": "9955.44", "Realized_PnL": "233.76", "Cash_After": "40222.54",
         "Reason": "Review exit: Stop_Loss_Hit", "Scan_Date": "2026-10-07",
         "Portfolio_ID": "US-50000-001", "Unit_ID": "U003"},
        {"Txn_ID": "ADSK|2026-10-07|Core_Dragon|SELL|2026-10-16", "Date": "2026-10-16",
         "Ticker": "ADSK", "Action": "SELL", "Shares": "43", "Price": "237.81",
         "Amount": "10225.83", "Realized_PnL": "274.77", "Cash_After": "50448.37",
         "Reason": "Review exit: Trailing_Profit_Take", "Scan_Date": "2026-10-07",
         "Portfolio_ID": "US-50000-001", "Unit_ID": "U001"},
        {"Txn_ID": "APA|2026-10-19|Core_Dragon|BUY", "Date": "2026-10-19", "Ticker": "APA",
         "Action": "BUY", "Shares": "200", "Price": "49.76", "Amount": "9952.00",
         "Realized_PnL": "0.00", "Cash_After": "40496.37", "Reason": "Core recommendation",
         "Recommendation_ID": "APA|2026-10-19|Core_Dragon", "Scan_Date": "2026-10-19",
         "Portfolio_ID": "US-50000-001", "Unit_ID": "U001"},
    ])

    _write(tmp_path / "portfolio_50000_history.csv", pf.HISTORY_COLUMNS, [{
        "Date": "2026-10-20", "Cash": "40496.37", "Stock_Value": "9952.00",
        "Total_Equity": "50448.37", "Realized_PnL": "448.37", "Unrealized_PnL": "0.00",
        "Total_PnL": "448.37", "Return_Pct": "0.90", "Open_Positions": "1",
        "Portfolio_ID": "US-50000-001",
    }])

    monkeypatch.setattr(
        pf, "fetch_intraday_last_prices",
        lambda tickers, now_et=None: {"APA": {"current": Decimal("48.14"),
                                              "as_of": "2026-10-22T11:30:00-04:00"}},
    )

    now_et = datetime(2026, 10, 22, 11, 30, tzinfo=ZoneInfo("America/New_York"))
    res = pf._run_intraday_stop(tmp_path, "2026-10-22", offline=False, now_et=now_et)
    assert res["triggered"] == 1

    txns = list(csv.DictReader((tmp_path / "portfolio_50000_transactions.csv").open(encoding="utf-8")))
    sell = [t for t in txns if t["Txn_ID"] == "INTRADAY|APA|2026-10-22"]
    assert len(sell) == 1, [t["Txn_ID"] for t in txns]
    assert sell[0]["Amount"] == "9628.00"
    assert sell[0]["Realized_PnL"] == "-324.00"
    assert sell[0]["Cash_After"] == "50124.37"          # 回填成功

    hist = list(csv.DictReader((tmp_path / "portfolio_50000_history.csv").open(encoding="utf-8")))
    today = [h for h in hist if h["Date"] == "2026-10-22"]
    assert len(today) == 1, hist
    assert today[0]["Cash"] == "50124.37"
    assert today[0]["Stock_Value"] == "0.00"
    assert today[0]["Total_Equity"] == "50124.37"
    assert today[0]["Realized_PnL"] == "124.37"
    assert today[0]["Total_PnL"] == "124.37"
    assert today[0]["Open_Positions"] == "0"

    pos = list(csv.DictReader((tmp_path / "portfolio_50000_positions.csv").open(encoding="utf-8")))
    assert pos[0]["Status"] == "CLOSED" and pos[0]["Shares"] == "0"

    side = list(csv.DictReader((tmp_path / "portfolio_50000_txn_time.csv").open(encoding="utf-8")))
    assert side and side[0]["Txn_ID"] == "INTRADAY|APA|2026-10-22"
