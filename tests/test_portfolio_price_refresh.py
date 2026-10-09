# -*- coding: utf-8 -*-
"""50k 价格跟随 dashboard-data + Extended_Price 回归（pytest）。

覆盖：
  1. --price-only 只更新价格，不处理买卖、不写交易/历史（不与 review 抢账本）
  2. Extended_Price 抓取成功 → 写入持仓 CSV
  3. Extended_Price 抓取失败（None）→ 留空，不影响 Current_Price
  4. 前端 positionCard 渲染：Extended_Price 为空 → 不显示该行（node 子进程校验 app.js 真代码）

运行：python3.12 -m pytest tests/test_portfolio_price_refresh.py -q
"""

import importlib.util
import csv
import json
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("pfrefresh", REPO / "portfolio_50000.py")
pfmod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pfmod)

TH_COLS = ["Date", "Ticker", "Name", "Tag", "Score", "Price", "Stop_Loss",
           "Exit_Date", "Exit_Price", "Status", "Close_Price"]


def mk(d, recs, start_date=None):
    with open(d / "trade_history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TH_COLS)
        w.writeheader()
        for r in recs:
            row = {c: "" for c in TH_COLS}
            row.update(r)
            w.writerow(row)
    if start_date:
        (d / "portfolio_50000_meta.json").write_text(json.dumps({
            "portfolio_id": "US-50000-001",
            "initial_capital": "50000.00",
            "start_date": start_date,
            "unit_dollars": "10000.00",
            "max_open_positions": 4,
            "currency": "USD",
        }), encoding="utf-8")


def read(d, name):
    p = d / name
    if not p.exists():
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def core(ticker, date, price, status="Active", exit_date="", exit_price="", tag="Core_Dragon"):
    return dict(Date=date, Ticker=ticker, Name=ticker, Tag=tag, Score="80", Price=price,
                Stop_Loss="0", Exit_Date=exit_date, Exit_Price=exit_price, Status=status,
                Close_Price=price)


def mock_fetch(prices):
    """prices: {TICKER: {"current": Decimal, "extended": Decimal|None, "extended_time": str}}"""
    def f(tickers):
        return {t.upper(): prices[t.upper()] for t in tickers if t.upper() in prices}
    pfmod.fetch_last_closes = f


TODAY = pfmod.us_today_str()


@pytest.fixture
def fx(tmp_path):
    return tmp_path


def test_price_only_updates_prices_only(fx):
    d = fx
    mk(d, [core("AMD", TODAY, "630.48")])
    mock_fetch({"AMD": {"current": Decimal("630.48"), "extended": None, "extended_time": ""}})
    pfmod.run(d, offline=False)                       # 完整跑 → 建仓

    # 追加一条 Active 推荐：price-only 必须忽略，不能建仓
    rows = list(csv.DictReader(open(d / "trade_history.csv", encoding="utf-8")))
    rows.append(core("META", TODAY, "700.00"))
    with open(d / "trade_history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TH_COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    txn_before = len(read(d, "portfolio_50000_transactions.csv"))
    hist_before = len(read(d, "portfolio_50000_history.csv"))

    mock_fetch({"AMD": {"current": Decimal("700.00"), "extended": None, "extended_time": ""}})
    pfmod.run(d, offline=False, price_only=True)      # 仅刷新价格

    pos = read(d, "portfolio_50000_positions.csv")
    amd = [p for p in pos if p["Ticker"] == "AMD"][0]
    assert Decimal(amd["Current_Price"]) == Decimal("700.00"), amd["Current_Price"]
    # 不处理买卖
    assert "META" not in [p["Ticker"] for p in pos]
    # 不写交易流水
    assert len(read(d, "portfolio_50000_transactions.csv")) == txn_before
    # 不写历史快照
    assert len(read(d, "portfolio_50000_history.csv")) == hist_before


def test_extended_price_written(fx):
    d = fx
    mk(d, [core("AMD", TODAY, "630.48")])
    mock_fetch({"AMD": {"current": Decimal("630.48"),
                        "extended": Decimal("640.00"),
                        "extended_time": "10-09 18:30 ET"}})
    pfmod.run(d, offline=False)
    amd = [p for p in read(d, "portfolio_50000_positions.csv") if p["Ticker"] == "AMD"][0]
    assert Decimal(amd["Extended_Price"]) == Decimal("640.00"), amd["Extended_Price"]
    assert amd["Extended_Time"] == "10-09 18:30 ET"


def test_extended_price_failure_keeps_current(fx):
    d = fx
    mk(d, [core("AMD", TODAY, "630.48")])
    # extended 抓取失败（None），不影响 current
    mock_fetch({"AMD": {"current": Decimal("630.48"), "extended": None, "extended_time": ""}})
    pfmod.run(d, offline=False)
    amd = [p for p in read(d, "portfolio_50000_positions.csv") if p["Ticker"] == "AMD"][0]
    assert Decimal(amd["Current_Price"]) == Decimal("630.48"), amd["Current_Price"]
    assert amd["Extended_Price"] == ""
    assert amd["Extended_Time"] == ""


def test_frontend_render_ext_guard():
    script = Path(__file__).resolve().parent / "_ext_render_check.cjs"
    res = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
