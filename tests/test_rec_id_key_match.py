"""rec_id_of 键归一化 + process_sells 漏卖告警测试。

验证 STOPLOSS key bug 修复：
  · rec_id_of 把日期部分归一化为 YYYY-MM-DD（与仓位存储的 date-only RecID 对齐）
  · load_recommendations 据此产出 date-only 键，使 process_sells 能匹配到推荐
  · 当 RecID 匹配不到 recommendations 时，打印告警（不再静默 continue）

不联网、不重算盈亏。直接用 importlib 载入 portfolio_50000.py。
"""
import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "portfolio_50000_keyfix", REPO_ROOT / "portfolio_50000.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pf = _load()


# ----------------------------------------------------------------- 1 & 2: rec_id_of 归一化
def test_rec_id_of_normalizes_full_timestamp():
    assert (
        pf.rec_id_of("ANET", "2026-10-07 00:00:00", "Core_Dragon")
        == "ANET|2026-10-07|Core_Dragon"
    )


def test_rec_id_of_keeps_date_only():
    assert (
        pf.rec_id_of("ANET", "2026-10-07", "Core_Dragon")
        == "ANET|2026-10-07|Core_Dragon"
    )


# --------------------------------------------------------- 3: 端到端匹配（修复后应当能卖）
def test_process_sells_matches_date_only_rid_and_sells(capsys):
    """仓位存 date-only RecID，recs 由带时分秒的 Date 经归一化拼键 → 应匹配并卖出。"""
    rid = "ANET|2026-10-07|Core_Dragon"  # 仓位存储的 date-only 形式
    # 模拟 load_recommendations：用带时分秒的 Date 拼键（修复后归一化为 date-only）
    rec_key = pf.rec_id_of("ANET", "2026-10-07 00:00:00", "Core_Dragon")
    assert rec_key == rid  # 前置：归一化确保两键相等
    recs = {
        rec_key: {
            "Recommendation_ID": rec_key,
            "Ticker": "ANET",
            "Rec_Date": "2026-10-07 00:00:00",
            "Tag": "Core_Dragon",
            "Price": Decimal("211.30"),
            "Status": "Stop_Loss_Hit",   # 终态
            "Exit_Date": "2026-10-12",
            "Exit_Price": Decimal("210.24"),
            "Stop_Loss": "209.36",
        }
    }
    position = {
        "Ticker": "ANET",
        "Unit_ID": "U002",
        "Status": "OPEN",
        "Shares": "10",
        "Entry_Price": "211.30",
        "Recommendation_ID": rid,
        "Cooldown_Until": "",
    }
    transactions = []
    log = pf.process_sells([position], transactions, recs, "2026-10-13")
    out = capsys.readouterr().out
    # 匹配成功 → 不应出现漏卖告警
    assert "⚠️ [process_sells]" not in out
    # 终态 + 有 Exit_Price/Exit_Date → 应实际卖出
    assert position["Status"] == "CLOSED"
    assert any("SELL" in line for line in log)
    assert len(transactions) == 1
    assert transactions[0]["Action"] == "SELL"


# --------------------------------------------------------- 4: 漏卖告警（匹配不到时打印）
def test_process_sells_warns_on_unmatched_rid(capsys):
    """RecID 确实匹配不到 recommendations → 打印告警，不静默跳过。"""
    rid = "ANET|2026-10-07|Core_Dragon"
    # recs 里只有另一个键，刻意不匹配
    recs = {
        "OTHER|2026-10-07|Core_Dragon": {
            "Recommendation_ID": "OTHER|2026-10-07|Core_Dragon",
            "Ticker": "OTHER",
            "Rec_Date": "2026-10-07 00:00:00",
            "Tag": "Core_Dragon",
            "Price": Decimal("1.0"),
            "Status": "Stop_Loss_Hit",
            "Exit_Date": "2026-10-12",
            "Exit_Price": Decimal("1.0"),
            "Stop_Loss": "1.0",
        }
    }
    position = {
        "Ticker": "ANET",
        "Unit_ID": "U002",
        "Status": "OPEN",
        "Shares": "10",
        "Entry_Price": "211.30",
        "Recommendation_ID": rid,  # 与 recs 中任何键都不等
        "Cooldown_Until": "",
    }
    transactions = []
    pf.process_sells([position], transactions, recs, "2026-10-13")
    out = capsys.readouterr().out
    assert "⚠️ [process_sells]" in out
    assert "ANET" in out


# ----------------------------------------------- 5: load_recommendations 产出 date-only 键
def test_load_recommendations_uses_date_only_key(tmp_path):
    """load_recommendations 读带时分秒 Date 的 CSV，应产出 date-only 键。"""
    csv_path = tmp_path / "trade_history.csv"
    csv_path.write_text(
        "Date,Ticker,Name,Tag,Score,Price,RSI,Bias,Hold_Period,Stop_Loss,Stop_Method,"
        "Trail_Stop,Exit_Date,Exit_Price,Status,Close_Price\n"
        "2026-10-07 00:00:00,ANET,Arista Networks,Core_Dragon,73.9,211.30,67.3,6.58,"
        "动态持有,209.36,MA20/MA50,209.36,,,Active,215.83\n",
        encoding="utf-8",
    )
    recs = pf.load_recommendations(tmp_path)
    assert "ANET|2026-10-07|Core_Dragon" in recs
    assert recs["ANET|2026-10-07|Core_Dragon"]["Status"] == "Active"
