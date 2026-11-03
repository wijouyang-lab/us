# -*- coding: utf-8 -*-
from pathlib import Path

import pandas as pd
import pytest

from tools.research.vix_term_structure import Account, allocation, run, total_return

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "research" / "vix_term_structure"


def test_backwardation_state_and_missing_pair():
    assert allocation(20.0, 18.0) == {"BIL": 1.0}
    assert allocation(18.0, 20.0) == {"SPY": 0.70, "IEF": 0.15, "TLT": 0.15}
    assert allocation(None, 18.0) == {"BIL": 1.0}
    assert allocation(18.0, None) == {"BIL": 1.0}


def test_pit_pair_has_same_vintage_and_prior_observation():
    p = pd.read_csv(D / "pit_vix_vxv.csv")
    assert len(p) == 150
    assert p["vintage_date"].notna().all()
    assert (pd.to_datetime(p["vintage_date"]) >= pd.Timestamp("2014-04-17")).all()
    assert p["vix_response_sha256"].str.len().eq(64).all()
    assert p["vxv_response_sha256"].str.len().eq(64).all()
    assert (pd.to_datetime(p["vix_obs"]) <= pd.to_datetime(p["vintage_date"])).all()
    assert (pd.to_datetime(p["vxv_obs"]) <= pd.to_datetime(p["vintage_date"])).all()
    assert (pd.to_datetime(p["vintage_date"]) < pd.to_datetime(p["decision_date"])).all()


def test_benchmark_total_return_includes_dividend():
    idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
    f = pd.DataFrame({"Close": [100.0, 100.0], "Open": [100.0, 100.0],
                      "Dividends": [0.0, 1.0]}, index=idx)
    r = total_return(f, idx)
    assert r.iloc[1] == pytest.approx(0.01)


def test_initial_trade_and_raw_open(study=None):
    out = Path("docs/research/vix_term_structure")
    legs = pd.read_csv(out / "trades_pit_2014_2026.csv")
    first = legs.sort_values("date").iloc[0]
    assert first["side"] == "BUY" and first["date"] == "2014-05-01"
    assert first["cost"] > 0
    nav = pd.read_csv(out / "nav_pit_2014_2026.csv", index_col=0, parse_dates=True)["nav"]
    assert nav.index.min() == pd.Timestamp("2014-05-01")
    assert (legs["notional"] - legs["shares"] * legs["price"]).abs().max() < 1e-8


def test_dividend_only_to_held_shares():
    idx = pd.to_datetime(["2020-01-02"])
    f = {"BIL": pd.DataFrame({"Open": [100.0], "Close": [100.0], "Dividends": [0.5]}, index=idx)}
    a = Account(f, 5.0); a.shares["BIL"] = 10.0; a.cash = 0.0
    a.credit_dividends(idx[0])
    assert a.cash == pytest.approx(5.0)


def test_cutoff_injection_does_not_change_results(tmp_path):
    d = tmp_path / "data"; d.mkdir()
    for t in ("SPY", "IEF", "TLT", "BIL", "VIXCLS", "VXVCLS"):
        pd.read_csv(D / f"{t}.csv").to_csv(d / f"{t}.csv", index=False)
    for t in ("pit_vix_vxv",):
        pd.read_csv(D / f"{t}.csv").to_csv(d / f"{t}.csv", index=False)
    s = pd.read_csv(d / "SPY.csv")
    fut = s.iloc[-1].copy()
    fut["Date"] = str(fut["Date"]).replace("2026-10-30", "2026-11-02")
    fut["Close"] = 1e9
    pd.concat([s, pd.DataFrame([fut])]).to_csv(d / "SPY.csv", index=False)
    a = run(D, tmp_path / "base")
    b = run(d, tmp_path / "inject")
    assert a["results"]["pit_2014_2026|5"]["cagr"] == pytest.approx(b["results"]["pit_2014_2026|5"]["cagr"])
    assert a["results"]["pit_2014_2026|5"]["max_drawdown"] == pytest.approx(b["results"]["pit_2014_2026|5"]["max_drawdown"])
