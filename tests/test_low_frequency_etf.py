# -*- coding: utf-8 -*-
"""Tests for low-frequency ETF strategy research."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tools.research.low_frequency_etf import (
    BASE_SLIP_BPS, commission, leg_cost, run,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "research" / "etf_strategy_study"


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


def test_full_backtest_outputs_and_c_four_legs(tmp_path):
    report = run(DATA, tmp_path)
    assert set(report["results"]) == {f"{s}|{b}" for s in "ABC" for b in (1, 3, 5, 10, 20)}
    for k in ("A", "B", "C"):
        nav = pd.read_csv(tmp_path / f"nav_{k}.csv", index_col=0, parse_dates=True)["nav"]
        assert np.isfinite(nav).all()
        assert (nav > 0).all()
    legs = pd.read_csv(tmp_path / "trades_base5.csv")
    c = legs[legs.strategy == "C"]
    assert len(c) % 4 == 0
    assert set(c.side) == {"BUY", "SELL"}
    for _, r in c.iterrows():
        assert r["notional"] == pytest.approx(r["shares"] * r["price"])
        assert r["cost"] == pytest.approx(r["commission"] + r["sec_fee"] + r["taf_fee"] + r["exchange_fee"] + r["slippage"])
