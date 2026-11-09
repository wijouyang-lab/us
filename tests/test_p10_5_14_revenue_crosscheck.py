import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_14_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_revenue_correction():
    rows=list(csv.DictReader((P/"aapl_revenue_8q.csv").open()))
    d={(r["fy"],r["quarter"]):float(r["value"]) for r in rows}
    assert d[("2019","Q2")]==58015
    assert d[("2019","Q3")]==53809
def test_40_match():
    rows=list(csv.DictReader((P/"aapl_40_secondary_crosscheck.csv").open()))
    assert len(rows)==40
    assert all(r["status"]=="SECONDARY_FILING_MATCH" for r in rows)
def test_context_gaps_and_not_ready():
    s=load("p10_5_14_status.json")
    assert s["status"]=="P10_5_14_PARTIAL"
    assert s["context_empty_cells"]>0
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
