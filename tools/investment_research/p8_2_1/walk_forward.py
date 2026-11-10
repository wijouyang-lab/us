"""P8.2.1 walk-forward with actual target-weight switch costs."""
from __future__ import annotations
import csv,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd

OUT=Path("data/research/p8_2_1"); TRAIN=60;PURGE=1;TEST=12;BPS=10.0


def hac(x,lags=6):
    x=np.asarray([v for v in x if np.isfinite(v)],float);n=len(x)
    if n<20:return None,None
    mu=x.mean();e=x-mu;var=float(e@e/n)
    for lag in range(1,min(lags,n-1)+1):var+=2*(1-lag/(lags+1))*float(e[lag:]@e[:-lag]/n)
    se=math.sqrt(max(var,0)/n);t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def st(r,ew):
    r=np.asarray(r,float);ew=np.asarray(ew,float);eq=np.cumprod(1+r);y=len(r)/12;t,p=hac(r-ew)
    return {"months":len(r),"cagr":float(eq[-1]**(1/y)-1),"sharpe":float(r.mean()/r.std(ddof=1)*math.sqrt(12)) if r.std(ddof=1)>0 else None,"max_drawdown":float((eq/np.maximum.accumulate(eq)-1).min()),"hac_active_t":t,"p_value":p}


def main():
    df=pd.read_csv(OUT/"event_time_monthly.csv",parse_dates=["formation"]);p=df.pivot(index="formation",columns="strategy",values="net").sort_index()
    ew=pd.read_csv(OUT/"event_time_equal_weight.csv",parse_dates=["date"]).set_index("date")["equal_weight"]
    h=pd.read_csv(OUT/"event_time_holdings.csv",parse_dates=["formation"])
    def holds(strategy,d):
        x=h[(h.strategy==strategy)&(h.formation==d)&(h.status=="VALID")]
        if x.empty:return None
        return {t:1/len(x.tickers.iloc[0].split("|")) for t in x.tickers.iloc[0].split("|")}
    windows=[];selected=[];sd=[];prev_strategy=None;prev_target=None;sw=[];switch_costs=0.0
    for start in range(TRAIN+PURGE,len(p)-TEST+1,TEST):
        train=p.iloc[start-TRAIN-PURGE:start-PURGE];test=p.iloc[start:start+TEST]
        sh={c:float(train[c].mean()/train[c].std(ddof=1)*math.sqrt(12)) for c in p.columns if train[c].std(ddof=1)>0}
        if not sh:continue
        best=max(sh,key=sh.get); rr=[]
        for k,(d,row) in enumerate(test.iterrows()):
            v=row[best]
            if not np.isfinite(v): continue
            cost=0.0
            if k==0 and prev_strategy is not None and best!=prev_strategy:
                nt=holds(best,d); pt=prev_target
                if nt and pt:
                    L1=sum(abs(nt.get(t,0)-pt.get(t,0)) for t in set(nt)|set(pt))
                else: L1=1.0
                cost=BPS/10000*L1;switch_costs+=cost
                sw.append({"date":str(d.date()),"from":prev_strategy,"to":best,"L1_weight_change":L1,"switch_cost_usd_bps":BPS*L1})
            rr.append(float(v)-cost);selected.append(float(v)-cost);sd.append(d)
        if k==0: pass
        windows.append({"test_start":str(test.index[0].date()),"test_end":str(test.index[-1].date()),"train_start":str(train.index[0].date()),"train_end":str(train.index[-1].date()),"train_n":len(train),"test_n":len(test),"selected":best,"train_sharpes":{k:round(v,6) for k,v in sh.items()},"test_return":float(np.prod(1+np.array(rr))-1) if rr else None})
        prev_strategy=best;prev_target=holds(best,test.index[0])
    sel=np.array(selected);ewv=np.array([ew.loc[d] for d in sd]);fixed={}
    for c in p.columns:
        r=[];e=[]
        for w in windows:
            lo=pd.Timestamp(w["test_start"]);hi=pd.Timestamp(w["test_end"]);sub=p.loc[(p.index>=lo)&(p.index<=hi),c]
            r.extend(sub.values);e.extend([ew.loc[d] for d in sub.index])
        fixed[c]=st(r,e)
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"method":"60m train/1m purge/12m test; actual target-weight L1 switch cost; 10bps per side",
            "windows":windows,"switches":sw,"switch_cost_bps_total":switch_costs,"selected":st(sel,ewv),"fixed":fixed,
            "untested_tail_months":[str(d.date()) for d in p.index[-((len(p)-TRAIN-PURGE)%TEST or TEST):]],
            "status":"WALK_FORWARD_COMPLETE","note":"selected uses equal-weight target holdings from event-time method D; no future anomaly used for selection."}
    (OUT/"walk_forward_results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    pd.DataFrame(sw).to_csv(OUT/"walk_forward_switches.csv",index=False)
    print(json.dumps({"windows":len(windows),"switches":len(sw),"switch_cost_bps":switch_costs,"selected":report["selected"],"fixed":{k:v["sharpe"] for k,v in fixed.items()}},indent=2))


if __name__=="__main__":raise SystemExit(main())
