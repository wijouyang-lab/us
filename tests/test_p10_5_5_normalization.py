import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_5_financial_normalization"

def load(n):return json.loads((P/n).read_text())
def test_panel_and_q4():
    q=list(csv.DictReader((P/"aapl_normalized_quarterly_panel.csv").open()))
    assert len(q)>300
    assert {r["quarter"] for r in q}>={"Q1","Q2","Q3","Q4"}
    d=list(csv.DictReader((P/"aapl_qtd_ytd_derivation.csv").open()))
    assert len(d)>=2
def test_amendment_final():
    rows=list(csv.DictReader((P/"amendment_comparison_final.csv").open()))
    assert len(rows)==30
    assert all(r["final_status"] for r in rows)
    assert not any(r["final_status"]=="TRUE_NUMERIC_CHANGE_CANDIDATE" for r in rows)
def test_form25_subject_and_security():
    rows=list(csv.DictReader((P/"form25_nse_subject_audit.csv").open()))
    assert len(rows)==45
    assert all(r["subject_cik_guess"] for r in rows)
    assert all(r["security_type"] for r in rows)
def test_real_asof_and_manifest():
    rows=list(csv.DictReader((P/"real_asof_query_tests.csv").open()))
    assert len(rows)>=2
    assert all(r["returned_accession"] for r in rows)
    m=load("run_manifest.json")
    assert m["manifest_capture_mode"]=="PRE_RUN_PLUS_POST_RUN"
    assert m["outputs"]
def test_partial_not_p106():
    s=load("p10_5_5_status.json")
    assert s["status"]=="P10_5_5_PARTIAL"
    assert s["p10_6_allowed"] is False
    assert s["no_shadow"] is True
