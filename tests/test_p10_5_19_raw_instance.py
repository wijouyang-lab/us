import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_19_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_cashflow_contexts():
    rows=list(csv.DictReader((P/"aapl_cashflow_fact_inputs_v9.csv").open()))
    assert len(rows)==16
    assert sum(1 for r in rows if r["context_verified"]=="True")==6
    assert all(r["period_start"] and r["period_end"] for r in rows)
def test_24_exact():
    rows=list(csv.DictReader((P/"aapl_cashflow_quarterly_lineage_v9.csv").open()))
    assert len(rows)==8
    assert all(abs(float(r["diff_ocf"]))<1e-6 for r in rows)
    assert all(abs(float(r["diff_capex"]))<1e-6 for r in rows)
def test_no_fake_core_verified():
    s=load("p10_5_19_status.json")
    assert s["fact_level_verified"]==0
    assert s["lineage_incomplete"]==72
    assert s["cashflow_context_verified"]==6
    assert s["html_xbrl_match"]==40
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
