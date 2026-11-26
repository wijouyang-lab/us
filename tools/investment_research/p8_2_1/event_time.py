"""P8.2.1 event-time-safe method D.

Known anomalies are used only up to formation; anomalies that occur during a
holding period are marked DATA_INVALID/UNPRICEABLE, not used to choose holdings.
"""
from __future__ import annotations
import csv, json, math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT=Path("."); OUT=ROOT/"data/research/p8_2_1"; P82=ROOT/"data/research/p8_2"
TOP_N=20; BPS=10.0; OOS=date(2015,1,1)


def hac(x,lags=6):
    x=np.asarray([v for v in x if np.isfinite(v)],float);n=len(x)
    if n<20:return None,None
    mu=x.mean();e=x-mu;var=float(e@e/n)
    for lag in range(1,min(lags,n-1)+1):var+=2*(1-lag/(lags+1))*float(e[lag:]@e[:-lag]/n)
    se=math.sqrt(max(var,0)/n);t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def stats(r,ew,dates):
    r=np.asarray(r,float);ew=np.asarray(ew,float);eq=np.cumprod(1+r);yrs=len(r)/12
    oos=np.array([x for x,d in zip(r,dates) if d>=OOS]);oo=np.array([x for x,d in zip(ew,dates) if d>=OOS])
    t,p=hac(r-ew)
    return {"months":len(r),"cagr":float(eq[-1]**(1/yrs)-1),"sharpe":float(r.mean()/r.std(ddof=1)*math.sqrt(12)),
            "max_drawdown":float((eq/np.maximum.accumulate(eq)-1).min()),"oos_months":len(oos),
            "oos_cagr":float(np.cumprod(1+oos)[-1]**(12/len(oos))-1) if len(oos) else None,
            "oos_sharpe":float(oos.mean()/oos.std(ddof=1)*math.sqrt(12)) if len(oos)>1 and oos.std(ddof=1)>0 else None,
            "hac_active_t":t,"p_value":p}


