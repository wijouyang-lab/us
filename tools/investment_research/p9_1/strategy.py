"""P9.1 support/resistance + candlestick + MACD/KDJ event research."""
from __future__ import annotations
import csv,json,math
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p9_1_support_resistance";O.mkdir(parents=True,exist_ok=True)
ATR_N=14;PIV=5;LOOK=252;CLUSTER=0.5


def atr14(h,l,c):
    pc=pd.DataFrame(c).shift(1).to_numpy()
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.DataFrame(tr).rolling(ATR_N,min_periods=ATR_N).mean().to_numpy()


def macd(c):
    s=pd.DataFrame(c)
    dif=s.ewm(span=12,adjust=False).mean().to_numpy()-s.ewm(span=26,adjust=False).mean().to_numpy()
    dea=pd.DataFrame(dif).ewm(span=9,adjust=False).mean().to_numpy()
    hist=dif-dea
    return dif,dea,hist


def kdj(h,l,c):
    hh=pd.DataFrame(h).rolling(9,min_periods=9).max().to_numpy();ll=pd.DataFrame(l).rolling(9,min_periods=9).min().to_numpy()
    rsv=(c-ll)/np.maximum(hh-ll,1e-12)*100
    k=np.full_like(c,np.nan);d=np.full_like(c,np.nan);k[8]=50;d[8]=50
    for i in range(9,c.shape[0]):
        k[i]=2/3*k[i-1]+1/3*rsv[i];d[i]=2/3*d[i-1]+1/3*k[i]
    return k,d,3*k-2*d


def pivot_arrays(low,high):
    s=pd.DataFrame(low);pl=(s < s.shift(1)) & (s < s.shift(2)) & (s < s.shift(3)) & (s < s.shift(4)) & (s < s.shift(5)) & (s < s.shift(-1)) & (s < s.shift(-2)) & (s < s.shift(-3)) & (s < s.shift(-4)) & (s < s.shift(-5))
    sh=pd.DataFrame(high);ph=(sh > sh.shift(1)) & (sh > sh.shift(2)) & (sh > sh.shift(3)) & (sh > sh.shift(4)) & (sh > sh.shift(5)) & (sh > sh.shift(-1)) & (sh > sh.shift(-2)) & (sh > sh.shift(-3)) & (sh > sh.shift(-4)) & (sh > sh.shift(-5))
    return pl.to_numpy(),ph.to_numpy()


