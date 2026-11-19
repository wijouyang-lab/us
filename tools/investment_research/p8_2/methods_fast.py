"""Fast vectorized P8.2 A/B/C method comparison."""
from __future__ import annotations
import csv, json, math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("."); OUT = ROOT/"data/research/p8_2"; P8=ROOT/"data/research/p8"
TOP_N=20; BPS=10.0; OOS=date(2015,1,1)


def hac(x,lags=6):
    x=np.asarray([v for v in x if np.isfinite(v)],float); n=len(x)
    if n<20:return None,None
    mu=x.mean(); e=x-mu; var=float(e@e/n)
    for lag in range(1,min(lags,n-1)+1): var+=2*(1-lag/(lags+1))*float(e[lag:]@e[:-lag]/n)
    se=math.sqrt(max(var,0)/n); t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def stats(r,ew,dates):
    r=np.asarray(r,float); ew=np.asarray(ew,float); eq=np.cumprod(1+r); yrs=len(r)/12
    oos=np.array([x for x,d in zip(r,dates) if d>=OOS]); oo=np.array([x for x,d in zip(ew,dates) if d>=OOS])
    ex=r-ew; t,p=hac(ex)
    return {"months":len(r),"cagr":float(eq[-1]**(1/yrs)-1) if yrs else None,
            "vol":float(r.std(ddof=1)*math.sqrt(12)),"sharpe":float(r.mean()/r.std(ddof=1)*math.sqrt(12)),
            "max_drawdown":float((eq/np.maximum.accumulate(eq)-1).min()),
            "oos_months":len(oos),"oos_cagr":float(np.cumprod(1+oos)[-1]**(12/len(oos))-1) if len(oos) else None,
            "oos_sharpe":float(oos.mean()/oos.std(ddof=1)*math.sqrt(12)) if len(oos)>1 and oos.std(ddof=1)>0 else None,
            "hac_active_t":t,"p_value":p}


