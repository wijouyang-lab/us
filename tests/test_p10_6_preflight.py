import csv,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"docs/research/p10_6_preflight"

def load(n):return json.loads((P/n).read_text())
def test_models_blocked():
    rows=list(csv.DictReader((P/"fundamental_factor_readiness.csv").open()))
    assert len(rows)==3
    assert {r["model"] for r in rows}=={"Value","Quality","GARP"}
    assert all(r["status"]=="DATA_BLOCKED" for r in rows)
    assert all(r["lookahead_risk"]=="HIGH" for r in rows)
def test_universe_and_price_blocked():
    u=list(csv.DictReader((P/"historical_universe_readiness.csv").open()))[0]
    p=list(csv.DictReader((P/"historical_price_readiness.csv").open()))[0]
    assert float(u["coverage"])<0.95
    assert int(u["missing_tickers_previously_identified"])==98
    assert p["status"]=="DATA_BLOCKED"
    assert p["delisting_return_verified"]=="False"
def test_manifest_pre_post():
    m=load("p10_6_preflight_manifest.json")
    assert m["pre_run"]["mode"]=="PRE_RUN"
    assert m["post_run"]["status"]=="DATA_BLOCKED"
    assert m["post_run"]["model_status"]=={"Value":"DATA_BLOCKED","Quality":"DATA_BLOCKED","GARP":"DATA_BLOCKED"}
