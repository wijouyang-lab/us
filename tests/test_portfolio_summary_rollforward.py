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