def main():
    px=pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","close","adjusted_close"])
    px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>="2000-01-03")&(px.date<="2024-12-31")].copy();px["adj_open"]=px.open*px.adjusted_close/px.close
    close=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index();open_=px.pivot_table(index="date",columns="symbol",values="adj_open",aggfunc="last").reindex(close.index)
    cols=list(close.columns);ci={c:i for i,c in enumerate(cols)};cn=close.to_numpy(float);on=open_.to_numpy(float)
    f={"MOMENTUM_20":(close/close.shift(20)-1,20),"MOMENTUM_60":(close/close.shift(60)-1,60),"MOMENTUM_120":(close/close.shift(120)-1,120),
       "TREND_MA200":(close/close.rolling(200).mean()-1,200),"LOW_VOL_60":(-(close.pct_change().rolling(60).std()*math.sqrt(252)),60),"REVERSAL_5":(-(close/close.shift(5)-1),5)}
    fds={k:v[0].to_numpy(float) for k,v in f.items()};lens={k:v[1] for k,v in f.items()}
    bad=defaultdict(set)
    with (OUT/"ticker_anomaly_audit.csv").open(encoding="utf-8",newline="") as fh:
        for r in csv.DictReader(fh):
            if r["classification"] in ("VERIFIED_CORRUPT","UNRESOLVED","ZERO_VOLUME_OR_STALE"):
                bad[r["ticker"]].add(date.fromisoformat(r["anomaly_date"]))
    m=pd.read_csv(ROOT/"data/research/historical_universe/sp500_daily.csv");m["date"]=pd.to_datetime(m.date).dt.date;m=m.drop_duplicates("date").sort_values("date")
    md=list(m.date);mt=list(m.tickers);dates=list(close.index.date);pos={d:i for i,d in enumerate(dates)};mi_dates=pos
    s=pd.Series(dates,index=pd.to_datetime(dates));month_ends=list(s.groupby([s.index.year,s.index.month]).last().values)
    ret={k:[] for k in f};ew=[];dts=[];rows=[];holdings=[];prev={k:set() for k in f};audit=defaultdict(lambda:{"evals":0,"known_anomaly":0,"insufficient":0})
    for mi,mdte in enumerate(month_ends[:-1]):
        p=np.searchsorted(md,mdte,side="right")-1
        if p<0:continue
        mem={x.strip().upper() for x in str(mt[p]).split(",") if x.strip()};di=pos.get(mdte);ndi=pos.get(month_ends[mi+1])
        if di is None or ndi is None or di+1>=len(dates) or ndi+1>=len(dates):continue
        entry=di+1;exitd=ndi+1
        idx=[ci[x] for x in mem if x in ci]
        avail=[j for j in idx if np.isfinite(cn[di,j]) and np.isfinite(on[entry,j]) and np.isfinite(on[exitd,j])]
        if len(avail)<30:continue
        er=float(np.mean(on[exitd,avail]/on[entry,avail]-1));ew.append(er);dts.append(mdte)
        for name,ff in fds.items():
            n=lens[name];valid=[];known=0;ins=0
            for j in avail:
                t=cols[j];audit[(name,t)]["evals"]+=1
                if di-n<0 or not all(np.isfinite(cn[di-k,j]) for k in range(n+1)):
                    audit[(name,t)]["insufficient"]+=1;ins+=1;continue
                # only anomalies already known by formation can affect the signal
                if any(d<=mdte and d>=dates[di-n] for d in bad.get(t,set())):
                    audit[(name,t)]["known_anomaly"]+=1;known+=1;continue
                valid.append(j)
            vals=[(j,ff[di,j]) for j in valid if np.isfinite(ff[di,j])];vals.sort(key=lambda z:-z[1]);hold={j for j,_ in vals[:TOP_N]}
            if not hold:continue
            # future anomaly during holding -> unpriceable, but do NOT use it to change holdings
            future_bad=[t for j in hold for t in [cols[j]] if any(entry<=pos[d]<=exitd for d in bad.get(t,set()))]
            if future_bad:
                holdings.append({"strategy":name,"formation":str(mdte),"status":"DATA_INVALID_UNPRICEABLE","invalid_positions":len(future_bad),"holdings":len(hold)})
                continue
            gross=float(np.mean(on[exitd,list(hold)]/on[entry,list(hold)]-1));turn=len(hold^prev[name])/len(hold);net=gross-BPS/10000*turn
            ret[name].append(net);rows.append({"strategy":name,"formation":str(mdte),"entry":str(dates[entry]),"exit":str(dates[exitd]),"gross":gross,"net":net,"turnover_two_sided":turn,"n":len(hold),"status":"VALID"})
            holdings.append({"strategy":name,"formation":str(mdte),"status":"VALID","tickers":"|".join(cols[j] for j in sorted(hold)),"n":len(hold)})
            prev[name]=hold
    for k,v in ret.items():
        vals=[(d,x) for d,x in zip(dts,v) if x is not None];rr=[x for _,x in vals];ee=[ew[dts.index(d)] for d,_ in vals]
        ret[k]=stats(rr,ee,[d for d,_ in vals])
    rows_out=[]
    for (s,t),x in audit.items(): rows_out.append({"strategy":s,"ticker":t,**x})
    with (OUT/"factor_window_audit.csv").open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=["strategy","ticker","evals","known_anomaly","insufficient"]);w.writeheader();w.writerows(rows_out)
    pd.DataFrame(holdings).to_csv(OUT/"event_time_holdings.csv",index=False)
    pd.DataFrame({"date":[str(d) for d in dts],"equal_weight":ew}).to_csv(OUT/"event_time_equal_weight.csv",index=False)
    pd.DataFrame(rows).to_csv(OUT/"event_time_monthly.csv",index=False)
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"as_of":"2024-12-31","method":"D_EVENT_TIME",
            "policy":"formation uses only anomalies known at formation; anomalies during holding are DATA_INVALID, never used to change holdings",
            "results":ret,"invalid_months":sum(1 for h in holdings if h["status"]!="VALID"),
            "invalid_exposure":float(np.mean([h.get("invalid_positions",0)/max(h.get("holdings",1),1) for h in holdings if h["status"]!="VALID"])) if any(h["status"]!="VALID" for h in holdings) else 0.0,
            "cost":{"bps_per_side":BPS,"formula":"10bps * |hold XOR prev|/n; initial once"},
            "status":"EVENT_TIME_COMPLETE"}
    (OUT/"event_time_results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"invalid_months":report["invalid_months"],"results":{k:{kk:v[kk] for kk in ("cagr","oos_cagr","sharpe","oos_sharpe","hac_active_t","max_drawdown")} for k,v in ret.items()}},indent=2))


if __name__=="__main__":raise SystemExit(main())
