import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_20_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_eight_instances():
    rows=list(csv.DictReader((P/"sec_instance_discovery_v2.csv").open()))
    assert len(rows)==8
    assert all(r["status"]=="INSTANCE_FOUND" for r in rows)
def test_cashflow_16_contexts():
    rows=list(csv.DictReader((P/"aapl_cashflow_fact_inputs_v10.csv").open()))
    assert len(rows)==16
    assert all(r["verified"]=="True" for r in rows)
    assert all(int(r["candidate_count"])==1 for r in rows)
def test_core_72_closed():
    rows=list(csv.DictReader((P/"aapl_core_panel_v10.csv").open()))
    assert len(rows)==72
    assert not any(r["lineage_status"]=="LINEAGE_INCOMPLETE" for r in rows)
    s=load("p10_5_20_status.json")
    assert s["fact_level_verified"]==44
    assert s["derived_lineage_verified"]==28
    assert s["lineage_incomplete"]==0
    assert s["cashflow_context_verified"]==16
    assert s["html_xbrl_match"]==40
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
