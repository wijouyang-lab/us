# -*- coding: utf-8 -*-
import json
from pathlib import Path
from tools.investment_research.dividend.sector_governance import (
    classify, evaluate, comparable, PROFILES, normalize_label)


def test_alias_normalization():
    assert normalize_label("  Regional  Banks ") == "regional banks"
    assert classify("X","Regional Banks")["classification"] == "BANK"
    assert classify("X","Life Insurance")["classification"] == "INSURANCE"
    assert classify("X","Property & Casualty Insurance")["classification"] == "INSURANCE"


def test_real_estate_is_not_automatically_reit():
    assert classify("X","Real Estate Services")["classification"] == "FINANCIAL_OTHER"
    assert classify("X","REIT")["classification"] == "REIT"


def test_unknown_industry_not_forced():
    assert classify("X","Unmapped")["classification"] == "UNKNOWN_INDUSTRY"


def test_bank_has_no_fcf_score_or_cet1_proxy():
    r=evaluate({}, "BANK")
    assert r["score"] is None and r["industry_model_status"]=="BANK_MODEL_NOT_READY"
    assert "CET1" in r["reason"] and "FCF" not in r.get("score_components",{})


def test_insurance_no_industrial_fcf():
    r=evaluate({}, "INSURANCE")
    assert r["score"] is None and r["industry_model_status"]=="INSURANCE_MODEL_NOT_READY"


def test_reit_requires_ffo():
    r=evaluate({}, "REIT")
    assert r["score"] is None and r["industry_model_status"]=="REIT_FFO_REQUIRED"
    assert r["reit_ffo_status"]=="DATA_BLOCKED" and r["reit_payout_status"]=="DATA_BLOCKED"


def test_nonfinancial_fixed_three_components():
    m={"net_income_payout":{"status":"OK","value":0.4},
       "fcf_dividend_coverage":{"status":"OK","value":2.0},"continuity_status":"OK"}
    r=evaluate(m,"NON_FINANCIAL")
    assert r["score"] is not None and r["score_denominator"]==3
    assert r["score_weights"]=={"payout":1/3,"fcf_coverage":1/3,"continuity":1/3}
    assert r["score_component_signature"]=="payout|fcf_coverage|continuity"


def test_missing_component_no_renormalization():
    m={"net_income_payout":{"status":"OK","value":0.4},"continuity_status":"OK"}
    r=evaluate(m,"NON_FINANCIAL")
    assert r["score"] is None and r["score_status"]=="NOT_READY"
    assert r["missing_components"]==["fcf_coverage"]


def test_profiles_not_comparable_across_signature():
    a={"score_version":"p46-1.0","score_profile_id":"A","score_component_signature":"x",
       "score_weights":{},"score_denominator":3}
    b={**a,"score_component_signature":"y"}
    assert not comparable(a,b)


def test_unknown_metric_values_preserved_when_not_ready():
    m={"net_income_payout":{"status":"OK","value":0.4}}
    r=evaluate(m,"NON_FINANCIAL")
    assert r["score"] is None and r["available_components"]["payout"]==0.4


def test_actual_28_industry_counts_and_no_network():
    d=json.loads(Path("data/research/dividend_quality_p46.json").read_text())
    assert len(d["tickers"])==28
    assert d["summary"]["industry_counts"]=={"NON_FINANCIAL":21,"INSURANCE":3,"BANK":2,"REIT":2}
    assert d["summary"]["score_ready"]==10
    assert d["summary"]["industry_model_not_ready"]==7


def rec(**kw):
    x={"score_status":"SCORE_READY","score":80.0,"score_version":"p46-1.0",
       "score_profile_id":"NON_FINANCIAL_DIVIDEND_V1",
       "score_component_signature":"payout|fcf_coverage|continuity",
       "score_weights":{"payout":1/3,"fcf_coverage":1/3,"continuity":1/3},
       "score_denominator":3,
       "available_components":{"payout":0.4,"fcf_coverage":2.0,"continuity":1.0},
       "component_scores":{"payout":0.8,"fcf_coverage":1.0,"continuity":1.0},
       "missing_components":[]}
    x.update(kw); return x


def test_comparable_empty_false():
    from tools.investment_research.dividend.sector_governance import comparable
    assert comparable({}, {}) is False


def test_comparable_not_ready_false():
    from tools.investment_research.dividend.sector_governance import comparable
    a=rec(score_status="NOT_READY", score=None)
    assert comparable(a,a) is False


def test_comparable_industry_model_false():
    from tools.investment_research.dividend.sector_governance import comparable
    a=rec(score_status="INDUSTRY_MODEL_NOT_READY", score=None)
    assert comparable(a,a) is False


def test_comparable_none_nan_inf_bool_false():
    from tools.investment_research.dividend.sector_governance import comparable
    import math
    for v in (None, float("nan"), float("inf"), True, False):
        assert comparable(rec(score=v),rec(score=v)) is False


def test_comparable_missing_component_false():
    from tools.investment_research.dividend.sector_governance import comparable
    a=rec(available_components={"payout":0.4,"fcf_coverage":2.0})
    assert comparable(a,rec()) is False


def test_comparable_weights_keys_mismatch_false():
    from tools.investment_research.dividend.sector_governance import comparable
    a=rec(score_weights={"payout":0.5,"fcf_coverage":0.5})
    assert comparable(a,rec()) is False


def test_comparable_weights_sum_false():
    from tools.investment_research.dividend.sector_governance import comparable
    a=rec(score_weights={"payout":0.5,"fcf_coverage":0.4,"continuity":0.4})
    assert comparable(a,rec()) is False


def test_comparable_denominator_false():
    from tools.investment_research.dividend.sector_governance import comparable
    assert comparable(rec(score_denominator=2),rec()) is False


def test_comparable_duplicate_signature_false():
    from tools.investment_research.dividend.sector_governance import comparable
    a=rec(score_component_signature="payout|payout|continuity")
    assert comparable(a,rec()) is False


def test_comparable_valid_true():
    from tools.investment_research.dividend.sector_governance import comparable
    assert comparable(rec(),rec()) is True


def test_comparable_profile_different_false():
    from tools.investment_research.dividend.sector_governance import comparable
    assert comparable(rec(),rec(score_profile_id="OTHER")) is False


def test_comparable_signature_different_false():
    from tools.investment_research.dividend.sector_governance import comparable
    a=rec(score_component_signature="payout|continuity|fcf_coverage",
          score_weights={"payout":1/3,"continuity":1/3,"fcf_coverage":1/3})
    assert comparable(a,rec()) is False


def test_comparable_weights_different_false():
    from tools.investment_research.dividend.sector_governance import comparable
    a=rec(score_weights={"payout":0.4,"fcf_coverage":0.3,"continuity":0.3})
    assert comparable(a,rec()) is False
