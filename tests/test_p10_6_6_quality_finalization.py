import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_6_quality_slice_finalization"

def load(n):return json.loads((P/n).read_text())
def test_reconciliation_92():
    rows=list(csv.DictReader((P/"quality_row_status_reconciliation.csv").open()))
    assert len(rows)==92
    c={}
    for r in rows:c[r["p65_status"]]=c.get(r["p65_status"],0)+1
    assert c["XBRL_CONTEXT_VERIFIED"]==46
    assert c["XBRL_CONTEXT_UNRESOLVED"]==34
    assert c["NOT_APPLICABLE_AFTER_ACQUISITION"]==10
    assert c["SOURCE_FILE_MISSING"]==2
def test_transitions_xlnx():
    rows=list(csv.DictReader((P/"quality_row_status_reconciliation.csv").open()))
    t=[r for r in rows if r["p46_status"]!=r["p65_status"]]
    assert len(t)==10
    assert all(r["ticker"]=="XLNX" for r in t)
    assert sum(1 for r in t if r["p46_status"]=="XBRL_CONTEXT_UNRESOLVED")==6
    assert sum(1 for r in t if r["p46_status"]=="XBRL_CONTEXT_VERIFIED")==4
def test_sources_and_repeat():
    s=list(csv.DictReader((P/"ibm_intc_source_recovery.csv").open()))
    assert all(r["status"]=="SOURCE_RECOVERED" for r in s)
    r=list(csv.DictReader((P/"quality_repeatability_comparison.csv").open()))[0]
    assert r["status"]=="PASS" and r["all_equal"]=="True"
def test_partial():
    m=load("p10_6_6_manifest.json")
    assert m["post_run"]["status"]=="QUALITY_SLICE_PARTIAL"
