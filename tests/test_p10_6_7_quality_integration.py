import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_7_quality_integration"

def load(n):return json.loads((P/n).read_text())
def test_ibm_intc():
    rows=list(csv.DictReader((P/"ibm_intc_2017_quality_integration.csv").open()))
    assert sum(1 for r in rows if r["ticker"]=="IBM" and r["status"]=="FACT_LEVEL_VERIFIED")==4
    assert sum(1 for r in rows if r["ticker"]=="INTC" and r["status"]=="FACT_LEVEL_VERIFIED")==2
def test_hpq_liabilities():
    rows=list(csv.DictReader((P/"hpq_total_liabilities_final.csv").open()))
    assert len(rows)==2
    assert all(r["status"]=="DERIVED_FORMULA_VERIFIED" for r in rows)
    assert abs(float(rows[0]["total_liabilities"])-41505000000)<1
def test_unresolved_and_panel():
    u=list(csv.DictReader((P/"quality_unresolved_final_classification.csv").open()))
    assert len(u)==34
    p=list(csv.DictReader((P/"quality_five_company_panel_final.csv").open()))
    assert len(p)==20
    c={}
    for r in p:c[r["status"]]=c.get(r["status"],0)+1
    assert c["VALID"]==7 and c["PARTIAL"]==11 and c["NOT_APPLICABLE_AFTER_ACQUISITION"]==2
def test_repeat_and_partial():
    r=list(csv.DictReader((P/"quality_repeatability_final.csv").open()))[0]
    assert r["all_equal"]=="True"
    m=load("p10_6_7_manifest.json")
    assert m["post_run"]["status"]=="QUALITY_SLICE_PARTIAL"
