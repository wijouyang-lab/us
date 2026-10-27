# -*- coding: utf-8 -*-
"""Dashboard 汇总的「快照之后」滚动：盘中止损卖出后不得出现假亏损。

背景（线上真实事故）：
  2026-10-22 APA 盘中止损卖出 200 股 / $9,628，但 history.csv 最后一行仍是
  2026-10-20（Cash=40496.37）。旧逻辑直接读 history 的 Cash，
  于是 Total Equity = 40496.37 + 0 = 40496.37 → Total PnL = -$9,503.63（-19%）。
  实际卖出后现金应为 50124.37，总盈亏 +$124.37。

本测试锁死：
  1) history 之后的 SELL/BUY 会滚动进 cash / realized_pnl；
  2) asof 取「快照日 与 流水最大日」的较大者；
  3) equity_curve 末尾补上当前权益点（曲线终点 == 汇总 Total Equity）；
  4) open_positions 以 positions 实际 OPEN 数为准，不再信 history 的旧计数。
"""
import json
import csv
import datetime as dt
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dashboard_export import build_portfolio  # noqa: E402


def _write(tmp_path: Path):
    (tmp_path / "portfolio_50000_meta.json").write_text(json.dumps({
        "portfolio_id": "US-50000-001",
        "initial_capital": 50000.0,
        "start_date": "2026-10-06",
        "unit_dollars": 10000.0,
        "max_open_positions": 4,
    }), encoding="utf-8")

    # 已全部平仓：没有 OPEN 持仓
    (tmp_path / "portfolio_50000_positions.csv").write_text(
        "Portfolio_ID,Unit_ID,Ticker,Shares,Entry_Price,Entry_Date,Cost_Basis,Current_Price,"
        "Market_Value,Unrealized_PnL,Unrealized_PnL_Pct,Weight_Pct,Status,Stop_Loss\n"
        "US-50000-001,U001,APA,0,49.76,2026-10-19,9952.00,48.14,0.00,0.00,0.00,0.00,CLOSED,48.27\n",
        encoding="utf-8")

    # 关键：现金流水的 SELL 发生在 history 快照日之后
    (tmp_path / "portfolio_50000_transactions.csv").write_text(
        "Txn_ID,Date,Ticker,Action,Shares,Price,Amount,Realized_PnL,Cash_After,Reason,"
        "Recommendation_ID,Scan_Date,Portfolio_ID,Unit_ID,Pending_Reason,Quote_As_Of\n"
        "APA|2026-10-19|Core_Dragon|BUY,2026-10-19,APA,BUY,200,49.76,9952.00,0.00,"
        "40496.37,Core recommendation,APA|2026-10-19|Core_Dragon,2026-10-19,US-50000-001,U001,,\n"
        "INTRADAY|APA|2026-10-22,2026-10-22,APA,SELL,200,48.14,9628.00,-324.00,,"
        "Intraday Stop Loss,APA|2026-10-19|Core_Dragon,2026-10-19,US-50000-001,U001,True,"
        "2026-10-22T11:30:00-04:00\n",
        encoding="utf-8")

    (tmp_path / "portfolio_50000_history.csv").write_text(
        "Date,Cash,Stock_Value,Total_Equity,Realized_PnL,Unrealized_PnL,Total_PnL,"
        "Return_Pct,Open_Positions\n"
        "2026-10-20,40496.37,9952.00,50448.37,448.37,0.00,448.37,0.90,1\n",
        encoding="utf-8")


def test_post_snapshot_sell_rolls_cash_and_realized(tmp_path):
    _write(tmp_path)
    pf = build_portfolio(tmp_path)

    assert pf["cash"] == pytest.approx(50124.37, abs=0.01)      # 40496.37 + 9628
    assert pf["stock_value"] == 0.0
    assert pf["total_equity"] == pytest.approx(50124.37, abs=0.01)
    assert pf["realized_pnl"] == pytest.approx(124.37, abs=0.01)  # 448.37 - 324
    assert pf["total_pnl"] == pytest.approx(124.37, abs=0.01)     # 不再是 -9503.63
    assert pf["return_pct"] == pytest.approx(0.25, abs=0.01)
    assert pf["asof"] == "2026-10-22"
    assert pf["open_positions"] == 0
    assert pf["open_pct"] == 0.0

    curve = pf["equity_curve"]
    assert curve[-1]["date"] == "2026-10-22"
    assert curve[-1]["total_equity"] == pytest.approx(50124.37, abs=0.01)
    assert curve[-1]["total_equity"] == pf["total_equity"]


