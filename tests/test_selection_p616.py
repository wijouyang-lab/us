import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/universe/selection"


def load(name):
    with (OUT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_extreme_value_audit_marks_but_does_not_delete():
    rows = {r["ticker"]: r for r in load("valuation_integrity_audit.csv")}
    assert len(rows) == 50
    assert rows["CRMT"]["valuation_status"] == "VALUATION_INPUT_SUSPECT"
    assert "EXTREME" in rows["CRMT"]["valuation_reason"]
    assert rows["LIVE"]["valuation_status"] in ("VALUATION_VALID", "VALUATION_INPUT_SUSPECT")
    assert "market_cap_calc" in rows["CRMT"]
    assert "fcf_calc" in rows["CRMT"]
    assert rows["CRMT"]["company_name"]
    # original ranking is retained
    assert rows["CRMT"]["ticker"] in {r["ticker"] for r in load("value_top50.csv")}


def test_freshness_catches_inmd_quality_and_keeps_original():
    q = {r["ticker"]: r for r in load("quality_freshness_adjusted.csv")}
    assert q["INMD"]["freshness_status"] == "FUNDAMENTALS_STALE"
    assert q["INMD"]["freshness_adjusted_rank"] == ""
    assert q["INMD"]["original_rank"] == "5"
    assert any(r["ticker"] == "INMD" for r in load("quality_top50.csv"))
    fresh = [r for r in q.values() if r["freshness_status"] == "FUNDAMENTALS_FRESH"]
    assert fresh


def test_adv_computed_from_completed_sessions_and_eligible_is_explicit():
    s = json.loads((OUT / "tradability/tradability_summary.json").read_text(encoding="utf-8"))
    assert s["liquidity_source"].startswith("YFINANCE")
    rows = load("tradability/value_tradable_candidates.csv")
    assert all(r["valid_sessions_20"] == "20" and r["valid_sessions_60"] == "60" for r in rows)
    assert all(float(r["adv20_usd"]) > 0 and float(r["adv60_usd"]) > 0 for r in rows)
    assert s["value"]["eligible"] == 13
    assert s["quality"]["eligible"] == 3
    assert s["garp"]["eligible"] == 0
    assert all(r["tradability_status"] in ("ELIGIBLE", "WATCH", "BLOCKED", "DATA_BLOCKED") for r in rows)


def test_bdc_zero_is_reported_as_coverage_gap_not_no_bdc():
    s = json.loads((OUT / "special_model_coverage.json").read_text(encoding="utf-8"))
    b = s["bdc_audit"]
    assert b["explicit_bdc_model_family_rows"] == 0
    assert b["sic_6726_rows"] == 0
    assert b["bdc_name_candidate_count"] > 0
    assert "does not mean no BDCs" in b["note"]
    assert s["classification_blocked"]["garp_blocked"] == 293
    assert s["classification_blocked"]["unclassified_none"] == 65


def test_quality_report_is_research_only_and_consistent():
    s = json.loads((OUT / "selection_quality_report.json").read_text(encoding="utf-8"))
    assert s["status"] == "CURRENT_CROSS_SECTIONAL_RESEARCH"
    assert s["pit_status"] == "PIT_BACKTEST_BLOCKED"
    assert s["research_label"] == "RESEARCH_ONLY_NOT_A_BUY_SELL_SIGNAL"
    assert s["counts"]["value_candidates"] == 2529
    assert sum(s["valuation"]["status_counts"].values()) == 50
