import json
from pathlib import Path

import pandas as pd


def test_coverage_uses_expected_member_days_and_retains_missing():
    c = json.loads(Path("data/research/p13_1/p13_1_coverage.json").read_text())
    for row in c["5Y"], c["3Y"]:
        assert 0 < row["member_day_coverage"] <= 1
        assert row["observed_member_days"] <= row["expected_member_days"]
    assert c["5Y"]["member_day_coverage"] > 0.95
    assert c["pools"]["missing"] == 26


def test_stock_coverage_has_zero_for_missing_members():
    s = pd.read_csv("data/research/p13_1/p13_1_stock_coverage.csv")
    assert (s.coverage == 0).sum() == 26
    assert s.longest_missing_streak.max() > 0


def test_entry_exit_dates_are_same_market_calendar():
    a = pd.read_csv("data/research/p13_1/p13_1_alignment_sample.csv")
    assert (a.signal_date == a.entry_date).all()
    assert (a.exit_date > a.entry_date).all()
    assert a[["stock_entry_price", "stock_exit_price", "benchmark_entry_price", "benchmark_exit_price"]].notna().all().all()


def test_price_results_do_not_claim_bh_significance():
    h = pd.read_csv("data/research/p13_1/p13_1_price_hac.csv")
    assert h.q.min() > 0.10
    o = pd.read_csv("data/research/p13_1/p13_1_price_oos.csv")
    vol = o[(o.window == "5Y") & (o.cohort == "broad") & (o.factor == "vol20")].set_index("segment")
    assert vol.loc["test", "mean_spread"] < 0


def test_no_duplicate_windows():
    c = json.loads(Path("data/research/p13_1/p13_1_coverage.json").read_text())
    assert c["calendar"]["spy_duplicate_dates"] == 0
    assert c["calendar"]["membership_duplicate_snapshots"] == 0
    assert c["calendar"]["price_duplicate_symbol_days"] == 0
