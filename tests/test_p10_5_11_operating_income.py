import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_11_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_operating_income_8_quarters():
    rows=list(csv.DictReader((P/"aapl_operating_income_check.csv").open()))
    assert len(rows)==8
    assert all(abs(float(r["diff"]))<1e-6 for r in rows)
def test_72_cells_but_not_ready():
    p=list(csv.DictReader((P/"aapl_two_fy_panel_final.csv").open()))
    assert len(p)==72
    s=load("p10_5_11_status.json")
    assert s["status"]=="P10_5_11_PARTIAL"
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
