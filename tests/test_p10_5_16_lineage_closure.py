import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_16_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_eps_from_facts():
    rows=list(csv.DictReader((P/"aapl_annual_eps_reconciliation_v2.csv").open()))
    assert len(rows)==2
    assert all(r["status"]=="PASS" for r in rows)
    assert abs(float(rows[0]["basic_round"])-12.01)<1e-9
    assert abs(float(rows[1]["diluted_round"])-11.89)<1e-9
def test_input_facts_count():
    rows=list(csv.DictReader((P/"aapl_annual_eps_input_facts.csv").open()))
    assert len(rows)==10
def test_context_gaps_not_hidden():
    s=load("p10_5_16_status.json")
    assert s["status"]=="P10_5_16_PARTIAL"
    assert s["context_gaps"]==43
    assert s["fact_level_traceable"]==29
    assert s["html_note_locators"]==0
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
