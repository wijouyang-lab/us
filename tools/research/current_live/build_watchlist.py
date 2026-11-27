#!/usr/bin/env python3
"""Current watchlist + immutable forward signal snapshot. Research only."""
import json, hashlib, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/"data/research/current_live_v1"
OUT=Path(os.environ.get("CURRENT_OUT",str(ROOT/"artifacts/current_us_selection_forward_v1")))
OUT.mkdir(parents=True,exist_ok=True)
p=pd.read_parquet(DATA/"daily_14m.parquet"); e=pd.read_parquet(DATA/"etf_1y.parquet"); u=pd.read_csv(DATA/"unified_selection_v1_1.csv")
p["Date"]=pd.to_datetime(p.Date); e["Date"]=pd.to_datetime(e.Date)
last=p.Date.max(); spy=e[e.ticker=="SPY"].set_index("Date").Close.sort_index()
# pivots
adj=p.pivot(index="Date",columns="ticker",values="Adj Close").sort_index()
raw=p.pivot(index="Date",columns="ticker",values="Close").sort_index()
vol=p.pivot(index="Date",columns="ticker",values="Volume").sort_index()
# require at least 220 observations
ok=adj.notna().sum()>=220
adj=adj.loc[:,ok]; raw=raw.loc[:,ok]; vol=vol.loc[:,ok]
a=adj.iloc[-1]; r6=adj.iloc[-1]/adj.iloc[-126]-1
r12=adj.iloc[-22]/adj.iloc[-252]-1
hi=adj.iloc[-252:].max(); pos=adj.iloc[-1]/hi
ma20=adj.iloc[-20:].mean(); ma50=adj.iloc[-50:].mean(); ma200=adj.iloc[-200:].mean()
vol20=adj.pct_change().iloc[-20:].std()*np.sqrt(252)
adv20=(raw.iloc[-20:]*vol.iloc[-20:]).mean()
spy6=spy.iloc[-1]/spy.iloc[-126]-1
rel6=r6-spy6
u=u.set_index("ticker"); meta=u.reindex(adj.columns)
filed=pd.to_datetime(meta.filed,errors="coerce")
# current signal uses only filings filed on/before signal date
pub=filed<=last
quality=pd.to_numeric(meta.quality_pct,errors="coerce").where(pub)
# z scores cross-section
def z(s): return (s-s.mean())/s.std(ddof=0)
trend_raw=0.40*z(r12)+0.20*z(r6)+0.20*z(pos)+0.10*z(ma50/a-1)+0.10*z(rel6)
trend_pct=trend_raw.rank(pct=True)
liq=np.clip(np.log10(adv20.clip(lower=2e6)/2e6)/2,0,1)
risk=(vol20>0.65).astype(float)*0.08+(pd.to_numeric(meta.liabilities_to_assets,errors="coerce")>0.8).astype(float)*0.08+(pd.to_numeric(meta.fcf_yield,errors="coerce")<0).astype(float)*0.06
score=(0.50*trend_pct+0.35*quality+0.15*liq-risk*0.5)*100
base=pd.DataFrame({"ticker":adj.columns,"price":a.values,"r12":r12.values,"r6":r6.values,"rel6":rel6.values,"pos52":pos.values,"ma20":ma20.values,"ma50":ma50.values,"ma200":ma200.values,"vol20":vol20.values,"adv20":adv20.values,"quality_pct":quality.values,"trend_pct":trend_pct.values,"liq":liq.values,"score":score.values,"filed":filed.values})
base=base.merge(meta[["issuer_name","security_type","industry","data_quality_status","tradability_status"]],left_on="ticker",right_index=True,how="left")
base["trend_ok"]=(base.r6>0)&(base.pos52>=0.75)&(base.price>base.ma50)&(base.ma50>base.ma200)
base["risk_flags"]=""
base.loc[base.vol20>0.65,"risk_flags"]+="HIGH_VOL;"
base.loc[pd.to_numeric(base.adv20,errors="coerce")<2e6,"risk_flags"]+="LOW_LIQUIDITY;"
base.loc[pd.to_numeric(meta.liabilities_to_assets,errors="coerce").reindex(base.ticker).values>0.8,"risk_flags"]+="HIGH_LEVERAGE;"
base.loc[pd.to_numeric(meta.fcf_yield,errors="coerce").reindex(base.ticker).values<0,"risk_flags"]+="NEG_FCF;"
base["risk_flags"]=base.risk_flags.str.rstrip(";")
base["eligible"]=base.ticker.isin(meta.index)&base.security_type.isin(["COMMON","ADR"])&(base.price>=5)&(base.adv20>=2e6)&base.trend_ok&base.quality_pct.notna()&(base.score>=50)
base["complete"]=base.eligible&base.filed.notna()&base.data_quality_status.isin(["FULL","VERIFIED"])
base["entry_date"]=last.date().isoformat()
# main top 10 max; no padding
tmp=base[base.eligible].sort_values("score",ascending=False); chosen=[]; counts={}
for _,row in tmp.iterrows():
    ind=row.industry or "UNKNOWN"
    if counts.get(ind,0)>=2: continue
    counts[ind]=counts.get(ind,0)+1; chosen.append(row)
    if len(chosen)>=10: break
