"""P4.3 quality view: primary-source status does not promote scores."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

p42=json.loads(Path("data/research/dividend_quality_p42.json").read_text())
splits=json.loads(Path("data/research/split_evidence_p43.json").read_text())
events=json.loads(Path("data/research/dividend_events_p43.json").read_text())
by_t={}
for x in splits: by_t.setdefault(x["ticker"],[]).append(x)
out={"generated_at":datetime.now(timezone.utc).isoformat(),
     "score_version":"dividend-score-2.1", "tickers":{}}
for t,v in p42["tickers"].items():
    primary=by_t.get(t,[])
    rec=dict(v)
    rec["primary_split_records"]=len(primary)
    rec["primary_split_status"]="SPLIT_CONFIRMED" if any(x.get("status")=="SPLIT_CONFIRMED" for x in primary) else "PARTIALLY_VERIFIED" if primary else "SPLIT_HISTORY_INCOMPLETE"
    rec["official_events_v43"]=[e for e in events.get("events",[]) if e.get("ticker")==t]
    rec["score_status"]="NOT_READY" if rec.get("score_status")=="NOT_READY" else rec.get("score_status")
    out["tickers"][t]=rec
out["event_summary"]=events.get("summary",{})
out["split_summary"]={"records":len(splits),"confirmed":sum(1 for x in splits if x.get("status")=="SPLIT_CONFIRMED"),
                      "partial":sum(1 for x in splits if x.get("status")=="PARTIALLY_VERIFIED")}
Path("data/research/dividend_quality_p43.json").write_text(json.dumps(out,indent=2,default=str),encoding="utf-8")
print("wrote",len(out["tickers"]))
