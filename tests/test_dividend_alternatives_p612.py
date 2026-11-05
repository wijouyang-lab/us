import csv, json
from pathlib import Path
from tools.research.normalize_dividend_sources_p612 import standard_event, stop_after_status

OUT = Path("data/universe")


def ev(**kw):
    d = dict(ticker="CSCO", cik="0000858877", security_type="COMMON", source="NASDAQ_DIVIDEND_HISTORY",
             source_symbol="CSCO", announcement_date="08/12/2026", ex_dividend_date="10/02/2026",
             record_date="10/02/2026", payment_date="10/21/2026", dps="0.42", currency="USD",
             dividend_type="REGULAR_CASH", frequency="", source_url="https://www.nasdaq.com/",
             as_of="2026-11-06", retrieved_at="2026-11-06T00:00:00Z", raw_payload={"x": 1},
             split_adjustment="NOT_SPLIT_ADJUSTED")
    d.update(kw); return standard_event(**d)


def test_date_fields_map_independently():
    e = ev()
    assert e["announcement_date"] == "2026-08-12"
    assert e["ex_dividend_date"] == "2026-10-02"
    assert e["payment_date"] == "2026-10-21"


def test_dps_not_total_cash_paid():
    e = ev()
    assert e["dps"] == "0.42"
    assert "total" not in e


def test_special_cash_is_classified():
    assert ev(dividend_type="SPECIAL_CASH")["dividend_type"] == "SPECIAL_CASH"


def test_empty_values_remain_partial_not_ready():
    e = ev(payment_date="", announcement_date="", currency="")
    assert e["payment_date"] == ""
    assert e["verification_status"] == "PARTIAL_EVENT"


def test_adr_ratio_missing_blocks_final_dps():
    e = ev(security_type="ADR", ticker="ASML", adr_ratio_verified=False)
    assert "ADR_RATIO_UNVERIFIED" in e["blocker_codes"]


def test_currency_missing_not_assumed_usd():
    e = ev(currency="")
    assert e["currency"] == ""
    assert "CURRENCY_MISSING" in e["blocker_codes"]


def test_source_identity_and_hash_preserved():
    e = ev()
    assert e["source"] == "NASDAQ_DIVIDEND_HISTORY"
    assert len(e["raw_payload_hash"]) == 64
    assert e["source_url"]


def test_429_stops_source():
    assert stop_after_status(429) is True
    assert stop_after_status(200) is False


def test_yahoo_and_nasdaq_adjustment_are_separate():
    rows = list(csv.DictReader(open(OUT / "dividend_alternative_events_p612.csv", encoding="utf-8")))
    y = [r for r in rows if r["source"] == "YAHOO_FINANCE"]
    n = [r for r in rows if r["source"] == "NASDAQ_DIVIDEND_HISTORY"]
    assert y and set(r["split_adjustment"] for r in y) == {"YAHOO_SPLIT_ADJUSTED_HISTORY"}
    assert n and set(r["split_adjustment"] for r in n) == {"NOT_SPLIT_ADJUSTED_PER_NASDAQ"}


def test_empty_response_is_unknown_not_nonpayer():
    d = json.load(open(OUT / "dividend_alternative_source_results_p612.json", encoding="utf-8"))
    assert d["decision"]["FULL_MARKET_A"] is False
    assert d["source_capability"]["SMARTERDIVIDENDS"]["ADR_DIVIDEND_READY"] is False


def test_actual_source_counts():
    d = json.load(open(OUT / "dividend_alternative_source_results_p612.json", encoding="utf-8"))
    c = d["source_capability"]
    assert c["SMARTERDIVIDENDS"]["attempted"] == 30
    assert c["SMARTERDIVIDENDS"]["tickers_with_events"] == 26
    assert c["YAHOO_FINANCE"]["tickers_with_events"] == 26
    assert c["NASDAQ_DIVIDEND_HISTORY"]["attempted"] == 13
    assert c["NASDAQ_DIVIDEND_HISTORY"]["tickers_with_events"] == 9
    assert d["metadata"]["requests"] == {"SMARTERDIVIDENDS": 30, "YAHOO_FINANCE": 30, "NASDAQ_DIVIDEND_HISTORY": 13}


def test_no_preferred_common_mix_in_nasdaq_rows():
    rows = [r for r in csv.DictReader(open(OUT / "dividend_alternative_events_p612.csv", encoding="utf-8"))
            if r["source"] == "NASDAQ_DIVIDEND_HISTORY"]
    assert all(r["dividend_type"] in ("REGULAR_CASH","SPECIAL_CASH","OTHER") for r in rows)
