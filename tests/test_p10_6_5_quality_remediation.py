import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_5_quality_pit_remediation"

def load(n):return json.loads((P/n).read_text())
def test_slice_counts():
    rows=list(csv.DictReader((P/"quality_context_resolution.csv").open()))
    c={}
    for r in rows:c[r["status"]]=c.get(r["status"],0)+1
    assert c["XBRL_CONTEXT_VERIFIED"]==46
    assert c["XBRL_CONTEXT_UNRESOLVED"]==34
    assert c["NOT_APPLICABLE_AFTER_ACQUISITION"]==10
    assert c["SOURCE_FILE_MISSING"]==2
def test_xlnx():
    rows=list(csv.DictReader((P/"xlnx_acquisition_lifecycle.csv").open()))
    assert any(r["event"]=="AMD-Xilinx acquisition closed" and r["event_date"]=="2022-02-14" for r in rows)
    assert sum(1 for r in rows if r.get("applicable")=="False")==2
def test_hpq_amendment():
    rows=list(csv.DictReader((P/"hpq_10k_original_vs_amended.csv").open()))
    d={r["metric"]:r for r in rows}
    assert float(d["NetIncomeLoss"]["difference"])==-71000000
    assert d["OCF"]["status"]=="UNCHANGED"
    assert d["Equity"]["status"]=="AMENDED_FACT"
def test_repeat_not_run_and_partial():
    r=list(csv.DictReader((P/"quality_repeatability_comparison.csv").open()))[0]
    assert r["status"]=="NOT_RUN"
    m=load("p10_6_5_manifest.json")
    assert m["post_run"]["status"]=="QUALITY_SLICE_PARTIAL"
