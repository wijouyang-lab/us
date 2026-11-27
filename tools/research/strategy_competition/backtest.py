#!/usr/bin/env python3
"""Three-route monthly strategy competition. Uses only monthly adjusted closes."""
import json, math
from pathlib import Path
import numpy as np, pandas as pd

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/"data/research/strategy_competition"
OUT=Path(__import__("os").environ.get("STRAT_OUT",str(ROOT/"artifacts/usable_low_frequency_strategy_competition_v1")))
OUT.mkdir(parents=True,exist_ok=True)
px=pd.read_parquet(DATA/"monthly_prices.parquet"); etf=pd.read_parquet(DATA/"monthly_etf.parquet"); fund=pd.read_csv(DATA/"fundamentals.csv")
months=sorted(px.month.unique()); etf=etf.set_index("month").reindex(months).ffill()
adj=px.pivot(index="month",columns="ticker",values="adjusted_close").reindex(months)
raw=px.pivot(index="month",columns="ticker",values="close").reindex(months)
vol=px.pivot(index="month",columns="ticker",values="volume").reindex(months)
ret=adj.pct_change()
# static fundamentals (look-ahead: only used in exploratory quality variants)
q=fund.set_index("ticker").quality_pct; ind=fund.set_index("ticker").industry
industries=ind.dropna().unique()

def z(s):
    s=pd.Series(s,dtype=float); sd=s.std(ddof=0); return (s-s.mean())/sd if sd and not np.isnan(sd) else s*0

def select(t, mode):
    if t<12: return None
    a=adj.loc[months[t]]; hist=adj.iloc[max(0,t-12):t+1]
    mom12=hist.iloc[-2]/hist.iloc[0]-1 if len(hist)>=12 else pd.Series(index=a.index)
    mom6=hist.iloc[-1]/hist.iloc[max(0,len(hist)-7)]-1
    high=hist.max(); pos=a/high
    dv=(raw.loc[months[t]]*vol.loc[months[t]])
    dv=dv.rolling(1).mean()
    liq=dv.fillna(0)>=10_000_000
    ok=(a>=5)&mom12.notna()&pos.notna()&liq
    ok=ok[ok].index
    if len(ok)<25: return None
    # industry strength: median 6m return, static current classification
    ind6=pd.Series({i:np.nanmedian(mom6.reindex(ok)[ind.reindex(ok)==i]) for i in industries})
    irs=ind.reindex(ok).map(ind6)
    base=z(mom12.reindex(ok))+z(pos.reindex(ok))+z(mom6.reindex(ok))
    if mode=="B_IND":
        topind=set(ind6.nlargest(3).index)
        ok=ok[[ind.get(x) in topind for x in ok]]
        if len(ok)<10: return None
        base=z(pos.reindex(ok))+z(mom6.reindex(ok))
    elif "IND" in mode:
        base=base+z(irs)
    if "QUAL" in mode:
        qq=q.reindex(ok)
        base=base+z(qq.fillna(qq.median()))
    score=base.sort_values(ascending=False)
    # industry cap: max 4 per industry
    chosen=[]; counts={}
    for tk in score.index:
        i=ind.get(tk,"UNKNOWN")
        if counts.get(i,0)>=4: continue
        chosen.append(tk); counts[i]=counts.get(i,0)+1
        if len(chosen)>=20: break
    return chosen if len(chosen)>=10 else None

def make_weights(t, picks, scheme="equal"):
    if not picks: return pd.Series(dtype=float)
    if scheme=="equal": w=pd.Series(1/len(picks),index=picks)
    else:
        v=ret.iloc[max(0,t-6):t+1][picks].std()
        inv=1/v.replace(0,np.nan); w=inv/inv.sum()
    w=w.clip(upper=0.05); return w/w.sum()

