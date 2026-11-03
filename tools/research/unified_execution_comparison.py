#!/usr/bin/env python3
"""Unified IBKR execution comparison: Transition, risk-matched passive, G."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd
from tools.research.ibkr_costs import fees

START="2007-05-30"; END="2026-10-30"; SLIPS=(1,3,5,10,20)
WEIGHT=0.10533682247623799
CONFIG="w25_c10_all_legs"


def load(t,p):
    d=pd.read_csv(p); c={x.lower().replace(" ","_"):x for x in d.columns}
    o=pd.DataFrame({"Date":pd.to_datetime(d[c["date"]],utc=True).dt.tz_convert(None).dt.normalize(),
                    "Open":pd.to_numeric(d[c["open"]],errors="coerce"),
                    "Close":pd.to_numeric(d[c["close"]],errors="coerce"),
                    "Dividends":pd.to_numeric(d[c["dividends"]],errors="coerce").fillna(0.0)}).dropna()
    return o.sort_values("Date").set_index("Date")


class Acct:
    def __init__(self,f,slip,cost_on=True):
        self.f=f; self.slip=slip; self.cost_on=cost_on; self.cash=50000.0; self.shares={}
        self.legs=[]; self.navs=[]; self.divs=0.0
    def px(self,t,d): return float(self.f[t].Open.loc[d])
    def order(self,d,t,side,q,px):
        q=abs(float(q)); raw=px
        eff=raw*(1+self.slip/10000) if side=="BUY" else raw*(1-self.slip/10000)
        n=q*eff; fe=fees(q,eff,side,d) if self.cost_on else {"commission":0,"sec_fee":0,"taf_fee":0,"cat_fee":0,"clearing_fee":0,"exchange_fee":0,"cost":0}
        sl=q*abs(eff-raw) if self.cost_on else 0.0
        if side=="BUY": self.cash-=n+fe["cost"]; self.shares[t]=self.shares.get(t,0)+q
        else: self.cash+=n-fe["cost"]; self.shares[t]=self.shares.get(t,0)-q
        self.legs.append({"date":d.date().isoformat(),"ticker":t,"side":side,"shares":q,
                          "raw_open":raw,"price":eff,"notional":n,**fe,"slippage":sl,
                          "total_cost":fe["cost"]+sl})
    def divid(self,d):
        for t,s in self.shares.items():
            if s>0 and d in self.f[t].index:
                x=float(self.f[t].Dividends.loc[d])
                if x>0: self.cash+=s*x; self.divs+=s*x
    def nav(self,d,op=False):
        return self.cash+sum(s*float(self.f[t].Open.loc[d] if op else self.f[t].Close.loc[d]) for t,s in self.shares.items())


def initial_bil(a,cal):
    q=int(50000/a.px("BIL",cal[0])); a.order(cal[0],"BIL","BUY",q,a.px("BIL",cal[0]))


def monthly(a,frames,cal,weight):
    me={cal[i] for i in range(len(cal)-1) if cal[i+1].month!=cal[i].month}; pending=False
    for i,d in enumerate(cal):
        a.divid(d)
        if pending:
            nv=a.nav(d,True); ps={t:a.px(t,d) for t in ("QQQ","BIL")}
            want={"QQQ":int(nv*weight/ps["QQQ"]),"BIL":int(nv*(1-weight)/ps["BIL"])}
            delta={t:want[t]-a.shares.get(t,0) for t in want}
            for t,x in delta.items():
                if x<0: a.order(d,t,"SELL",-x,ps[t])
            for t,x in delta.items():
                if x>0:
                    q=min(x,int(max(a.cash,0)/ps[t]))
                    if q: a.order(d,t,"BUY",q,ps[t])
            pending=False
        a.navs.append({"date":d,"nav":a.nav(d),"cash":a.cash,
                       "risky":a.shares.get("QQQ",0)*float(frames["QQQ"].Close.loc[d])})
        if d in me and i+1<len(cal): pending=True


def transition(a,frames,cal,ledger):
    initial_bil(a,cal)
    entries={pd.Timestamp(r.entry):r for _,r in ledger.iterrows()}
    exits={pd.Timestamp(r.exit):r for _,r in ledger.iterrows()}
    for d in cal:
        a.divid(d)
        # process exits before entries on same-day rollovers
        if d in exits and a.shares.get("QQQ",0)>0:
            qpx=a.px("QQQ",d); qq=a.shares.get("QQQ",0)
            a.order(d,"QQQ","SELL",qq,qpx)
            bpx=a.px("BIL",d); qb=int(max(a.cash,0)/bpx)
            if qb: a.order(d,"BIL","BUY",qb,bpx)
        if d in entries and a.shares.get("QQQ",0)==0:
            ps=a.px("QQQ",d); nv=a.nav(d,True); q=int(nv*0.25/ps)
            need=q*ps; bpx=a.px("BIL",d)
            sell=min(a.shares.get("BIL",0), int(need/bpx)+1)
            if sell: a.order(d,"BIL","SELL",sell,bpx)
            if q: a.order(d,"QQQ","BUY",q,ps)
        a.navs.append({"date":d,"nav":a.nav(d),"cash":a.cash,
                       "risky":a.shares.get("QQQ",0)*float(frames["QQQ"].Close.loc[d])})

def replay_before(legs,frames,cal):
    a=Acct(frames,0,False); a.cash=50000.0
    by={}
    for x in legs: by.setdefault(x["date"],[]).append(x)
    for d in cal:
        a.divid(d)
        for x in by.get(d.date().isoformat(),[]):
            t=x["ticker"]; q=x["shares"]; px=float(frames[t].Open.loc[d])
            if x["side"]=="BUY": a.cash-=q*px; a.shares[t]=a.shares.get(t,0)+q
            else: a.cash+=q*px; a.shares[t]=a.shares.get(t,0)-q
        a.navs.append({"date":d,"nav":a.cash+sum(q*float(frames[t].Close.loc[d]) for t,q in a.shares.items())})
    return pd.DataFrame(a.navs).set_index("date")["nav"]


def metrics(nav,rf):
    r=nav.pct_change(fill_method=None); r.iloc[0]=nav.iloc[0]/50000-1; r=r.dropna()
    y=max((nav.index[-1]-nav.index[0]).days/365.25,1e-9); eq=nav/50000; cum=eq.cummax(); dd=eq/cum-1
    vol=float(r.std(ddof=1)*np.sqrt(252)); mean=float(r.mean()*252); mdd=float(dd.min()); cagr=float(eq.iloc[-1]**(1/y)-1)
    ex=(r-rf.reindex(r.index).fillna(0)).dropna(); ev=float(ex.std(ddof=1)*np.sqrt(252)); sx=float(ex.mean()*252)/ev if ev else None
    tr=dd.idxmin(); tp=nav.index.get_loc(tr); pk=eq.iloc[:tp+1].idxmax(); pp=nav.index.get_loc(pk)
    aft=eq.iloc[tp:]; rec=aft[aft>=eq.loc[pk]]; rd=rec.index[0] if len(rec) else None; rp=nav.index.get_loc(rd) if rd is not None else None
    under=(eq<cum).to_numpy(); longest=cur=0
    for u in under: cur=cur+1 if u else 0; longest=max(longest,cur)
    return {"final_nav":float(nav.iloc[-1]),"cagr":cagr,"volatility":vol,"sharpe_rf0":mean/vol if vol else None,
            "sharpe_excess_bil":sx,"max_drawdown":mdd,"max_drawdown_peak_date":str(pk.date()),
            "max_drawdown_trough_date":str(tr.date()),"max_drawdown_recovery_date":str(rd.date()) if rd else None,
            "longest_underwater_sessions":int(longest)}


def bench(frames,cal):
    s=50000/float(frames["BIL"].Open.loc[cal[0]]); cash=0; v=[]
    for d in cal:
        x=float(frames["BIL"].Dividends.loc[d])
        if x>0: cash+=s*x
        v.append(s*float(frames["BIL"].Close.loc[d])+cash)
    return pd.Series(v,index=cal)


def hac(y):
    y=np.asarray(y.dropna(),float); beta=y.mean(); s=y-beta; meat=float(s@s)
    for lag in range(1,21): meat+=2*(1-lag/21)*float(s[lag:]@s[:-lag])
    se=math.sqrt(max(meat/len(y)**2,0)); t=beta/se if se else None
    return {"mean_annual":beta*252,"t":t,"p":math.erfc(abs(t)/math.sqrt(2)) if t else None,
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


def run(data_dir:Path,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    frames={t:load(t,data_dir/f"{t}.csv") for t in ("QQQ","BIL")}
    cal_all=frames["BIL"].index; frames={t:f.reindex(cal_all) for t,f in frames.items()}
    cal=cal_all[(cal_all>=pd.Timestamp(START))&(cal_all<=pd.Timestamp(END))]
    if frames["QQQ"].loc[cal,["Open","Close"]].isna().any().any(): raise ValueError("QQQ missing")
    rf=bench(frames,cal).pct_change(fill_method=None).fillna(0)
    ledger=pd.read_csv(data_dir/"transition_trade_ledger.csv"); ledger=ledger[ledger.config==CONFIG]
    results={}
    for name in ("Transition","RiskMatched","G"):
        for slip in SLIPS:
            a=Acct(frames,slip,True)
            if name=="Transition": transition(a,frames,cal,ledger)
            elif name=="RiskMatched": monthly(a,frames,cal,WEIGHT)
            else: monthly(a,frames,cal,0.20)
            nav=pd.DataFrame(a.navs).set_index("date")["nav"].astype(float)
            m=metrics(nav,rf); legs=a.legs
            m.update({"slip_bps":slip,"order_legs":len(legs),
                      "ibkr_fees":sum(x["cost"] for x in legs),"slippage":sum(x["slippage"] for x in legs),
                      "total_cost":sum(x["total_cost"] for x in legs),"dividends":a.divs})
            if slip==3:
                before=replay_before(legs,frames,cal); bm=metrics(before,rf)
                m["before_cost_nav"]=float(before.iloc[-1]); m["before_cost_cagr"]=bm["cagr"]
                m["before_cost_maxdd"]=bm["max_drawdown"]
                m["bootstrap"]=boot(nav,rf)
                m["hac_bil"]=hac(nav.pct_change(fill_method=None).fillna(0)-rf)
                m["stages"]={}
                for s,(x0,x1) in {"2007-2015":("2007-01-01","2015-12-31"),"2016-2020":("2016-01-01","2020-12-31"),"2021-2026":("2021-01-01","2099-12-31")}.items():
                    x=nav[(nav.index>=x0)&(nav.index<=x1)]; m["stages"][s]=metrics(x,rf) if len(x)>3 else {"status":"INSUFFICIENT"}
                nav.rename("nav").to_csv(out/f"nav_{name}.csv"); pd.DataFrame(legs).to_csv(out/f"trades_{name}.csv",index=False)
                before.rename("nav").to_csv(out/f"nav_{name}_before_cost.csv")
            results[f"{name}|{slip}"]=m
    return {"label":"UNIFIED_EXECUTION_COMPARISON","config":CONFIG,"weight":WEIGHT,
            "start":START,"end":END,"results":results}


if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",type=Path,default=Path("data/research/transition_risk_match"))
    ap.add_argument("--out",type=Path,default=Path("docs/research/unified_execution")); a=ap.parse_args()
    r=run(a.data_dir,a.out); (a.out/"results.json").write_text(json.dumps(r,indent=2),encoding="utf-8")
    print(json.dumps(r,indent=2)[:2500])
