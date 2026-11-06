# -*- coding: utf-8 -*-
from datetime import datetime, timezone
import pytest
from tools.investment_research.metrics import analyze, Snapshot
from tools.investment_research.sec.normalize import Fact


def F(concept, value, start=None, end="2025-12-31", filed="2025-05-05", unit="USD",
      form="10-Q", acc="A", accepted=None, quality="FILED_DATE_ONLY", first=None):
    return Fact("1", "us-gaap", concept, unit, value, start, end, filed, form, acc,
                accepted_at=accepted, availability_quality=quality, first_seen_at=first)


def flows(concept, values, unit="USD", filed="2025-05-05", accepted=None, quality="FILED_DATE_ONLY"):
    periods=[("2025-01-01","2025-03-31"),("2025-04-01","2025-06-30"),
             ("2025-07-01","2025-09-30"),("2025-10-01","2025-12-31")]
    return [F(concept,v,s,e,filed,unit=unit,acc=f"Q{i}",accepted=accepted,quality=quality) for i,((s,e),v) in enumerate(zip(periods,values))]


def test_same_day_intraday_acceptance_is_not_leaked():
    f=F("RevenueFromContractWithCustomerExcludingAssessedTax",100,"2025-01-01","2025-03-31",
        accepted="2025-05-05T20:00:00Z",quality="ACCEPTANCE_ESTIMATE")
    early=Snapshot("X","1",[f],as_of="2025-05-05T16:00:00Z").available()
    late=Snapshot("X","1",[f],as_of="2025-05-05T21:00:00Z").available()
    assert early == [] and len(late) == 1


def test_filed_date_only_excluded_same_day():
    f=F("RevenueFromContractWithCustomerExcludingAssessedTax",100,"2025-01-01","2025-03-31")
    assert Snapshot("X","1",[f],as_of="2025-05-05T16:00:00Z").available() == []
    assert len(Snapshot("X","1",[f],as_of="2025-05-06T16:00:00Z").available()) == 1


def test_observed_first_seen_controls_exact_time():
    f=F("RevenueFromContractWithCustomerExcludingAssessedTax",100,"2025-01-01","2025-03-31",
        quality="OBSERVED_FIRST_SEEN",first="2025-05-06T12:00:00Z")
    assert Snapshot("X","1",[f],as_of="2025-05-06T11:00:00Z").available() == []
    assert len(Snapshot("X","1",[f],as_of="2025-05-06T13:00:00Z").available()) == 1


def test_ttm_requires_contiguous_quarters():
    rev=flows("RevenueFromContractWithCustomerExcludingAssessedTax",[100,110,120,130])
    # remove Q3, no annual -> no TTM
    rev=[x for x in rev if x.end != "2025-09-30"]
    a=analyze("X","1",rev,as_of="2026-01-01")
    assert a["value"]["revenue"]["status"]=="INSUFFICIENT_DATA"


def test_roe_uses_average_equity():
    fs=flows("NetIncomeLoss",[10,10,10,10])+flows("RevenueFromContractWithCustomerExcludingAssessedTax",[100]*4)
    fs += [F("StockholdersEquity",100,None,"2025-01-01"), F("StockholdersEquity",200,None,"2025-12-31")]
    a=analyze("X","1",fs,as_of="2026-01-01")
    assert a["quality"]["roe"]["status"]=="OK"
    assert a["quality"]["roe"]["value"] == pytest.approx(40/150)


def test_ev_blocks_when_cash_missing():
    fs=flows("NetIncomeLoss",[10]*4)+flows("RevenueFromContractWithCustomerExcludingAssessedTax",[100]*4)
    fs += [F("StockholdersEquity",100,None,"2025-12-31"),F("LongTermDebt",50,None,"2025-12-31")]
    q={"price":10,"currency":"USD","price_type":"LAST","timestamp":"2025-12-31T20:00:00Z","source":"T","license_status":"AUTHORIZED"}
    sh={"shares":10,"observation_date":"2025-12-31","available_at":"2025-12-31","source":"T"}
    a=analyze("X","1",fs,as_of="2026-01-01",market_quote=q,share_count=sh)
    assert a["value"]["enterprise_value"]["status"]=="INSUFFICIENT_DATA"
    assert "cash" in a["value"]["enterprise_value"]["missing_reason"]


def test_roic_and_interest_coverage_with_consistent_periods():
    fs=flows("RevenueFromContractWithCustomerExcludingAssessedTax",[100]*4)
    fs+=flows("OperatingIncomeLoss",[20]*4)+flows("IncomeTaxExpenseBenefit",[4]*4)
    fs+=flows("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems",[20]*4)
    fs+=flows("InterestExpense",[2]*4)
    fs += [F("StockholdersEquity",100,None,"2025-01-01"),F("StockholdersEquity",100,None,"2025-12-31"),
           F("CashAndCashEquivalentsAtCarryingValue",20,None,"2025-01-01"),
           F("CashAndCashEquivalentsAtCarryingValue",20,None,"2025-12-31"),
           F("LongTermDebt",50,None,"2025-01-01"),
           F("LongTermDebt",50,None,"2025-12-31")]
    a=analyze("X","1",fs,as_of="2026-01-01")
    assert a["quality"]["roic"]["status"]=="OK"
    assert a["quality"]["interest_coverage"]["value"] == pytest.approx(10)
    assert len(a["quality"]["roic"]["input_facts"]) >= 6