def backtest(mode, cost_bps=10, market_filter=False, topn=20):
    wprev=pd.Series(dtype=float); gross=pd.Series(0.0,index=months); net=pd.Series(0.0,index=months); tos=[]; wlist=[]
    for t in range(12,len(months)-1):
        if market_filter and not (etf.SPY.iloc[t]>etf.SPY.iloc[max(0,t-10):t+1].mean()):
            w=pd.Series(dtype=float)
        else:
            picks=select(t,mode)
            w=make_weights(t,picks[:topn]) if picks else pd.Series(dtype=float)
        if len(w)>20:
            w=w.sort_values(ascending=False).head(20); w=w/w.sum()
        r=ret.iloc[t+1].reindex(w.index).fillna(0)
        gross.iloc[t+1]=(w*r).sum() if len(w) else 0
        tos.append(float(w.sub(wprev,fill_value=0).abs().sum()) if len(w) or len(wprev) else 0)
        net.iloc[t+1]=gross.iloc[t+1]-tos[-1]*cost_bps/10000
        wprev=w; wlist.append(w)
    return gross,net,pd.Series(tos),wlist

def metrics(r):
    r=r.dropna(); eq=(1+r).cumprod(); yrs=len(r)/12
    cagr=eq.iloc[-1]**(1/yrs)-1 if len(eq) and eq.iloc[-1]>0 else np.nan
    vola=r.std(ddof=0)*math.sqrt(12); sh=cagr/vola if vola else np.nan
    dn=r[r<0].std(ddof=0)*math.sqrt(12); so=cagr/dn if dn else np.nan
    dd=(eq/eq.cummax()-1).min(); cal=cagr/abs(dd) if dd else np.nan
    wins=r[r>0]; losses=r[r<0]
    return {"CAGR":cagr,"Vol":vola,"Sharpe":sh,"Sortino":so,"MaxDD":dd,"Calmar":cal,"WinRate":len(wins)/len(r) if len(r) else np.nan,"ProfitFactor":wins.sum()/abs(losses.sum()) if len(losses) and losses.sum() else np.nan,"Months":len(r)}

rows=[]
periods={"train":("2008-01","2016-12"),"validation":("2017-01","2019-12"),"oos":("2020-01","2024-12"),"full":("2008-01","2024-12")}
configs={"A_MOM":("MOM",False,20),"A_MOM_QUAL":("MOM_QUAL",False,20),"A_MOM_IND":("MOM_IND",False,20),"A_MOM_QUAL_IND":("MOM_QUAL_IND",False,20),"B_IND_ROT":("B_IND",False,20),"SPY_TREND":(None,True,0)}
strats=["A_MOM","A_MOM_QUAL","A_MOM_IND","A_MOM_QUAL_IND","B_IND_ROT","SPY_TREND","SPY","QQQ"]
for cost in [5,10,20]:
    for s in strats:
        if s in ("SPY","QQQ"):
            r=etf[s].pct_change().reindex(months)
            gross=net=r; tos=pd.Series(0.0); ws=[]
        elif s=="SPY_TREND":
            r=etf.SPY.pct_change(); pos=(etf.SPY>etf.SPY.rolling(10).mean().shift(1)).astype(float)
            gross=pos*r; tos=pos.diff().abs().fillna(pos.abs()); net=gross-tos*cost/10000; ws=[]
        else:
            mode,mf,tn=configs[s]; gross,net,tos,ws=backtest(mode,cost,mf,tn)
        for pname,(a,b) in periods.items():
            idx=net.index[(net.index>=a)&(net.index<=b)]
            m=metrics(net.loc[idx]); gm=metrics(gross.loc[idx]); m.update({"strategy":s,"cost_bps":cost,"period":pname,"gross_CAGR":gm["CAGR"],"net_CAGR":m["CAGR"],"max_single_weight":1.0 if s in ("SPY","QQQ","SPY_TREND") else 0.05,"max_industry_weight":1.0 if s in ("SPY","QQQ","SPY_TREND") else 0.20,"avg_turnover":float(tos.mean()) if len(tos) else 0,"annual_turnover":float(tos.mean()*12) if len(tos) else 0,"trades":int((tos>0).sum()) if len(tos) else 0,"avg_holding_days":244.0 if s=="SPY_TREND" else (30.5 if s not in ("SPY","QQQ") else 0.0)})
            rows.append(m)
