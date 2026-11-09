import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_17_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_cashflow_24_exact():
    rows=list(csv.DictReader((P/"aapl_cashflow_quarterly_lineage_v7.csv").open()))
    assert len(rows)==8
    assert all(abs(float(r["diff_ocf"]))<1e-6 for r in rows)
    assert all(abs(float(r["diff_capex"]))<1e-6 for r in rows)
    assert all(abs(float(r["diff_fcf"]))<1e-6 for r in rows)
def test_inputs_periods():
    rows=list(csv.DictReader((P/"aapl_cashflow_fact_inputs_v7.csv").open()))
    assert len(rows)==16
    assert all(r["period_start"] and r["period_end"] for r in rows)
def test_html_40():
    rows=list(csv.DictReader((P/"aapl_40_html_note_crosscheck_v2.csv").open()))
    assert len(rows)==40
    assert all(r["table_index"] in ("84","85") for r in rows)
    assert all(r["status"]=="HTML_CELL_PARSED" for r in rows)
def test_not_ready():
    s=load("p10_5_17_status.json")
    assert s["status"]=="P10_5_17_PARTIAL"
    assert s["cashflow_exact"]==8
    assert s["html_locators"]==40
    assert s["context_gaps"]==43
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
