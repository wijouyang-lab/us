import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_1_pit_pilot"

def load(n):return json.loads((P/n).read_text())
def test_coverage_reconciles():
    rows=list(csv.DictReader((P/"coverage_reconciliation.csv").open()))
    d={r["metric"]:int(r["numerator"]) for r in rows}
    assert d["member_day_verified"]+d["unknown_member_day"]+d["quarantined_member_day"]==1095490
    assert d["quarantined_member_day"]==160
def test_sample_and_core():
    s=list(csv.DictReader((P/"pit_pilot_sample.csv").open()))
    assert len(s)==20
    assert sum(1 for r in s if r["survival_status"].startswith("NON_SURVIVING"))==5
    r=list(csv.DictReader((P/"pit_reconstruction_results.csv").open()))
    core={"Revenue","OperatingIncomeLoss","NetIncomeLoss","DilutedEPS","Assets","Equity","TotalDebt","OCF","Capex"}
    c=[x for x in r if x["metric"] in core]
    assert len(c)==638
    assert all(x["filed"]<=x["cutoff"] for x in c)
    assert all(x["pit_status"]=="PIT_DATE_PROXY" for x in c)
def test_partial_status():
    m=load("p10_6_1_manifest.json")
    assert m["post_run"]["status"]=="PIT_PILOT_PARTIAL"
    assert m["post_run"]["sample"]==20