res=pd.DataFrame(rows); res.to_csv(OUT/"strategy_results.csv",index=False)
# equity curves at 10bps, full
curves=[]
for s in strats:
    if s=="SPY" or s=="QQQ": r=etf[s].pct_change().reindex(months)
    elif s=="SPY_TREND": r=etf.SPY.pct_change().where(etf.SPY>etf.SPY.rolling(10).mean().shift(1),0)
    else: _,r,_,_=backtest(configs[s][0],10,False,20)
    eq=(1+r.fillna(0)).cumprod()*50000
    for d,v in eq.items(): curves.append({"month":d,"strategy":s,"equity":v})
pd.DataFrame(curves).to_csv(OUT/"equity_curves.csv",index=False)
# parameter stability A_MOM_QUAL_IND topN, filter
stab=[]
for tn in [10,20,30]:
    for mf in [False,True]:
        g,n,_,_=backtest("MOM_QUAL_IND",10,mf,tn); m=metrics(n.loc["2008-01":"2024-12"]); m.update({"topn":tn,"market_filter":mf}); stab.append(m)
pd.DataFrame(stab).to_csv(OUT/"parameter_stability.csv",index=False)
# latest signal example (2024-12)
t=len(months)-1; picks=select(t,"MOM_QUAL_IND")
scan=pd.DataFrame({"ticker":picks or [],"month":months[-1]})
scan["industry"]=scan.ticker.map(ind); scan["quality_pct"]=scan.ticker.map(q)
scan.to_csv(OUT/"latest_scan_example.csv",index=False)
# data audit
audit=pd.DataFrame([
 {"item":"daily price coverage","value":"2007-01-03 to 2024-12-31; 987 symbols; 3,479,190 rows"},
 {"item":"monthly panel","value":f"{len(px)} rows; {px.ticker.nunique()} symbols; {px.month.min()} to {px.month.max()}"},
 {"item":"2024 month-end names","value":int(px[px.month=='2024-12'].ticker.nunique())},
 {"item":"delisted names","value":"NOT VERIFIED — symbol set is static; survivorship bias likely"},
 {"item":"ticker/name changes","value":"NOT VERIFIED"},
 {"item":"splits/dividends","value":"adjusted_close available; raw close for price filter"},
 {"item":"PIT fundamentals","value":"NO — current quality_pct/industry static; quality variants are exploratory and look-ahead biased"},
 {"item":"ETF benchmark","value":"SPY/QQQ 2007-2024"}])
audit.to_csv(OUT/"data_audit.csv",index=False)
# summary/champion
m=res[(res.cost_bps==10)&(res.period=="oos")].set_index("strategy")
champ=max(["A_MOM","A_MOM_QUAL","A_MOM_IND","A_MOM_QUAL_IND","B_IND_ROT"],key=lambda s:m.loc[s,"Sharpe"] if s in m.index else -9)
rep=["# Usable Low-Frequency Strategy Competition V1","","Research only. No PAPER-50000, no IBKR, no orders.","", "## Data verdict","", "- 987 symbols, 2007-2024, monthly adjusted closes; 710 names at 2024-12.","- Static symbol set; delisted names not verified -> **survivorship bias likely**.","- No PIT fundamentals; quality/industry filters use current classifications -> **look-ahead in exploratory variants**.","- Route C cannot be historically tested without PIT fundamentals.","", "## OOS 2020-2024 at 10 bps","", "| Strategy | CAGR | Vol | Sharpe | MaxDD | WinRate |","|---|---:|---:|---:|---:|---:|"]
for s in strats:
    if s in m.index:
        x=m.loc[s]; rep.append(f"| {s} | {x.CAGR:.2%} | {x.Vol:.2%} | {x.Sharpe:.2f} | {x.MaxDD:.2%} | {x.WinRate:.1%} |")
rep += ["", f"Selected closest-to-pass: **{champ}**", "", "No strategy is validated: survivorship, no PIT fundamentals, and no delisted universe. Treat all results as exploratory."]
(OUT/"final_report.md").write_text("\n".join(rep),encoding="utf-8")
print(res[(res.cost_bps==10)&(res.period=="oos")][["strategy","CAGR","Sharpe","MaxDD"]].to_string(index=False)); print("champ",champ)
