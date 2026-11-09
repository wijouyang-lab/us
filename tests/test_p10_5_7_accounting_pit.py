import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_7_accounting_pit"

def load(n):return json.loads((P/n).read_text())
def test_event_evidence():
    e=load("filing_evidence.json")
    assert e["retrospective_mention"] is True
    assert e["adoption_mention"] is True
    assert len(e["sha256"])==64
def test_asof_switches_on_date():
    rows=list(csv.DictReader((P/"apple_policy_adoption_asof_tests.csv").open()))
    assert len(rows)==20
    assert all(r["returned_accession"] for r in rows)
    early=[r for r in rows if r["query_date"]=="2009-10-28"]
    late=[r for r in rows if r["query_date"]=="2010-01-26"]
    assert all(r["returned_accession"]=="0001193125-09-214859" for r in early)
    assert all(r["returned_accession"]=="0001193125-10-012091" for r in late)
def test_panel_and_form25():
    p=list(csv.DictReader((P/"aapl_quarterly_panel_final.csv").open()))
    assert len(p)==472
    f=list(csv.DictReader((P/"form25_nse_45_final.csv").open()))
    assert len(f)==45
    assert sum(1 for r in f if r["final_classification"]=="UNRESOLVED")==6
def test_partial_not_p106():
    s=load("p10_5_7_status.json")
    assert s["status"]=="P10_5_7_PARTIAL"
    assert s["p10_6_allowed"] is False
    assert s["no_shadow"] is True
