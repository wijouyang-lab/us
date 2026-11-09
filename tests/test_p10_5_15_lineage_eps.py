import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_15_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_40_secondary_match():
    rows=list(csv.DictReader((P/"aapl_40_secondary_v5.csv").open()))
    assert len(rows)==40
    assert all(r["status"]=="SECONDARY_FILING_MATCH" for r in rows)
def test_annual_eps():
    rows=list(csv.DictReader((P/"aapl_annual_eps_reconciliation.csv").open()))
    assert len(rows)==2
    assert all(r["status"]=="PASS" for r in rows)
def test_revenue_raw_components():
    rows=list(csv.DictReader((P/"aapl_core_panel_v5.csv").open()))
    d={(r["fy"],r["quarter"],r["field"]):r for r in rows}
    for q,prod,svc,total in (("Q2","46565","11450","58015"),("Q3","42354","11455","53809")):
        r=d[("2019",q,"Revenue")]
        assert float(r["value"])==float(total)
        assert float(r["raw_value"])==float(total)*1e6
        assert float(r["products_value"])==float(prod)
        assert float(r["services_value"])==float(svc)
def test_not_ready():
    s=load("p10_5_15_status.json")
    assert s["status"]=="P10_5_15_PARTIAL"
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
