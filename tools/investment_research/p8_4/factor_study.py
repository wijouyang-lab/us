"""P8.4 market-neutral residual and conditional-alpha research."""
from __future__ import annotations
import csv, json, math
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import rankdata

ROOT=Path(".");O=ROOT/"data/research/p8_4_market_neutral_alpha";O.mkdir(parents=True,exist_ok=True)
H=(5,10,20); OOS=date(2015,1,1)


def hac(x,lags):
    x=np.asarray([v for v in x if np.isfinite(v)],float);n=len(x)
    if n<12:return None,None
    mu=x.mean();e=x-x.mean();v=float(e@e/n)
    for l in range(1,min(lags,n-1)+1):v+=2*(1-l/(lags+1))*float(e[l:]@e[:-l]/n)
    se=math.sqrt(max(v,0)/n);t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def main():
    px=pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","high","low","close","adjusted_close","volume"])
    px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>="2000-01-03")&(px.date<="2024-12-31")].copy();px["adj_open"]=px.open*px.adjusted_close/px.close
    close=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index();open_=px.pivot_table(index="date",columns="symbol",values="adj_open",aggfunc="last").reindex(close.index)
    high=px.pivot_table(index="date",columns="symbol",values="high",aggfunc="last").reindex(close.index);low=px.pivot_table(index="date",columns="symbol",values="low",aggfunc="last").reindex(close.index)
    rawclose=px.pivot_table(index="date",columns="symbol",values="close",aggfunc="last").reindex(close.index);volume=px.pivot_table(index="date",columns="symbol",values="volume",aggfunc="last").reindex(close.index)
    high=high*(close/rawclose);low=low*(close/rawclose)
    ret=close.pct_change(fill_method=None);jump=ret.abs()>5;c=close.to_numpy(float);o=open_.to_numpy(float);h=high.to_numpy(float);l=low.to_numpy(float);v=volume.to_numpy(float);r=ret.to_numpy(float)
    base=np.isfinite(c)&(c>0)&np.isfinite(o)&(o>0)&np.isfinite(h)&np.isfinite(l)&np.isfinite(v)&(v>0)&(h>=np.maximum(o,c))&(l<=np.minimum(o,c))
    shock60=pd.DataFrame(jump).rolling(60,min_periods=1).max().to_numpy(bool)
    cols=list(close.columns);dates=list(close.index.date)
    spy=pd.read_csv(O/"spy.csv",parse_dates=["Date"]).set_index("Date")["close"];spy.index=[d.date() for d in spy.index];spy=spy.reindex(dates);spy_ret=spy.pct_change()
    # rolling market model, only past data at each formation
    sr=pd.Series(spy_ret.values,index=close.index)
    cov=close.pct_change(fill_method=None).rolling(252,min_periods=126).cov(sr)
    var=sr.rolling(252,min_periods=126).var()
    beta=cov.div(var,axis=0)
    mean_i=close.pct_change(fill_method=None).rolling(252,min_periods=126).mean()
    mean_m=sr.rolling(252,min_periods=126).mean()
    alpha=mean_i.sub(beta.mul(mean_m,axis=0))
    resid=close.pct_change(fill_method=None).sub(alpha).sub(beta.mul(sr,axis=0))
    rn=resid.to_numpy(float); betan=beta.to_numpy(float)
    spy_mom60=(spy/spy.shift(60)-1).to_numpy(float)
    mom60=(close/close.shift(60)-1).to_numpy(float)
    F={
        "RESID_MOM_252": resid.rolling(252,min_periods=126).sum().shift(21).to_numpy(float),
        "RESID_REV_5": -resid.rolling(5,min_periods=5).sum().to_numpy(float),
        "RESID_REV_20": -resid.rolling(20,min_periods=20).sum().to_numpy(float),
        "IDIO_VOL_60": -(resid.rolling(60,min_periods=40).std()*math.sqrt(252)).to_numpy(float),
        "DOWNSIDE_IDIO_60": -(resid.clip(upper=0).rolling(60,min_periods=40).std()*math.sqrt(252)).to_numpy(float),
        "RESID_TREND_PERSIST_60": np.sign(resid).rolling(60,min_periods=40).mean().to_numpy(float),
        "BETA_ADJ_MOM_60": mom60 - betan*spy_mom60[:,None],
    }
    # market states, all observable at formation
    spy_ma200=spy.rolling(200,min_periods=200).mean()
    spy_trend=(spy>spy_ma200).astype(float).to_numpy()
    spy_vol20=spy_ret.rolling(20).std().mul(math.sqrt(252)).to_numpy()
    spy_vol60=spy_ret.rolling(60).std().mul(math.sqrt(252)).to_numpy()
    ma200c=close.rolling(200,min_periods=200).mean().to_numpy(float)
    m=pd.read_csv(ROOT/"data/research/historical_universe/sp500_daily.csv");m["date"]=pd.to_datetime(m.date).dt.date;m=m.drop_duplicates("date").sort_values("date")
    ms={row.date:{x.strip().upper() for x in str(row.tickers).split(",") if x.strip()} for row in m.itertuples()}
    # labels and state arrays
    labels={}; future_shock={}
    for hz in H:
        entry=np.roll(o,-1,axis=0);exitp=np.roll(o,-(hz+1),axis=0);lab=exitp/entry-1
        fs=pd.DataFrame(jump).rolling(hz+1,min_periods=1).max().shift(-hz-1).to_numpy(bool)
        lab[~np.isfinite(lab)]=np.nan;lab[fs]=np.nan;labels[hz]=lab;future_shock[hz]=fs
    states=[]
    for i,d in enumerate(dates):
        mem=ms.get(d,set());idx=[k for k,t in enumerate(cols) if t in mem]
        val=[k for k in idx if base[i,k] and not shock60[i,k] and np.isfinite(ma200c[i,k])]
        above=sum(1 for k in val if c[i,k]>ma200c[i,k]);rr=[r[i,k] for k in val if np.isfinite(r[i,k])]
        states.append({"date":d,"spy_trend":float(spy_trend[i]) if np.isfinite(spy_trend[i]) else np.nan,"spy_vol20":float(spy_vol20[i]) if np.isfinite(spy_vol20[i]) else np.nan,"spy_vol60":float(spy_vol60[i]) if np.isfinite(spy_vol60[i]) else np.nan,"breadth":above/len(val) if len(val)>=30 else np.nan,"dispersion":float(np.std(rr,ddof=1)) if len(rr)>=30 else np.nan,"advance":float(np.mean([x>0 for x in rr])) if rr else np.nan,"effective":len(val)})
    state=pd.DataFrame(states).set_index("date")
    # sample dates (non-overlapping), same as P8.3 style
    sample={hz:[i for i in range(200,len(dates)-hz-2,hz) if dates[i] in ms] for hz in H}
    # IC/FM/quantile
    ic_rows=[];fm_rows=[];q_rows=[];series=[];reg_rows=[]
    factor_names=list(F)
    def cross(i,ff,hz):
        mem=ms[dates[i]];idx=[k for k,t in enumerate(cols) if t in mem]
        return [k for k in idx if base[i,k] and not shock60[i,k] and np.isfinite(ff[i,k]) and np.isfinite(labels[hz][i,k])]
    for fn,ff in F.items():
        for hz in H:
            ics=[];top=[];bottom=[];fm=[];valid=[];lab=[]
            for i in sample[hz]:
                idx=cross(i,ff,hz)
                if len(idx)<30:continue
                x=ff[i,idx];y=labels[hz][i,idx]
                if np.all(x==x[0]) or np.all(y==y[0]):continue
                ic=float(np.corrcoef(rankdata(x),rankdata(y))[0,1])
                if not np.isfinite(ic):continue
                ics.append((dates[i],ic));order=np.argsort(x);q=max(1,len(order)//5)
                top.append(float(np.mean(y[order[-q:]])));bottom.append(float(np.mean(y[order[:q]])))
                X=np.column_stack([np.ones(len(idx)),(x-np.mean(x))/(np.std(x) or 1)])
                coef=np.linalg.lstsq(X,y,rcond=None)[0];fm.append(float(coef[1]));valid.append(len(idx));lab.append(len(idx))
            if len(ics)<12:continue
            vals=np.array([x for _,x in ics]);t,p=hac(vals,max(1,hz//5));fmb=np.array(fm);fmt,fmp=hac(fmb,1)
            ic_rows.append({"factor":fn,"horizon":hz,"mean_ic":float(vals.mean()),"ic_std":float(vals.std(ddof=1)),"icir":float(vals.mean()/vals.std(ddof=1)*math.sqrt(252/hz)) if vals.std(ddof=1) else None,"n_dates":len(vals),"avg_names":float(np.mean(valid)),"hac_t":t,"p_value":p})
            fm_rows.append({"factor":fn,"horizon":hz,"mean_fm_coef":float(fmb.mean()),"fm_t":fmt,"p_value":fmp,"n_dates":len(fmb)})
            q_rows.append({"factor":fn,"horizon":hz,"top":float(np.mean(top)),"bottom":float(np.mean(bottom)),"top_minus_bottom":float(np.mean(top)-np.mean(bottom)),"n_dates":len(top)})
            series += [{"factor":fn,"horizon":hz,"date":str(d),"ic":v} for d,v in ics]
    ic=pd.DataFrame(ic_rows);fm=pd.DataFrame(fm_rows);q=pd.DataFrame(q_rows)
    # BH across 7*3
    ps=ic.sort_values("p_value");qs=[]
    for rank,p in enumerate(ps.p_value,1):qs.append(min(1.0,float(p)*len(ps)/rank))
    ps["bh_q"]=qs;ic=ic.merge(ps[["factor","horizon","bh_q"]],on=["factor","horizon"],how="left")
    ic.to_csv(O/"factor_ic_results.csv",index=False);fm.to_csv(O/"factor_fama_macbeth.csv",index=False);q.to_csv(O/"factor_quantile_results.csv",index=False);pd.DataFrame(series).to_csv(O/"factor_ic_timeseries.csv",index=False)
    ic[["factor","horizon","hac_t","p_value","bh_q"]].to_csv(O/"factor_hac_results.csv",index=False);ic[["factor","horizon","bh_q"]].to_csv(O/"factor_bh_results.csv",index=False)
    # correlation of IC series
    st=pd.DataFrame(series);corr_rows=[]
    for hz in H:
        piv=st[st.horizon==hz].pivot(index="date",columns="factor",values="ic")
        cm=piv.corr(min_periods=12)
        for a in cm.index:
            for b in cm.columns:
                if a<b and np.isfinite(cm.loc[a,b]):corr_rows.append({"factor_a":a,"factor_b":b,"horizon":hz,"ic_corr":float(cm.loc[a,b])})
    pd.DataFrame(corr_rows).to_csv(O/"factor_correlation.csv",index=False)
    # regime conditional IC for pre-registered interactions
    reg=[]
    conditions=[("RESID_MOM_252","spy_trend",lambda s:s["spy_trend"]>=0.5),("RESID_REV_5","spy_vol20",lambda s:s["spy_vol20"]>=state.spy_vol20.median()),("RESID_MOM_252","breadth",lambda s:s["breadth"]>=state.breadth.median()),("RESID_MOM_252","dispersion",lambda s:s["dispersion"]>=state.dispersion.median()),("BETA_ADJ_MOM_60","breadth",lambda s:s["breadth"]>=state.breadth.median()),("DOWNSIDE_IDIO_60","spy_vol20",lambda s:s["spy_vol20"]>=state.spy_vol20.median())]
    for fn,cond,fnc in conditions:
        for hz in H:
            for label,flag in (("HIGH",True),("LOW",False)):
                vals=[]
                for i in sample[hz]:
                    if i>=len(state):continue
                    s=state.iloc[i]
                    ok=fnc(s) if flag else not fnc(s)
                    if not ok or not np.isfinite(s.get(cond,np.nan)):continue
                    idx=cross(i,F[fn],hz)
                    if len(idx)<30:continue
                    x=F[fn][i,idx];y=labels[hz][i,idx]
                    if np.all(x==x[0]) or np.all(y==y[0]):continue
                    v=float(np.corrcoef(rankdata(x),rankdata(y))[0,1])
                    if np.isfinite(v):vals.append(v)
                if len(vals)>=10:
                    t,p=hac(vals,1);reg.append({"factor":fn,"condition":cond,"regime":label,"horizon":hz,"mean_ic":float(np.mean(vals)),"n_dates":len(vals),"hac_t":t,"p_value":p})
    pd.DataFrame(reg).to_csv(O/"factor_regime_results.csv",index=False)
    # robustness by periods
    rob=[]
    for fn in factor_names:
        for hz in H:
            sv=[x for x in series if x["factor"]==fn and x["horizon"]==hz]
            vals={}
            for name,a,b in (("2000-2007",date(2000,1,1),date(2007,12,31)),("2008-2015",date(2008,1,1),date(2015,12,31)),("2016-2024",date(2016,1,1),date(2024,12,31))):
                qv=[x["ic"] for x in sv if a<=date.fromisoformat(x["date"])<=b];vals[name]=float(np.mean(qv)) if qv else None
            rob.append({"factor":fn,"horizon":hz,**vals,"sign_stable":len({x>0 for x in vals.values() if x is not None})==1})
    pd.DataFrame(rob).to_csv(O/"factor_robustness.csv",index=False)
    # definitions/manifest/status
    defs={k:{"formula":"residual return factor using 252d market model, min 126 obs","window":252,"direction":1,"economic":"market-neutral stock-specific signal"} for k in F}
    (O/"factor_definitions.json").write_text(json.dumps(defs,indent=2),encoding="utf-8")
    manifest={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P8_4_MARKET_NEUTRAL_RESEARCH","as_of":"2024-12-31","factors":len(F),"horizons":list(H),"sample_dates":{str(k):len(v) for k,v in sample.items()},"beta_model":{"window":252,"min_obs":126,"market":"SPY"},"prices":"finsaber_prices_raw.csv","membership":"sp500_daily.csv","note":"all factor inputs use data through formation date; post-hoc classification not used"}
    (O/"p8_4_research_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P8_4_MARKET_NEUTRAL_RESEARCH","as_of":"2024-12-31","factors":len(F),"ic_rows":len(ic),"fm_rows":len(fm),"regime_rows":len(reg),"go_count":0,"data_blocked":["NDX/DJI history","historical fundamental PIT","event/macro PIT"],"note":"Requires BH and OOS; no shadow."}
    (O/"p8_4_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"factors":len(F),"ic_rows":len(ic),"regime_rows":len(reg),"top":ic.sort_values("bh_q").head(5)[["factor","horizon","mean_ic","hac_t","bh_q"]].to_dict("records")},indent=2))


if __name__=="__main__":raise SystemExit(main())
