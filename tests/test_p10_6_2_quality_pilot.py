import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_2_quality_pilot"

def load(n):return json.loads((P/n).read_text())
def test_panel_and_scores():
    p=list(csv.DictReader((P/"quality_historical_panel.csv").open()))
    s=list(csv.DictReader((P/"quality_factor_scores.csv").open()))
    assert len(p)==80
    assert len(s)==80
    assert all(r["quality_score_v1"]=="" for r in s)
    assert all(r["scoring_status"]=="NOT_SCORED_PEER_GROUP_TOO_SMALL" for r in s)
def test_pit_no_leak():
    rows=list(csv.DictReader((P/"quality_factor_lineage.csv").open()))
    assert len(rows)>0
    assert all(r["filed"]<=r["cutoff"] for r in rows)
    assert all(r["raw_xbrl_verified"]=="False" for r in rows)
    assert all(r["contextRef"]=="" for r in rows)
def test_exit_classification():
    rows=list(csv.DictReader((P/"quality_sample_exit_classification.csv").open()))
    assert len(rows)==5
    assert sum(1 for r in rows if r["exit_type"]=="ACQUISITION")==4
    assert sum(1 for r in rows if r["exit_type"]=="MERGER")==1
def test_partial_manifest():
    m=load("p10_6_2_manifest.json")
    assert m["post_run"]["status"]=="QUALITY_PIT_PANEL_PARTIAL"
    assert m["post_run"]["valid_scores"]==0
