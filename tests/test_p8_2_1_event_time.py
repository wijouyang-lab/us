import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/research/p8_2_1"


def load(name): return json.loads((P / name).read_text(encoding="utf-8"))


def test_event_time_does_not_use_future_anomaly_for_selection():
    s = load("event_time_results.json")
    assert s["method"] == "D_EVENT_TIME"
    assert "never used to change holdings" in s["policy"].lower()
    assert s["invalid_months"] == 48
    assert 0 < s["invalid_exposure"] < 0.1
    h = list(csv.DictReader((P / "event_time_holdings.csv").open(encoding="utf-8")))
    assert any(x["status"] == "DATA_INVALID_UNPRICEABLE" for x in h)
    assert all(x["tickers"] for x in h if x["status"] == "VALID")


def test_full_ohlcv_coverage_not_just_adjusted_close():
    s = load("ohlcv_coverage_summary.json")["totals"]
    assert s["member_days"] == 1095490
    assert s["full_ohlcv"] <= s["valid_close"]
    assert s["verified_tradable"] <= s["full_ohlcv"]
    assert s["verified_tradable_coverage"] < s["full_ohlcv_coverage"]
    assert s["corrupt"] + s["unresolved"] + s["zero_or_stale"] > 0


def test_anomaly_reclassification_zero_volume_not_corrupt():
    s = load("anomaly_classification.json")
    assert s["counts"]["ZERO_VOLUME_OR_STALE"] == 1199
    assert s["counts"]["VERIFIED_CORRUPT"] == 735
    assert s["counts"]["VERIFIED_REAL_RETURN"] == 2
    assert "zero volume is ZERO_VOLUME_OR_STALE" in s["policy"]


def test_factor_window_audit_has_all_strategies():
    rows = list(csv.DictReader((P / "factor_window_audit.csv").open(encoding="utf-8")))
    assert len(rows) == 5478
    assert {r["strategy"] for r in rows} == {"MOMENTUM_20","MOMENTUM_60","MOMENTUM_120","TREND_MA200","LOW_VOL_60","REVERSAL_5"}


def test_switch_costs_use_actual_holdings():
    s = load("walk_forward_results.json")
    assert s["status"] == "WALK_FORWARD_COMPLETE"
    assert len(s["windows"]) == 19
    assert len(s["switches"]) == 8
    assert all("L1_weight_change" in x and "switch_cost_usd_bps" in x for x in s["switches"])
    assert s["selected"]["hac_active_t"] < 1.64
    assert s["selected"]["max_drawdown"] < -0.35


def test_bh_families_and_p8_2_preserved():
    s = load("bh_consistency.json")
    assert s["primary_family"] == 8
    assert s["sensitivity_family"] == 24
    assert load("p8_2_1_status.json")["go_count"] == 0
    assert (ROOT / "data/research/p8_2/p8_2_status.json").exists()
    assert (ROOT / "data/research/p8/p8_status.json").exists()
