import csv, json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p8_2_2"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_member_day_partition_is_exact():
    s = load("member_day_status_summary.json")
    assert s["denominator"] == 1095490
    assert sum(s["statuses"].values()) == 1095490
    assert s["statuses"]["VALID_VERIFIED_TRADABLE"] == 981362
    assert s["statuses"]["ZERO_VOLUME_OR_STALE"] == 4845
    assert s["statuses"]["VERIFIED_CORRUPT"] == 117
    assert s["statuses"]["UNRESOLVED"] == 34
    assert s["statuses"]["UNKNOWN_MISSING_DATA"] == 109132


def test_full_ohlcv_not_equal_tradable():
    s = load("ohlcv_coverage_summary.json")["totals"]
    assert s["full_ohlcv"] == 986358
    assert s["verified_tradable"] == 981362
    assert s["verified_tradable"] < s["full_ohlcv"]


def test_event_time_metrics_are_valid_subset_not_complete_nav():
    s = load("event_time_results.json")
    assert s["nav_complete"] is False
    assert s["status"] == "EVENT_TIME_COMPLETE_NAV_INCOMPLETE"
    assert s["invalid_months"] > 0
    for v in s["results"].values():
        assert v["invalid_months"] > 0
        assert v["valid_months"] + v["invalid_months"] == 298


def test_time_travel_detection_delayed_after_decision_is_not_available():
    s = load("event_time_policy.json")
    assert s["post_hoc_used_for_signal"] is False if "post_hoc_used_for_signal" in s else True
    # explicit helper semantics
    from tools.investment_research.p8_2_2.event_time_audit import available_on
    event = date(2021, 1, 27); decision = date(2021, 1, 29)
    assert available_on(event, decision, date(2021, 1, 27)) is True
    assert available_on(event, decision, date(2021, 2, 1)) is False


def test_event_time_status_no_go_and_bh():
    s = load("p8_2_2_status.json")
    assert s["status"] == "P8_2_2_AUDIT_COMPLETE_NO_GO"
    assert s["go_count"] == 0
    assert s["nav_status"] == "INCOMPLETE_FOR_EQUITY_STRATEGIES"
    assert s["walk_forward_gate"] == "NO-GO"
    assert s["bh"]["primary_family"] == 8


def test_switch_costs_and_old_artifacts():
    w = load("walk_forward_results.json")
    assert w["status"] == "WALK_FORWARD_COMPLETE"
    assert len(w["windows"]) == 19
    assert w["switches"]
    assert all("L1_weight_change" in x for x in w["switches"])
    assert (ROOT / "data/research/p8_2_1/p8_2_1_status.json").exists()
    assert (ROOT / "data/research/p8_2/p8_2_status.json").exists()
    assert (ROOT / "data/research/p8/p8_status.json").exists()
