# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
import pytest

from tools.research.fixed_risk_budget import Account, load, run
from tools.research.ibkr_costs import fees

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "research" / "fixed_risk_budget"


def test_cost_model_components_and_holiday():
    f = fees(100, 100, "SELL", "2026-09-30")
    assert f["commission"] >= 0.35
    assert f["sec_fee"] == pytest.approx(100 * 100 * 0.0000206)
    assert f["cat_fee"] == pytest.approx(100 * 0.000003)
    assert f["clearing_fee"] == pytest.approx(100 * 0.00020)
    h = fees(100, 100, "SELL", "2026-10-02")
    assert h["taf_fee"] == 0.0


def test_initial_equity_and_integer_shares():
    legs = pd.read_csv(ROOT / "docs/research/fixed_risk_budget/trades_G.csv")
    assert legs.iloc[0]["date"] == "2007-05-30"
    assert (legs["shares"] == legs["shares"].astype(int)).all()
    assert (legs["notional"] - legs["shares"] * legs["price"]).abs().max() < 1e-8
    assert legs.iloc[0]["cost"] > 0
    assert abs(legs.iloc[0]["shares"] * legs.iloc[0]["price"] - 10000) < 200


def test_benchmark_and_dividend_accounting():
    idx = pd.to_datetime(["2020-01-02"])
    f = {"BIL": pd.DataFrame({"Open": [100.0], "Close": [100.0], "Dividends": [0.5]}, index=idx)}
    a = Account(f, 5.0); a.shares["BIL"] = 10.0; a.cash = 0.0
    a.credit_dividends(idx[0])
    assert a.cash == pytest.approx(5.0)
    assert a.dividend_cash == pytest.approx(5.0)


def test_cutoff_injection_does_not_change_results(tmp_path):
    d = tmp_path / "data"; d.mkdir()
    for t in ("QQQ", "BIL"):
        pd.read_csv(D / f"{t}.csv").to_csv(d / f"{t}.csv", index=False)
    s = pd.read_csv(d / "QQQ.csv")
    fut = s.iloc[-1].copy(); fut["Date"] = str(fut["Date"]).replace("2026-10-30", "2026-11-02")
    fut["Close"] = 1e9
    pd.concat([s, pd.DataFrame([fut])]).drop_duplicates("Date", keep="last").to_csv(d / "QQQ.csv", index=False)
    a = run(D, tmp_path / "base"); b = run(d, tmp_path / "inject")
    assert a["results"]["G|5"]["cagr"] == pytest.approx(b["results"]["G|5"]["cagr"])
    assert a["results"]["G|5"]["max_drawdown"] == pytest.approx(b["results"]["G|5"]["max_drawdown"])


def test_no_leverage_and_trade_prices_are_raw_open():
    legs = pd.read_csv(ROOT / "docs/research/fixed_risk_budget/trades_G.csv")
    frames = {t: load(t, D / f"{t}.csv") for t in ("QQQ", "BIL")}
    for _, r in legs.iterrows():
        assert r["price"] == pytest.approx(float(frames[r["ticker"]].loc[pd.Timestamp(r["date"]), "Open"]))
        assert r["shares"] > 0
    assert (legs["side"].isin(["BUY", "SELL"])).all()


def test_account_nav_reconciles_to_cash_and_positions():
    from tools.research.fixed_risk_budget import Account
    idx = pd.to_datetime(["2020-01-02"])
    f = {"QQQ": pd.DataFrame({"Open": [100.0], "Close": [101.0], "Dividends": [0.0]}, index=idx),
         "BIL": pd.DataFrame({"Open": [100.0], "Close": [100.0], "Dividends": [0.0]}, index=idx)}
    a = Account(f, 5.0); a.cash = 50000.0
    a.trade(idx[0], "QQQ", "BUY", 10, 100.0)
    assert a.nav(idx[0]) == pytest.approx(a.cash + 10 * 101.0)
