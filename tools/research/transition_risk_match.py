#!/usr/bin/env python3
"""Risk-matched passive QQQ/BIL comparison to PR438 Transition."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd
from tools.research.ibkr_costs import fees

START = "2007-05-30"; END = "2026-10-30"; SLIP_BPS = 10.0
CONFIG = "w25_c10_all_legs"


def load(t, path):
    d = pd.read_csv(path); cols = {c.lower().replace(" ", "_"): c for c in d.columns}
    o = pd.DataFrame({"Date": pd.to_datetime(d[cols["date"]], utc=True).dt.tz_convert(None).dt.normalize(),
                      "Open": pd.to_numeric(d[cols["open"]], errors="coerce"),
                      "Close": pd.to_numeric(d[cols["close"]], errors="coerce"),
                      "Dividends": pd.to_numeric(d[cols["dividends"]], errors="coerce").fillna(0.0)}).dropna()
    return o.sort_values("Date").set_index("Date")


class Acct:
    def __init__(self, f, slip):
        self.f=f; self.slip=slip; self.cash=50000.0; self.shares={}; self.legs=[]; self.navs=[]
        self.dividend_cash=0.0
    def px(self,t,d): return float(self.f[t].Open.loc[d])
    def trade(self,d,t,side,q,px):
        q=abs(float(q)); n=q*px; fe=fees(q,px,side,d); sl=n*self.slip/10000; tot=fe["cost"]+sl
        if side=="BUY": self.cash-=n+tot; self.shares[t]=self.shares.get(t,0)+q
        else: self.cash+=n-tot; self.shares[t]=self.shares.get(t,0)-q
        self.legs.append({"date":d.date().isoformat(),"ticker":t,"side":side,"shares":q,"price":px,
                          "notional":n,**fe,"slippage":sl,"total_cost":tot})
    def divs(self,d):
        for t,s in self.shares.items():
            if s>0 and d in self.f[t].index:
                x=float(self.f[t].Dividends.loc[d])
                if x>0: self.cash+=s*x; self.dividend_cash+=s*x
    def nav(self,d,open_=False):
        return self.cash+sum(s*float(self.f[t].Open.loc[d] if open_ else self.f[t].Close.loc[d])
                             for t,s in self.shares.items())


def passive(frames, cal, w, slip):
    a=Acct(frames,slip); weights={"QQQ":w,"BIL":1-w}
    for t,x in weights.items():
        q=int(50000*x/a.px(t,cal[0]))
        if q: a.trade(cal[0],t,"BUY",q,a.px(t,cal[0]))
    me={cal[i] for i in range(len(cal)-1) if cal[i+1].month!=cal[i].month}
    pend=False
    for i,d in enumerate(cal):
        a.divs(d)
        if pend:
            nv=a.nav(d,True); ps={t:a.px(t,d) for t in weights}
            want={t:int(nv*x/ps[t]) for t,x in weights.items()}
            delta={t:want[t]-a.shares.get(t,0) for t in weights}
            for t,x in delta.items():
                if x<0: a.trade(d,t,"SELL",-x,ps[t])
            for t,x in delta.items():
                if x>0:
                    q=min(x,int(max(a.cash,0)/ps[t]))
                    if q: a.trade(d,t,"BUY",q,ps[t])
            pend=False
        a.navs.append({"date":d,"nav":a.nav(d),"risky":a.shares.get("QQQ",0)*float(frames["QQQ"].Close.loc[d])})
        if d in me and i+1<len(cal): pend=True
    df=pd.DataFrame(a.navs).set_index("date")
    return df["nav"].astype(float),a.legs,a.dividend_cash,df


def metrics(nav, rf=None):
    r=nav.pct_change(fill_method=None); r.iloc[0]=nav.iloc[0]/50000-1; r=r.dropna()
    y=max((nav.index[-1]-nav.index[0]).days/365.25,1e-9); eq=nav/50000; cum=eq.cummax(); dd=eq/cum-1
    vol=float(r.std(ddof=1)*np.sqrt(252)); mean=float(r.mean()*252); mdd=float(dd.min()); cagr=float(eq.iloc[-1]**(1/y)-1)
    sx=None
    if rf is not None:
        ex=(r-rf.reindex(r.index).fillna(0)).dropna(); ev=float(ex.std(ddof=1)*np.sqrt(252))
        sx=float(ex.mean()*252)/ev if ev else None
    tr=dd.idxmin(); tp=nav.index.get_loc(tr); pk=eq.iloc[:tp+1].idxmax(); pp=nav.index.get_loc(pk)
    aft=eq.iloc[tp:]; rec=aft[aft>=eq.loc[pk]]; rd=rec.index[0] if len(rec) else None; rp=nav.index.get_loc(rd) if rd is not None else None
    under=(eq<cum).to_numpy(); longest=cur=0
    for u in under: cur=cur+1 if u else 0; longest=max(longest,cur)
    return {"start":str(nav.index[0].date()),"end":str(nav.index[-1].date()),"final_nav":float(nav.iloc[-1]),
            "cagr":cagr,"volatility":vol,"sharpe_rf0":mean/vol if vol else None,
            "sharpe_excess_bil":sx,"max_drawdown":mdd,"max_drawdown_peak_date":str(pk.date()),
            "max_drawdown_trough_date":str(tr.date()),"max_drawdown_recovery_date":str(rd.date()) if rd else None,
            "max_drawdown_peak_to_trough_sessions":int(tp-pp),
            "max_drawdown_trough_to_recovery_sessions":int(rp-tp) if rp else None,
            "longest_underwater_sessions":int(longest)}


def bench(frames,t,cal):
    s=50000/float(frames[t].Open.loc[cal[0]]); cash=0; v=[]
    for d in cal:
        x=float(frames[t].Dividends.loc[d])
        if x>0: cash+=s*x
        v.append(s*float(frames[t].Close.loc[d])+cash)
    return pd.Series(v,index=cal)


def hac(y):
    y=np.asarray(y.dropna(),float); beta=y.mean(); s=y-beta; meat=float(s@s)
    for lag in range(1,21): meat+=2*(1-lag/21)*float(s[lag:]@s[:-lag])
    se=math.sqrt(max(meat/len(y)**2,0)); t=beta/se if se else None
    return {"excess_annual":beta*252,"t":t,"p":math.erfc(abs(t)/math.sqrt(2)) if t else None,
            "ci_low":(beta-1.96*se)*252,"ci_high":(beta+1.96*se)*252,"n":len(y)}


def boot(nav,rf):
    r=(nav.pct_change(fill_method=None)-rf.reindex(nav.index).fillna(0)); r.iloc[0]=0; r=r.dropna().to_numpy()
    rng=np.random.default_rng(42); out=[]
    for _ in range(500):
        st=rng.integers(0,len(r),size=int(np.ceil(len(r)/20)))
        idx=np.concatenate([(np.arange(s,s+20)%len(r)) for s in st])[:len(r)]
        out.append(np.prod(1+r[idx])**(252/len(idx))-1)
    return {"method":"circular_block_bootstrap","seed":42,"block_sessions":20,"samples":500,
            "low":float(np.quantile(out,.025)),"high":float(np.quantile(out,.975))}


def run(data_dir: Path, out: Path):
    out.mkdir(parents=True,exist_ok=True)
    frames={t:load(t,data_dir/f"{t}.csv") for t in ("QQQ","BIL")}
    cal_all=frames["BIL"].index; frames={t:f.reindex(cal_all) for t,f in frames.items()}
    cal=cal_all[(cal_all>=pd.Timestamp(START))&(cal_all<=pd.Timestamp(END))]
    for t in ("QQQ","BIL"):
        if frames[t].loc[cal,["Open","Close"]].isna().any().any(): raise ValueError(f"{t}: missing price")
    bil=bench(frames,"BIL",cal); bil_r=bil.pct_change(fill_method=None).fillna(0)
    tdf=pd.read_csv(data_dir/"transition_daily_nav.csv")
    tdf=tdf[tdf.config==CONFIG].copy(); tdf["date"]=pd.to_datetime(tdf.date); tdf=tdf.set_index("date").sort_index()
    tdf=tdf.reindex(cal)
    if tdf.nav.isna().any(): raise ValueError("Transition date mismatch")
    tr=tdf.nav.astype(float)*50000
    target_vol=float(tr.pct_change(fill_method=None).std(ddof=1)*np.sqrt(252))
    # solve by bisection on exact monthly passive volatility, only vol is objective
    lo,hi=0.0,0.60
    for _ in range(30):
        mid=(lo+hi)/2; nav,_,_,_=passive(frames,cal,mid,SLIP_BPS)
        v=float(nav.pct_change(fill_method=None).std(ddof=1)*np.sqrt(252))
        if v<target_vol: lo=mid
        else: hi=mid
    w=(lo+hi)/2; nav,legs,div,df=passive(frames,cal,w,SLIP_BPS)
    pm=metrics(nav,bil_r); pm.update({"order_legs":len(legs),"total_cost":sum(x["total_cost"] for x in legs),
                                      "dividend_cash":div,"weight":w,"target_vol":target_vol,
                                      "actual_vol":float(nav.pct_change(fill_method=None).std(ddof=1)*np.sqrt(252)),
                                      "vol_error":float(nav.pct_change(fill_method=None).std(ddof=1)*np.sqrt(252))-target_vol,
                                      "avg_risky":float((df.risky/df.nav).mean())})
    pm["excess_vs_bil"]=hac(nav.pct_change(fill_method=None).fillna(0)-bil_r); pm["bootstrap"]=boot(nav,bil_r)
    tm=metrics(tr,bil_r); tm.update({"total_cost":0.03802426620754108*50000,"order_legs":128})
    tm["excess_vs_bil"]=hac(tr.pct_change(fill_method=None).fillna(0)-bil_r); tm["bootstrap"]=boot(tr,bil_r)
    # G from existing results for same 10 bps
    g=json.loads((Path("docs/research/fixed_risk_budget/results.json")).read_text())["results"]["G|10"]
    result={"label":"TRANSITION_VS_RISK_MATCHED_PASSIVE","config":CONFIG,"start":START,"end":END,
            "target_vol":target_vol,"matched_weight":w,"vol_error":pm["vol_error"],
            "transition":tm,"risk_matched":pm,"G_10bps":g,
            "note":"Weight solved only from volatility; CAGR/MaxDD not used. Ex-post descriptive comparison, not OOS."}
    (out/"risk_match.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    nav.rename("nav").to_csv(out/"nav_risk_matched.csv"); pd.DataFrame(legs).to_csv(out/"trades_risk_matched.csv",index=False)
    tr.rename("nav").to_csv(out/"nav_transition.csv")
    return result


if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",type=Path,default=Path("data/research/transition_risk_match"))
    ap.add_argument("--out",type=Path,default=Path("docs/research/transition_risk_match")); a=ap.parse_args()
    r=run(a.data_dir,a.out); print(json.dumps(r,indent=2)[:3000])
