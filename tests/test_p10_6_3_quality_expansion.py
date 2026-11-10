import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_3_quality_expansion"

def load(n):return json.loads((P/n).read_text())
def test_cohort():
    rows=list(csv.DictReader((P/"quality_peer_cohort.csv").open()))
    assert len(rows)==60
    assert any(r["ticker"]=="XLNX" for r in rows)
def test_all_cutoffs_30_peer():
    stats=list(csv.DictReader((P/"quality_peer_stats.csv").open()))
    assert len(stats)==4
    assert all(int(r["peer_count"])>=30 for r in stats)
    assert all(r["status"]=="PILOT_SAMPLE_RANKING" for r in stats)
    assert sum(int(r["scored"]) for r in stats)==176
def test_no_fake_context():
    rows=list(csv.DictReader((P/"quality_factor_lineage.csv").open()))
    assert all(r["filed"]<=r["cutoff"] for r in rows)
    assert all(r["raw_xbrl_verified"]=="False" for r in rows)
    assert all(r["contextRef"]=="" for r in rows)
def test_ranking_not_accepted():
    m=load("p10_6_3_manifest.json")
    assert m["post_run"]["status"]=="QUALITY_PILOT_RANKING_READY"
    assert m["post_run"]["cohort"]==60
