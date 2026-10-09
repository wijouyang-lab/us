"""盘中机械止损（--intraday-stop）回归测试。

覆盖用户要求的 6 项必验 + 幂等 / 离线 / 全平仓 / 交易结构。
约束验证：默认 run()（无 --intraday-stop，即 review 路径）绝不进入 _run_intraday_stop。
"""
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

import portfolio_50000 as pf

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

ET = ZoneInfo("America/New_York") if ZoneInfo else None


def _et(hour, minute, day=9, month=10, year=2026):
    if ET is None:  # pragma: no cover
        return datetime(year, month, day, hour, minute)
    return datetime(year, month, day, hour, minute, tzinfo=ET)


def _base_row(ticker, stop="95.00", entry="100.00", shares="10", status="OPEN"):
    return {
        "Portfolio_ID": "US-50000-001",
        "Unit_ID": "U1",
        "Ticker": ticker,
        "Shares": shares,
        "Entry_Price": entry,
        "Entry_Date": "2026-01-01",
        "Cost_Basis": "1000.00",
        "Current_Price": entry,
        "Market_Value": "1000.00",
        "Unrealized_PnL": "0.00",
        "Unrealized_PnL_Pct": "0.00",
        "Weight_Pct": "25.00",
        "Status": status,
        "Stop_Loss": stop,
        "Recommendation_ID": f"{ticker}|2026-01-01|Core_Dragon",
        "Last_Update": "2026-10-09",
    }


def _setup(tmp_path, positions, transactions=None):
    d = Path(tmp_path)
    pf.write_csv_rows(d / pf.POSITIONS_FILE, pf.POSITION_COLUMNS, positions)
    pf.write_csv_rows(d / pf.TRANSACTIONS_FILE, pf.TRANSACTION_COLUMNS, transactions or [])
    return d


def _intraday_txns(d):
    rows = pf.read_csv_rows(d / pf.TRANSACTIONS_FILE)
    return [t for t in rows if str(t.get("Reason", "")) == "Intraday Stop Loss"]


def _positions_after(d):
    return pf.read_csv_rows(d / pf.POSITIONS_FILE)


@pytest.fixture(autouse=True)
def _fix_today(monkeypatch):
    # 让 today 与测试用例里的 Date 固定一致，避免依赖真实系统时钟
    monkeypatch.setattr(pf, "us_today_str", lambda: "2026-10-09")


# —— 必验 1：非交易时段静默退出 ——
@pytest.mark.parametrize("hh,mm", [(8, 0), (16, 30), (0, 0), (20, 0)])
def test_out_of_session_silent_exit(monkeypatch, tmp_path, hh, mm):
    monkeypatch.setattr(pf, "_et_now", lambda: _et(hh, mm))
    d = _setup(tmp_path, [_base_row("AAA")])
    res = pf.run(d, intraday_stop=True)
    assert res["triggered"] == 0
    assert _intraday_txns(d) == []                       # 未写任何盘中止损


def test_weekend_silent_exit(monkeypatch, tmp_path):
    # 2026-10-10 是周六，12:00 ET 仍在盘前外（实际盘后也无常规交易）
    monkeypatch.setattr(pf, "_et_now", lambda: _et(12, 0, day=10))
    d = _setup(tmp_path, [_base_row("AAA")])
    res = pf.run(d, intraday_stop=True)
    assert res["triggered"] == 0
    assert _intraday_txns(d) == []


