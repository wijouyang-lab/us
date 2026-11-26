"""P9.1 long-only portfolio for the support + bullish pattern experiment."""
from __future__ import annotations
import argparse,csv,json,math
from datetime import date,datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd
from tools.paper_trading.ibkr_costs import fees

ROOT=Path(".");O=ROOT/"data/research/p9_1_support_resistance"
START=date(2007,5,30);END=date(2024,12,31);CAP=50000.0;EQ_BUDGET=10000.0;MAX_POS=5;HOLD=20;SLIP=5.0


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--experiment",default="C_SUPPORT_PATTERN"); exp=ap.parse_args().experiment
    px=pd.read_csv("data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","close","adjusted_close"])
    px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>=START.isoformat())&(px.date<=END.isoformat())].copy();px["adj_open"]=px.open*px.adjusted_close/px.close
    c=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index();op=px.pivot_table(index="date",columns="symbol",values="adj_open",aggfunc="last").reindex(c.index)
    dates=[d.date() for d in c.index];pos={d:i for i,d in enumerate(dates)};cols=list(c.columns)
    etf=pd.read_csv("data/research/p8/etf_prices.csv",parse_dates=["Date"]).set_index("Date");etf.index=[d.date() for d in etf.index]
    bil=etf["BIL"].reindex(dates).ffill();qqq=etf["QQQ"].reindex(dates).ffill();spy=etf["SPY"].reindex(dates).ffill()
    signals=list(csv.DictReader((O/"p9_1_signals.csv").open(encoding="utf-8")))
    bydate={}
    for s in signals:
        if s["experiment"]!=exp:continue
        d=date.fromisoformat(s["date"]);bydate.setdefault(d,[]).append(s["ticker"])
    bil_units=40000.0/bil.iloc[0];eq_cash=10000.0;positions=[];trades=[];nav=[];gross_exposure=[];costs=0.0
    for i,d in enumerate(dates):
        # exits at open
        for p in list(positions):
            if i>=p["exit_i"]:
                j=cols.index(p["ticker"]);px0=op.iloc[i,j]
                if not np.isfinite(px0): continue
                px0=px0*(1-SLIP/10000);gross=px0*p["shares"];f=fees(p["shares"],px0,"SELL",d)["cost"]
                eq_cash+=gross-f;costs+=f;p["exit_price"]=px0;p["exit_date"]=str(d);trades.append(p);positions.remove(p)
        # entries at open, from prior close signal
        if i>0:
            for t in bydate.get(dates[i-1],[]):
                if len(positions)>=MAX_POS or t not in cols: continue
                j=cols.index(t);px0=op.iloc[i,j]
                if not np.isfinite(px0) or px0<=0: continue
                notional=min(2000.0,eq_cash)
                if notional<100: continue
                buy=px0*(1+SLIP/10000);shares=math.floor(notional/buy)
                if shares<1: continue
                gross=shares*buy;f=fees(shares,buy,"BUY",d)["cost"]
                if gross+f>eq_cash: continue
                eq_cash-=gross+f;costs+=f
                positions.append({"ticker":t,"entry_date":str(d),"entry_price":buy,"shares":shares,"exit_i":i+HOLD,"cost_buy":f})
        pv=0.0
        for p in positions:
            j=cols.index(p["ticker"]);px0=c.iloc[i,j]
            if np.isfinite(px0):pv+=px0*p["shares"]
        bilv=bil_units*bil.iloc[i];nav.append(eq_cash+pv+bilv);gross_exposure.append(pv/(nav[-1] or 1))
    navs=pd.Series(nav,index=dates)
    def stats(navs):
        r=navs.pct_change().dropna();eq=navs/navs.iloc[0];yrs=len(r)/252
        dd=(eq/eq.cummax()-1).min();cagr=eq.iloc[-1]**(1/yrs)-1
        sharpe=r.mean()/r.std(ddof=1)*math.sqrt(252) if r.std(ddof=1)>0 else None
        return {"start":str(navs.index[0]),"end":str(navs.index[-1]),"cagr":float(cagr),"vol":float(r.std(ddof=1)*math.sqrt(252)),"sharpe":float(sharpe) if sharpe else None,"max_drawdown":float(dd)}
    bench={}
    for name,series in (("BIL",bil),("20QQQ_80BIL",0.2*qqq+0.8*bil),("20SPY_80BIL",0.2*spy+0.8*bil)):
        # proper compounded benchmark: use returns of 20/80 basket
        if name=="BIL": b=series/series.iloc[0]*CAP
        else: b=(0.2*series.pct_change().fillna(0)+0.8*bil.pct_change().fillna(0)).add(1).cumprod()*CAP
        bench[name]=stats(pd.Series(b.values,index=dates))
    periods={}
    for name,a,b in (("2007-2012","2007-05-30","2012-12-31"),("2013-2017","2013-01-01","2017-12-31"),("2018-2024","2018-01-01","2024-12-31")):
        sub=navs[(navs.index>=date.fromisoformat(a))&(navs.index<=date.fromisoformat(b))]
        periods[name]=stats(sub) if len(sub)>5 else None
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"strategy":exp,"initial_capital":CAP,
            "equity_budget":EQ_BUDGET,"max_positions":MAX_POS,"hold_days":HOLD,"slippage_bps_per_side":SLIP,
            "cost_model":"tools/paper_trading/ibkr_costs.py plus 5bps slippage","trades":len(trades),"total_costs":round(costs,2),
            "strategy_stats":stats(navs),"benchmarks":bench,"avg_gross_exposure":float(np.mean(gross_exposure)),"periods":periods,
            "nav":[{"date":str(d),"nav":float(v)} for d,v in zip(dates,nav)],"trades_detail":trades,
            "status":"P9_1_PORTFOLIO_DIAGNOSTIC","gate":"NO-GO" if stats(navs)["max_drawdown"]<-0.15 or stats(navs)["cagr"]<=bench["20QQQ_80BIL"]["cagr"] else "REVIEW"}
    (O/f"portfolio_{exp}.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("strategy_stats","benchmarks","trades","total_costs","avg_gross_exposure","gate")},indent=2))


if __name__=="__main__":raise SystemExit(main())
