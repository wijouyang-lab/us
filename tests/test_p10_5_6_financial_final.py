import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_6_financial_final"

def load(n):return json.loads((P/n).read_text())
def test_units_and_amendment():
    rows=list(csv.DictReader((P/"amendment_comparison_final_v2.csv").open()))
    assert len(rows)==30
    assert sum(1 for r in rows if r["final_status"]=="TRUE_NUMERIC_CHANGE_CANDIDATE")==13
    assert sum(1 for r in rows if r["final_status"]=="NORMALIZED_EQUAL")==11
    assert sum(1 for r in rows if r["final_status"]=="DUPLICATE_FACT")==6
def test_real_asof_before_after():
    rows=list(csv.DictReader((P/"real_asof_query_tests.csv").open()))
    assert len(rows)==26
    before=[r for r in rows if r["expected"]=="BEFORE_AMENDMENT"]
    after=[r for r in rows if r["expected"]=="AFTER_AMENDMENT"]
    assert all(r["returned_accession"] for r in rows)
    assert len(before)==13 and len(after)==13
def test_form25_not_common():
    rows=list(csv.DictReader((P/"form25_nse_45_final.csv").open()))
    assert len(rows)==45
    assert sum(1 for r in rows if r["final_classification"]=="UNRESOLVED")==6
    assert all(r["final_classification"]!="COMMON_STOCK" for r in rows)
def test_partial_not_p106():
    s=load("p10_5_6_status.json")
    assert s["status"]=="P10_5_6_PARTIAL"
    assert s["p10_6_allowed"] is False
    assert s["no_shadow"] is True
