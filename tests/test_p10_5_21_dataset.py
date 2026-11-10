import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"data/research/p10_5_21_aapl_dataset"

def load(n):return json.loads((P/n).read_text())
def test_72_and_types():
    s=load("p10_5_21_status.json")
    assert s["core_records"]==72
    assert s["direct_fact"]+s["reconstructed_cumulative"]+s["derived_formula"]+s["derived_annual_minus_9m"]+s["reconstructed_components"]==72
    assert s["direct_fact"]==48
    assert s["reconstructed_cumulative"]==12
    assert s["derived_formula"]==8
def test_legacy_and_gross():
    s=load("p10_5_21_status.json")
    assert s["legacy_rows"]==29 and s["legacy_mapped"]==29
    assert s["gross_margin_done"]==0 and s["gross_margin_unresolved"]==8
def test_manifest_and_repro():
    m=load("aapl_dataset_run_manifest.json")
    assert m["post_run"]["all_equal"] is True
    assert m["post_run"]["status"]=="CORE_DATASET_ACCEPTED"
    assert m["pre_run"]["mode"]=="PRE_RUN"
