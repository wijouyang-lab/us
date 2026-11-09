import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_13_aapl_panel"

def load(n):return json.loads((P/n).read_text())
def test_72_and_units():
    rows=list(csv.DictReader((P/"aapl_two_fy_panel_final_v3.csv").open()))
    assert len(rows)==72
    assert all(r["unit"] in ("USD millions","USD/share") for r in rows)
    assert all(r["provenance_status"]=="TRACEABLE" for r in rows)
def test_recovered_targets():
    rows=list(csv.DictReader((P/"aapl_two_fy_panel_final_v3.csv").open()))
    want={("2018","Q1","Revenue"):88293,("2018","Q4","Revenue"):62900,("2018","Q4","OperatingIncomeLoss"):16118,("2019","Q4","Revenue"):64040,("2019","Q4","GrossProfit"):24313,("2019","Q4","OperatingIncomeLoss"):15625,("2019","Q4","NetIncomeLoss"):13686,("2019","Q4","EarningsPerShareBasic"):3.05,("2019","Q4","EarningsPerShareDiluted"):3.03}
    got={(r["fy"],r["quarter"],r["field"]):float(r["value"]) for r in rows}
    for k,v in want.items():assert abs(got[k]-v)<1e-6,k
def test_cashflow_and_status():
    s=load("p10_5_13_status.json")
    assert s["panel_cells"]==72
    assert s["unresolved_cells"]==0
    assert s["dimension_contaminated_cells"]==0
    assert s["unit_failures"]==0
    assert s["bad_accession_cells"]==0
    assert s["independently_verified_cells"]==32
    assert s["AAPL_DATASET_READY"] is False
    assert s["p10_6_allowed"] is False
