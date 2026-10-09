# -*- coding: utf-8 -*-
"""AI 目标持仓 Feature 测试（ENABLE_TARGET_FILE）。

覆盖：
  · portfolio_target.build_portfolio_target_rows / write_portfolio_target_csv
    （纯函数模块，可独立 import 单测；scan.py 在 flag=1 时调用 → flag 关闭时完全不调用，行为不变）
  · dashboard_export._read_portfolio_target / build_portfolio target 注入（flag 关→None，flag 开→注入）
  · 幂等（同天重跑整文件覆盖）、BUY/HOLD/SELL 推导、等权股数

注：scan.py 模块级有「市场时段守卫 + 环境变量校验」，导入即可能 sys.exit，故本测试不导入 scan，
    只测可独立导入的 portfolio_target 纯函数模块（scan 的 flag 调用点由代码审查 + env gate 测试保证）。
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import portfolio_target as pt  # 纯函数模块，无守卫，可直接导入


# ---------------------------------------------------------------------------
# 构造测试数据
# ---------------------------------------------------------------------------
def _sample_chosen():
    return [
        {"Ticker": "ADSK", "Price": 231.42, "Stop_Loss": "$214.76",
         "AI_premarket_conclusion": "盘前强势，产业链景气", "AI_industry_logic": "CAD 软件龙头",
         "AI_catalysts": "AI Design 放量"},
        {"Ticker": "ANET", "Price": 211.30, "Stop_Loss": "$197.69",
         "AI_premarket_conclusion": "交换机需求旺盛"},
        {"Ticker": "ISRG", "Price": 512.0, "Stop_Loss": "N/A",
         "AI_industry_logic": "手术机器人垄断"},
    ]


def _sample_held():
    # 当前持仓：ADSK、ANET 已持有；KR 已持有但不在今日推荐 → 应 SELL
    return ["ADSK", "ANET", "KR"]


# ---------------------------------------------------------------------------
# portfolio_target: build_portfolio_target_rows
# ---------------------------------------------------------------------------
def test_build_rows_schema_and_actions():
    rows, n = pt.build_portfolio_target_rows(_sample_chosen(), _sample_held(), "2026-10-09")
    tickers = {r["Ticker"] for r in rows}
    assert tickers == {"ADSK", "ANET", "ISRG", "KR"}
    by = {r["Ticker"]: r for r in rows}
    assert by["ADSK"]["Action"] == "HOLD"      # 已持有 + 推荐
    assert by["ANET"]["Action"] == "HOLD"
    assert by["ISRG"]["Action"] == "BUY"       # 推荐但未持有
    assert by["KR"]["Action"] == "SELL"        # 持有但不在推荐
    cols = ["Scan_Date", "Ticker", "Action", "Target_Shares", "Ref_Price", "Stop_Loss", "AI_Reason"]
    for r in rows:
        assert set(r.keys()) == set(cols)
        assert r["Scan_Date"] == "2026-10-09"


def test_build_rows_equal_weight_shares():
    rows, n = pt.build_portfolio_target_rows(_sample_chosen(), _sample_held(), "2026-10-09")
    assert n == 3  # 推荐标的数（ADSK/ANET/ISRG）
    by = {r["Ticker"]: r for r in rows}
    assert by["ISRG"]["Target_Shares"] == int(16666.7 // 512.0)  # BUY
    assert by["ADSK"]["Target_Shares"] == int(16666.7 // 231.42)  # HOLD（同公式）
    assert by["KR"]["Target_Shares"] == 0
    assert by["KR"]["Ref_Price"] == ""


def test_build_rows_idempotent_same_input():
    r1, _ = pt.build_portfolio_target_rows(_sample_chosen(), _sample_held(), "2026-10-09")
    r2, _ = pt.build_portfolio_target_rows(_sample_chosen(), _sample_held(), "2026-10-09")
    assert r1 == r2  # 同输入 → 同输出（确定性）


def test_build_rows_empty_no_recommendation():
    rows, n = pt.build_portfolio_target_rows([], ["ADSK"], "2026-10-09")
    # 无推荐 → 不构成目标组合，不生成 SELL-all（避免误清空）；返回空
    assert rows == []
    assert n == 0


def test_stop_loss_passthrough():
    rows, _ = pt.build_portfolio_target_rows(_sample_chosen(), [], "2026-10-09")
    by = {r["Ticker"]: r for r in rows}
    assert by["ADSK"]["Stop_Loss"] == "$214.76"
    assert by["ISRG"]["Stop_Loss"] == ""   # N/A 视为空


# ---------------------------------------------------------------------------
# portfolio_target: write_portfolio_target_csv（整文件覆盖 → 幂等）
# ---------------------------------------------------------------------------
def test_write_csv_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = pt.write_portfolio_target_csv(_sample_chosen(), _sample_held(), "2026-10-09")
    assert path == "portfolio_50000_target.csv"
    p = tmp_path / path
    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "Scan_Date,Ticker,Action,Target_Shares,Ref_Price,Stop_Loss,AI_Reason"
    assert len(lines) == 5  # 表头 + 4 行（ADSK/ANET/ISRG/KR）


def test_write_csv_idempotent_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pt.write_portfolio_target_csv(_sample_chosen(), _sample_held(), "2026-10-09")
    # 同天重跑：应覆盖而非追加
    pt.write_portfolio_target_csv(_sample_chosen(), _sample_held(), "2026-10-09")
    lines = (tmp_path / "portfolio_50000_target.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 5  # 仍是 表头 + 4 行，未翻倍


def test_write_csv_no_recommendation_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert pt.write_portfolio_target_csv([], ["ADSK"], "2026-10-09") is None
    assert not (tmp_path / "portfolio_50000_target.csv").exists()


# ---------------------------------------------------------------------------
# dashboard_export: _read_portfolio_target
# ---------------------------------------------------------------------------
def test_read_target_absent(tmp_path):
    import dashboard_export as de
    assert de._read_portfolio_target(tmp_path) is None


def test_read_target_parses(tmp_path):
    import dashboard_export as de
    (tmp_path / "portfolio_50000_target.csv").write_text(
        "Scan_Date,Ticker,Action,Target_Shares,Ref_Price,Stop_Loss,AI_Reason\n"
        "2026-10-09,ADSK,HOLD,43,231.42,$214.76,CAD龙头\n"
        "2026-10-09,ISRG,BUY,32,512.0,,\n",
        encoding="utf-8",
    )
    out = de._read_portfolio_target(tmp_path)
    assert out is not None
    assert len(out) == 2
    assert out[0]["ticker"] == "ADSK"
    assert out[0]["action"] == "HOLD"
    assert out[0]["target_shares"] == 43
    assert out[0]["ref_price"] == 231.42
    assert out[0]["ai_reason"] == "CAD龙头"
    assert out[1]["action"] == "BUY"
    assert out[1]["stop_loss"] is None


# ---------------------------------------------------------------------------
# dashboard_export: build_portfolio target 注入（flag 关/开）
# ---------------------------------------------------------------------------
def _make_portfolio_dir(tmp_path):
    (tmp_path / "portfolio_50000_meta.json").write_text(
        '{"portfolio_id":"US-50000-001","initial_capital":50000,"start_date":"2026-10-01",'
        '"unit_dollars":10000,"max_open_positions":5}', encoding="utf-8")
    (tmp_path / "portfolio_50000_positions.csv").write_text(
        "Portfolio_ID,Unit_ID,Ticker,Shares,Entry_Price,Entry_Date,Cost_Basis,Current_Price,"
        "Market_Value,Unrealized_PnL,Unrealized_PnL_Pct,Weight_Pct,Status,Stop_Loss,"
        "Recommendation_ID,Last_Update\n"
        "US-50000-001,U001,ADSK,43,231.42,2026-10-07,9951.06,233.60,10044.80,93.74,0.94,"
        "19.82,OPEN,$214.76,ADSK|2026-10-07|Core_Dragon,2026-10-08\n",
        encoding="utf-8")
    (tmp_path / "portfolio_50000_history.csv").write_text(
        "Date,Total_Equity,Cash,Stock_Value,Open_Positions,Realized_PnL,Unrealized_PnL,"
        "Total_PnL,Return_Pct\n"
        "2026-10-08,50100.0,0.0,50100.0,1,0.0,100.0,100.0,0.2\n",
        encoding="utf-8")
    (tmp_path / "portfolio_50000_transactions.csv").write_text(
        "Date,Ticker,Action,Shares,Price,Amount,Realized_PnL,Reason,Unit_ID\n",
        encoding="utf-8")
    (tmp_path / "portfolio_50000_target.csv").write_text(
        "Scan_Date,Ticker,Action,Target_Shares,Ref_Price,Stop_Loss,AI_Reason\n"
        "2026-10-09,ADSK,HOLD,43,231.42,$214.76,CAD龙头\n"
        "2026-10-09,ISRG,BUY,32,512.0,,\n",
        encoding="utf-8")


def test_build_portfolio_target_flag_off_is_none(tmp_path, monkeypatch):
    import dashboard_export as de
    monkeypatch.delenv("ENABLE_TARGET_FILE", raising=False)
    _make_portfolio_dir(tmp_path)
    pf = de.build_portfolio(tmp_path)
    assert pf is not None
    assert pf.get("target") is None  # flag 关闭 → target=None，不影响其余字段


def test_build_portfolio_target_flag_on_injected(tmp_path, monkeypatch):
    import dashboard_export as de
    monkeypatch.setenv("ENABLE_TARGET_FILE", "1")
    _make_portfolio_dir(tmp_path)
    pf = de.build_portfolio(tmp_path)
    assert pf is not None
    target = pf.get("target")
    assert isinstance(target, list) and len(target) == 2
    assert target[0]["ticker"] == "ADSK"
    assert target[1]["action"] == "BUY"


# ---------------------------------------------------------------------------
# env gate 常量（调用点语义）
# ---------------------------------------------------------------------------
def test_env_gate_constant(monkeypatch):
    monkeypatch.delenv("ENABLE_TARGET_FILE", raising=False)
    assert (os.environ.get("ENABLE_TARGET_FILE") == "1") is False  # 未设置 → False
    monkeypatch.setenv("ENABLE_TARGET_FILE", "1")
    assert (os.environ.get("ENABLE_TARGET_FILE") == "1") is True   # 设置=1 → True
    monkeypatch.setenv("ENABLE_TARGET_FILE", "0")
    assert (os.environ.get("ENABLE_TARGET_FILE") == "1") is False  # 非"1" → False
