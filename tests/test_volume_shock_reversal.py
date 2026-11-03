# -*- coding: utf-8 -*-
"""Tests for the volume-shock reversal event study and portfolio."""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tools.research.volume_shock_reversal import DataError, features, load, run

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "research" / "volume_shock_reversal"


def _frame(n=40):
    dates = pd.bdate_range("2020-01-01", periods=n)
    rng = np.random.default_rng(7)
    ret = rng.normal(0, 0.01, n)
    close = 100 * np.exp(np.cumsum(ret))
    return pd.DataFrame({"Date": dates, "Open": close, "High": close, "Low": close,
                         "Close": close, "Volume": 1_000_000.0, "Adj Close": close})


def test_sigma_and_dv_medians_exclude_current_day(tmp_path):
    d = _frame(40)
    p = tmp_path / "QQQ.csv"; d.to_csv(p, index=False)
    f = features(load(p, "QQQ"))
    t = 30
    r = np.log(f.AdjClose / f.AdjClose.shift(1))
    expected_sigma = r.iloc[t - 20:t].std(ddof=1)
    assert f.Sigma20.iloc[t] == pytest.approx(expected_sigma)
    dv = f.Close * f.Volume
    assert f.DV_Ratio.iloc[t] == pytest.approx(dv.iloc[t] / dv.iloc[t - 20:t].median())
    assert f.Z.iloc[t] == pytest.approx(r.iloc[t] / expected_sigma)


def test_event_threshold_is_fixed(tmp_path):
    d = _frame(40)
    d.loc[39, "Adj Close"] = d["Adj Close"].iloc[38] * np.exp(-0.10)
    d.loc[39, "Volume"] = 5_000_000
    p = tmp_path / "QQQ.csv"; d.to_csv(p, index=False)
    f = features(load(p, "QQQ"))
    assert bool(f.Event.iloc[-1])


def test_duplicate_and_invalid_data_rejected(tmp_path):
    d = _frame(30)
    p = tmp_path / "QQQ.csv"
    pd.concat([d, d.tail(1)]).to_csv(p, index=False)
    with pytest.raises(DataError):
        load(p, "QQQ")
    d2 = _frame(30); d2.loc[0, "Volume"] = 0
    d2.to_csv(p, index=False)
    with pytest.raises(DataError):
        load(p, "QQQ")


def test_full_study_and_portfolio_outputs(tmp_path):
    out = tmp_path / "out"
    report = run(DATA, out)
    assert len(report["study"]) == 12
    assert all(0 <= r["q_bh"] <= 1 for r in report["study"])
    assert report["study"][0]["non_overlap_events"] <= report["study"][0]["events"]
    assert set(report["portfolio"]) == {"5", "10", "20", "50"}
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


def test_no_overlapping_global_positions(tmp_path):
    out = tmp_path / "out"
    run(DATA, out)
    t = pd.read_csv(out / "trades.csv")
    t = t[t.cost_bps == 10].sort_values("entry")
    assert (pd.to_datetime(t.entry) > pd.to_datetime(t.exit).shift(1).fillna(pd.Timestamp("1900-01-01"))).all()


def test_missing_etf_fails_closed(tmp_path):
    bad = tmp_path / "data"
    shutil.copytree(DATA, bad)
    d = pd.read_csv(bad / "GLD.csv")
    d.loc[d.index[-5], "Volume"] = np.nan
    d.to_csv(bad / "GLD.csv", index=False)
    with pytest.raises(DataError):
        run(bad, tmp_path / "out")
