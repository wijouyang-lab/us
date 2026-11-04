"""P4.6 28-company sector governance report (cached SEC only)."""
from __future__ import annotations
import json, collections
from pathlib import Path
from datetime import datetime, timezone
from tools.investment_research.dividend.sector_governance import classify, evaluate, comparable

snap=json.loads(Path("docs/research/sec_fundamentals_snapshot.json").read_text())
old=json.loads(Path("data/research/dividend_quality_p41.json").read_text())["tickers"]
out={"generated_at":datetime.now(timezone.utc).isoformat(),
     "score_profile":"NON_FINANCIAL_DIVIDEND_V1","tickers":{}}
counts=collections.Counter(); ready=0
for t,a in snap.items():
    src=a.get("industry") or {}
    c=classify(t, src.get("normalized_industry"), sic=src.get("sic"))
    m=old.get(t,{})
    ev=evaluate(m.get("metrics",{}), c["classification"],
                insurance_subtype=src.get("sic_description") if c["classification"]=="INSURANCE" else None)
    rec={"ticker":t,"cik":a.get("cik"),"industry":c,"old_score":m.get("score"),
         "old_score_status":m.get("score_status"),**ev,
         "raw_metrics":m.get("metrics",{})}
    out["tickers"][t]=rec; counts[c["classification"]]+=1
    if ev["score_status"]=="SCORE_READY": ready+=1
out["summary"]={"industry_counts":dict(counts),"score_ready":ready,
                "not_ready":sum(1 for v in out["tickers"].values() if v["score_status"]=="NOT_READY"),
                "industry_model_not_ready":sum(1 for v in out["tickers"].values() if v["score_status"]=="INDUSTRY_MODEL_NOT_READY")}
Path("data/research/dividend_quality_p46.json").write_text(json.dumps(out,indent=2,default=str),encoding="utf-8")
print(out["summary"])