def main():
    px=pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","close","adjusted_close"])
    px["date"]=pd.to_datetime(px.date); px["symbol"]=px.symbol.str.upper()
    px=px[(px.date>="2000-01-03")&(px.date<="2024-12-31")].copy(); px["adj_open"]=px.open*px.adjusted_close/px.close
    close=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index()
    open_=px.pivot_table(index="date",columns="symbol",values="adj_open",aggfunc="last").reindex(close.index)
    cols=list(close.columns); ci={c:i for i,c in enumerate(cols)}
    cn=close.to_numpy(float); on=open_.to_numpy(float)
    factors={"MOMENTUM_20":close/close.shift(20)-1,"MOMENTUM_60":close/close.shift(60)-1,
             "MOMENTUM_120":close/close.shift(120)-1,"TREND_MA200":close/close.rolling(200).mean()-1,
             "LOW_VOL_60":-(close.pct_change().rolling(60).std()*math.sqrt(252)),"REVERSAL_5":-(close/close.shift(5)-1)}
    fds={k:v.to_numpy(float) for k,v in factors.items()}
    anom=defaultdict(set)
    with (OUT/"ticker_anomaly_audit.csv").open(encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f): anom[r["ticker"]].add(date.fromisoformat(r["anomaly_date"]))
    bad_tickers={ci[t] for t in anom if t in ci}
    m=pd.read_csv(ROOT/"data/research/historical_universe/sp500_daily.csv"); m["date"]=pd.to_datetime(m.date).dt.date
    m=m.drop_duplicates("date").sort_values("date"); md=list(m.date); mt=list(m.tickers)
    dates=list(close.index.date); pos={d:i for i,d in enumerate(dates)}
    s=pd.Series(dates,index=pd.to_datetime(dates)); month_ends=list(s.groupby([s.index.year,s.index.month]).last().values)
    out={}
    for method in ("A_RAW","B_EXCLUDE_ALL","C_PER_DATE"):
        ret={k:[] for k in factors}; ew=[]; dts=[]; rows=[]; prev={k:set() for k in factors}
        for mi,mdte in enumerate(month_ends[:-1]):
            p=np.searchsorted(md,mdte,side="right")-1
            if p<0:continue
            mem={x.strip().upper() for x in str(mt[p]).split(",") if x.strip()}
            di=pos.get(mdte); ndi=pos.get(month_ends[mi+1])
            if di is None or ndi is None or di+1>=len(dates) or ndi+1>=len(dates):continue
            entry=di+1; exitd=ndi+1
            idx=[ci[x] for x in mem if x in ci]
            if method=="B_EXCLUDE_ALL": idx=[j for j in idx if j not in bad_tickers]
            if method=="C_PER_DATE":
                # isolate ticker only when anomaly falls inside this holding interval
                keep=[]
                for j in idx:
                    t=cols[j]
                    if any(entry<=pos[d]<=exitd for d in anom.get(t,set()) if d in pos): continue
                    keep.append(j)
                idx=keep
            avail=[j for j in idx if np.isfinite(cn[md_idx:=pos.get(mdte),j]) if False]
            # explicit loop avoids walrus edge cases
            avail=[]; mi_pos=pos.get(mdte)
            for j in idx:
                if mi_pos is not None and np.isfinite(cn[mi_pos,j]) and np.isfinite(on[entry,j]) and np.isfinite(on[exitd,j]): avail.append(j)
            if len(avail)<30:continue
            er=float(np.mean(on[exitd,avail]/on[entry,avail]-1)); ew.append(er); dts.append(mdte)
            for name,f in fds.items():
                vals=[(j,f[mi_pos,j]) for j in avail if np.isfinite(f[mi_pos,j])]
                vals.sort(key=lambda z:-z[1]); hold={j for j,_ in vals[:TOP_N]}
                if not hold: ret[name].append(None); continue
                gross=float(np.mean(on[exitd,list(hold)]/on[entry,list(hold)]-1))
                turn=len(hold ^ prev[name])/len(hold)  # additions + removals
                net=gross-BPS/10000.0*turn
                ret[name].append(net); prev[name]=hold
                rows.append({"method":method,"strategy":name,"formation":str(mdte),"entry":str(dates[entry]),"exit":str(dates[exitd]),"gross":gross,"net":net,"turnover_two_sided":turn,"n":len(hold)})
        for name,xs in ret.items():
            vals=[(d,x) for d,x in zip(dts,xs) if x is not None]; rr=[x for _,x in vals]
            ewv=[ew[dts.index(d)] for d,_ in vals]
            out.setdefault(method,{})[name]=stats(rr,ewv,[d for d,_ in vals])
        rows.append({"method":method,"strategy":"EQUAL_WEIGHT","formation":"","entry":"","exit":"","gross":"","net":"","turnover_two_sided":0,"n":""})
        # write EW separately from strategy returns
        pd.DataFrame(rows).to_csv(OUT/f"monthly_{method}.csv",index=False)
        pd.DataFrame({"date":[str(d) for d in dts],"equal_weight":ew}).to_csv(OUT/f"equal_weight_{method}.csv",index=False)
        out[method]["_equal_weight"]={"months":len(ew),"cagr":float(np.cumprod(1+np.array(ew))[-1]**(12/len(ew))-1),
                                      "sharpe":float(np.mean(ew)/np.std(ew,ddof=1)*math.sqrt(12))}
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"as_of":"2024-12-31",
            "methods":{"A_RAW":"no filtering","B_EXCLUDE_ALL":"P8.1 diagnostic all-history exclusion",
                       "C_PER_DATE":"formal per-date isolation; earlier history retained"},
            "cost":{"bps_per_side":10.0,"turnover_definition":"|hold XOR prev|/n = two-sided traded fraction; cost=bps*turnover (no x2)"},
            "results":out,"status":"P8_2_METHOD_COMPARISON"}
    (OUT/"method_comparison.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({m:{k:{kk:v[kk] for kk in ("cagr","oos_cagr","sharpe","oos_sharpe","hac_active_t","max_drawdown")} for k,v in x.items() if k!="_equal_weight"} for m,x in out.items()},indent=2))


if __name__=="__main__":raise SystemExit(main())
