import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P82 = ROOT / "data/research/p8_2"
P8 = ROOT / "data/research/p8"


def load(name):
    return json.loads((P82 / name).read_text(encoding="utf-8"))


def test_anomaly_audit_reviews_109_not_auto_delete():
    s = load("ticker_anomaly_summary.json")
    assert s["tickers_checked"] == 109
    assert s["anomaly_rows"] == 3041
    assert s["classification_counts"]["VERIFIED_CORRUPT"] == 2466
    assert s["classification_counts"]["VERIFIED_REAL_RETURN"] == 2
    rows = list(csv.DictReader((P82 / "ticker_anomaly_audit.csv").open(encoding="utf-8")))
    assert len({r["ticker"] for r in rows}) == 109
    assert any(r["ticker"] == "GME" and r["classification"] == "VERIFIED_REAL_RETURN" for r in rows)
    assert any(r["ticker"] == "CBE" and r["classification"] == "VERIFIED_CORRUPT" for r in rows)
    assert any(r["ticker"] == "ACS" and r["classification"] == "VERIFIED_CORRUPT" for r in rows)


def test_pit_coverage_denominator_is_full_membership():
    s = load("pit_coverage_summary.json")
    t = s["totals"]
    assert t["member_days"] == 1095490
    assert t["valid"] + t["unknown"] == t["member_days"]
    assert t["verified"] + t["quarantined"] == t["valid"]
    assert t["original_coverage"] < 0.91
    assert t["repaired_coverage"] <= t["original_coverage"]
    assert s["denominator"] == "ALL effective-dated S&P member-days, 2000-01-03..2024-12-31"


def test_three_methods_and_cost_definition():
    s = load("method_comparison.json")
    assert set(s["results"]) == {"A_RAW", "B_EXCLUDE_ALL", "C_PER_DATE"}
    assert s["cost"]["turnover_definition"].startswith("|hold XOR prev|/n")
    assert len(s["results"]["C_PER_DATE"]) == 7  # 6 + EW
    c = s["results"]["C_PER_DATE"]
    assert c["MOMENTUM_20"]["cagr"] < s["results"]["A_RAW"]["MOMENTUM_20"]["cagr"]


def test_walk_forward_active_return_and_switch_cost():
    s = load("walk_forward_results.json")
    assert s["status"] == "WALK_FORWARD_COMPLETE"
    assert len(s["windows"]) == 19
    assert s["switches"] >= 1
    assert s["selected"]["hac_active_t"] < 1.64
    assert s["selected"]["max_drawdown"] < -0.35


def test_bh_consistency_8_and_18():
    s = load("bh_consistency.json")
    assert s["primary_family"] == 8
    assert len(s["primary_q"]) == 8
    assert s["family_sensitivity"]["count_18"] == 18
    assert all(q > 0.10 for q in s["primary_q"].values())


def test_p8_1_is_preserved():
    s = json.loads((P8 / "p8_status.json").read_text(encoding="utf-8"))
    assert s["status"] == "P8_FIRST_ROUND_NO_GO"
    assert (P8 / "p8_audit.json").exists()
    assert (P82 / "p8_2_status.json").exists()
