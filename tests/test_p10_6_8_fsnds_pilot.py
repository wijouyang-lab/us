import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_8_sec_fsnds_pilot"

def load(n):return json.loads((P/n).read_text())
def test_controls_scope():
    c=list(csv.DictReader((P/"fsnds_positive_control_reconciliation.csv").open()))
    a=list(csv.DictReader((P/"fsnds_ambiguous_context_reconciliation.csv").open()))
    assert len(c)==92
    assert all(r["status"]=="NOT_IN_FSNDS_SCOPE" for r in c)
    assert len(a)==34
    assert all(r["fsnds_status"]=="NOT_IN_FSNDS_SCOPE" for r in a)
def test_ibm_intc():
    rows=list(csv.DictReader((P/"fsnds_ibm_intc_2017.csv").open()))
    assert sum(1 for r in rows if r["ticker"]=="IBM")==4
    assert sum(1 for r in rows if r["ticker"]=="INTC")==4
    assert any(r["status"]=="SEC_FSND_DERIVED" for r in rows)
def test_hpq_and_panel():
    h=list(csv.DictReader((P/"fsnds_hpq_liabilities_validation.csv").open()))
    assert all(r["fsnds_status"].startswith("NOT_DOWNLOADED") for r in h)
    p=list(csv.DictReader((P/"fsnds_quality_five_company_panel.csv").open()))
    c={}
    for r in p:c[r["status"]]=c.get(r["status"],0)+1
    assert c["VALID"]==7 and c["PARTIAL"]==11
def test_partial():
    m=load("p10_6_8_manifest.json")
    assert m["post_run"]["status"]=="FSNDS_PILOT_PARTIAL"
