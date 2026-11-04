# -*- coding: utf-8 -*-
from pathlib import Path
from tools.investment_research.metrics import Snapshot
from tools.investment_research.sec.normalize import Fact
from tools.investment_research.dividend.dividend_quality import dividend_metrics


def F(c,v,s,e,unit="USD",filed="2026-05-01",acc="A"):
    return Fact("1","us-gaap",c,unit,v,s,e,filed,"10-K",acc)


def annual(year, dps=1.0, cash=100, ni=500, cfo=300, capex=50):
    s,e=f"{year}-01-01",f"{year}-12-31"
    return [F("CommonStockDividendsPerShareDeclared",dps,s,e,"USD/shares"),
            F("PaymentsOfDividendsCommonStock",cash,s,e),
            F("NetIncomeLoss",ni,s,e), F("NetCashProvidedByUsedInOperatingActivities",cfo,s,e),
            F("PaymentsToAcquirePropertyPlantAndEquipment",capex,s,e)]


def test_fy_dividend_vs_mismatched_ni_rejected():
    fs=[F("PaymentsOfDividendsCommonStock",100,"2025-01-01","2025-12-31"),
        F("NetIncomeLoss",400,"2024-07-01","2025-06-30")]
    m=dividend_metrics(Snapshot("X","1",fs))
    assert m["net_income_payout"]["status"] in ("PERIOD_MISMATCH","INSUFFICIENT_DATA")


def test_fy_dividend_vs_mismatched_fcf_rejected():
    fs=[F("PaymentsOfDividendsCommonStock",100,"2025-01-01","2025-12-31"),
        F("NetCashProvidedByUsedInOperatingActivities",200,"2024-01-01","2024-12-31"),
        F("PaymentsToAcquirePropertyPlantAndEquipment",10,"2024-01-01","2024-12-31")]
    m=dividend_metrics(Snapshot("X","1",fs))
    assert m["fcf_dividend_coverage"]["status"] in ("PERIOD_MISMATCH","DATA_BLOCKED")


def test_missing_fiscal_year_is_insufficient_history():
    fs=[]
    for y in [2020,2021,2022,2024,2025]: fs += annual(y,dps=1+y*0.01)
    m=dividend_metrics(Snapshot("X","1",fs))
    assert m["continuity_status"]=="INSUFFICIENT_HISTORY"
    assert m["dividend_continuity"] is False


def test_consecutive_growth_resets_after_decline():
    fs=[]
    for y,d in zip([2020,2021,2022,2023,2024,2025],[1.0,1.1,1.2,1.1,1.15,1.2]):
        fs += annual(y,dps=d)
    m=dividend_metrics(Snapshot("X","1",fs), split_basis_verified=True)
    assert m["consecutive_growth_years"]==2
    assert m["total_positive_growth_years"] >= 4


def test_missing_components_do_not_become_zero():
    m=dividend_metrics(Snapshot("X","1",annual(2025)))
    assert m["score_status"] in ("NOT_READY","SCORE_READY")
    assert all(v > 0 for v in m["score_components"].values())


def test_bank_does_not_use_fcf_component():
    fs=[]
    for y in [2020,2021,2022,2023,2024,2025]: fs += annual(y)
    m=dividend_metrics(Snapshot("X","1",fs), sector="Banking", split_basis_verified=True)
    assert "fcf_coverage" not in m["score_components"]
    assert m["score_status"]=="INDUSTRY_SPECIFIC_SCORE"


def test_unverified_split_blocks_cagr():
    fs=[]
    for y in [2020,2021,2022,2023,2024,2025]: fs += annual(y,dps=1+y*0.01)
    m=dividend_metrics(Snapshot("X","1",fs), split_basis_verified=False)
    assert m["dps_split_basis"]=="DPS_SPLIT_BASIS_UNVERIFIED"
    assert m["dps_cagr_5y"] is None


def test_actual_p41_old_new_comparison_is_present():
    import json
    d=json.loads(Path("data/research/dividend_quality_p41.json").read_text())
    assert len(d["tickers"])==28
    assert d["score_version"]=="dividend-score-2.0"
    assert d["tickers"]["AAPL"]["old_score"] is not None
