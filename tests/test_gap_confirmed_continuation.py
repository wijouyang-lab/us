# -*- coding: utf-8 -*-
"""Tests for gap-confirmed continuation research."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tools.research.gap_confirmed_continuation import DataError, features, load, run

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "research" / "volume_shock_reversal"


def _frame(n=40):
    dates = pd.bdate_range("2020-01-01", periods=n)
    close = 100 + np.arange(n) * 0.1
    return pd.DataFrame({"Date": dates, "Open": close, "AdjOpen": close, "High": close, "Low": close,
                         "Close": close, "Volume": 1_000_000.0, "Adj Close": close})


def test_adjusted_open_and_gap_returns(tmp_path):
    d = _frame(40)
    d.loc[39, "Open"] = 102.0
    d.loc[39, "Adj Close"] = 110.0
    d.loc[39, "Close"] = 105.0
    p = tmp_path / "QQQ.csv"; d.to_csv(p, index=False)
    f = features(load(p, "QQQ"))
    adj_open = 102.0 * 110.0 / 105.0
    assert f.AdjOpen.iloc[39] == pytest.approx(adj_open)
    assert f.Overnight.iloc[39] == pytest.approx(adj_open / f.AdjClose.iloc[38] - 1)
    assert f.Intraday.iloc[39] == pytest.approx(f.AdjClose.iloc[39] / adj_open - 1)


def test_sigma_uses_only_prior_20_sessions(tmp_path):
    d = _frame(40)
    p = tmp_path / "QQQ.csv"; d.to_csv(p, index=False)
    f = features(load(p, "QQQ"))
    t = 30
    assert f.SigmaOvernight.iloc[t] == pytest.approx(f.Overnight.iloc[t - 20:t].std(ddof=1))
    assert f.SigmaIntraday.iloc[t] == pytest.approx(f.Intraday.iloc[t - 20:t].std(ddof=1))
    assert f.OvernightZ.iloc[t] == pytest.approx(f.Overnight.iloc[t] / f.SigmaOvernight.iloc[t])


def test_signal_is_positive_gap_and_intraday_confirmation():
    d = _frame(40).rename(columns={"Adj Close": "AdjClose"}).set_index("Date")
    f = features(d)
    f.loc[f.index[-1], "OvernightZ"] = 1.0
    f.loc[f.index[-1], "IntradayZ"] = 0.5
    assert (f.OvernightZ.iloc[-1] >= 1.0) and (f.IntradayZ.iloc[-1] >= 0.5)
    assert not ((f.OvernightZ.iloc[-1] < 1.0) or (f.IntradayZ.iloc[-1] < 0.5))


def test_duplicate_and_missing_data_rejected(tmp_path):
    d = _frame(30); p = tmp_path / "QQQ.csv"
    pd.concat([d, d.tail(1)]).to_csv(p, index=False)
    with pytest.raises(DataError):
        load(p, "QQQ")
    d2 = _frame(30); d2.loc[0, "Volume"] = np.nan
    d2.to_csv(p, index=False)
    with pytest.raises(DataError):
        load(p, "QQQ")


def test_full_gap_study_outputs(tmp_path):
    out = tmp_path / "out"
    report = run(DATA, out)
    assert len(report["study"]) == 15
    assert all(0 <= r["q_bh"] <= 1 for r in report["study"])
    assert report["study"][0]["non_overlap_events"] <= report["study"][0]["events"]
    nav = pd.read_csv(out / "nav_10bps.csv", index_col=0).iloc[:, 0]
    assert nav.notna().all() and np.isfinite(nav).all()
    trades = pd.read_csv(out / "trades.csv")
    assert len(trades) > 0
    for _, t in trades[trades.cost_bps == 10].iterrows():
        assert abs(t["units"] * t["entry_price"] - t["qqq_notional"]) < 1e-6
        assert abs(t["entry_bil_units"] * t["entry_bil_price"] - t["entry_bil_notional"]) < 1e-6
        assert abs(t["exit_qqq_units"] * t["exit_price"] - t["exit_gross"]) < 1e-6
        assert abs(t["exit_bil_units"] * t["exit_bil_price"] - t["exit_bil_notional"]) < 1e-6
        assert t["total_cost"] == pytest.approx(t["entry_fee"] + t["qqq_fee"] + t["exit_fee"] + t["exit_bil_fee"])


def test_no_overlapping_positions_and_deterministic_tie(tmp_path):
    out1 = tmp_path / "a"; out2 = tmp_path / "b"
    run(DATA, out1); run(DATA, out2)
    t = pd.read_csv(out1 / "trades.csv"); t = t[t.cost_bps == 10].sort_values("entry")
    assert (pd.to_datetime(t.entry) > pd.to_datetime(t.exit).shift(1).fillna(pd.Timestamp("1900-01-01"))).all()
    a = pd.read_csv(out1 / "trades.csv"); b = pd.read_csv(out2 / "trades.csv")
    assert a.equals(b)
