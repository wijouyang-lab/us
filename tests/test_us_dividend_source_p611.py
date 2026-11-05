import csv, json
from pathlib import Path
from tools.research.normalize_us_dividend_events_p611 import normalize_event, dedupe_events

OUT = Path("data/universe")


def raw(**kw):
    d = {"dps": 1.25, "currency": "USD", "dividend_type": "REGULAR_CASH",
         "announcement_date": "2026-01-02", "ex_dividend_date": "2026-01-15",
         "record_date": "2026-01-16", "payment_date": "2026-02-01", "frequency": "QUARTERLY"}
    d.update(kw); return d


def ev(**kw):
    return normalize_event(raw(**kw), "CAT", "0000018230", "COMMON", "Caterpillar", "test", "CAT", "2026-11-05")


def test_dps_not_total_cash_dividend():
    e = ev()
    assert e["dps"] == 1.25
    assert "total" not in e
    assert e["verification_status"] == "DIVIDEND_EVENT_FIELDS_COMPLETE"


def test_announcement_and_ex_date_are_separate():
    e = ev()
    assert e["announcement_date"] == "2026-01-02"
    assert e["ex_dividend_date"] == "2026-01-15"


def test_regular_and_special_are_distinct():
    assert ev(dividend_type="REGULAR_CASH")["dividend_type"] == "REGULAR_CASH"
    assert ev(dividend_type="SPECIAL_CASH")["dividend_type"] == "SPECIAL_CASH"


def test_missing_payment_date_is_blank_not_filled():
    e = ev(payment_date="")
    assert e["payment_date"] == ""
    assert "PAYMENT_DATE_MISSING" in e["blocker_codes"]


def test_duplicate_detection():
    a = ev(); b = ev()
    out, dup = dedupe_events([a, b])
    assert len(out) == 1 and dup == 1


def test_currency_missing_is_flagged():
    e = ev(currency="")
    assert "CURRENCY_MISSING" in e["blocker_codes"]
    assert e["currency"] == ""


def test_adr_ratio_unverified_blocks_final_dps():
    e = normalize_event(raw(), "ASML", "0000937966", "ADR", "ASML", "test", "ASML", "2026-11-05", adr_ratio_verified=False)
    assert "ADR_RATIO_UNVERIFIED" in e["blocker_codes"]
    assert e["verification_status"] == "DIVIDEND_PARTIAL_DATA"


def test_empty_source_is_not_non_payer():
    d = json.loads((OUT / "us_dividend_source_sample_p611.json").read_text(encoding="utf-8"))
    assert d["event_status_counts"]["SOURCE_UNAVAILABLE"] == 30
    assert d["confirmed"]["CONFIRMED_NON_PAYER"] == 0
    assert d["confirmed"]["DIVIDEND_STATUS_UNKNOWN"] == 30


def test_sec_filed_gate_and_cashfacts():
    rows = list(csv.DictReader(open(OUT / "us_dividend_sec_reconciliation_p611.csv", encoding="utf-8")))
    assert len(rows) == 30
    assert all(not r["sec_dividends_paid_filed"] or r["sec_dividends_paid_filed"] <= "2026-11-05" for r in rows)
    assert any(r["cross_check_status"] == "SEC_CASHFLOW_ONLY" for r in rows)


def test_no_per_share_sec_tag_in_panel():
    d = json.loads((OUT / "us_dividend_source_sample_p611.json").read_text(encoding="utf-8"))
    assert d["source_audit"]["sec_per_share_tags_in_map"] == []
    assert d["sec_evidence"]["per_share_fact_present"] == 0


def test_no_duplicate_issuer_in_sample():
    d = json.loads((OUT / "us_dividend_source_sample_p611.json").read_text(encoding="utf-8"))
    ciks = [x["cik"] for x in d["sample"]]
    assert len(ciks) == len(set(ciks)) == 30


def test_source_capability_is_unavailable():
    d = json.loads((OUT / "us_dividend_source_sample_p611.json").read_text(encoding="utf-8"))
    assert d["source_audit"]["has_stock_us_dividend_payout"] is False
    assert d["source_audit"]["has_stock_us_financial_indicator"] is False
    assert d["source_audit"]["source_status"] == "SOURCE_UNAVAILABLE"
