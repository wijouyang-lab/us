import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_12_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_72_and_units():
    rows=list(csv.DictReader((P/"aapl_two_fy_panel_final_v2.csv").open()))
    assert len(rows)==72
    assert all(r["unit"] in ("USD millions","USD/share") for r in rows)
def test_cashflow_zero_diff():
    rows=list(csv.DictReader((P/"aapl_cashflow_unit_check.csv").open()))
    assert len(rows)==24
    assert all(abs(float(r["diff"]))<1e-6 for r in rows)
def test_no_bad_accessions():
    s=load("p10_5_12_status.json")
    assert s["bad_accession_cells"]==0
    assert s["cashflow_max_abs_diff"]==0
def test_not_ready():
    s=load("p10_5_12_status.json")
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
