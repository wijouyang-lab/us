# -*- coding: utf-8 -*-
"""买入侧冷却（#1）回归测试 —— 对应 WEEKEND_IMPLEMENTATION_PLAN.md §1.7。

覆盖三道买入冷却闸门：
  · 闸门 0：全清仓当天停手（open_count==0 且今日 Intraday Stop Loss）
  · 闸门 1：7 天字段冷却（positions 带 Cooldown_Until 且 >= today）
  · 闸门 2：近 1-2 日刚止损防御（transactions 含 Intraday Stop Loss，无字段兜底）

不依赖真实数据 / 网络；仅验证 process_buys 的冷却逻辑。
"""

import portfolio_50000 as pf
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path


def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


def _rec(ticker: str, price: float, rdate: str) -> dict:
    """构造一条 Active Core 推荐（仅含 process_buys 实际读取的字段）。"""
    return {
        "Recommendation_ID": f"R_{ticker}",
        "Ticker": ticker,
        "Tag": pf.CORE_TAG,                       # "Core_Dragon"
        "Status": "Active",
        "Rec_Date": rdate,
        "Price": Decimal(str(price)),
        "Stop_Loss": Decimal(str(price * 0.9)),
    }


def _no_buy(log) -> bool:
    return not any("BUY " in s for s in log)


def test_cooldown_active_blocks_buy():
    """用例1：冷却期内不买——持仓 CLOSED + Cooldown_Until=今+3，候选应被跳过。"""
    cd = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
    positions = [{"Ticker": "ADSK", "Status": "CLOSED", "Cooldown_Until": cd}]
    recs = {r["Recommendation_ID"]: r for r in [_rec("ADSK", 200, _today())]}
    log = pf.process_buys(positions, [], recs, {"start_date": "2020-01-01"}, _today())
    assert any("冷却期" in s for s in log)        # 日志出现冷却跳过
    assert _no_buy(log)                            # 没有产生 BUY 交易


def test_cooldown_expired_allows_buy():
    """用例2：冷却期满可买——Cooldown_Until=昨天，候选应通过冷却走完买入。"""
    yest = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    positions = [{"Ticker": "ADSK", "Status": "CLOSED", "Cooldown_Until": yest}]
    recs = {r["Recommendation_ID"]: r for r in [_rec("ADSK", 200, _today())]}
    log = pf.process_buys(positions, [], recs, {"start_date": "2020-01-01"}, _today())
    assert any("BUY ADSK" in s for s in log)      # 走完买入，日志出现 BUY


def test_full_liquidation_halts_buys():
    """用例3：全清仓当天不买——open_count==0 且今日有 Intraday Stop Loss → 顶部停手。"""
    t = _today()
    positions = [{"Ticker": "NVDA", "Status": "CLOSED"}]
    txns = [{"Action": "SELL", "Reason": "Intraday Stop Loss", "Date": t, "Ticker": "NVDA"}]
    recs = {r["Recommendation_ID"]: r for r in [_rec("NEW", 100, t)]}
    log = pf.process_buys(positions, txns, recs, {"start_date": "2020-01-01"}, t)
    assert any("全清仓" in s for s in log)         # 顶部停手日志
    assert _no_buy(log)


def test_stop_same_day_and_next_day_blocked():
    """用例4：止损当天+次日不买——用 _recent_stop_tickers 防御（无 Cooldown_Until 字段）。"""
    today = _today()
    yest = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    txns = [{"Action": "SELL", "Reason": "Intraday Stop Loss", "Date": yest, "Ticker": "AMD"}]
    positions = []                                 # 无字段冷却，仅靠防御
    recs = {r["Recommendation_ID"]: r for r in [_rec("AMD", 150, today)]}
    log = pf.process_buys(positions, txns, recs, {"start_date": "2020-01-01"}, today)
    assert any("刚止损" in s for s in log)         # 防御跳过日志
    assert _no_buy(log)


def test_no_stop_history_buys_normally():
    """用例5：无止损记录正常买——干净持仓 + 无止损交易 → 正常 BUY。"""
    t = _today()
    positions = [{"Ticker": "CRM", "Status": "OPEN"}]   # 已持 CRM
    recs = {r["Recommendation_ID"]: r for r in [_rec("NEW", 100, t)]}  # 新 ticker
    log = pf.process_buys(positions, [], recs, {"start_date": "2020-01-01"}, t)
    assert any("BUY NEW" in s for s in log)        # 正常买入新标的


def test_intraday_stop_writes_cooldown(monkeypatch, tmp_path):
    """用例6（守护修正）：盘中机械止损触发后，持仓写入 Cooldown_Until = today+7。

    这是 #1 冷却的关键写入点之一（另一处为 Review 终态止损）；缺它则盘中止损的
    ticker 不会被 7 天字段冷却覆盖，仅能靠 1-2 日防御——功能不完整。
    """
    TODAY = "2026-10-09"
    monkeypatch.setattr(pf, "us_today_str", lambda: TODAY)
    monkeypatch.setattr(pf, "fetch_last_closes",
                        lambda tickers: {t: {"current": Decimal("90.00")} for t in tickers})
    d = Path(tmp_path)
    pf.write_csv_rows(d / pf.POSITIONS_FILE, pf.POSITION_COLUMNS, [{
        "Portfolio_ID": "US-50000-001", "Unit_ID": "U001", "Ticker": "AAA",
        "Shares": "10", "Entry_Price": "100.00", "Entry_Date": "2026-10-07",
        "Cost_Basis": "1000.00", "Current_Price": "100.00", "Market_Value": "1000.00",
        "UnrealizedPnL": "0.00", "UnrealizedPnL_Pct": "0.00", "Weight_Pct": "0.00",
        "Status": "OPEN", "Stop_Loss": "95.00",
        "Recommendation_ID": "AAA|2026-10-07|Core_Dragon", "Last_Update": TODAY,
    }])
    pf.write_csv_rows(d / pf.TRANSACTIONS_FILE, pf.TRANSACTION_COLUMNS, [])
    res = pf._run_intraday_stop(d, TODAY, offline=False, now_et=datetime(2026, 10, 9, 12, 0))
    assert res["triggered"] == 1
    pos = pf.read_csv_rows(d / pf.POSITIONS_FILE)[0]
    assert pos["Status"] == "CLOSED"
    assert pos["Cooldown_Until"] == "2026-10-16"   # TODAY + 7 天
