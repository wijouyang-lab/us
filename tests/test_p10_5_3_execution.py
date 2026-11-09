import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_3_execution_recovery"

def load(n):return json.loads((P/n).read_text())
def test_real_datasets_downloaded_and_parsed():
    rows=list(csv.DictReader((P/"aapl_quarterly_dataset_manifest.csv").open()))
    assert len(rows)==3
    assert {r["quarter"] for r in rows}=={"2009q2","2019q4","2024q1"}
    assert all(int(r["sub_rows"])>=0 and int(r["num_rows"])>=0 for r in rows)
    assert all(r["status"]=="PARSED" for r in rows)
def test_aapl_facts_and_amendments():
    rows=list(csv.DictReader((P/"aapl_historical_financial_facts.csv").open()))
    assert len(rows)>5000
    assert all(r["accession"] for r in rows)
    s=load("p10_5_3_status.json")
    assert s["status"]=="P10_5_3_PARTIAL"
    assert s["aapl_facts"]>5000
def test_edgar_search_was_actual():
    s=load("p10_5_3_status.json")["edgar_search"]
    assert s["attempted"] is True
    assert s["status"]==200
    assert s["bytes"]>1000
    assert s["preview"].startswith("{")
def test_blocked_p10_6_and_no_delisted_claim():
    s=load("p10_5_3_status.json")
    assert s["delisted_companies"]==0
    assert s["p10_6_allowed"] is False
    assert s["no_shadow"] is True
