# -*- coding: utf-8 -*-
"""Recent Portfolio Transactions：成交时刻（几点几分）+ 持有时间。

覆盖三层：
  1. dashboard_export.build_portfolio 透传侧车时刻，并按 Unit 配对 BUY→SELL；
  2. 侧车缺失（历史/新账户）时降级为「只有日期、持有天数照算」，绝不捏造时刻；
  3. 侧车必须被持久化（.gitignore 不忽略 + 三个 workflow 都 git add），
     否则每次 Actions checkout 后历史时刻都会丢失。
"""
import json
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dashboard_export import build_portfolio  # noqa: E402

TXN_HEADER = ("Txn_ID,Date,Ticker,Action,Shares,Price,Amount,Realized_PnL,Cash_After,"
              "Reason,Recommendation_ID,Scan_Date,Portfolio_ID,Unit_ID,Pending_Reason\n")
TIME_HEADER = "Txn_ID,Execution_Time,Trade_Date\n"


def _write_dir(tmp_path: Path, txn_rows, time_rows=None):
    (tmp_path / "portfolio_50000_meta.json").write_text(json.dumps({
        "portfolio_id": "TEST-001",
        "initial_capital": 50000.0,
        "start_date": "2026-10-01",
        "unit_dollars": 10000.0,
        "max_open_positions": 4,
    }), encoding="utf-8")
    (tmp_path / "portfolio_50000_positions.csv").write_text(
        "Portfolio_ID,Unit_ID,Ticker,Shares,Entry_Price,Entry_Date,Cost_Basis,Current_Price,"
        "Market_Value,Unrealized_PnL,Unrealized_PnL_Pct,Weight_Pct,Status,Stop_Loss\n",
        encoding="utf-8")
    (tmp_path / "portfolio_50000_transactions.csv").write_text(
        TXN_HEADER + "".join(txn_rows), encoding="utf-8")
    (tmp_path / "portfolio_50000_history.csv").write_text(
        "Date,Cash,Stock_Value,Total_Equity,Realized_PnL,Unrealized_PnL,Total_PnL,"
        "Return_Pct,Open_Positions\n"
        "2026-10-19,50000.0,0.0,50000.0,0.0,0.0,0.0,0.0,0\n",
        encoding="utf-8")
    if time_rows is not None:
        (tmp_path / "portfolio_50000_txn_time.csv").write_text(
            TIME_HEADER + "".join(time_rows), encoding="utf-8")


BUY = ("ADSK|2026-10-07|Core_Dragon|BUY,2026-10-07,ADSK,BUY,43,231.42,9951.06,0.00,"
       "40048.94,Core recommendation -> 1 Unit long,ADSK|2026-10-07|Core_Dragon,"
       "2026-10-07,US-50000-001,U001,\n")
SELL = ("ADSK|2026-10-07|Core_Dragon|SELL|2026-10-16,2026-10-16,ADSK,SELL,43,237.81,"
        "10225.83,274.77,50448.37,Review exit: Trailing_Profit_Take,"
        "ADSK|2026-10-07|Core_Dragon,2026-10-07 00:00:00,US-50000-001,U001,\n")
BUY_ANET = ("ANET|2026-10-07|Core_Dragon|BUY,2026-10-07,ANET,BUY,47,211.30,9931.10,0.00,"
            "30117.84,Core recommendation -> 1 Unit long,ANET|2026-10-07|Core_Dragon,"
            "2026-10-07,US-50000-001,U002,\n")

BUY_TIME = "ADSK|2026-10-07|Core_Dragon|BUY,2026-10-07 21:44:58,2026-10-07\n"
SELL_TIME = "ADSK|2026-10-07|Core_Dragon|SELL|2026-10-16,2026-10-16 18:26:27,2026-10-16\n"


def _by_ticker_action(pf, ticker, action):
    for t in pf["transactions"]:
        if t["ticker"] == ticker and t["action"] == action:
            return t
    raise AssertionError(f"missing txn {ticker} {action}")


def test_txn_time_and_pairing_with_sidecar(tmp_path):
    _write_dir(tmp_path, [BUY, SELL, BUY_ANET], [BUY_TIME, SELL_TIME])
    pf = build_portfolio(tmp_path)

    buy = _by_ticker_action(pf, "ADSK", "BUY")
    sell = _by_ticker_action(pf, "ADSK", "SELL")

    # 本笔成交时刻（HH:MM，美东）
    assert buy["time"] == "21:44"
    assert sell["time"] == "18:26"
    assert buy["execution_time"] == "2026-10-07 21:44:58"

    # SELL 行回填买入侧；BUY 行回填卖出侧；两行共享同一段持有时间
    assert sell["entry_date"] == "2026-10-07"
    assert sell["entry_time"] == "21:44"
    assert buy["exit_date"] == "2026-10-16"
    assert buy["exit_time"] == "18:26"
    assert sell["holding_days"] == 9 and buy["holding_days"] == 9
    # 21:44 -> 18:26 跨 8 天 20 小时 = 212 小时
    assert sell["holding_hours"] == 212 and buy["holding_hours"] == 212
    assert buy["holding_open"] is False


