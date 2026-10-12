"""Portfolio 汇总字段单一数据源测试。

验证 build_portfolio 的汇总字段（stock_value / unrealized_pnl / total_equity /
total_pnl / return_pct / open_pct）全部从 positions 派生，而非从 history 末行
（旧快照）读取。这样可避免"汇总 ≠ 个股之和"的视觉不一致。

关键：positions.csv 与 history.csv 被故意写成不一致，以证明汇总确实来自
positions（最新数据），而非 history（15 分钟前的旧快照）。
"""
import os
import sys
import json
from pathlib import Path

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dashboard_export import build_portfolio  # noqa: E402


def _write_files(data_dir: Path):
    """写入 4 个数据文件，positions 与 history 故意不一致。"""
    # meta.json
    meta = {
        "portfolio_id": "TEST-001",
        "initial_capital": 50000.0,
        "start_date": "2026-10-01",
        "unit_dollars": 10000.0,
        "max_open_positions": 4,
    }
    (data_dir / "portfolio_50000_meta.json").write_text(
        json.dumps(meta), encoding="utf-8")

    # positions.csv：2 只 OPEN，market_value 之和 = 30000，unrealized_pnl 之和 = 300
    # 注意：与 history 末行的 Stock_Value=99999 / Unrealized_PnL=8888 故意不一致。
    positions_csv = (
        "Portfolio_ID,Ticker,Status,Shares,Entry_Price,Cost_Basis,Current_Price,"
        "Market_Value,Unrealized_PnL,Unrealized_PnL_Pct,Weight_Pct,Stop_Loss,Entry_Date\n"
        "TEST-001,AAA,OPEN,100,90.0,9000.0,100.0,10000.0,1000.0,11.11,33.33,,2026-10-02\n"
        "TEST-001,BBB,OPEN,200,95.0,19000.0,100.0,20000.0,-700.0,-3.68,66.67,,2026-10-03\n"
        "TEST-001,CCC,CLOSED,10,50.0,500.0,55.0,550.0,50.0,10.0,0.0,,2026-10-04\n"
    )
    (data_dir / "portfolio_50000_positions.csv").write_text(
        positions_csv, encoding="utf-8")

    # transactions.csv：仅表头（read_csv_rows 空文件返回 []）
    (data_dir / "portfolio_50000_transactions.csv").write_text(
        "Date,Ticker,Action,Shares,Price,Amount,Realized_PnL,Reason,Unit_ID\n",
        encoding="utf-8")

    # history.csv：末行故意与 positions 不一致（旧快照）
    history_csv = (
        "Date,Total_Equity,Cash,Stock_Value,Realized_PnL,Unrealized_PnL,Total_PnL,Return_Pct,Open_Positions\n"
        "2026-10-10,109999.0,10000.0,99999.0,0.0,8888.0,8888.0,17.77,2\n"
        "2026-10-12,109999.0,10000.0,99999.0,0.0,8888.0,8888.0,17.77,2\n"
    )
    (data_dir / "portfolio_50000_history.csv").write_text(
        history_csv, encoding="utf-8")


def test_portfolio_summary_derived_from_positions(tmp_path):
    _write_files(tmp_path)
    pf = build_portfolio(tmp_path)
    assert pf is not None

    positions = pf["positions"]
    # CLOSED 的 CCC 不应计入
    assert len(positions) == 2

    sum_mv = round(sum(p["market_value"] for p in positions), 2)
    sum_up = round(sum(p["unrealized_pnl"] for p in positions), 2)

    # 1) stock_value == Σ market_value（来自 positions，而非 history 的 99999）
    assert pf["stock_value"] == sum_mv
    assert pf["stock_value"] != 99999.0

    # 2) total_equity == cash + stock_value（不变量）
    assert pf["total_equity"] == round(pf["cash"] + pf["stock_value"], 2)
    # cash 保留 history 来源（10000.0）
    assert pf["cash"] == 10000.0

    # 3) unrealized_pnl == Σ positions.unrealized_pnl（而非 history 的 8888）
    assert pf["unrealized_pnl"] == sum_up
    assert pf["unrealized_pnl"] != 8888.0

    # 4) open_pct == stock_value / total_equity * 100（百分比量纲，与历史一致）
    assert pf["open_pct"] == round(pf["stock_value"] / pf["total_equity"] * 100, 2)

    # 5) total_pnl == total_equity - initial_capital；return_pct == total_pnl/initial*100
    assert pf["total_pnl"] == round(pf["total_equity"] - pf["initial_capital"], 2)
    assert pf["return_pct"] == round(
        pf["total_pnl"] / pf["initial_capital"] * 100, 2)


