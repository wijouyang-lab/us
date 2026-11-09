import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_10_aapl_cashflow"

def load(n):return json.loads((P/n).read_text())
def test_cashflow_matches_targets():
    rows=list(csv.DictReader((P/"aapl_cashflow_reconciliation.csv").open()))
    assert len(rows)==8
    assert all(abs(float(r["ocf_diff"]))<1e-6 and abs(float(r["capex_diff"]))<1e-6 and abs(float(r["fcf_diff"]))<1e-6 for r in rows)
def test_panel_72_cells():
    rows=list(csv.DictReader((P/"aapl_two_fy_panel_complete.csv").open()))
    assert len(rows)>=72
def test_not_ready():
    s=load("p10_5_10_status.json")
    assert s["status"]=="P10_5_10_PARTIAL"
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
    assert s["no_shadow"] is True