def test_open_buy_has_no_exit_and_uses_asof(tmp_path):
    _write_dir(tmp_path, [BUY_ANET], ["ANET|2026-10-07|Core_Dragon|BUY,2026-10-07 21:44:58,2026-10-07\n"])
    pf = build_portfolio(tmp_path)
    buy = _by_ticker_action(pf, "ANET", "BUY")
    assert buy["holding_open"] is True
    assert buy["exit_date"] is None and buy["exit_time"] is None
    assert buy["holding_days"] == 12          # asof 2026-10-19 - 2026-10-07
    assert buy["holding_hours"] is None


def test_missing_sidecar_degrades_to_date_only(tmp_path):
    """侧车缺失（旧账户/首次部署）→ time=None，但持有天数仍按日期计算。"""
    _write_dir(tmp_path, [BUY, SELL])
    pf = build_portfolio(tmp_path)
    buy = _by_ticker_action(pf, "ADSK", "BUY")
    sell = _by_ticker_action(pf, "ADSK", "SELL")
    assert buy["time"] is None and sell["time"] is None
    assert buy["execution_time"] is None
    assert sell["entry_date"] == "2026-10-07" and buy["exit_date"] == "2026-10-16"
    assert sell["holding_days"] == 9
    assert sell["holding_hours"] is None       # 无时刻 → 不给小时数，绝不猜


def test_unmatched_sell_keeps_own_time_only(tmp_path):
    """账本从半途开始（只有 SELL 无对应 BUY）→ 不猜测买入日/时。"""
    _write_dir(tmp_path, [SELL], [SELL_TIME])
    pf = build_portfolio(tmp_path)
    sell = _by_ticker_action(pf, "ADSK", "SELL")
    assert sell["time"] == "18:26"
    assert sell["entry_date"] is None and sell["entry_time"] is None
    assert sell["holding_days"] is None and sell["holding_hours"] is None


def test_intraday_quote_as_of_is_used_when_sidecar_missing(tmp_path):
    """盘中止损行即便没有侧车，也用它自己的 Quote_As_Of（触发 K 线时间）显示时刻。"""
    _write_dir(tmp_path, [], None)
    header = ("Txn_ID,Date,Ticker,Action,Shares,Price,Amount,Realized_PnL,Cash_After,"
              "Reason,Recommendation_ID,Scan_Date,Portfolio_ID,Unit_ID,Pending_Reason,Quote_As_Of\n")
    rows = (
        "APA|2026-10-19|Core_Dragon|BUY,2026-10-19,APA,BUY,200,49.76,9952.00,0.00,"
        "40496.37,Core recommendation -> 1 Unit long,APA|2026-10-19|Core_Dragon,"
        "2026-10-19,US-50000-001,U001,,\n"
        "INTRADAY|APA|2026-10-22,2026-10-22,APA,SELL,200,48.14,9628.00,-324.00,,"
        "Intraday Stop Loss,APA|2026-10-19|Core_Dragon,2026-10-19,US-50000-001,U001,True,"
        "2026-10-22T11:30:00-04:00\n"
    )
    (tmp_path / "portfolio_50000_transactions.csv").write_text(header + rows, encoding="utf-8")
    (tmp_path / "portfolio_50000_txn_time.csv").write_text(
        TIME_HEADER + "APA|2026-10-19|Core_Dragon|BUY,2026-10-19 18:26:47,2026-10-19\n",
        encoding="utf-8")
    pf = build_portfolio(tmp_path)
    sell = _by_ticker_action(pf, "APA", "SELL")
    assert sell["time"] == "11:30"
    assert sell["time_source"] == "quote_as_of"
    assert sell["entry_date"] == "2026-10-19" and sell["entry_time"] == "18:26"
    assert sell["holding_days"] == 3
    # 10-19 18:26 -> 10-22 11:30 = 65 小时
    assert sell["holding_hours"] == 65


def test_txn_time_sidecar_is_persisted():
    """侧车必须入库：.gitignore 不忽略 + review/scan/dashboard-data 三个 workflow 都 add。"""
    root = Path(_REPO_ROOT)
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "portfolio_50000_txn_time.csv" not in gitignore, (
        "侧车被 .gitignore 忽略 → Actions checkout 后历史时刻会丢失")

    for rel in (".github/workflows/review.yml",
                ".github/workflows/scan.yml",
                ".github/workflows/dashboard-data.yml"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "git add portfolio_50000_txn_time.csv" in text, (
            f"{rel} 未持久化成交时刻侧车")