cand=pd.DataFrame(chosen).copy()
if len(cand)==0:
    status="NO_CANDIDATE"
else:
    cand["rank"]=range(1,len(cand)+1); status="WATCHLIST"; cand["filed"]=cand.filed.astype(str); cand["completeness"]=np.where(cand.complete,"FULL","PARTIAL")
sec=base[base.ticker.isin(meta.index)&~base.eligible].sort_values("score",ascending=False).head(30).copy()
def ex(x):
    if x.security_type not in ("COMMON","ADR"): return "SECURITY_TYPE"
    if x.price<5: return "PRICE_BELOW_5"
    if x.adv20<2e6: return "LOW_LIQUIDITY"
    if not x.trend_ok: return "TREND_NOT_CONFIRMED"
    if pd.isna(x.quality_pct): return "QUALITY_NOT_PUBLIC"
    if x.score<50: return "SCORE_BELOW_50"
    return "OTHER"
sec["exclude_reason"]=sec.apply(ex,axis=1)
# reasons
def why(x):
    s=[]
    if x.r12>0: s.append(f"12-1 {x.r12:.1%}")
    if x.r6>0: s.append(f"6m {x.r6:.1%}")
    if x.rel6>0: s.append(f"vs SPY {x.rel6:+.1%}")
    if x.pos52>=.9: s.append(f"near 52w high ({x.pos52:.0%})")
    if x.quality_pct>=.8: s.append(f"quality pct {x.quality_pct:.0%}")
    return "; ".join(s) or "trend/quality composite"
def risk(x):
    return x.risk_flags or "none flagged; verify latest 10-Q"
for x in ["why","risk"]:
    if x=="why": cand["why"]=cand.apply(why,axis=1)
    else: cand["risk"]=cand.apply(risk,axis=1)
# snapshot: content-hash immutable, same date rerun with different data creates new version
snap={"asof":last.date().isoformat(),"generated_at":"2026-11-27T17:30:00+08:00","algorithm":"current_watch.v1","params":{"price_min":5,"adv20_min":2000000,"pos52_min":0.75,"score_min":50,"max_names":10},"status":status,"coverage":{"prices":len(adj.columns),"spy_last":spy.index[-1].date().isoformat(),"latest":last.date().isoformat()},"signals":cand.drop(columns=["eligible","complete"]).to_dict("records")}
b=json.dumps(snap,sort_keys=True,separators=(",",":")).encode(); h=hashlib.sha256(b).hexdigest()[:10]
(OUT/"snapshots").mkdir(exist_ok=True)
snap_path=OUT/"snapshots"/f"signal_{last.date().isoformat()}_{h}.json"
if not snap_path.exists(): snap_path.write_bytes(b)
# forward tracker: 5/10/20/40 trading days after signal, only if date exists
def fwd(ticker, entry_date, days):
    s=adj[ticker].dropna(); idx=s.index
    if entry_date not in idx: return None,None
    i=idx.get_loc(entry_date); j=i+days
    if j>=len(idx): return "PENDING",None
    return idx[j].date().isoformat(), float(s.iloc[j]/s.iloc[i]-1)
rows=[]
for _,x in cand.iterrows():
    row={"signal_date":last.date().isoformat(),"ticker":x.ticker,"company":x.issuer_name,"entry_price":float(x.price),"rank":int(x["rank"]),"score":float(x.score),"why":x.why,"risk":x.risk,"filed":x.filed,"quality_pct":x.quality_pct,"data_quality":x.data_quality_status,"completeness":x.completeness}
    for d in [5,10,20,40]:
        dt,ret=fwd(x.ticker,last,int(d)); row[f"date_{d}d"]=dt; row[f"ret_{d}d"]=ret
    rows.append(row)
hist=pd.DataFrame(rows); hist["status"]="PENDING"; hist.to_csv(OUT/"forward_signals.csv",index=False)
(OUT/"signals_history.json").write_text(json.dumps({"snapshot":snap_path.name,"sha256":hashlib.sha256(b).hexdigest(),"signals":rows},indent=2))
# weekly stats
stats={"status":"SAMPLE_TOO_SMALL","asof":last.date().isoformat(),"signals":len(rows),"matured_5d":0,"matured_10d":0,"matured_20d":0,"matured_40d":0,"note":"No trading days have elapsed after the 2026-11-25 signal."}
(OUT/"weekly_stats.json").write_text(json.dumps(stats,indent=2))
# page payload
payload={"asof":last.date().isoformat(),"generated_at":snap["generated_at"],"status":status,"coverage":snap["coverage"],"market":{"spy":float(spy.iloc[-1]),"spy_6m":float(spy6),"regime":"above 200d" if spy.iloc[-1]>spy.iloc[-200:].mean() else "below 200d"},"signals":rows,"secondary":sec[["ticker","issuer_name","price","score","quality_pct","risk_flags"]].fillna("").to_dict("records"),"excluded":sec[["ticker","issuer_name","price","score","risk_flags","exclude_reason"]].fillna("").to_dict("records"),"weekly":stats}
(OUT/"watchlist_data.json").write_text(json.dumps(payload,indent=2))
base.to_csv(OUT/"all_scores.csv",index=False)
print(status,len(cand),len(sec),last.date(),h)
print(cand[["ticker","score","r12","r6","quality_pct"]].to_string(index=False))
