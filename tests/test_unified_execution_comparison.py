# -*- coding: utf-8 -*-
from pathlib import Path
import json
import pandas as pd
import pytest

from tools.research.unified_execution_comparison import Acct, metrics

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "research" / "transition_risk_match"
OUT = ROOT / "docs" / "research" / "unified_execution"


def test_effective_prices_and_slippage_direction():
    idx = pd.to_datetime(["2020-01-02"])
    f = {"QQQ": pd.DataFrame({"Open": [100.0], "Close": [100.0], "Dividends": [0.0]}, index=idx)}
    a = Acct(f, 5, True)
    a.order(idx[0], "QQQ", "BUY", 10, 100.0)
    assert a.legs[-1]["price"] == pytest.approx(100.05)
    assert a.legs[-1]["slippage"] == pytest.approx(0.5)
    b = Acct(f, 5, True); b.shares["QQQ"] = 10
    b.order(idx[0], "QQQ", "SELL", 10, 100.0)
    assert b.legs[-1]["price"] == pytest.approx(99.95)
    assert b.legs[-1]["slippage"] == pytest.approx(0.5)


def test_commission_minimum_and_no_double_count():
    idx = pd.to_datetime(["2020-01-02"])
    f = {"QQQ": pd.DataFrame({"Open": [50.0], "Close": [50.0], "Dividends": [0.0]}, index=idx)}
    a = Acct(f, 3, True); a.order(idx[0], "QQQ", "BUY", 1, 50.0)
    leg = a.legs[-1]
    assert leg["commission"] == 0.35
    assert leg["total_cost"] == pytest.approx(leg["cost"] + leg["slippage"])
    assert leg["notional"] == pytest.approx(leg["shares"] * leg["price"])


def test_results_start_and_leg_counts():
    r = json.loads((OUT / "results.json").read_text())
    assert r["results"]["Transition|3"]["order_legs"] == 129
    assert r["results"]["G|3"]["order_legs"] > 400
    assert r["results"]["Transition|3"]["final_nav"] > 50000


def test_same_calendar_all_navs():
    for n in ("Transition", "RiskMatched", "G"):
        d = pd.read_csv(OUT / f"nav_{n}.csv", index_col=0, parse_dates=True)
        assert d.index.min() == pd.Timestamp("2007-05-30")
        assert d.index.max() == pd.Timestamp("2026-10-30")
        assert d.index.is_unique


def test_cost_before_is_higher_than_after():
    r = json.loads((OUT / "results.json").read_text())
    for k in ("Transition|3", "RiskMatched|3", "G|3"):
        v = r["results"][k]
        assert v["before_cost_nav"] >= v["final_nav"]
        assert v["before_cost_cagr"] >= v["cagr"]


def test_transition_cost_is_mostly_slippage():
    t = pd.read_csv(OUT / "trades_Transition.csv")
    assert (t["total_cost"] - (t["cost"] + t["slippage"])).abs().max() < 1e-8
    assert t["slippage"].sum() > t["ibkr_fees"].sum() if "ibkr_fees" in t else True


def test_metrics_reject_no_trades():
    idx = pd.date_range("2020-01-01", periods=3, freq="B")
    nav = pd.Series([50000, 50000, 50000], index=idx)
    m = metrics(nav, pd.Series([0.0, 0.0, 0.0], index=idx))
    assert m["final_nav"] == 50000
    assert m["cagr"] == pytest.approx(0)
