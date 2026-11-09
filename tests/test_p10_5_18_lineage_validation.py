import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_18_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_cashflow_inputs_and_values():
    rows=list(csv.DictReader((P/"aapl_cashflow_fact_inputs_v8.csv").open()))
    assert len(rows)==16
    q=list(csv.DictReader((P/"aapl_cashflow_quarterly_lineage_v8.csv").open()))
    assert len(q)==8
    assert all(abs(float(r["diff_ocf"]))<1e-6 for r in q)
def test_html_xbrl_40():
    rows=list(csv.DictReader((P/"aapl_40_html_xbrl_reconciliation_v3.csv").open()))
    assert len(rows)==40
    assert all(r["comparison_status"]=="MATCH" for r in rows)
def test_no_fake_verification():
    s=load("p10_5_18_status.json")
    assert s["core_cells"]==72
    assert s["fact_level_verified"]==0
    assert s["lineage_incomplete"]==72
    assert s["context_id_verified_in_instance"]==0
    assert s["gross_margin_pre_done"]==0
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
