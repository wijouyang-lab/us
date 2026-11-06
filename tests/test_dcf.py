# -*- coding: utf-8 -*-
from tools.investment_research.value.dcf import DCFInputs, run


def test_positive_fcf_scenarios():
    r=run(DCFInputs(100, shares=10, net_debt=50))
    assert r["status"]=="OK"
    assert r["scenarios"]["base"]["value_per_share"] > 0
    assert r["label"].startswith("SCENARIO_ESTIMATE")


def test_negative_fcf_is_not_applicable():
    assert run(DCFInputs(-1))["status"]=="NOT_APPLICABLE"


def test_discount_must_exceed_terminal_growth():
    assert run(DCFInputs(100, discount_rate=0.02, terminal_growth=0.03))["status"]=="INSUFFICIENT_DATA"


def test_missing_shares_gives_no_per_share():
    r=run(DCFInputs(100, shares=None))
    assert r["scenarios"]["base"]["value_per_share"] is None


def test_sensitivity_tables_present():
    r=run(DCFInputs(100))
    assert len(r["sensitivity"]["discount_rate"]) >= 3
    assert len(r["sensitivity"]["terminal_growth"]) >= 3
    assert len(r["sensitivity"]["fcf_growth"]) == 3
