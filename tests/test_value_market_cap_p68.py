import csv, json
from pathlib import Path

OUT = Path("data/universe")


def rows():
    return list(csv.DictReader(open(OUT / "value_v1_readiness_p68.csv", encoding="utf-8")))


def audit():
    return json.load(open(OUT / "value_market_cap_audit_p68.json", encoding="utf-8"))


def test_market_cap_counts_and_units():
    d = audit(); rs = rows()
    assert d["market_cap"]["present"] == 5437
    assert d["market_cap"]["validated"] == 3685
    assert d["market_cap"]["status_counts"]["ADR_MARKET_CAP_UNVERIFIED"] == 314
    assert all(float(r["market_cap_raw"]) > 0 for r in rs if r["market_cap_raw"])


def test_same_cik_does_not_create_duplicate_issuer_count():
    d = audit()
    assert d["pool"]["target_records"] == 5502
    assert d["pool"]["target_unique_ciks"] == 5452
    assert d["market_cap"]["multi_ticker_ciks"] == 45


def test_multi_class_is_not_treated_as_validated():
    rs = rows()
    multi = [r for r in rs if int(r["cik_ticker_count"]) > 1]
    assert multi
    assert all(r["market_cap_validated"] == "False" for r in multi)
    assert all(r["market_cap_status"] != "ISSUER_MARKET_CAP_VALIDATED" for r in multi)


def test_adr_never_gets_validated_market_cap_or_value_ready():
    rs = [r for r in rows() if r["security_type"] == "ADR"]
    assert len(rs) == 315
    assert all(r["market_cap_validated"] == "False" for r in rs)
    assert all(r["value_v1_status"] != "VALUE_V1_DATA_READY" for r in rs)


def test_negative_earnings_preserve_negative_yield_and_pe_blocked():
    rs = rows()
    losses = [r for r in rs if r["net_income"] and float(r["net_income"]) < 0 and r["earnings_yield"]]
    assert losses
    assert any(float(r["earnings_yield"]) < 0 for r in losses)
    assert all(r["pe_derived"] == "" for r in losses)


def test_fcf_missing_capex_is_not_zero():
    rs = rows()
    blocked = [r for r in rs if r["operating_cash_flow"] and not r["capital_expenditure"]]
    assert blocked
    assert all(r["free_cash_flow"] == "" for r in blocked)


def test_ev_ebitda_is_blocked_without_da():
    d = audit(); rs = rows()
    assert d["ev_ebitda_ready"] == 0
    assert all(r["ev_ebitda"] == "" for r in rs)
    assert all(r["ev_ebitda_status"] == "EV_DATA_INCOMPLETE" for r in rs)


def test_accounting_and_special_models_are_separate():
    d = audit()
    assert d["by_accounting"]["IFRS"]["value_data_ready"] > 0
    assert d["by_accounting"]["MIXED"]["value_data_ready"] == 0
    assert d["by_accounting"]["NONE"]["value_data_ready"] == 0
    assert d["by_family"]["BANKS"]["value_data_ready"] == 0
    assert d["by_family"]["REIT"]["value_data_ready"] == 0


def test_actual_value_readiness_counts():
    d = audit()
    assert d["value_status_counts"]["VALUE_V1_DATA_READY"] == 2529
    assert d["value_status_counts"]["VALUE_SPECIAL_MODEL_REQUIRED"] == 1320
    assert d["pe_provider_mismatch_gt_20pct"] == 1108
    assert d["pe_comparable"] == 2035
