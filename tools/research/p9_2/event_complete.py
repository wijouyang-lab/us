"""P9.2 complete event table: absolute and relative returns, HAC, BH, CI."""
from __future__ import annotations
import csv,gzip,json,math
from datetime import date
from pathlib import Path
import numpy as np,pandas as pd

O=Path("data/research/p9_2_benchmark_audit");P91=Path("data/research/p9_1_support_resistance")


def hac(x,lags):
    x=np.asarray([v for v in x if np.isfinite(v)],float);n=len(x)
    if n<10:return None,None,None
    mu=x.mean();e=x-mu;v=float(e@e/n)
    for lag in range(1,min(lags,n-1)+1):v+=2*(1-lag/(lags+1))*float(e[lag:]@e[:-lag]/n)
    se=math.sqrt(max(v,0)/n);t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None),se


def main():
    px=pd.read_csv("data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","close","adjusted_close"])
    px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>="2000-01-01")&(px.date<="2024-12-31")].copy();px["adj_open"]=px.open*px.adjusted_close/px.close
    op=px.pivot_table(index="date",columns="symbol",values="adj_open",aggfunc="last").sort_index();dates=[d.date() for d in op.index];cols=list(op.columns);pos={d:i for i,d in enumerate(dates)};cp={t:i for i,t in enumerate(cols)}
    spy=pd.read_csv(P91/"spy.csv",parse_dates=["Date"]).set_index("Date")["close"];spy.index=[d.date() for d in spy.index];spy=spy.reindex(dates)
    bil=pd.read_csv(P91/"bil.csv",parse_dates=["Date"]).set_index("Date")["close"];bil.index=[d.date() for d in bil.index];bil=bil.reindex(dates)
    sr=spy.pct_change().to_numpy();br=bil.pct_change().to_numpy()
    ev=list(csv.DictReader(gzip.open(P91/"p9_1_signals.csv.gz","rt",encoding="utf-8")))
    # collapse duplicate signal rows per experiment/date/ticker
    uniq={}
    for e in ev:uniq[(e["experiment"],e["date"],e["ticker"])]=e
    rows=[]
    for exp in sorted({e["experiment"] for e in ev}):
        for hz in (5,10,20):
            rets=[];sp=[];bl=[];nr=[]
            for (x,d,tk),e in uniq.items():
                if x!=exp:continue
                i=pos.get(date.fromisoformat(d));j=cp.get(tk)
                if i is None or j is None or i+hz+1>=len(dates):continue
                r=op.iloc[i+hz+1,j]/op.iloc[i+1,j]-1
                if not np.isfinite(r):continue
                rets.append(float(r));sp.append(float(np.prod(1+sr[i+1:i+1+hz])-1));bl.append(float(np.prod(1+br[i+1:i+1+hz])-1))
            if len(rets)<10:continue
            tstat,pval,se=hac(rets,max(1,hz//5));_,ps,_=hac(sp,max(1,hz//5));_,pb,_=hac(bl,max(1,hz//5))
            ci=(float(np.mean(rets)-1.96*se),float(np.mean(rets)+1.96*se)) if se else (None,None)
            sp_arr=np.array(sp,float);bl_arr=np.array(bl,float);ret_arr=np.array(rets,float)
            # same non-overlap rule as P9.1
            seen={};non=[]
            for (x,d,tk),e in uniq.items():
                if x!=exp:continue
                i=pos.get(date.fromisoformat(d));j=cp.get(tk)
                if i is None or j is None or i+hz+1>=len(dates):continue
                r=op.iloc[i+hz+1,j]/op.iloc[i+1,j]-1
                if not np.isfinite(r):continue
                if tk not in seen or (date.fromisoformat(d)-seen[tk]).days>=hz*7//5:non.append(float(r));seen[tk]=date.fromisoformat(d)
            nts,_,_=hac(non,max(1,hz//5)) if len(non)>=10 else (None,None,None)
            rows.append({"experiment":exp,"horizon":hz,"events":len(rets),"mean_return":float(np.mean(rets)),"mean_excess_spy":float(np.nanmean(ret_arr-sp_arr)),"mean_excess_bil":float(np.nanmean(ret_arr-bl_arr)),"excess_bil_n":int(np.isfinite(ret_arr-bl_arr).sum()),"positive_rate":float(np.mean(ret_arr>0)),"hac_t":tstat,"p_value":pval,"ci95_low":ci[0],"ci95_high":ci[1],"nonoverlap_events":len(non),"nonoverlap_mean":float(np.mean(non)) if non else None,"nonoverlap_hac_t":nts})
    df=pd.DataFrame(rows);ps=df.dropna(subset=["p_value"]).sort_values("p_value");q=[]
    for rank,pv in enumerate(ps.p_value,1):q.append(min(1.0,float(pv)*len(ps)/rank))
    ps["bh_q"]=q;df=df.merge(ps[["experiment","horizon","bh_q"]],on=["experiment","horizon"],how="left");df.to_csv(O/"event_stats_complete.csv",index=False)
    print(df[["experiment","horizon","events","mean_return","mean_excess_spy","mean_excess_bil","hac_t","bh_q","ci95_low","ci95_high","nonoverlap_events"]].to_string(index=False))


if __name__=="__main__":raise SystemExit(main())
