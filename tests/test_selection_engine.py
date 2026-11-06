import csv
import json
import math
from pathlib import Path

import pytest

from tools.investment_research.selection.build_rankings import pct, num, AS_OF
from tools.investment_research.selection.build_garp_metrics import growth, cagr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/universe/selection"


def rows(name):
    with (OUT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_percentile_direction_and_order_invariance():
    hi = pct([10, 20, 30, 40], higher=True)
    lo = pct([10, 20, 30, 40], higher=False)
    assert hi == [25.0, 50.0, 75.0, 100.0]
    assert lo == [75.0, 50.0, 25.0, 0.0]
    # changing input order changes only position, not the rank of a value
    assert dict(zip(["a","b","c","d"], hi))["d"] == 100.0
    assert dict(zip(["d","c","b","a"], pct([40,30,20,10])) )["d"] == 100.0


def test_value_candidates_and_positive_composite():
    v = rows("value_rankings.csv")
    top = rows("value_top50.csv")
    assert sum(1 for r in v if r["candidate"] == "True") == 2529
    assert len(top) == 50
    assert len({r["cik"] for r in top}) == 50
    # top Value names must not be selected on negative earnings/FCF
    assert all(float(r["earnings_yield"]) >= 0 for r in top)
    assert all(float(r["fcf_yield"]) >= 0 for r in top)
    assert all(float(r["pb"]) > 0 and float(r["ps"]) > 0 for r in top)
    assert all(r["value_composite_experimental"] for r in top)


def test_value_negative_earnings_has_no_composite():
    v = rows("value_rankings.csv")
    negative = [r for r in v if r.get("earnings_yield") and float(r["earnings_yield"]) < 0]
    assert negative
    assert all(r["value_composite_experimental"] == "" for r in negative)
    assert all(r["value_status"] != "VALUE_EXPERIMENTAL_ALL_FOUR" for r in negative)


def test_pit_gate_for_top_rows():
    for name in ("value_top50.csv", "quality_top50.csv", "garp_top50.csv"):
        for r in rows(name):
            assert not r["filed"] or r["filed"] <= AS_OF.isoformat()


def test_quality_formula_matches_published_scores():
    q = [r for r in rows("quality_rankings.csv") if r["quality_status"] == "QUALITY_V1_SCORED"]
    assert len(q) == 2313
    for r in q:
        expected = (.30*float(r["roe_percentile"]) + .25*float(r["roa_percentile"])
                    + .25*float(r["cfo_percentile"]) + .20*float(r["leverage_percentile"]))
        assert abs(expected - float(r["quality_score_recomputed"])) < 0.02
    top = rows("quality_top50.csv")
    assert len(top) == 50
    assert all(r["quality_status"] == "QUALITY_V1_SCORED" for r in top)


def test_garp_is_historical_only_and_no_forward_fields():
    g = rows("garp_rankings.csv")
    header = set(g[0])
    assert "forward_eps" not in header and "peg" not in header
    top = rows("garp_top50.csv")
    assert len(top) == 50
    assert all(r["garp_status"] == "GARP_EXPERIMENTAL_HISTORICAL_GROWTH" for r in top)
    assert all(float(r["garp_score"]) >= 0 for r in top)


def test_growth_denominator_guards():
    assert growth(10, 0) is None
    assert growth(10, -5) is None
    assert cagr(100, 0, 3) is None
    assert cagr(100, 50, 0) is None


def test_snapshot_counts_hashes_and_statuses():
    s = json.loads((OUT / "selection_snapshot.json").read_text(encoding="utf-8"))
    assert s["status"] == "CURRENT_CROSS_SECTIONAL_RESEARCH"
    assert s["pit_status"] == "PIT_BACKTEST_BLOCKED"
    assert s["value"]["candidate_issuers"] == 2529
    assert s["value"]["all_four_ranked"] == 851
    assert s["value"]["all_five_p69_intersection"] == 992
    assert s["quality"]["scored_issuers"] == 2313
    assert s["garp"]["ranked_issuers"] == 3579
    assert s["quality"]["score_mismatches"] == 0
    assert all(len(v["sha256"]) == 64 for v in s["inputs"].values())
    assert s["research_label"] == "RESEARCH_ONLY_NOT_A_BUY_SELL_SIGNAL"


def test_data_quality_reports_missingness_not_zero():
    d = json.loads((OUT / "selection_data_quality.json").read_text(encoding="utf-8"))
    assert d["value"]["all_four"] == 851
    assert d["value"]["coverage"]["pb"] > 0
    assert d["quality"]["coverage"]["roe"] == 2313
    assert d["garp"]["ranked"] == 3579
    assert any("PIT_BACKTEST_BLOCKED" in x for x in d["limitations"])


def test_sensitivity_is_present_and_not_performance():
    s = json.load(open(OUT / "selection_sensitivity.json"))
    assert s["status"] == "EXPERIMENTAL_SENSITIVITY_ONLY"
    assert s["pit_status"] == "PIT_BACKTEST_BLOCKED"
    assert s["value"]["candidate_count"] == 2529
    assert 0 <= s["value"]["single_pb_top50_overlap"] <= 50
    assert 0 <= s["quality"]["equal_top50_overlap"] <= 50
    assert "backtest" in s["quality"]["weight_note"].lower()
