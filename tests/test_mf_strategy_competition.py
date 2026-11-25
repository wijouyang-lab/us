import json
from pathlib import Path

import pandas as pd


def test_three_strategies():
    d = pd.read_csv("data/research/mf_v1/strategy_comparison.csv")
    assert set(d.strategy) >= {"A", "B", "C"}


def test_a_underperforms_spy():
    d = pd.read_csv("data/research/mf_v1/strategy_comparison.csv").set_index("strategy")
    assert d.loc["A", "CAGR"] < d.loc["SPY", "CAGR"]


def test_a_drawdown_worse_than_15():
    d = pd.read_csv("data/research/mf_v1/strategy_comparison.csv").set_index("strategy")
    assert d.loc["A", "MaxDD"] < -0.15


def test_b_lookahead_flag():
    s = json.loads(Path("data/research/mf_v1/summary.json").read_text())
    assert "current fundamentals" in s["reason"]


def test_status_data_limited():
    s = json.loads(Path("data/research/mf_v1/summary.json").read_text())
    assert s["status"] == "DATA_LIMITED"


def test_nav_files():
    for k in "ABC":
        n = pd.read_csv(f"data/research/mf_v1/nav_{k}.csv")
        assert n.nav.iloc[0] == 50000


def test_feature_catalog():
    f = pd.read_csv("docs/research/MULTI_FACTOR_FEATURE_CATALOG_V1.csv")
    assert "Momentum_20D_Pct" in set(f.feature)


def test_exit_comparison():
    e = pd.read_csv("docs/research/MULTI_FACTOR_EXIT_COMPARISON_V1.csv")
    assert "NOT_RUN" in set(e.status)


def test_no_alpha_side_effects():
    assert not Path("data/research/mf_v1/trade_ledger.csv").exists()


def test_comparison_csv():
    d = pd.read_csv("docs/research/MULTI_FACTOR_STRATEGY_COMPARISON_V1.csv")
    assert len(d) >= 6