def test_portfolio_summary_matches_when_history_in_sync(tmp_path):
    """当 history 与 positions 一致（且 history 内部自洽）时，新派生输出与旧逻辑（读 history）结果相同。"""
    _write_files(tmp_path)
    # history 末行与 positions 一致，且内部自洽：Total_Equity=Cash+Stock_Value，Total_PnL=Total_Equity-Initial
    history_csv = (
        "Date,Total_Equity,Cash,Stock_Value,Realized_PnL,Unrealized_PnL,Total_PnL,Return_Pct,Open_Positions\n"
        "2026-10-12,40000.0,10000.0,30000.0,0.0,300.0,-10000.0,-20.0,2\n"
    )
    (tmp_path / "portfolio_50000_history.csv").write_text(
        history_csv, encoding="utf-8")
    pf = build_portfolio(tmp_path)
    assert pf["stock_value"] == 30000.0
    assert pf["total_equity"] == 40000.0  # 10000 + 30000
    assert pf["unrealized_pnl"] == 300.0
    assert pf["open_pct"] == round(30000.0 / 40000.0 * 100, 2)  # 75.0
    assert pf["total_pnl"] == -10000.0  # 40000 - 50000
    assert pf["return_pct"] == -20.0


def test_portfolio_empty_positions(tmp_path):
    """无 OPEN 持仓时，stock_value/unrealized_pnl 为 0，不变量仍成立。"""
    meta = {
        "portfolio_id": "TEST-002",
        "initial_capital": 50000.0,
        "start_date": "2026-10-01",
        "unit_dollars": 10000.0,
        "max_open_positions": 4,
    }
    (tmp_path / "portfolio_50000_meta.json").write_text(
        json.dumps(meta), encoding="utf-8")
    (tmp_path / "portfolio_50000_positions.csv").write_text(
        "Portfolio_ID,Ticker,Status,Shares,Entry_Price,Cost_Basis,Current_Price,"
        "Market_Value,Unrealized_PnL,Unrealized_PnL_Pct,Weight_Pct,Stop_Loss,Entry_Date\n"
        "TEST-002,AAA,CLOSED,10,50.0,500.0,55.0,550.0,50.0,10.0,0.0,,2026-10-04\n",
        encoding="utf-8")
    (tmp_path / "portfolio_50000_transactions.csv").write_text(
        "Date,Ticker,Action,Shares,Price,Amount,Realized_PnL,Reason,Unit_ID\n",
        encoding="utf-8")
    (tmp_path / "portfolio_50000_history.csv").write_text(
        "Date,Total_Equity,Cash,Stock_Value,Realized_PnL,Unrealized_PnL,Total_PnL,Return_Pct,Open_Positions\n"
        "2026-10-12,50000.0,50000.0,0.0,0.0,0.0,0.0,0.0,0\n",
        encoding="utf-8")
    pf = build_portfolio(tmp_path)
    assert pf["stock_value"] == 0.0
    assert pf["unrealized_pnl"] == 0.0
    assert pf["total_equity"] == pf["cash"]  # 50000.0
    assert pf["open_pct"] == 0.0
