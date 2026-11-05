# -*- coding: utf-8 -*-
from pathlib import Path
import json
import pandas as pd
import pytest

from tools.research.transition_risk_match import CONFIG, metrics

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "research" / "transition_risk_match"
OUT = ROOT / "docs" / "research" / "transition_risk_match"


def test_transition_config_and_dates_aligned():
    d = pd.read_csv(D / "transition_daily_nav.csv")
    d = d[d.config == CONFIG]
    assert CONFIG == "w25_c10_all_legs"
    assert d.date.is_unique
    q = pd.read_csv(D / "QQQ.csv"); b = pd.read_csv(D / "BIL.csv")
    qd = pd.to_datetime(q.Date, utc=True).dt.tz_convert(None).dt.normalize()
    bd = pd.to_datetime(b.Date, utc=True).dt.tz_convert(None).dt.normalize()
    qd = qd[(qd >= pd.Timestamp("2007-05-30")) & (qd <= pd.Timestamp("2026-10-30"))]
    bd = bd[(bd >= pd.Timestamp("2007-05-30")) & (bd <= pd.Timestamp("2026-10-30"))]
    assert len(d) == len(qd) == len(bd) == 4888
    assert d.date.min() == "2007-05-30" and d.date.max() == "2026-10-30"


def test_risk_match_weight_is_vol_only_and_tight():
    r = json.loads((OUT / "risk_match.json").read_text())
    assert 0 < r["matched_weight"] < 0.20
    assert abs(r["target_vol"] - r["risk_matched"]["actual_vol"]) < 1e-5
    assert abs(r["vol_error"]) < 1e-5


def test_transition_and_passive_metrics_present():
    r = json.loads((OUT / "risk_match.json").read_text())
    for k in ("transition", "risk_matched"):
        m = r[k]
        for field in ("cagr", "volatility", "max_drawdown", "sharpe_rf0",
                      "sharpe_excess_bil", "max_drawdown_peak_date",
                      "max_drawdown_trough_date", "max_drawdown_recovery_date"):
            assert field in m
    assert r["transition"]["cagr"] < r["risk_matched"]["cagr"]


def test_trade_costs_and_nav_reconcile():
    t = pd.read_csv(OUT / "trades_risk_matched.csv")
    assert (t["notional"] - t["shares"] * t["price"]).abs().max() < 1e-8
    assert (t["total_cost"] - (t["cost"] + t["slippage"])).abs().max() < 1e-8
    nav = pd.read_csv(OUT / "nav_risk_matched.csv", index_col=0, parse_dates=True)["nav"]
    assert nav.index.min() == pd.Timestamp("2007-05-30")
    assert nav.index.max() == pd.Timestamp("2026-10-30")


def test_benchmark_includes_dividend():
    idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
    f = pd.DataFrame({"Close": [100.0, 100.0], "Open": [100.0, 100.0],
                      "Dividends": [0.0, 1.0]}, index=idx)
    from tools.research.transition_risk_match import bench
    s = bench({"BIL": f}, "BIL", idx)
    assert s.iloc[1] == pytest.approx(50500.0)


def test_transition_dates_are_unique_and_no_duplicates():
    d = pd.read_csv(D / "transition_daily_nav.csv")
    d = d[d.config == CONFIG]
    assert not d.date.duplicated().any()


def test_missing_portfolio_price_fails_closed(tmp_path):
    import shutil
    from tools.research.transition_risk_match import run
    data = tmp_path / "data"; shutil.copytree(D, data)
    q = pd.read_csv(data / "QQQ.csv")
    q = q[pd.to_datetime(q.Date, utc=True).dt.strftime("%Y-%m-%d") != "2010-01-04"]
    q.to_csv(data / "QQQ.csv", index=False)
    with pytest.raises(ValueError):
        run(data, tmp_path / "out")


def test_cutoff_injection_does_not_change_result(tmp_path):
    import shutil
    from tools.research.transition_risk_match import run
    data = tmp_path / "data"; shutil.copytree(D, data)
    q = pd.read_csv(data / "QQQ.csv")
    last = q.iloc[-1].copy(); last["Date"] = "2026-11-02 00:00:00-05:00"; last["Close"] = 1e9
    pd.concat([q, pd.DataFrame([last])]).drop_duplicates("Date", keep="last").to_csv(data / "QQQ.csv", index=False)
    a = run(D, tmp_path / "base"); b = run(data, tmp_path / "inject")
    assert a["risk_matched"]["cagr"] == pytest.approx(b["risk_matched"]["cagr"])
    assert a["risk_matched"]["max_drawdown"] == pytest.approx(b["risk_matched"]["max_drawdown"])


def test_cost_legs_are_sum_of_components():
    t = pd.read_csv(OUT / "trades_risk_matched.csv")
    assert (t["total_cost"] - (t["commission"] + t["sec_fee"] + t["taf_fee"] +
                               t["cat_fee"] + t["clearing_fee"] + t["exchange_fee"] +
                               t["slippage"])).abs().max() < 1e-8


def test_strategy_and_benchmark_share_calendar():
    t = pd.read_csv(OUT / "nav_transition.csv", index_col=0, parse_dates=True)
    p = pd.read_csv(OUT / "nav_risk_matched.csv", index_col=0, parse_dates=True)
    assert t.index.equals(p.index)
    assert len(t) == 4888
