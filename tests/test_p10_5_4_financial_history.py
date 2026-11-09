import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_4_financial_history"

def load(n):return json.loads((P/n).read_text())
def test_quarterly_and_derivation():
    rows=list(csv.DictReader((P/"aapl_quarterly_financials.csv").open()))
    assert len(rows)==9327
    assert any(r["duration"]=="QTD" for r in rows)
    der=list(csv.DictReader((P/"aapl_qtd_ytd_derivation.csv").open()))
    assert len(der)==2
def test_amendment_audit_has_classification():
    rows=list(csv.DictReader((P/"aapl_19_fact_differences_audit.csv").open()))
    assert len(rows)==30
    assert all(r["classification"] for r in rows)
    assert any(r["classification"]=="UNIT_MISMATCH" for r in rows)
def test_form25_is_filtered_not_3663():
    s=load("p10_5_4_status.json")
    assert s["form25_search_total"]==45
    assert s["form25_rows"]==45
    assert s["verified_common_stock_exits"]==0
def test_partial_not_p106():
    s=load("p10_5_4_status.json")
    assert s["status"]=="P10_5_4_PARTIAL"
    assert s["p10_6_allowed"] is False
    assert s["no_shadow"] is True
