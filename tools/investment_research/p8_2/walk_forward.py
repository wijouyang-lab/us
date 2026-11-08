"""P8.2 walk-forward with strategy-switch cost and equal-weight HAC."""
from __future__ import annotations
import csv, json, math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

OUT=Path("data/research/p8_2"); TRAIN=60; PURGE=1; TEST=12; SWITCH_BPS=10.0


def hac(x,lags=6):
    x=np.asarray([v for v in x if np.isfinite(v)],float); n=len(x)
    if n<20:return None,None
    mu=x.mean(); e=x-mu; var=float(e@e/n)
    for lag in range(1,min(lags,n-1)+1):var+=2*(1-lag/(lags+1))*float(e[lag:]@e[:-lag]/n)
    se=math.sqrt(max(var,0)/n); t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def stats(r,ew):
    r=np.asarray(r,float); eq=np.cumprod(1+r); years=len(r)/12; t,p=hac(np.asarray(r)-np.asarray(ew))
    return {"months":len(r),"cagr":float(eq[-1]**(1/years)-1) if years else None,"sharpe":float(r.mean()/r.std(ddof=1)*math.sqrt(12)) if r.std(ddof=1)>0 else None,"max_drawdown":float((eq/np.maximum.accumulate(eq)-1).min()),"hac_active_t":t,"p_value":p}


def main():
    df=pd.read_csv(OUT/"monthly_C_PER_DATE.csv",parse_dates=["formation"])
    p=df.pivot(index="formation",columns="strategy",values="net").sort_index()
    ew=pd.read_csv(OUT/"equal_weight_C_PER_DATE.csv",parse_dates=["date"]).set_index("date")["equal_weight"]
    windows=[]; selected=[]; selected_dates=[]; prev=None; switches=0
    for start in range(TRAIN+PURGE,len(p)-TEST+1,TEST):
        train=p.iloc[start-TRAIN-PURGE:start-PURGE]; test=p.iloc[start:start+TEST]
        sh={c:float(train[c].mean()/train[c].std(ddof=1)*math.sqrt(12)) for c in p.columns if train[c].std(ddof=1)>0}
        if not sh: continue
        best=max(sh,key=sh.get)
        rr=test[best].values.astype(float)
        if prev is not None and best!=prev:
            rr=rr.copy(); rr[0]-=SWITCH_BPS/10000.0; switches+=1
        selected.extend(rr.tolist()); selected_dates.extend(test.index.tolist())
        windows.append({"test_start":str(test.index[0].date()),"test_end":str(test.index[-1].date()),
                        "train_start":str(train.index[0].date()),"train_end":str(train.index[-1].date()),
                        "train_n":len(train),"test_n":len(test),"selected":best,
                        "train_sharpes":{k:round(v,6) for k,v in sh.items()},
                        "switch_cost_bps":SWITCH_BPS if prev is not None and best!=prev else 0.0,
                        "test_return":float(np.prod(1+rr)-1)})
        prev=best
    sel=np.array(selected); ewa=np.array([ew.loc[d] for d in selected_dates])
    fixed={}
    for c in p.columns:
        # fixed strategy evaluation over the same test dates
        rr=[]; ee=[]
        for w in windows:
            idx=pd.to_datetime([w["test_start"],w["test_end"]])
            sub=p.loc[(p.index>=idx[0])&(p.index<=idx[1]),c]
            rr.extend(sub.values); ee.extend([ew.loc[d] for d in sub.index])
        fixed[c]=stats(rr,ee)
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"method":"60m train / 1m purge / 12m test; train-only strategy choice; 10bps switch cost",
            "windows":windows,"selected":stats(sel,ewa),"fixed":fixed,"switches":switches,
            "untested_tail_months":[str(d.date()) for d in p.index[len(p)-((len(p)-TRAIN-PURGE)%TEST or TEST):]],
            "status":"WALK_FORWARD_COMPLETE","note":"selected and EW aligned; strategy changes charged 10bps once."}
    (OUT/"walk_forward_results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"windows":len(windows),"switches":switches,"selected":report["selected"],"fixed":{k:v["sharpe"] for k,v in fixed.items()}},indent=2))


if __name__=="__main__":raise SystemExit(main())