def main():
    px=pd.read_csv("data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","high","low","close","adjusted_close","volume"])
    px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>="2000-01-03")&(px.date<="2024-12-31")].copy();px["adj_open"]=px.open*px.adjusted_close/px.close
    c=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index();o=px.pivot_table(index="date",columns="symbol",values="adj_open",aggfunc="last").reindex(c.index)
    h=px.pivot_table(index="date",columns="symbol",values="high",aggfunc="last").reindex(c.index);l=px.pivot_table(index="date",columns="symbol",values="low",aggfunc="last").reindex(c.index)
    rawc=px.pivot_table(index="date",columns="symbol",values="close",aggfunc="last").reindex(c.index);v=px.pivot_table(index="date",columns="symbol",values="volume",aggfunc="last").reindex(c.index)
    h=h*(c/rawc);l=l*(c/rawc)
    cn=c.to_numpy(float);on=o.to_numpy(float);hn=h.to_numpy(float);ln=l.to_numpy(float);vn=v.to_numpy(float);cols=list(c.columns);dates=list(c.index.date)
    daily_ret=pd.DataFrame(cn).pct_change(fill_method=None); jump=daily_ret.abs()>5.0; shock60=jump.rolling(60,min_periods=1).max().to_numpy(bool)
    base=np.isfinite(cn)&(cn>0)&np.isfinite(on)&(on>0)&np.isfinite(hn)&np.isfinite(ln)&np.isfinite(vn)&(vn>0)&(hn>=np.maximum(on,cn))&(ln<=np.minimum(on,cn))&~shock60
    m=pd.read_csv("data/research/historical_universe/sp500_daily.csv");m["date"]=pd.to_datetime(m.date).dt.date;m=m.drop_duplicates("date").sort_values("date")
    members={row.date:{x.strip().upper() for x in str(row.tickers).split(",") if x.strip()} for row in m.itertuples()}
    member_mask=np.zeros_like(base)
    for ii,d in enumerate(dates):
        idx=[kk for kk,t in enumerate(cols) if t in members.get(d,set())]
        member_mask[ii,idx]=True
    base &= member_mask
    atr=atr14(hn,ln,cn);dif,dea,hist=macd(cn);k,d,j=kdj(hn,ln,cn)
    macd_bull=(dif>dea)&(dif-dea>np.roll(dif-dea,1,axis=0));macd_bear=(dif<dea)&(dif-dea<np.roll(dif-dea,1,axis=0))
    kdj_bull=(k>d)&(k>np.roll(k,1,axis=0));kdj_bear=(k<d)&(k<np.roll(k,1,axis=0))
    # pivot levels and confirmation at i+5
    pl,ph=pivot_arrays(ln,hn)
    plv=np.where(pl,ln,np.nan);phv=np.where(ph,hn,np.nan)
    # keep only pivots confirmed by t-5; touch count in last 252 sessions
    pl_known=pd.DataFrame(pl).shift(5).rolling(LOOK,min_periods=1).sum().to_numpy()>=2
    ph_known=pd.DataFrame(ph).shift(5).rolling(LOOK,min_periods=1).sum().to_numpy()>=2
    lev_low=pd.DataFrame(plv).shift(5).ffill().to_numpy();lev_high=pd.DataFrame(phv).shift(5).ffill().to_numpy()
    pl_count=pd.DataFrame(pl).shift(5).rolling(LOOK,min_periods=1).sum().to_numpy();ph_count=pd.DataFrame(ph).shift(5).rolling(LOOK,min_periods=1).sum().to_numpy()
    sup=base&pl_known&(np.abs(ln-lev_low)<=CLUSTER*atr)
    res=base&ph_known&(np.abs(hn-lev_high)<=CLUSTER*atr)
    pivot_low_date=pd.DataFrame(np.where(pl,np.arange(len(dates))[:,None],np.nan)).shift(5).ffill().to_numpy()
    pivot_high_date=pd.DataFrame(np.where(ph,np.arange(len(dates))[:,None],np.nan)).shift(5).ffill().to_numpy()
    # patterns
    body=np.abs(cn-on);up=cn>on;dn=cn<on
    pb=np.roll(body,1,axis=0);pup=np.roll(up,1,axis=0);pdn=np.roll(dn,1,axis=0);po=np.roll(on,1,axis=0);pc=np.roll(cn,1,axis=0)
    bull_eng=up&pdn&(on<=pc)&(cn>=po)&np.isfinite(pc)
    bear_eng=dn&pup&(on>=pc)&(cn<=po)&np.isfinite(pc)
    b2=np.roll(body,2,axis=0);u2=np.roll(up,2,axis=0);d2=np.roll(dn,2,axis=0);o2=np.roll(on,2,axis=0);c2=np.roll(cn,2,axis=0)
    bull_star=u2&(body<=0.5*b2)&(b2>=0.5*atr)&up&(cn>(o2+c2)/2)
    bear_star=d2&(body<=0.5*b2)&(b2>=0.5*atr)&dn&(cn<(o2+c2)/2)
    bull_pat=bull_eng|bull_star;bear_pat=bear_eng|bear_star
    # experiment masks: long entries only
    groups={
        "A_LEVEL_TOUCH":sup,
        "B_PATTERN_ONLY":bull_pat,
        "C_SUPPORT_PATTERN":bull_pat&sup,
        "D_C_MACD":bull_pat&sup&macd_bull,
        "E_C_KDJ":bull_pat&sup&kdj_bull,
        "F_C_BOTH":bull_pat&sup&macd_bull&kdj_bull,
        "G_LEVEL_ALL_PATTERNS":bull_pat&sup,
        "H_G_BOTH":bull_pat&sup&macd_bull&kdj_bull,
    }
    # SPY/BIL alignment
    spy=pd.read_csv(O/"spy.csv",parse_dates=["Date"]).set_index("Date")["close"];spy.index=[x.date() for x in spy.index];spy=spy.reindex(dates)
    bil=pd.read_csv(O/"bil.csv",parse_dates=["Date"]).set_index("Date")["close"];bil.index=[x.date() for x in bil.index];bil=bil.reindex(dates)
    spy_ret=spy.pct_change().to_numpy();bil_ret=bil.pct_change().to_numpy()
    # forward labels next open
    lab={}
    for hz in (5,10,20):
        entry=np.roll(on,-1,axis=0);exitp=np.roll(on,-(hz+1),axis=0);lab[hz]=exitp/entry-1
        fs=jump.rolling(hz+1,min_periods=1).max().shift(-hz-1).to_numpy(bool)
        lab[hz][~np.isfinite(lab[hz])]=np.nan;lab[hz][-hz-2:,:]=np.nan;lab[hz][fs]=np.nan
    # event extraction
    events=[];event_stats=[];date_pos={d:i for i,d in enumerate(dates)};col_pos={t:i for i,t in enumerate(cols)}
    for gname,mask in groups.items():
        coords=np.argwhere(mask & base)
        for i,j in coords:
            # only use events after 210 sessions and with future open available
            events.append({"experiment":gname,"date":str(dates[i]),"ticker":cols[j],"support":bool(sup[i,j]),"resistance":bool(res[i,j]),"support_level":float(lev_low[i,j]) if np.isfinite(lev_low[i,j]) else "","resistance_level":float(lev_high[i,j]) if np.isfinite(lev_high[i,j]) else "","atr":float(atr[i,j]) if np.isfinite(atr[i,j]) else "","distance_atr":float((ln[i,j]-lev_low[i,j])/atr[i,j]) if np.isfinite(atr[i,j]) and np.isfinite(lev_low[i,j]) else "","support_touches":int(pl_count[i,j]) if np.isfinite(pl_count[i,j]) else 0,"resistance_touches":int(ph_count[i,j]) if np.isfinite(ph_count[i,j]) else 0,"pivot_low_date":str(dates[int(pivot_low_date[i,j])]) if np.isfinite(pivot_low_date[i,j]) else "","pivot_high_date":str(dates[int(pivot_high_date[i,j])]) if np.isfinite(pivot_high_date[i,j]) else "","bull_engulf":bool(bull_eng[i,j]),"morning_star":bool(bull_star[i,j]),"macd":bool(macd_bull[i,j]),"kdj":bool(kdj_bull[i,j])})
    with (O/"p9_1_signals.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(events[0].keys()));w.writeheader();w.writerows(events)
    # HAC + event stats; use unique event dates for benchmark alignment
    def hac(x,lags):
        x=np.asarray([x for x in x if np.isfinite(x)],float);n=len(x)
        if n<10:return None,None
        mu=x.mean();e=x-mu;v=float(e@e/n)
        for lag in range(1,min(lags,n-1)+1):v+=2*(1-lag/(lags+1))*float(e[lag:]@e[:-lag]/n)
        se=math.sqrt(max(v,0)/n);t=mu/se if se else None
        from math import erf,sqrt
        return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)
    for gname in groups:
        for hz in (5,10,20):
            rr=[];ex=[];raw=[]
            for e in events:
                if e["experiment"]!=gname:continue
                i=date_pos[date.fromisoformat(e["date"])];j=col_pos[e["ticker"]]
                r=lab[hz][i,j]
                if not np.isfinite(r):continue
                rr.append(float(r));raw.append((date.fromisoformat(e["date"]),e["ticker"],float(r)))
                sr=spy_ret[i+1:i+1+hz]
                if len(sr)==hz and np.isfinite(sr).all(): ex.append(float(r-(np.prod(1+sr)-1)))
            if len(rr)<10:continue
            t,p=hac(rr,max(1,hz//5));t2,p2=hac(ex,max(1,hz//5))
            by=defaultdict(list)
            for dd,tk,vv in raw:by[tk].append((dd,vv))
            non=[]
            for tk,vals in by.items():
                last=None
                for dd,vv in sorted(vals):
                    if last is None or (dd-last).days>=hz*7//5:
                        non.append(vv);last=dd
            nt,npv=hac(non,max(1,hz//5)) if len(non)>=10 else (None,None)
            event_stats.append({"experiment":gname,"horizon":hz,"events":len(rr),"mean_return":float(np.mean(rr)),"positive_rate":float(np.mean(np.array(rr)>0)),"hac_t":t,"p_value":p,"excess_spy":float(np.mean(ex)) if ex else None,"excess_hac_t":t2,"p_excess":p2,"nonoverlap_events":len(non),"nonoverlap_mean":float(np.mean(non)) if non else None,"nonoverlap_hac_t":nt,"nonoverlap_p":npv})
    edf=pd.DataFrame(event_stats);edf.to_csv(O/"event_results_raw.csv",index=False)
    psn=edf.dropna(subset=["nonoverlap_p"]).sort_values("nonoverlap_p");qsn=[]
    for rank,pv in enumerate(psn.nonoverlap_p,1):qsn.append(min(1.0,float(pv)*len(psn)/rank))
    psn["nonoverlap_bh_q"]=qsn;edf=edf.merge(psn[["experiment","horizon","nonoverlap_bh_q"]],on=["experiment","horizon"],how="left")
    ps=edf.dropna(subset=["p_value"]).sort_values("p_value");qs=[]
    for rank,p in enumerate(ps.p_value,1):qs.append(min(1.0,float(p)*len(ps)/rank))
    ps["bh_q"]=qs;edf=edf.merge(ps[["experiment","horizon","bh_q"]],on=["experiment","horizon"],how="left")
    edf.to_csv(O/"event_results.csv",index=False);edf[["experiment","horizon","hac_t","p_value","bh_q"]].to_csv(O/"event_hac.csv",index=False);edf[["experiment","horizon","bh_q"]].to_csv(O/"event_bh.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P9_1_EVENT_RESEARCH","as_of":"2024-12-31","patterns":["bullish_engulfing","bearish_engulfing","morning_star","evening_star"],"experiments":list(groups),"events":len(events),"event_rows":len(edf),"data_blocked":["portfolio not run unless event evidence passes"],"note":"PIT support levels confirmed at pivot+5; no future pivot; entry next open."}
    (O/"p9_1_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"events":len(events),"event_rows":len(edf),"top":edf.sort_values("bh_q").head(10)[["experiment","horizon","events","mean_return","hac_t","bh_q"]].to_dict("records")},indent=2))


if __name__=="__main__":raise SystemExit(main())
