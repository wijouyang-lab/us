"""P8.2 methods A/B/C: raw, whole-history exclusion, per-date isolation + fixed costs."""
from __future__ import annotations
import csv, json, math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(".")
P8 = ROOT / "data/research/p8"
OUT = ROOT / "data/research/p8_2"
OUT.mkdir(parents=True, exist_ok=True)
AS_OF = date(2024, 12, 31); TOP_N = 20; COST_BPS = 10.0


def members():
    m = pd.read_csv(ROOT/"data/research/historical_universe/sp500_daily.csv")
    m["date"] = pd.to_datetime(m.date).dt.date
    return m.drop_duplicates("date").sort_values("date")


def bad_map():
    d = defaultdict(set)
    with (OUT/"ticker_anomaly_audit.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f): d[r["ticker"]].add(date.fromisoformat(r["anomaly_date"]))
    return d


def metrics(r, ew_same):
    r = np.asarray(r, float); eq = np.cumprod(1+r); years=len(r)/12
    ex = np.asarray([a-b for a,b in zip(r, ew_same)], float); t,p = hac(ex)
    return {"months":len(r), "cagr":float(eq[-1]**(1/years)-1) if years else None,
            "vol":float(r.std(ddof=1)*math.sqrt(12)), "sharpe":float(r.mean()/r.std(ddof=1)*math.sqrt(12)),
            "max_drawdown":float((eq/np.maximum.accumulate(eq)-1).min()), "hac_active_t":t, "p_value":p}


def hac(x,lags=6):
    x=np.asarray(x,float); n=len(x)
    if n<20:return None,None
    mu=x.mean(); e=x-mu; var=float(e@e/n)
    for lag in range(1,min(lags,n-1)+1): var+=2*(1-lag/(lags+1))*float(e[lag:]@e[:-lag]/n)
    se=math.sqrt(max(var,0)/n); t=mu/se if se else None
    from math import erf,sqrt
    return t, (2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def main():
    px=pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","close","adjusted_close"])
    px["date"]=pd.to_datetime(px.date); px["symbol"]=px.symbol.str.upper()
    px=px[(px.date>="2000-01-03")&(px.date<="2024-12-31")].copy(); px["adj_open"]=px.open*px.adjusted_close/px.close
    close=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index()
    open_=px.pivot_table(index="date",columns="symbol",values="adj_open",aggfunc="last").reindex(close.index)
    factors={"MOMENTUM_20":close/close.shift(20)-1,"MOMENTUM_60":close/close.shift(60)-1,
             "MOMENTUM_120":close/close.shift(120)-1,"TREND_MA200":close/close.rolling(200).mean()-1,
             "LOW_VOL_60":-(close.pct_change().rolling(60).std()*math.sqrt(252)),"REVERSAL_5":-(close/close.shift(5)-1)}
    m=members(); md=list(m.date); mt=list(m.tickers); bad=bad_map(); bad_set=set(px.loc[px.symbol.isin([t for t in bad]),"symbol"])
    dates=list(close.index.date); pos={d:i for i,d in enumerate(dates)}
    s=pd.Series(dates,index=pd.to_datetime(dates)); month_ends=list(s.groupby([s.index.year,s.index.month]).last().values)
    all_out={}
    for method in ("A_RAW","B_EXCLUDE_ALL","C_PER_DATE"):
        ret={k:[] for k in factors}; ewr=[]; mrows=[]; prev={k:set() for k in factors}; ewp=[]
        for mi,mdte in enumerate(month_ends[:-1]):
            p=np.searchsorted(md,mdte,side="right")-1
            if p<0: continue
            mem={x.strip().upper() for x in str(mt[p]).split(",") if x.strip()}
            if method!="A_RAW": mem=mem-bad_set
            di=pos.get(mdte); ndi=pos.get(month_ends[mi+1])
            if di is None or ndi is None or di+1>=len(dates) or ndi+1>=len(dates): continue
            entry=dates[di+1]; exitd=dates[ndi+1]
            cols=[c for c in close.columns if c in mem]
            avail=[c for c in cols if pd.notna(close.loc[pd.Timestamp(mdte),c]) and pd.notna(open_.loc[pd.Timestamp(entry),c]) and pd.notna(open_.loc[pd.Timestamp(exitd),c])]
            if method=="C_PER_DATE":
                avail=[c for c in avail if not any(entry<=d<=exitd for d in bad.get(c,set()))]
            if len(avail)<30: continue
            er=float(np.mean([open_.loc[pd.Timestamp(exitd),c]/open_.loc[pd.Timestamp(entry),c]-1 for c in avail]))
            ewr.append(er); ewp.append(str(mdte))
            for name,f in factors.items():
                vals=[(c,f.loc[pd.Timestamp(mdte),c]) for c in avail if pd.notna(f.loc[pd.Timestamp(mdte),c]) and np.isfinite(f.loc[pd.Timestamp(mdte),c])]
                vals.sort(key=lambda z:-z[1]); hold={c for c,_ in vals[:TOP_N]}
                gross=float(np.mean([open_.loc[pd.Timestamp(exitd),c]/open_.loc[pd.Timestamp(entry),c]-1 for c in hold])) if hold else None
                if gross is None: ret[name].append(None); continue
                # total two-sided traded fraction for equal-weight sets:
                turn=len(hold ^ prev[name])/len(hold)  # additions+removals
                net=gross - COST_BPS/10000.0*turn  # 10bps per side; turn already sums both sides
                ret[name].append(net); mrows.append({"method":method,"strategy":name,"formation":str(mdte),"gross":gross,"net":net,"turnover_two_sided":turn,"n":len(hold)}); prev[name]=hold
        # align EW to same month count; EW and ret lists share months except missing holds
        ew=np.asarray(ewr, dtype=float).ravel()
        for name,xs in ret.items():
            vals=[(d,x) for d,x in zip(ewp,xs) if x is not None]
            rr=[x for _,x in vals]; ewv=[ew[ewp.index(d)] for d,_ in vals]
            all_out.setdefault(method,{})[name]={**metrics(rr,ewv),"cost_bps_per_side":COST_BPS,
                                                   "cost_model":"total two-sided traded notional x 10bps; no x2",
                                                   "coverage":len(avail)/len(cols) if cols else None}
        pd.DataFrame(mrows).to_csv(OUT/f"monthly_{method}.csv",index=False)
        all_out.setdefault(method,{})["_equal_weight"]= {"cagr":float(np.cumprod(1+ew)[-1]**(12/len(ew))-1),
                                                          "months":len(ew),"sharpe":float(np.mean(ew)/np.std(ew,ddof=1)*math.sqrt(12))}
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"as_of":AS_OF.isoformat(),
            "methods":{"A_RAW":"no anomaly filtering","B_EXCLUDE_ALL":"P8.1 diagnostic; all 109 removed",
                       "C_PER_DATE":"formal: isolate anomalous ticker-dates; no retroactive history deletion"},
            "cost":{"bps_per_side":10.0,"formula":"turnover_two_sided = |hold XOR prev|/n; cost = bps * turnover_two_sided"},
            "results":all_out,"status":"P8_2_METHOD_COMPARISON"}
    (OUT/"method_comparison.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({m:{k:{kk:v[kk] for kk in ("cagr","oos_cagr" if False else "sharpe","hac_active_t","max_drawdown")} for k,v in x.items() if k!="_equal_weight"} for m,x in all_out.items()},indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
