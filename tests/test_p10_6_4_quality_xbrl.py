import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_4_quality_xbrl_replay"

def load(n):return json.loads((P/n).read_text())
def test_vertical_counts():
    rows=list(csv.DictReader((P/"quality_xbrl_context_validation.csv").open()))
    assert len(rows)==92
    assert sum(1 for r in rows if r["status"]=="XBRL_CONTEXT_VERIFIED")==50
    assert sum(1 for r in rows if r["status"]=="XBRL_CONTEXT_UNRESOLVED")==40
    assert sum(1 for r in rows if r["status"]=="SOURCE_FILE_MISSING")==2
def test_verified_rows_have_context():
    rows=list(csv.DictReader((P/"quality_xbrl_context_validation.csv").open()))
    for r in rows:
        if r["status"]=="XBRL_CONTEXT_VERIFIED":
            assert r["contextRef"] and r["concept"] and r["raw_value"]
def test_amendment_and_repeat():
    a=list(csv.DictReader((P/"quality_amendment_replay.csv").open()))[0]
    assert a["status"]=="AMENDMENT_REPLAY_UNRESOLVED"
    r=list(csv.DictReader((P/"quality_repeatability_comparison.csv").open()))
    assert all(x["status"]=="NOT_RUN" for x in r)
def test_partial():
    m=load("quality_replay_manifest.json")
    assert m["post_run"]["status"]=="XBRL_VERTICAL_SLICE_PARTIAL"
    assert m["post_run"]["verified"]==50
