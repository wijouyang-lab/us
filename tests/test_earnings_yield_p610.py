import csv, json
from pathlib import Path

OUT = Path("data/universe")


def rows(): return list(csv.DictReader(open(OUT / "earnings_yield_v1_scores_p610.csv", encoding="utf-8")))
def cand(): return [r for r in rows() if r["candidate"] == "True"]
def cov(): return json.load(open(OUT / "earnings_yield_coverage_p610.json", encoding="utf-8"))
def corr(): return json.load(open(OUT / "earnings_yield_correlation_p610.json", encoding="utf-8"))
def rob(): return json.load(open(OUT / "earnings_yield_robustness_p610.json", encoding="utf-8"))


def test_pool_and_ey_coverage():
    d = cov()
    assert d["pool"]["candidates"] == 2529
    assert d["pool"]["unique_ciks"] == 2529
    assert d["pool"]["ey_valid"] == 2504
    assert d["pool"]["ey_ranked"] == 2449


def test_negative_earnings_and_near_zero_categories():
    d = cov()["categories"]
    assert d["POSITIVE_EARNINGS"]["n"] == 1272
    assert d["NEGATIVE_EARNINGS"]["n"] == 1151
    assert d["ZERO_OR_NEAR_ZERO_EARNINGS"]["n"] == 81
    assert d["NET_INCOME_MISSING"]["n"] == 23
    assert d["FINANCIAL_PERIOD_INVALID"]["n"] == 2


def test_missing_income_is_blank_not_zero():
    rs = [r for r in cand() if r["status"] == "METRIC_BLOCKED" and "NET_INCOME_MISSING" in r["blocker_codes"]]
    assert rs
    assert all(r["earnings_yield"] == "" for r in rs)


def test_market_cap_gate_and_no_adr():
    rs = cand()
    assert all(r["security_type"] == "COMMON" for r in rs)
    assert len(rs) == 2529


def test_unique_cik_no_duplicate_ranking():
    rs = cand()
    assert len({r["cik"] for r in rs}) == 2529


def test_accounting_split():
    d = cov()["by_accounting"]
    assert d["US_GAAP"]["candidates"] == 2430
    assert d["IFRS"]["candidates"] == 99
    assert d["US_GAAP"]["valid"] == 2405
    assert d["IFRS"]["valid"] == 99


def test_period_gate_blocks_invalid_periods():
    rs = [r for r in cand() if r["financial_period_invalid"] == "True"]
    assert len(rs) == 2
    assert all(r["status"] != "METRIC_RANK_AVAILABLE" for r in rs)
    assert all(r["financial_period"] <= "2026-11-05" for r in rows() if r["financial_period"] and r["candidate"] == "True" and r["financial_period_invalid"] != "True")


def test_pe_ey_reciprocal_and_correlation():
    c = corr()
    assert c["pe_ey"]["spearman"] == -1.0
    assert c["pairs"]["EY_FCF"]["spearman"] > 0
    assert c["pairs"]["EY_Quality"]["spearman"] > 0


def test_winsorization_preserves_raw_and_rank():
    r = rob()["winsorization"]
    assert r["spearman"] > 0.99
    assert r["mean_abs_percentile_change"] < 0.1
    assert any(x["earnings_yield"] and x["earnings_yield_percentile"] for x in cand())


def test_insufficient_group_has_no_rank():
    rs = [r for r in cand() if r["status"] == "INSUFFICIENT_PEER_GROUP"]
    assert len(rs) == 55
    assert all(r["earnings_yield_percentile"] == "" for r in rs)


def test_quality_quadrants_and_no_composite():
    q = list(csv.DictReader(open(OUT / "earnings_yield_quality_quadrants_p610.csv", encoding="utf-8")))
    assert sum(int(r["n"]) for r in q) == 1727
    assert cov()["verification"]["all_checks_pass"] is True
    assert "value_v1_composite" not in rows()[0]


def test_historical_gate_remains_closed():
    g = cov()["historical_gate"]
    assert g["member_session_coverage"] < 0.95
    assert g["ticker_coverage"] < 0.98
    assert g["backtest_ready"] is False
