import json
from pathlib import Path

import pandas as pd


def test_coverage_uses_expected_member_days():
    c = json.loads(Path("data/research/p13_1/p13_1_coverage.json").read_text())
    for row in c:
        assert 0 < row["member_day_coverage"] <= 1
        assert row["observed_member_days"] <= row["expected_member_days"]
        assert row["member_day_coverage"] > 0.95
    assert c[0]["window"] == "5Y" and c[1]["window"] == "3Y"


def test_price_results_do_not_claim_bh_significance():
    h = pd.read_csv("data/research/p13_1/p13_1_price_hac.csv")
    assert h.q.min() > 0.10
    o = pd.read_csv("data/research/p13_1/p13_1_price_oos.csv")
    vol = o[o.factor == "vol20"].set_index("segment")
    assert vol.loc["test", "high_minus_low"] < 0


def test_coverage_file_has_no_duplicate_windows():
    c = json.loads(Path("data/research/p13_1/p13_1_coverage.json").read_text())
    assert len({r["window"] for r in c}) == len(c)