def test_garp_operating_leverage_ratio_and_margin_expansion():
    fs=[]; fs+=flows("OperatingIncomeLoss",[10]*4)
    # annual facts for growth
    fs += [F("RevenueFromContractWithCustomerExcludingAssessedTax",100,"2024-01-01","2024-12-31",form="10-K",acc="Y1"),
           F("RevenueFromContractWithCustomerExcludingAssessedTax",120,"2025-01-01","2025-12-31",form="10-K",acc="Y2"),
           F("OperatingIncomeLoss",10,"2024-01-01","2024-12-31",form="10-K",acc="Y1"),
           F("OperatingIncomeLoss",18,"2025-01-01","2025-12-31",form="10-K",acc="Y2")]
    a=analyze("X","1",fs,as_of="2026-01-01")
    assert a["garp"]["operating_leverage_ratio"]["status"]=="OK"
    assert a["garp"]["operating_margin_expansion"]["status"]=="OK"
    assert "operating_leverage" not in a["garp"] or a["garp"]["operating_leverage"]["metric"] == "operating_margin_expansion"


def test_debt_total_does_not_double_count_current_portion():
    from tools.investment_research.metrics import _total_debt
    fs=[F("LongTermDebt",50,None,"2025-12-31"),F("LongTermDebtCurrent",10,None,"2025-12-31"),
        F("ShortTermBorrowings",5,None,"2025-12-31")]
    d=_total_debt(Snapshot("X","1",fs), "2025-12-31")
    assert d["value"] == 55
    assert "not added" in d["debt_rule"]


def test_stability_requires_five_years():
    fs=[]
    for y in range(2021,2025):
        fs.append(F("RevenueFromContractWithCustomerExcludingAssessedTax",100,f"{y}-01-01",f"{y}-12-31",form="10-K"))
    a=analyze("X","1",fs,as_of="2026-01-01")
    assert a["quality"]["revenue_stability"]["status"]=="INSUFFICIENT_DATA"


def test_garp_zero_revenue_base_is_not_a_percentage():
    fs=[F("RevenueFromContractWithCustomerExcludingAssessedTax",0,"2024-01-01","2024-12-31",form="10-K"),
        F("RevenueFromContractWithCustomerExcludingAssessedTax",100,"2025-01-01","2025-12-31",form="10-K")]
    a=analyze("X","1",fs,as_of="2026-01-01")
    assert a["garp"]["revenue_growth"]["status"]=="NOT_APPLICABLE"


def test_roic_rejects_mismatched_tax_period():
    fs=flows("RevenueFromContractWithCustomerExcludingAssessedTax",[100]*4)
    fs+=flows("OperatingIncomeLoss",[20]*4)
    # tax covers only 9 months, pretax 12 months
    fs += [F("IncomeTaxExpenseBenefit",3,"2025-01-01","2025-09-30"),
           F("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems",20,"2025-01-01","2025-12-31")]
    a=analyze("X","1",fs,as_of="2026-01-01")
    assert a["quality"]["roic"]["status"]=="INSUFFICIENT_DATA"


def test_net_debt_and_ebitda_include_debt_cash_facts():
    fs=flows("OperatingIncomeLoss",[20]*4)+flows("DepreciationDepletionAndAmortization",[5]*4)
    fs += [F("StockholdersEquity",100,None,"2025-12-31"),F("CashAndCashEquivalentsAtCarryingValue",20,None,"2025-12-31"),
           F("LongTermDebt",50,None,"2025-12-31")]
    a=analyze("X","1",fs,as_of="2026-01-01")
    nd=a["value"]["net_debt"]
    assert nd["status"]=="OK"
    assert {x["concept"] for x in nd["input_facts"]} >= {"LongTermDebt","CashAndCashEquivalentsAtCarryingValue"}
    ne=a["quality"]["net_debt_to_ebitda"]
    assert ne["status"]=="OK"
    assert {x["concept"] for x in ne["input_facts"]} >= {"LongTermDebt","CashAndCashEquivalentsAtCarryingValue",
                                                          "OperatingIncomeLoss","DepreciationDepletionAndAmortization"}


def test_stability_rejects_gapped_fiscal_years():
    fs=[]
    for y in [2019,2020,2021,2022,2024]:
        fs.append(F("RevenueFromContractWithCustomerExcludingAssessedTax",100,f"{y}-01-01",f"{y}-12-31",form="10-K"))
    a=analyze("X","1",fs,as_of="2026-01-01")
    assert a["quality"]["revenue_stability"]["status"]=="INSUFFICIENT_DATA"


def test_zero_revenue_growth_blocks_ratio_not_margin_expansion():
    fs=[F("RevenueFromContractWithCustomerExcludingAssessedTax",100,"2024-01-01","2024-12-31",form="10-K"),
        F("RevenueFromContractWithCustomerExcludingAssessedTax",100,"2025-01-01","2025-12-31",form="10-K"),
        F("OperatingIncomeLoss",10,"2024-01-01","2024-12-31",form="10-K"),
        F("OperatingIncomeLoss",12,"2025-01-01","2025-12-31",form="10-K")]
    a=analyze("X","1",fs,as_of="2026-01-01")
    assert a["garp"]["operating_leverage_ratio"]["status"]=="NOT_APPLICABLE"
    assert a["garp"]["operating_margin_expansion"]["status"]=="OK"
