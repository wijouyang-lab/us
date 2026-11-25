from __future__ import annotations
import argparse, json, time
from pathlib import Path
import pandas as pd, numpy as np, yfinance as yf

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_fs1_out"); OUT.mkdir(parents=True,exist_ok=True)
UNIV=ROOT/"data/universe/selection_inputs/us_equities_current.csv"
CACHE=OUT/"price_cache_v1.csv.gz"

def fetch(tickers, period="1y"):
    yf.set_tz_cache_location(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_yf_tmp")
    return yf.download(list(tickers),period=period,interval="1d",group_by="ticker",progress=False,threads=False,auto_adjust=False,actions=False)

def rows_from(df, ticker):
    if df is None or len(df)==0: return pd.DataFrame()
    x=df.copy()
    if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(-1)
    x=x.reset_index()
    ren={"Date":"date","Open":"raw_open","High":"raw_high","Low":"raw_low","Close":"raw_close","Adj Close":"adjusted_close","Volume":"raw_volume"}
    x=x.rename(columns={k:v for k,v in ren.items() if k in x.columns})
    if "date" not in x: return pd.DataFrame()
    x["ticker"]=ticker
    for c in ["raw_open","raw_high","raw_low","raw_close","adjusted_close","raw_volume"]:
        if c not in x: x[c]=np.nan
    return x[["ticker","date","raw_open","raw_high","raw_low","raw_close","adjusted_close","raw_volume"]]

def identity():
    from tools.investment_research.price_liquidity.identity import load_universe
    u=load_universe(UNIV)
    u.to_csv(OUT/"universe_identity_v1.csv",index=False)
    print(len(u),u.security_type.value_counts().to_dict(),u.mapping_confidence.value_counts().to_dict())

def sample():
    from tools.investment_research.price_liquidity.identity import load_universe
    u=load_universe(UNIV)
    groups=[]
    for t,g in u.groupby("security_type"):
        groups.append(g.sample(min(12,len(g)),random_state=20261125))
    s=pd.concat(groups).drop_duplicates("ticker")
    res=[]; t0=time.time()
    for i in range(0,len(s),20):
        b=s.iloc[i:i+20]; d=fetch(b.ticker.tolist(),"6mo")
        for t in b.ticker:
            try:
                x=rows_from(d[t] if isinstance(d.columns,pd.MultiIndex) and t in d.columns.get_level_values(0) else d, t)
            except Exception:
                x=pd.DataFrame()
            n=len(x); ok=n>=20
            res.append({"ticker":t,"security_type":b[b.ticker==t].security_type.iloc[0],"rows":n,"success":ok,"reason":"" if ok else "EMPTY_OR_SHORT"})
    r=pd.DataFrame(res); r.to_csv(OUT/"provider_coverage_v1.csv",index=False)
    print(len(r),r.success.sum(),round(time.time()-t0,1))

def cache(limit=0):
    from tools.investment_research.price_liquidity.identity import load_universe
    u=load_universe(UNIV); u=u[u.security_type.isin(["COMMON","ADR"])]
    if limit: u=u.head(limit)
    frames=[]; status=[]
    for i in range(0,len(u),150):
        b=u.iloc[i:i+150]; d=fetch(b.ticker.tolist(),"1y")
        for t in b.ticker:
            x=pd.DataFrame()
            try:
                if isinstance(d.columns,pd.MultiIndex) and t in d.columns.get_level_values(0): x=rows_from(d[t],t)
            except Exception: pass
            if len(x): frames.append(x); status.append({"ticker":t,"status":"OK","rows":len(x)})
            else: status.append({"ticker":t,"status":"NO_DATA","rows":0})
        if i%300==0: print("batch",i,"rows",sum(len(f) for f in frames),flush=True)
        time.sleep(0.3)
    if frames:
        allp=pd.concat(frames,ignore_index=True).drop_duplicates(["ticker","date"])
        allp["source"]="yfinance"; allp["fetched_at"]=pd.Timestamp.utcnow().isoformat(); allp["data_status"]="OK"
        allp.to_csv(CACHE,index=False,compression="gzip")
    pd.DataFrame(status).to_csv(OUT/"cache_status_v1.csv",index=False)
    print("cached",len(frames),len(status))

def adv():
    d=pd.read_csv(CACHE); d["date"]=pd.to_datetime(d.date)
    rows=[]
    for t,g in d.groupby("ticker"):
        g=g.sort_values("date").tail(60); g=g[g.raw_close>0]; g=g[g.raw_volume>=0]
        g["dv"]=g.raw_close*g.raw_volume
        last=g.date.max(); l20=g.tail(20); l60=g.tail(60)
        r60=g.raw_close.pct_change().abs().max()
        ca="CORPORATE_ACTION_REVIEW" if (r60>0.5 if pd.notna(r60) else False) else "OK"
        rows.append({"ticker":t,"last_date":last.date().isoformat(),"valid_days":len(g),"adv20_shares":l20.raw_volume.mean(),"adv60_shares":l60.raw_volume.mean(),"adv20_usd":l20.dv.mean(),"adv60_usd":l60.dv.mean(),"corporate_action_status":ca,"data_age_days":(pd.Timestamp.today().normalize()-last).days})
    pd.DataFrame(rows).to_csv(OUT/"liquidity_metrics_v1.csv",index=False)
    print("adv",len(rows))

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--limit",type=int,default=0); a=ap.parse_args()
    {"identity":identity,"sample":sample,"cache":lambda:cache(a.limit),"adv":adv}[a.cmd]()

