import csv, json
from pathlib import Path

OUT = Path("data/universe")


def rows(): return list(csv.DictReader(open(OUT / "value_metric_rankings_p69.csv", encoding="utf-8")))
def cand(): return [r for r in rows() if r["security_type"] in ("COMMON","ADR") and r["candidate"] == "True"]
def audit(): return json.load(open(OUT / "value_metric_audit_p69.json", encoding="utf-8"))


def test_pe_only_positive_earnings():
    rs = cand()
    assert all(float(r["pe"]) > 0 for r in rs if r["pe"])
    assert any(float(r["earnings_yield"]) < 0 for r in rs if r["earnings_yield"])


def test_pb_rejects_negative_equity():
    rs = [r for r in cand() if r["pb"]]
    assert all(float(r["pb"]) > 0 for r in rs)


def test_ps_requires_positive_revenue():
    assert all(float(r["ps"]) > 0 for r in cand() if r["ps"])


def test_fcf_missing_capex_is_not_zero():
    rs = cand()
    missing = [r for r in rs if not r["fcf_yield"]]
    assert missing
    assert all(r["fcf_yield"] == "" for r in missing)


def test_negative_fcf_is_retained():
    assert any(float(r["fcf_yield"]) < 0 for r in cand() if r["fcf_yield"])


def test_pe_earnings_yield_are_reciprocal_and_highly_redundant():
    rs = [r for r in cand() if r["pe"] and r["earnings_yield"]]
    assert rs
    assert all(abs(float(r["pe"]) * float(r["earnings_yield"]) - 1) < 1e-6 for r in rs)
    assert audit()["pe_earnings_yield_spearman"] == -1.0


def test_accounting_groups_are_separate():
    d = audit()
    assert d["by_accounting"]["US_GAAP"]["securities"] == 2430
    assert d["by_accounting"]["IFRS"]["securities"] == 99
    assert "MATERIALS|IFRS" in {g["model_family"] + "|" + g["accounting_standard"] for g in
        csv.DictReader(open(OUT / "value_metric_peer_groups_p69.csv", encoding="utf-8"))}


def test_insufficient_group_has_no_percentile():
    rs = [r for r in rows() if r["scoring_status"] == "INSUFFICIENT_PEER_GROUP"]
    assert len(rs) == 55
    assert all(r["pe_percentile"] == "" and r["pb_percentile"] == "" for r in rs)


def test_winsorization_preserves_raw_values():
    rs = [r for r in cand() if r["pe"] and r["pe_percentile"]]
    assert rs
    assert all(float(r["pe"]) == float(r["pe"]) for r in rs)
    assert audit()["winsorization_rank_abs_change"]["n"] > 0


def test_candidate_count_and_no_cik_duplication():
    rs = cand(); d = audit()
    assert len(rs) == 2529
    assert len({r["cik"] for r in rs}) == 2529
    assert d["duplicate_cik_candidate_securities"] == 0


def test_no_future_filed_and_market_cap_gate():
    rs = [r for r in cand() if r["filed"]]
    assert rs
    assert all(r["filed"] <= "2026-11-05" for r in rs)
    # all candidates came from P6.8 VALUE_V1_DATA_READY
    assert all(r["candidate"] == "True" for r in cand())


def test_actual_intersections_and_status():
    d = audit()
    assert d["intersections"]["all_five"] == 992
    assert d["intersections"]["four_of_five"] == 1051
    assert d["status_counts"]["METRIC_RANK_AVAILABLE"] == 2474
