"""后端"交易观测"统计测试（_build_trade_stats，纯函数、离线可测）。

覆盖：
  1) 空 transactions → 全 0 / null（前端据此显「暂无交易记录」）
  2) 5 笔 SELL（3 盈 2 亏）→ 胜率 60%
  3) 频次统计正确（7d / 30d 窗口，锚点取流水最新日期）
  4) realized_pnl 缺失的笔 → 跳过不计入胜率分母
  5) 平均持仓天数正确（entry 取得到时计算，缺则跳过）
不依赖本地时钟、不重算盈亏、缺失不伪造。
"""
import importlib.util

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dex():
    spec = importlib.util.spec_from_file_location(
        "dex_trade_stats", REPO_ROOT / "dashboard_export.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sell(pnl, date="2026-10-10", amount=1000.0, unit="U001"):
    return {"Action": "SELL", "Date": date, "Realized_PnL": pnl,
            "Amount": amount, "Unit_ID": unit, "Ticker": "X"}


def _buy(date="2026-10-10"):
    return {"Action": "BUY", "Date": date, "Realized_PnL": 0.0,
            "Amount": 1000.0, "Unit_ID": "U001", "Ticker": "X"}


def test_empty_transactions_all_zero_or_null():
    """空 transactions → 全 0 / null，不崩。"""
    dex = _load_dex()
    ts = dex._build_trade_stats([], [])
    assert ts["total_buys"] == 0
    assert ts["total_sells"] == 0
    assert ts["buys_last_7d"] == 0 and ts["buys_last_30d"] == 0
    assert ts["sells_last_7d"] == 0 and ts["sells_last_30d"] == 0
    assert ts["win_rate"] is None
    assert ts["avg_holding_days"] is None
    assert ts["avg_win_pct"] is None and ts["avg_loss_pct"] is None
    assert ts["total_realized_pnl"] == 0.0
    assert ts["closed_count"] == 0 and ts["wins"] == 0


def test_win_rate_3_of_5():
    """5 笔 SELL（3 盈 2 亏）→ 胜率 60%（wins=3, closed=5）。"""
    dex = _load_dex()
    rows = [
        _sell(100.0), _sell(200.0), _sell(50.0),   # 3 盈
        _sell(-30.0), _sell(-40.0),                # 2 亏
    ]
    ts = dex._build_trade_stats(rows, [])
    assert ts["total_sells"] == 5
    assert ts["closed_count"] == 5
    assert ts["wins"] == 3
    assert abs(ts["win_rate"] - 60.0) < 1e-6
    # 平均盈/亏 %：入场成本 = amount - pnl = 900 → 盈 +11.1% 起
    assert ts["avg_win_pct"] is not None
    assert ts["avg_loss_pct"] is not None


def test_frequency_windows():
    """频次统计：7d / 30d 窗口正确（锚点 = 最新日期 2026-10-10）。"""
    dex = _load_dex()
    rows = [
        _buy("2026-10-10"),     # 7d✓ 30d✓
        _buy("2026-09-20"),     # 7d✗ 30d✓ (20d)
        _sell(10.0, "2026-10-05"),   # 7d✓ 30d✓ (5d)
        _sell(-10.0, "2026-08-01"),  # 7d✗ 30d✗ (70d)
    ]
    ts = dex._build_trade_stats(rows, [])
    assert ts["total_buys"] == 2 and ts["total_sells"] == 2
    assert ts["buys_last_7d"] == 1 and ts["buys_last_30d"] == 2
    assert ts["sells_last_7d"] == 1 and ts["sells_last_30d"] == 1


def test_realized_pnl_missing_skipped():
    """realized_pnl 缺失 → 跳过，不计入胜率分母（closed=2, wins=1 → 50%）。"""
    dex = _load_dex()
    rows = [
        _sell(None),        # 缺失 → 跳过
        _sell(100.0),       # 盈
        _sell(-50.0),       # 亏
    ]
    ts = dex._build_trade_stats(rows, [])
    assert ts["total_sells"] == 3          # 频次仍计全部 SELL
    assert ts["closed_count"] == 2         # 分母只含有效平仓
    assert ts["wins"] == 1
    assert abs(ts["win_rate"] - 50.0) < 1e-6


def test_avg_holding_days():
    """平均持仓天数正确：U001 持 10 天 + U002 持 6 天 → 8.0（锚点 2026-10-11）。"""
    dex = _load_dex()
    rows = [
        _sell(100.0, date="2026-10-11", unit="U001"),
        _sell(50.0, date="2026-10-11", unit="U002"),
    ]
    positions = [
        {"unit_id": "U001", "entry_date": "2026-10-01"},
        {"unit_id": "U002", "entry_date": "2026-10-05"},
    ]
    ts = dex._build_trade_stats(rows, positions)
    assert abs(ts["avg_holding_days"] - 8.0) < 1e-6
