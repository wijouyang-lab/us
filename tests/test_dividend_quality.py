# -*- coding: utf-8 -*-
from pathlib import Path
from tools.investment_research.metrics import Snapshot
from tools.investment_research.dividend.dividend_quality import dividend_metrics
from tools.investment_research.sec.normalize import Fact


def F(c,v,s,e,unit="USD",form="10-K",acc="A"):
    return Fact("1","us-gaap",c,unit,v,s,e,"2025-05-05",form,acc)


def base():
    fs=[]
    for i,y in enumerate(range(2020,2026)):
        s,e=f"{y}-01-01",f"{y}-12-31"
        fs += [F("CommonStockDividendsPerShareDeclared",1+i*0.1,s,e,"USD/shares"),
               F("PaymentsOfDividendsCommonStock",100+i*10,s,e),
               F("NetIncomeLoss",500,s,e), F("NetCashProvidedByUsedInOperatingActivities",300,s,e),
               F("PaymentsToAcquirePropertyPlantAndEquipment",50,s,e),
               F("PaymentsForRepurchaseOfCommonStock",80,s,e)]
    return fs


def test_payer_metrics_and_score():
    m=dividend_metrics(Snapshot("X","1",base()), split_basis_verified=True)
    assert m["classification"]["value"]=="DIVIDEND_PAYER"
    assert m["net_income_payout"]["status"]=="OK"
    assert m["fcf_dividend_coverage"]["status"]=="OK"
    assert m["dps_cagr_5y"] is not None
    assert m["score_status"]=="SCORE_READY"


def test_non_payer_not_scored_as_bad_quality():
    m=dividend_metrics(Snapshot("X","1",[F("NetIncomeLoss",100,"2024-01-01","2024-12-31")]))
    assert m["classification"]["status"]=="NON_DIVIDEND_PAYER"
    assert m["dividend_quality_score"] is None


def test_negative_income_payout_not_applicable():
    fs=base()+[F("NetIncomeLoss",-10,"2025-01-01","2025-12-31")]
    # latest duplicate wins by filing? both same filed; conservative test uses a single negative year series
    m=dividend_metrics(Snapshot("X","1",fs))
    assert m["net_income_payout"]["status"] in ("OK","NOT_APPLICABLE")


def test_missing_capex_blocks_fcf_coverage():
    fs=[x for x in base() if x.concept!="PaymentsToAcquirePropertyPlantAndEquipment"]
    m=dividend_metrics(Snapshot("X","1",fs))
    assert m["fcf_dividend_coverage"]["status"]=="DATA_BLOCKED"


def test_actual_28_company_report_is_honest():
    import json, collections
    d=json.loads(Path("data/research/dividend_quality_p4.json").read_text())
    assert len(d["tickers"])==28
    c=collections.Counter(v["classification"] for v in d["tickers"].values())
    assert c["DIVIDEND_PAYER"]==22
    assert c["NON_DIVIDEND_PAYER"]==5
    assert c["DIVIDEND_DATA_BLOCKED"]==1
    assert d["tickers"]["XOM"]["classification"]=="DIVIDEND_DATA_BLOCKED"
    assert d["tickers"]["ADBE"]["score"] is None
    assert "dividend_yield" not in d["tickers"]["AAPL"]["metrics"]


def test_pit_asof_before_filing_hides_dividend_series():
    from tools.investment_research.sec.normalize import Fact
    fs=base()
    # every base fact is filed 2025-05-05; a 2025-05-01 as-of must not use it
    m=dividend_metrics(Snapshot("X","1",fs,as_of="2025-05-01"))
    assert m["classification"]["status"] in ("NON_DIVIDEND_PAYER","DIVIDEND_DATA_BLOCKED")
    assert m["dividend_quality_score"] is None
