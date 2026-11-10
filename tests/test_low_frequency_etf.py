# -*- coding: utf-8 -*-
"""Tests for low-frequency ETF strategy research."""
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tools.research.low_frequency_etf import (
    DataError, END, START, block_bootstrap_ci, commission, leg_cost, load,
    metrics, run,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "research" / "etf_strategy_study"


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    out = tmp_path_factory.mktemp("etf_study")
    report = run(DATA, out)
    return out, report


def test_ibkr_commission_minimum_and_cap():
    c, _, _, _ = commission(1, 20, "BUY")
    assert c == 0.35
    c2, _, _, _ = commission(1_000_000, 10_000, "BUY")
    assert c2 == pytest.approx(100.0)  # 1% of notional cap dominates
    c3, _, _, _ = commission(1000, 10_000, "BUY")
    assert c3 == 3.5


def test_sell_has_sec_and_taf_but_buy_does_not():
    buy = leg_cost(100, 100, "BUY", 5)
    sell = leg_cost(100, 100, "SELL", 5)
    assert buy["sec_fee"] == 0 and buy["taf_fee"] == 0
    assert sell["sec_fee"] > 0 and sell["taf_fee"] > 0
    assert sell["slippage"] == pytest.approx(100 * 100 * 5 / 10000)


def test_full_backtest_outputs_and_c_four_legs(study):
    out, report = study
    assert set(report["results"]) == {f"{s}|{b}" for s in "ABC" for b in (1, 3, 5, 10, 20)}
    for k in ("A", "B", "C"):
        nav = pd.read_csv(out / f"nav_{k}.csv", index_col=0, parse_dates=True)["nav"]
        assert np.isfinite(nav).all()
        assert (nav > 0).all()
    legs = pd.read_csv(out / "trades_base5.csv")
    c = legs[legs.strategy == "C"]
    assert len(c) == 129  # initial BIL buy + 32 four-leg round trips
    assert set(c.side) == {"BUY", "SELL"}
    for _, r in c.iterrows():
        assert r["notional"] == pytest.approx(r["shares"] * r["price"])
        assert r["cost"] == pytest.approx(r["commission"] + r["sec_fee"] + r["taf_fee"] + r["exchange_fee"] + r["slippage"])


def test_warmup_has_252_sessions_before_portfolio(study):
    spy = load(DATA / "SPY.csv", "SPY")
    pre = spy.index[spy.index < pd.Timestamp(START)]
    assert len(pre) >= 252
    assert pre.min() <= pd.Timestamp("2006-05-30")


def test_no_nav_or_trades_before_start(study):
    out, _ = study
    for k in ("A", "B", "C"):
        nav = pd.read_csv(out / f"nav_{k}.csv", index_col=0, parse_dates=True)
        assert nav.index.min() == pd.Timestamp(START)
        assert nav.index.max() <= pd.Timestamp(END)
    legs = pd.read_csv(out / "trades_base5.csv")
    assert pd.to_datetime(legs["date"]).min() >= pd.Timestamp(START)


def test_c_matches_pr438_trade_count_and_dates():
    comp = ROOT / "docs" / "research" / "etf_strategy_study" / "pr438_comparison.json"
    import json
    d = json.loads(comp.read_text(encoding="utf-8"))
    assert d["our_trades"] == 32
    assert d["pr438_trades"] == 32
    assert d["date_matched_trades"] == 30
    assert len(d["date_only_ours"]) == 2


def test_c_uses_next_open_and_exits_after_five_sessions(study):
    out, _ = study
    legs = pd.read_csv(out / "trades_base5.csv")
    c = legs[legs.strategy == "C"].reset_index(drop=True)
    qqq = load(DATA / "QQQ.csv", "QQQ")
    entries = c[(c.ticker == "QQQ") & (c.side == "BUY")].reset_index(drop=True)
    exits = c[(c.ticker == "QQQ") & (c.side == "SELL")].reset_index(drop=True)
    assert len(entries) == len(exits) == 32
    for (_, e), (_, x) in zip(entries.iterrows(), exits.iterrows()):
        assert e["date"] in qqq.index and x["date"] in qqq.index
        assert e["price"] == pytest.approx(float(qqq.loc[e["date"], "Open"]))
        assert x["price"] == pytest.approx(float(qqq.loc[x["date"], "Open"]))
        spy = load(DATA / "SPY.csv", "SPY").index
        assert spy.get_loc(pd.Timestamp(x["date"])) - spy.get_loc(pd.Timestamp(e["date"])) == 5


def test_no_forward_fill_for_missing_portfolio_price(tmp_path):
    dst = tmp_path / "data"
    shutil.copytree(DATA, dst)
    q = pd.read_csv(dst / "QQQ.csv")
    q = q[pd.to_datetime(q["Date"], utc=True).dt.strftime("%Y-%m-%d") != "2010-01-04"]
    q.to_csv(dst / "QQQ.csv", index=False)
    with pytest.raises(DataError):
        run(dst, tmp_path / "out")


def test_drawdown_recovery_is_not_underwater_streak():
    idx = pd.date_range("2020-01-01", periods=5, freq="B")
    nav = pd.Series([100, 120, 90, 100, 130], index=idx, dtype=float)
    m = metrics(nav)
    assert m["max_drawdown"] == pytest.approx(-0.25)
    assert m["max_drawdown_peak_date"] == "2020-01-02"
    assert m["max_drawdown_trough_date"] == "2020-01-03"
    assert m["max_drawdown_recovery_date"] == "2020-01-07"
    assert m["max_drawdown_peak_to_trough_sessions"] == 1
    assert m["max_drawdown_trough_to_recovery_sessions"] == 2
    assert m["longest_underwater_sessions"] == 2


def test_cutoff_data_is_not_used_after_research_end(study):
    out, report = study
    assert report["end"] == END
    spy = load(DATA / "SPY.csv", "SPY")
    assert spy.index.max() <= pd.Timestamp(END)
    for k in ("A", "B", "C"):
        nav = pd.read_csv(out / f"nav_{k}.csv", index_col=0, parse_dates=True)
        assert (nav.index <= pd.Timestamp(END)).all()


def test_initial_equity_and_initial_trade_costs(study):
    out, report = study
    for k in ("A", "B", "C"):
        assert report["results"][f"{k}|5"]["initial_equity"] == 50000.0
        nav = pd.read_csv(out / f"nav_{k}.csv", index_col=0, parse_dates=True)["nav"]
        assert nav.index.min() == pd.Timestamp(START)
        legs = pd.read_csv(out / "trades_base5.csv")
        first = legs[legs.strategy == k].sort_values("date").iloc[0]
        assert first["date"] == START
        assert first["ticker"] == "BIL" and first["side"] == "BUY"
        assert first["cost"] > 0


def test_first_day_return_uses_initial_equity():
    idx = pd.date_range("2020-01-01", periods=2, freq="B")
    nav = pd.Series([49_900.0, 50_100.0], index=idx)
    m = metrics(nav, 50_000.0)
    # first return is 49,900/50,000 - 1, not 50,100/49,900 - 1
    assert m["total_return"] == pytest.approx(50_100 / 50_000 - 1)
    assert m["initial_equity"] == 50_000.0


def test_circular_block_bootstrap_metadata_and_ci():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    rng = np.random.default_rng(1)
    nav = pd.Series(50_000 * np.cumprod(1 + rng.normal(0.0002, 0.01, len(idx))), index=idx)
    b = block_bootstrap_ci(nav, n=50, block=20, initial=50_000.0, seed=7)
    assert b["method"] == "circular_block_bootstrap"
    assert b["seed"] == 7 and b["block_sessions"] == 20 and b["samples"] == 50
    assert b["cagr_ci_low"] < b["cagr_ci_high"]