# —— 必验 2：实时价 > 止损 → 不触发 ——
def test_price_above_stop_no_trigger(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_et_now", lambda: _et(12, 0))
    monkeypatch.setattr(pf, "fetch_last_closes",
                        lambda tickers: {t: {"current": Decimal("110.00")} for t in tickers})
    d = _setup(tmp_path, [_base_row("AAA", stop="95.00")])
    res = pf.run(d, intraday_stop=True)
    assert res["triggered"] == 0
    assert _intraday_txns(d) == []
    assert _positions_after(d)[0]["Status"] == "OPEN"     # 仓位未变


# —— 必验 3：实时价 ≤ 止损 → 触发 + 写 transactions ——
def test_price_below_stop_triggers(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_et_now", lambda: _et(12, 0))
    monkeypatch.setattr(pf, "fetch_last_closes",
                        lambda tickers: {t: {"current": Decimal("90.00")} for t in tickers})
    d = _setup(tmp_path, [_base_row("AAA", stop="95.00", entry="100.00", shares="10")])
    res = pf.run(d, intraday_stop=True)
    assert res["triggered"] == 1
    txns = _intraday_txns(d)
    assert len(txns) == 1
    t = txns[0]
    assert t["Action"] == "SELL"
    assert t["Ticker"] == "AAA"
    assert t["Price"] == "90.00"                           # 执行价 = 触发实时价
    assert t["Reason"] == "Intraday Stop Loss"
    assert t["Pending_Reason"] == "True"                   # 待 AI 补原因
    assert t["Txn_ID"] == "INTRADAY|AAA|2026-10-09"        # 与 Review 的 {rid}|SELL|date 区分
    pos = _positions_after(d)[0]
    assert pos["Status"] == "CLOSED"                        # 持仓关仓
    assert pos["Current_Price"] == "90.00"


# —— 必验 4：单日止损 ≥ 2 → 不再触发 ——
def test_max_two_stops_per_day(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_et_now", lambda: _et(12, 0))
    monkeypatch.setattr(pf, "fetch_last_closes",
                        lambda tickers: {t: {"current": Decimal("90.00")} for t in tickers})
    positions = [
        _base_row("AAA", stop="95.00"),
        _base_row("BBB", stop="95.00"),
        _base_row("CCC", stop="95.00"),
    ]
    d = _setup(tmp_path, positions)
    res = pf.run(d, intraday_stop=True)
    assert res["triggered"] == 2                            # 只触发 2 只
    assert len(_intraday_txns(d)) == 2
    statuses = {p["Ticker"]: p["Status"] for p in _positions_after(d)}
    closed = [t for t in statuses if statuses[t] == "CLOSED"]
    assert sorted(closed) == ["AAA", "BBB"]                 # 第三只 CCC 未触发
    assert statuses["CCC"] == "OPEN"


# —— 必验 5：默认 run()（无 flag = review 路径）行为不变 ——
def test_default_run_does_not_invoke_intraday(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(pf, "_run_intraday_stop",
                        lambda *a, **k: calls.append(1) or {"triggered": 0})
    # 即便实时价远低于止损线，默认路径也不应触发盘中止损
    monkeypatch.setattr(pf, "fetch_last_closes",
                        lambda tickers: {t: {"current": Decimal("50.00")} for t in tickers})
    d = _setup(tmp_path, [_base_row("AAA", stop="95.00")])
    pf.run(d, offline=True)                                 # 默认：无 --intraday-stop
    assert calls == []                                       # _run_intraday_stop 从未被调用
    assert _positions_after(d)[0]["Status"] == "OPEN"        # 仓位未被盘中止损关仓
    assert _intraday_txns(d) == []


def test_default_run_review_path_unchanged(monkeypatch, tmp_path):
    # 直接验证：不带 intraday_stop 时，执行的是完整 run() 而非早退分支
    d = _setup(tmp_path, [_base_row("AAA", stop="95.00")])
    res = pf.run(d, offline=True)                            # 无 intraday_stop
    # 完整 run 返回完整字段（含 history / transactions / meta），早退分支没有
    assert "history" in res and "meta" in res
    assert _positions_after(d)[0]["Status"] == "OPEN"


# —— 必验 6：transactions.csv 结构只追加字段 ——
def test_transaction_columns_append_only():
    expected_prior = [
        "Txn_ID", "Date", "Ticker", "Action", "Shares", "Price", "Amount",
        "Realized_PnL", "Cash_After", "Reason", "Recommendation_ID", "Scan_Date",
        "Portfolio_ID", "Unit_ID",
    ]
    assert pf.TRANSACTION_COLUMNS[:-1] == expected_prior      # 原 14 列顺序不变
    assert pf.TRANSACTION_COLUMNS[-1] == "Pending_Reason"    # 仅追加


# —— 附加：离线（取不到价）→ 不触发（绝不猜价）——
def test_offline_no_trigger(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_et_now", lambda: _et(12, 0))
    # offline=True → fetch_last_closes 返回 {} → 取不到价
    d = _setup(tmp_path, [_base_row("AAA", stop="95.00")])
    res = pf.run(d, intraday_stop=True, offline=True)
    assert res["triggered"] == 0
    assert _intraday_txns(d) == []


# —— 附加：已今日盘中止损 → 幂等不重复处理 ——
def test_idempotent_already_stopped_today(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_et_now", lambda: _et(12, 0))
    monkeypatch.setattr(pf, "fetch_last_closes",
                        lambda tickers: {t: {"current": Decimal("90.00")} for t in tickers})
    prior = [{
        "Txn_ID": "INTRADAY|AAA|2026-10-09", "Date": "2026-10-09", "Ticker": "AAA",
        "Action": "SELL", "Shares": "10", "Price": "90.00", "Amount": "900.00",
        "Realized_PnL": "-100.00", "Cash_After": "", "Reason": "Intraday Stop Loss",
        "Recommendation_ID": "AAA|2026-01-01|Core_Dragon", "Scan_Date": "2026-01-01",
        "Portfolio_ID": "US-50000-001", "Unit_ID": "U1", "Pending_Reason": "True",
    }]
    d = _setup(tmp_path, [_base_row("AAA", stop="95.00")], transactions=prior)
    res = pf.run(d, intraday_stop=True)
    assert res["triggered"] == 0
    assert len(_intraday_txns(d)) == 1                       # 仍是原来的那一条
    assert _positions_after(d)[0]["Status"] == "OPEN"         # 未重复关仓/重复卖


# —— 附加：全部持仓已 CLOSED → 不再触发 ——
def test_all_closed_no_trigger(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_et_now", lambda: _et(12, 0))
    d = _setup(tmp_path, [_base_row("AAA", stop="95.00", status="CLOSED")])
    res = pf.run(d, intraday_stop=True)
    assert res["triggered"] == 0
    assert _intraday_txns(d) == []
