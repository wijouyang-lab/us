import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_9_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_panel_grain_and_basis():
    p=list(csv.DictReader((P/"aapl_quarterly_panel_v3.csv").open()))
    assert len(p)==472
    assert all(r["grain_key"] for r in p)
    assert any(r["accounting_basis"]=="ORIGINAL_REPORTED" for r in p)
def test_fact_asof_20():
    rows=list(csv.DictReader((P/"aapl_fact_level_asof_tests.csv").open()))
    assert len(rows)==20
    assert all(r["pass"]=="True" for r in rows)
def test_two_fy_not_ready():
    s=load("p10_5_9_status.json")
    assert s["AAPL_FACT_PIT_READY"] is True
    assert s["AAPL_DATASET_READY"] is False
    assert s["HISTORICAL_UNIVERSE_READY"] is False
    assert s["p10_6_allowed"] is False
def test_form25_six_unresolved():
    u=list(csv.DictReader((P/"form25_nse_unresolved_final.csv").open()))
    assert len(u)==6
    assert all(r["security_type"]=="UNRESOLVED" for r in u)
