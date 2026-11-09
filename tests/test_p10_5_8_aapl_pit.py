import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_8_aapl_pit"

def load(n):return json.loads((P/n).read_text())
def test_63_availability_and_no_lookahead():
    a=list(csv.DictReader((P/"aapl_63_accession_availability_final.csv").open()))
    n=list(csv.DictReader((P/"aapl_63_accession_no_lookahead_final.csv").open()))
    assert len(a)==63
    assert len(n)==63
    assert all(r["status"]=="PASS" for r in n)
def test_panel_grain_and_fy2008():
    p=list(csv.DictReader((P/"aapl_quarterly_panel_v2.csv").open()))
    assert len(p)==472
    assert all(r["accounting_version"] for r in p)
    v=list(csv.DictReader((P/"apple_accounting_versioned_facts.csv").open()))
    assert len(v)==13
def test_form25_unresolved():
    u=list(csv.DictReader((P/"form25_nse_unresolved_resolution.csv").open()))
    assert len(u)==6
    assert all(r["resolution"] for r in u)
def test_partial_not_p106():
    s=load("p10_5_8_status.json")
    assert s["status"]=="P10_5_8_PARTIAL"
    assert s["p10_6_allowed"] is False
    assert s["no_shadow"] is True
