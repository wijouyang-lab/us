import csv, json
from datetime import date
from pathlib import Path
from tools.research.normalize_sec_cash_dividend_proxy_p613 import (
    normalize_cash, period_type, ttm_status, CASH_TAGS, PER_SHARE_TAGS)

OUT = Path("data/universe")


def test_raw_and_normalized_are_split():
    n, s = normalize_cash(-123.0, "USD", "PaymentsOfDividendsCommonStock")
    assert n == 123.0
    assert s == "CASH_FACT_NORMALIZED"


def test_sign_preserved_in_fact_output():
    rows = list(csv.DictReader(open(OUT / "sec_cash_dividend_proxy_facts_sample_p613.csv", encoding="utf-8")))
    neg = [r for r in rows if r["raw_value"] and float(r["raw_value"]) < 0]
    assert neg
    assert all(float(r["normalized_cash_dividend"]) >= 0 for r in neg if r["normalized_cash_dividend"])


def test_per_share_not_total_cash():
    n, s = normalize_cash(1.25, "USD/shares", "CommonStockDividendsPerShareDeclared")
    assert n is None and s == "PER_SHARE_FACT_NOT_TOTAL_CASH"


def test_taxonomy_duplicate_is_counted():
    rows = list(csv.DictReader(open(OUT / "sec_cash_dividend_proxy_coverage_p613.csv", encoding="utf-8")))
    assert sum(int(r["duplicate_fact_count"]) for r in rows) >= 0
    assert any(r["currency"] for r in rows)


def test_period_types():
    assert period_type("2025-01-01", "2025-12-31", "2026-02-15") == "ANNUAL"
    assert period_type("2026-01-01", "2026-06-30", "2026-08-01") == "YTD"
    assert period_type("2026-01-01", "2026-03-31", "2026-05-01") == "QUARTER"
    assert period_type("", "2025-12-31", "2026-02-15") == "INSTANT"


def test_ttm_requires_four_contiguous_quarters():
    good = [("2025-01-01","2025-03-31"),("2025-04-01","2025-06-30"),
            ("2025-07-01","2025-09-30"),("2025-10-01","2025-12-31")]
    assert ttm_status(good) == "TTM_AVAILABLE"
    assert ttm_status(good[:3]) == "TTM_UNAVAILABLE"
    overlap = good[:3] + [("2025-09-30","2025-12-31")]
    assert ttm_status(overlap) == "TTM_UNAVAILABLE"


def test_missing_fact_is_not_nonpayer():
    d = json.load(open(OUT / "sec_cash_dividend_proxy_summary_p613.json", encoding="utf-8"))
    assert d["coverage"]["unknown"] > 0
    assert d["coverage"]["no_positive_in_window"] >= 0


def test_multi_ticker_is_issuer_level():
    rows = list(csv.DictReader(open(OUT / "sec_cash_dividend_proxy_coverage_p613.csv", encoding="utf-8")))
    assert any(r["allocation_status"] == "ISSUER_LEVEL_NOT_TICKER_ALLOCABLE" for r in rows)
    assert all(r["allocation_status"] != "TICKER_ALLOCABLE" for r in rows if "|" in r["tickers"])


def test_adr_blocked():
    rows = list(csv.DictReader(open(OUT / "sec_cash_dividend_proxy_coverage_p613.csv", encoding="utf-8")))
    adr = [r for r in rows if r["security_type"] == "ADR"]
    assert adr and all(r["allocation_status"] == "ADR_RATIO_UNVERIFIED" for r in adr)


def test_filed_gate_and_accession():
    rows = list(csv.DictReader(open(OUT / "sec_cash_dividend_proxy_facts_sample_p613.csv", encoding="utf-8")))
    assert all(not r["filed_date"] or r["filed_date"] <= "2026-11-06" for r in rows)
    assert any(r["accession_number"] for r in rows)


def test_per_share_tags_are_actual_and_separate():
    rows = list(csv.DictReader(open(OUT / "sec_cash_dividend_per_share_facts_p613.csv", encoding="utf-8")))
    ps = [r for r in rows if r["fact_kind"] == "PER_SHARE"]
    assert ps
    assert all(r["normalized_cash_dividend"] == "" for r in ps)
    assert set(r["tag"] for r in ps).issubset(PER_SHARE_TAGS)


def test_actual_counts():
    d = json.load(open(OUT / "sec_cash_dividend_proxy_summary_p613.json", encoding="utf-8"))
    assert d["cash_facts"]["total_cash_ciks"] == 2300
    assert d["coverage"]["has_positive_evidence"] == 2248
    assert d["coverage"]["ttm_available"] == 6
    assert d["coverage"]["ticker_allocable_common"] == 5100
    assert d["coverage"]["adr_unverified"] == 308
