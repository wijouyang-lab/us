"""Read immutable signal snapshots and fill only matured trading-day horizons."""
import json, hashlib, os
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(os.environ.get("CURRENT_OUT",str(ROOT/"artifacts/current_us_selection_forward_v1")))
P=pd.read_parquet(ROOT/"data/research/current_live_v1/daily_14m.parquet")
P["Date"]=pd.to_datetime(P.Date); P=P.sort_values(["ticker","Date"])
close={t:g.set_index("Date").Close.dropna() for t,g in P.groupby("ticker")}
rows=[]
for f in sorted((OUT/"snapshots").glob("signal_*.json")):
    s=json.loads(f.read_text()); d=s["asof"]
    for r in s.get("signals",[]):
        t=r["ticker"]; x=close.get(t)
        row={"snapshot":f.name,"signal_date":d,"ticker":t,"entry_price":r.get("entry_price",r.get("price")),"rank":r.get("rank"),"score":r["score"]}
        if x is None or d not in x.index:
            for n in [5,10,20,40]: row[f"date_{n}d"]="PENDING"; row[f"ret_{n}d"]=None
            rows.append(row); continue
        i=x.index.get_loc(d)
        for n in [5,10,20,40]:
            j=i+n
            if j>=len(x): row[f"date_{n}d"]="PENDING"; row[f"ret_{n}d"]=None
            else: row[f"date_{n}d"]=x.index[j].date().isoformat(); row[f"ret_{n}d"]=float(x.iloc[j]/x.iloc[i]-1)
        rows.append(row)
df=pd.DataFrame(rows); df.to_csv(OUT/"forward_signals.csv",index=False)
mat={n:int(df[f"ret_{n}d"].notna().sum()) for n in [5,10,20,40]}
st={"status":"SAMPLE_TOO_SMALL" if min(mat.values())<10 else "AVAILABLE","asof":str(P.Date.max().date()),"signals":len(df),"matured_5d":mat[5],"matured_10d":mat[10],"matured_20d":mat[20],"matured_40d":mat[40],"note":"Forward returns are filled only when the Nth trading day exists; otherwise PENDING."}
(OUT/"weekly_stats.json").write_text(json.dumps(st,indent=2)); print(st)