def test_history_in_sync_is_unchanged(tmp_path):
    """history 已含最新成交时，滚动为 0，结果与旧口径一致。"""
    _write(tmp_path)
    (tmp_path / "portfolio_50000_history.csv").write_text(
        "Date,Cash,Stock_Value,Total_Equity,Realized_PnL,Unrealized_PnL,Total_PnL,"
        "Return_Pct,Open_Positions\n"
        "2026-10-22,50124.37,0.00,50124.37,124.37,0.00,124.37,0.25,0\n",
        encoding="utf-8")
    pf = build_portfolio(tmp_path)
    assert pf["cash"] == pytest.approx(50124.37, abs=0.01)
    assert pf["total_pnl"] == pytest.approx(124.37, abs=0.01)
    assert pf["asof"] == "2026-10-22"
    assert len(pf["equity_curve"]) == 2          # 原点 + 快照，无重复追加


def test_exit_rules_are_passed_from_strategy_params(tmp_path):
    """前端「止盈价何时激活」必须用真实阈值，不能硬编码。"""
    _write(tmp_path)
    (tmp_path / "strategy_params.json").write_text(json.dumps({
        "exit": {
            "breakeven_trigger_pct": 5.0,
            "breakeven_floor_multiplier": 1.0,
            "profit_lock_1_pct": 15.0, "profit_lock_1_drawdown_pct": 10.0,
            "profit_lock_2_pct": 30.0, "profit_lock_2_drawdown_pct": 8.0,
            "profit_lock_3_pct": 50.0, "profit_lock_3_drawdown_pct": 12.0,
            "early_stop_pct": -5.0,
        }
    }), encoding="utf-8")
    pf = build_portfolio(tmp_path)
    rules = pf["exit_rules"]
    assert rules is not None
    assert rules["breakeven_trigger_pct"] == 5.0
    assert rules["profit_lock_1_pct"] == 15.0
    assert rules["early_stop_pct"] == -5.0


def test_exit_rules_null_when_params_missing(tmp_path):
    _write(tmp_path)
    pf = build_portfolio(tmp_path)
    assert pf["exit_rules"] is None          # 前端回退为「浮盈达标后抬保本」文案


def _write_many_sells(tmp_path, n=25, start="2026-09-25", history_date="2026-10-01"):
    """写 n 笔 SELL（跨 9/10 月），用于验证月度聚合不受 20 条展示截断影响。"""
    _write(tmp_path)
    cols = ["Txn_ID", "Date", "Ticker", "Action", "Shares", "Price", "Amount",
            "Realized_PnL", "Cash_After", "Reason", "Recommendation_ID", "Scan_Date",
            "Portfolio_ID", "Unit_ID", "Pending_Reason", "Quote_As_Of"]
    d0 = dt.date.fromisoformat(start)
    rows = []
    for i in range(n):
        day = (d0 + dt.timedelta(days=i)).isoformat()
        profit = i % 2 == 0
        rows.append({
            "Txn_ID": f"T{i}|SELL|{day}", "Date": day, "Ticker": f"T{i}", "Action": "SELL",
            "Shares": "10", "Price": "20.00", "Amount": "200.00",
            "Realized_PnL": "10.00" if profit else "-5.00",
            "Reason": "Review exit: Trailing_Profit_Take" if profit else "Review exit: Stop_Loss_Hit",
            "Recommendation_ID": f"T{i}", "Scan_Date": day,
            "Portfolio_ID": "US-50000-001", "Unit_ID": f"U{i}",
        })
    with (tmp_path / "portfolio_50000_transactions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (tmp_path / "portfolio_50000_history.csv").write_text(
        "Date,Cash,Stock_Value,Total_Equity,Realized_PnL,Unrealized_PnL,Total_PnL,"
        "Return_Pct,Open_Positions\n"
        f"{history_date},50000.00,0.00,50000.00,0.00,0.00,0.00,0.00,0\n",
        encoding="utf-8")


def test_closed_months_covers_full_ledger_beyond_20_rows(tmp_path):
    _write_many_sells(tmp_path, n=25)
    pf = build_portfolio(tmp_path)

    # 展示窗口仍只有 20 条
    assert len(pf["transactions"]) == 20
    # 但月度聚合基于全量流水：25 笔一个不少
    months = pf["closed_months"]
    assert months, months
    total = sum((m["profit"]["n"] + m["stop"]["n"]) for m in months)
    assert total == 25, months
    assert sum(m["profit"]["n"] for m in months) == 13
    assert sum(m["stop"]["n"] for m in months) == 12
    assert [m["month"] for m in months] == sorted((m["month"] for m in months), reverse=True)


def test_snapshot_lag_flags_rolled_txns(tmp_path):
    _write_many_sells(tmp_path, n=5, start="2026-09-25", history_date="2026-09-26")
    pf = build_portfolio(tmp_path)
    assert pf["snapshot_asof"] == "2026-09-26"
    assert pf["asof"] == "2026-09-29"          # 最后一笔 SELL 日期
    assert pf["rolled_txns"] == 3              # 快照日(09-26)之后仍有 3 笔成交

