import csv, json
from pathlib import Path
from tools.research.audit_six_styles_readiness_p64 import (
    classify_security, derive_quarter_from_ytd, industry_group, norm_ticker,
)
from tools.research.normalize_sec_companyfacts_p63 import next_weekday

OUT = Path("data/universe")


def base_q(): return {"match_status": "QUOTE_MATCHED", "quote_price": 10, "market_cap_raw": 1000}
def base_c():
    c = {"companyfacts_found": "True", "standard_facts": "True", "us_gaap_facts": "True", "ifrs_facts": "False"}
    for m in ("Revenue","NetIncome","EPSBasic","EPSDiluted","TotalAssets","StockholdersEquity",
              "OperatingCashFlow","CapitalExpenditure","CashAndCashEquivalents","LongTermDebt",
              "CommonSharesOutstanding","DividendsPaid"):
        c[m+"_any"] = "True"; c[m+"_recent"] = "True"
    return c
def base_p():
    return {"annual": {"NetIncome": 3, "Revenue": 3, "EPSBasic": 3},
            "metric_period": {"TotalAssets": {"INSTANT": 3}, "StockholdersEquity": {"INSTANT": 3}}}


def test_value_blocked_without_share_class_or_adr_ratio():
    r = classify_security(base_q(), base_c(), base_p(), "Information Technology")
    assert r["value_status"] == "DATA_QUALITY_PASS"
    assert r["value_input_ready"] is False
    assert "VALUE_SHARE_CLASS_OR_ADR_RATIO_UNVERIFIED" in r["blocker_codes"]


def test_ifrs_and_us_gaap_separate():
    c = base_c(); c["us_gaap_facts"] = "False"; c["ifrs_facts"] = "True"
    r = classify_security(base_q(), c, base_p(), "Industrials")
    assert r["accounting_standard"] == "IFRS"
    c2 = base_c(); c2["ifrs_facts"] = "True"
    assert classify_security(base_q(), c2, base_p(), "Industrials")["accounting_standard"] == "MIXED"


def test_ytd_difference_is_not_relabelled_as_quarter():
    assert derive_quarter_from_ytd(150, 100) == 50
    assert derive_quarter_from_ytd(100, None) is None
    q = base_q(); c = base_c(); p = base_p(); p["annual"] = {"NetIncome": 0, "Revenue": 0, "EPSBasic": 0}
    r = classify_security(q, c, p, "Information Technology")
    assert r["quality_status"] != "INPUT_READY"
    assert "QUALITY_HISTORY_INSUFFICIENT" in r["blocker_codes"]


def test_forward_eps_missing_keeps_garp_blocked():
    r = classify_security(base_q(), base_c(), base_p(), "Information Technology")
    assert r["historical_growth_ready"] is True
    assert r["forward_growth_ready"] is False
    assert "GARP_FORWARD_EPS_MISSING" in r["blocker_codes"]
    assert r["garp_status"] == "DATA_QUALITY_PASS"


def test_special_industry_not_forced_into_quality_model():
    r = classify_security(base_q(), base_c(), base_p(), "Financials")
    assert r["special_industry"] is True
    assert r["quality_status"] == "DATA_QUALITY_PASS"
    assert "QUALITY_SPECIAL_INDUSTRY_MODEL_NOT_READY" in r["blocker_codes"]


def test_missing_industry_cannot_become_quality_input_ready():
    r = classify_security(base_q(), base_c(), base_p(), "")
    assert r["industry_group"] == "INDUSTRY_CLASSIFICATION_MISSING"
    assert r["quality_status"] == "DATA_QUALITY_PASS"
    assert "QUALITY_INDUSTRY_MODEL_UNRESOLVED" in r["blocker_codes"]


def test_dividend_missing_is_not_confirmed_non_payer():
    c = base_c(); c["DividendsPaid_any"] = "False"; c["DividendsPaid_recent"] = "False"
    r = classify_security(base_q(), c, base_p(), "Information Technology")
    assert r["dividend_class"] == "DIVIDEND_DATA_MISSING"
    assert r["dividend_input_ready"] is False


def test_trend_and_options_never_ready_without_history():
    r = classify_security(base_q(), base_c(), base_p(), "Information Technology", historical_pass=False)
    assert r["current_quote_ready"] is True
    assert r["historical_price_ready"] is False
    assert r["pit_universe_ready"] is False
    assert r["trend_backtest_ready"] is False
    assert r["options_hedge_input_ready"] is False
    assert r["risk_control_input_ready"] is False


def test_pit_next_weekday_no_future_leak():
    assert next_weekday("2026-11-06") == "2026-11-09"
    assert next_weekday("2026-11-05") == "2026-11-06"


def test_shared_cik_can_share_fundamentals_but_quotes_stay_separate():
    a = classify_security({"match_status": "QUOTE_MATCHED", "quote_price": 10, "market_cap_raw": 1000},
                          base_c(), base_p(), "Information Technology")
    b = classify_security({"match_status": "INVALID_QUOTE", "quote_price": None, "market_cap_raw": None},
                          base_c(), base_p(), "Information Technology")
    assert a["companyfacts_found"] == b["companyfacts_found"]
    assert a["value_status"] != b["value_status"]


def test_actual_p64_counts_and_unclassified_separate():
    d = json.loads((OUT / "us_equity_style_coverage_p64.json").read_text())
    assert d["counts"]["target_records"] == 5502
    assert d["status_counts"]["value"]["INPUT_READY"] == 0
    assert d["status_counts"]["quality"]["INPUT_READY"] == 322
    assert d["status_counts"]["garp"]["INPUT_READY"] == 0
    assert d["status_counts"]["trend"]["INPUT_READY"] == 0
    assert d["status_counts"]["dividend"]["INPUT_READY"] == 0
    assert d["status_counts"]["hedge"]["INPUT_READY"] == 0
    assert d["score_ready"] == 0 and d["backtest_ready"] == 0
    assert d["unclassified_status_counts"]["quality"]["INPUT_READY"] == 0
