# -*- coding: utf-8 -*-
from pathlib import Path

import pandas as pd
import pytest

from tools.research.real_yield_shock import Account, allocation, run, load, signal_map, START, END

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "research" / "real_yield_shock"


def test_threshold_and_missing_are_frozen():
    assert allocation(0.49) == {"SPY": 0.70, "IEF": 0.15, "TLT": 0.15}
    assert allocation(0.50) == {"BIL": 1.0}
    assert allocation(0.51) == {"BIL": 1.0}
    assert allocation(None) == {"BIL": 1.0}


def test_pit_change_is_latest_minus_base_and_vintage_is_prior():
    p = pd.read_csv(D / "pit_DFII10.csv")
    assert len(p) == 233
    assert p["vintage_date"].notna().all()
    assert p["latest_obs"].notna().all()
    assert ((p["latest"] - p["base"] - p["change_63"]).abs() < 1e-10).all()
    assert (pd.to_datetime(p["vintage_date"]) <= pd.to_datetime(p["decision_date"])).all()
    # one full session: latest observation must be before the decision date
    assert (pd.to_datetime(p["latest_obs"]) < pd.to_datetime(p["decision_date"])).all()


def test_signal_map_does_not_use_future_rows():
    p = pd.read_csv(D / "pit_DFII10.csv")
    p2 = p.copy()
    p2.loc[len(p2)] = {"decision_date": "2027-01-29", "vintage_date": "2027-01-28",
                       "latest_obs": "2027-01-27", "latest": 99, "base_obs": "2026-10-28",
                       "base": 0, "change_63": 99, "raw_sha256": "future"}
    m = signal_map(p2)
    assert pd.Timestamp("2027-01-29") not in m
    assert len(m) == 233


def test_backtest_initial_equity_and_raw_open(study=None):
    out = Path("docs/research/real_yield_shock")
    nav = pd.read_csv(out / "nav_E.csv", index_col=0, parse_dates=True)["nav"]
    legs = pd.read_csv(out / "trades_E.csv")
    assert nav.index.min() == pd.Timestamp(START)
    assert nav.index.max() <= pd.Timestamp(END)
    first = legs.sort_values("date").iloc[0]
    assert first["ticker"] == "BIL" and first["side"] == "BUY"
    assert first["cost"] > 0
    assert first["price"] == pytest.approx(float(load("BIL", D / "BIL.csv").loc[pd.Timestamp(START), "Open"]))
    assert (legs["notional"] - legs["shares"] * legs["price"]).abs().max() < 1e-8


def test_cutoff_injection_does_not_change_results(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    for t in ("SPY", "IEF", "TLT", "BIL"):
        pd.read_csv(D / f"{t}.csv").to_csv(d / f"{t}.csv", index=False)
    for t in ("DFII10", "pit_DFII10"):
        pd.read_csv(D / f"{t}.csv").to_csv(d / f"{t}.csv", index=False)
    # inject a future price: it must be ignored by the date filter
    s = pd.read_csv(d / "SPY.csv")
    fut = s.iloc[-1].copy()
    fut["Date"] = str(fut["Date"]).replace("2026-10-30", "2026-11-02")
    fut["Close"] = 1e9
    pd.concat([s, pd.DataFrame([fut])]).to_csv(d / "SPY.csv", index=False)
    r = run(d, tmp_path / "out")
    base = run(D, tmp_path / "base")
    assert r["results"]["E|5"]["cagr"] == pytest.approx(base["results"]["E|5"]["cagr"])
    assert r["results"]["E|5"]["max_drawdown"] == pytest.approx(base["results"]["E|5"]["max_drawdown"])


def test_dividend_credited_only_to_held_shares():
    idx = pd.to_datetime(["2020-01-02"])
    f = {"BIL": pd.DataFrame({"Open": [100.0], "Close": [100.0], "Dividends": [0.5]}, index=idx)}
    a = Account(f, 5.0); a.shares["BIL"] = 10.0; a.cash = 0.0
    a.credit_dividends(idx[0])
    assert a.cash == pytest.approx(5.0)
    assert a.dividend_cash == pytest.approx(5.0)
