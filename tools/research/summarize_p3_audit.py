import json
from pathlib import Path
p=Path("data/research/free_market_data_audit_p3.json"); d=json.loads(p.read_text())
for src in ("Yahoo/yfinance","AKShare/Sina"):
    rows=[x for x in d["coverage"] if x["source"]==src]
    d.setdefault("summary",{})[src]={
        "symbols":len(rows),"ok":sum(1 for x in rows if x["status"]=="OK"),
        "rows_total":sum(x.get("rows",0) for x in rows),
        "duplicates":sum(x.get("duplicates",0) for x in rows),
        "bad_ohlcv_rows":sum(x.get("bad_ohlcv_rows",0) for x in rows),
        "zero_volume_rows":sum(x.get("zero_volume_rows",0) for x in rows),
        "jumps_gt_35pct":sum(x.get("jumps_gt_35pct",0) for x in rows),
        "period_coverage":{per:sum(1 for x in rows if x.get("period_rows",{}).get(per,0)>0) for per in ("1y","2y","5y","10y")},
        "min_first":min(x.get("first") for x in rows if x.get("first")),
        "max_last":max(x.get("last") for x in rows if x.get("last")),
    }
d["ratings"]={
 "yahoo":{"technical":"TECHNICAL_PASS","license":"LICENSE_UNVERIFIED","overall":"DATA_BLOCKED",
          "reason":"public terms restrict redistribution/public display; no written permission"},
 "akshare":{"technical":"TECHNICAL_PASS","license":"LICENSE_UNVERIFIED","overall":"DATA_BLOCKED",
            "reason":"Sina upstream terms not verified; 75 bad OHLC rows and split-induced jumps"},
 "finnhub":{"technical":"NOT_CONFIGURED","license":"LICENSE_UNVERIFIED","overall":"DATA_BLOCKED",
            "reason":"no API key present; no quote/candle/plan/quota test possible"},
}
d["usage_matrix"]={k:{"private_research":"LICENSE_UNVERIFIED","local_backtest":"LICENSE_UNVERIFIED",
 "long_term_storage":"LICENSE_UNVERIFIED","derived_factors":"LICENSE_UNVERIFIED",
 "github_data":"LICENSE_UNVERIFIED","github_pages_display":"LICENSE_UNVERIFIED",
 "public_results":"LICENSE_UNVERIFIED"} for k in ("yahoo","akshare","finnhub")}
p.write_text(json.dumps(d,indent=2,default=str),encoding="utf-8")
print(json.dumps(d["summary"],indent=2))
