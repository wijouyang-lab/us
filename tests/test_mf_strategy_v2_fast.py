import json
from pathlib import Path

import pandas as pd


def test_fast_results_exist():
    d = pd.read_csv("docs/research/MULTI_FACTOR_V2_STRATEGY_COMPARISON.csv")
    assert set(d.strategy) >= {"A", "B", "C", "SPY", "QQQ"}


def test_a_5y():
    d = pd.read_csv("docs/research/MULTI_FACTOR_V2_STRATEGY_COMPARISON.csv").set_index("strategy")
    assert abs(d.loc["A", "CAGR"] - 0.092963899) < 1e-3


def test_a_drawdown_under_15():
    d = pd.read_csv("docs/research/MULTI_FACTOR_V2_STRATEGY_COMPARISON.csv").set_index("strategy")
    assert d.loc["A", "MaxDD"] > -0.15


def test_exit_variants():
    e = pd.read_csv("docs/research/MULTI_FACTOR_V2_EXIT_COMPARISON.csv")
    assert set(e.exit) == {"fixed6", "fixed8", "atr20", "atr25", "atr30", "ma50", "rank"}


def test_fixed6_vs_fixed8_differ():
    e = pd.read_csv("docs/research/MULTI_FACTOR_V2_EXIT_COMPARISON.csv").set_index("exit")
    assert e.loc["fixed6", "MaxDD"] != e.loc["fixed8", "MaxDD"]


def test_cost_rows():
    c = pd.read_csv("docs/research/MULTI_FACTOR_V2_COST_SENSITIVITY.csv")
    assert c.bps_per_side.astype(int).tolist() == [5, 10, 20]


def test_ledger_nonempty():
    l = pd.read_csv("docs/research/MULTI_FACTOR_V2_TRADE_LEDGER.csv")
    assert len(l) > 1000
    assert "exit_reason" in l.columns


def test_daily_nav():
    n = pd.read_csv("docs/research/MULTI_FACTOR_V2_DAILY_NAV.csv")
    assert len(n) > 1000


def test_annual_returns():
    a = pd.read_csv("docs/research/MULTI_FACTOR_V2_ANNUAL_RETURNS.csv")
    assert len(a) >= 4


def test_no_paper_authorization():
    s = Path("docs/research/MULTI_FACTOR_STRATEGY_V2_FINAL.md").read_text()
    assert "PAPER_50000 = NOT_AUTHORIZED" in s
