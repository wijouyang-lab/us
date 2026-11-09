"""P9.2 benchmark, corporate-action and exposure audit."""
from __future__ import annotations
import csv, gzip, json, math
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p9_2_benchmark_audit";O.mkdir(parents=True,exist_ok=True)
START=date(2007,5,30)


def load_etf(t):
    d=pd.read_csv(O/f"{t.lower()}_yf.csv",parse_dates=["Date"]).set_index("Date")["close"]
    d.index=[x.date() for x in d.index];return d.sort_index()


def nav_from_returns(qr,br,rebal="D"):
    idx=qr.index; nav=[1.0]; wq=0.2; wb=0.8; last=None
    for i,rq in enumerate(qr):
        rb=br.iloc[i]
        if i>0:
            if rebal=="D": wq,wb=0.2,0.8
            elif last is None or (idx[i].year,idx[i].month)!=(last.year,last.month): wq,wb=0.2,0.8
        r=wq*rq+wb*rb; nav.append(nav[-1]*(1+r))
        if rebal!="BH":
            wq=wq*(1+rq)/(1+r); wb=wb*(1+rb)/(1+r)
        last=idx[i]
    return pd.Series(nav[1:],index=idx)


def stats(nav,start,end):
    yrs=(end-start).days/365.25; cagr=nav.iloc[-1]**(1/yrs)-1; dd=(nav/nav.cummax()-1).min();r=nav.pct_change().dropna()
    return {"start":str(nav.index[0]),"end":str(nav.index[-1]),"cagr":float(cagr),"max_drawdown":float(dd),"vol":float(r.std(ddof=1)*math.sqrt(252)) if len(r)>2 else None,"days":len(nav)}


def main():
    q=load_etf("qqq");b=load_etf("bil");s=load_etf("spy")
    # align all three
    dates=[d for d in q.index if d in set(b.index)&set(s.index)]
    q=q.reindex(dates);b=b.reindex(dates);s=s.reindex(dates)
    qr=q.pct_change().fillna(0);br=b.pct_change().fillna(0);sr=s.pct_change().fillna(0)
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"start":str(START),"end_2024":str(dates[-1])}
    variants={}
    for end in ("2024-12-31","2026-10-30"):
        idx=[d for d in dates if d<=date.fromisoformat(end)]
        variants[end]={}
        for rebal in ("D","M","Q","A","BH"):
            nav=nav_from_returns(qr.reindex(idx),br.reindex(idx),rebal);variants[end][rebal]=stats(nav,date.fromisoformat("2007-05-30"),date.fromisoformat(end))
    # P9.1 legacy price-weighted benchmark (the exact source of the 2.09% figure)
    legacy=pd.read_csv("data/research/p8/etf_prices.csv",parse_dates=["Date"]).set_index("Date")
    ldates=[d.date() for d in legacy.index if date(2007,5,30)<=d.date()<=date(2024,12,31)]
    lq=legacy["QQQ"].reindex(pd.to_datetime(ldates)).ffill();lb=legacy["BIL"].reindex(pd.to_datetime(ldates)).ffill()
    # Exact P9.1 formula: 0.2 * pct_change(0.2*QQQ_price + 0.8*BIL_price) + 0.8*BIL_pct
    p9_1_formula=(0.2*(0.2*lq+0.8*lb).pct_change().fillna(0)+0.8*lb.pct_change().fillna(0))
    p9_1_nav=(1+p9_1_formula).cumprod();legacy_stat=stats(p9_1_nav,START,date(2024,12,31))
    price_weight_nav=(1+(0.2*lq+0.8*lb).pct_change().fillna(0)).cumprod();price_weight_stat=stats(price_weight_nav,START,date(2024,12,31))
    # clean return-weighted daily benchmark, 2024 and 2026
    clean24=variants["2024-12-31"]["D"];clean26=variants["2026-10-30"]["D"]
    # G reported values; exact G code/data is not in this repo.
    g={"reported_cagr":0.0442,"reported_maxdd":-0.1138,"reported_end":"2026-10-30","reproduced_cagr":clean26["cagr"],"reproduced_maxdd":clean26["max_drawdown"],"delta_cagr":clean26["cagr"]-0.0442,"status":"PARTIAL_EXACT_G_CODE_ABSENT"}
    # Corporate actions from yfinance actions
    import yfinance as yf, tempfile
    yf.set_tz_cache_location(tempfile.mkdtemp())
    actions={}
    for t in ("QQQ","SPY","BIL"):
        try:
            a=yf.Ticker(t).actions
            idx=pd.DatetimeIndex(a.index); idx=idx.tz_localize(None) if idx.tz is not None else idx
            mask=idx<=pd.Timestamp("2024-12-31")
            aa=a.iloc[np.where(mask)[0]]
            actions[t]={"dividends":int((aa.get("Dividends",pd.Series(dtype=float))>0).sum()),"splits":int((aa.get("Stock Splits",pd.Series(dtype=float))>0).sum()),"first":str(idx.min().date()) if len(idx) else None,"last":str(idx.max().date()) if len(idx) else None}
        except Exception as e:
            actions[t]={"error":str(e)}
    # P9.1 exposure audit
    exposures=[]
    for p in sorted((ROOT/"data/research/p9_1_support_resistance").glob("portfolio_*.json")):
        d=json.loads(p.read_text(encoding="utf-8"));trades=d.get("trades_detail",[]);nav=pd.Series([x["nav"] for x in d.get("nav",[])],dtype=float)
        buy=sum(t["shares"]*t["entry_price"] for t in trades);sell=sum(t["shares"]*t["exit_price"] for t in trades if t.get("exit_price"))
        exposures.append({"file":p.name,"strategy":d.get("strategy"),"avg_equity_exposure":d.get("avg_gross_exposure"),"avg_bil_exposure":1-(d.get("avg_gross_exposure") or 0),"max_positions":d.get("max_positions"),"trades":d.get("trades"),"total_costs":d.get("total_costs"),"buy_notional":buy,"sell_notional":sell,"turnover_two_way_notional":buy+sell,"turnover_vs_avg_nav":(buy+sell)/nav.mean() if len(nav) else None,"hold_days":d.get("hold_days"),"gate":d.get("gate")})
    pd.DataFrame(exposures).to_csv(O/"strategy_exposure_audit.csv",index=False)
    report["variants"]=variants;report["p9_1_formula_result"]=legacy_stat;report["price_weight_basket"]=price_weight_stat;report["g_comparison"]=g;report["corporate_actions"]=actions
    report["benchmark"]={"primary":"20QQQ_80BIL daily rebalanced, return-weighted, total-return yfinance adjusted close","p9_1_legacy_error":"0.2*QQQ_price + 0.8*BIL_price then pct_change; this is a drifting price-weighted basket, not a 20/80 return portfolio","correction":"P9.1 applied 0.2 to an already 20/80 price basket, producing 4% QQQ / 96% BIL; corrected return-weighted 20/80 daily benchmark is 4.28% CAGR, MaxDD -11.43% (2007-2024)"}
    (O/"benchmark_rebuild.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    pd.DataFrame([{"range":k,"rebalance":r,**v} for k,vv in variants.items() for r,v in vv.items()]).to_csv(O/"benchmark_variants.csv",index=False)
    pd.DataFrame([{"asset":k,**v} for k,v in actions.items()]).to_csv(O/"corporate_actions_audit.csv",index=False)
    print(json.dumps({"legacy":legacy_stat,"clean2024":clean24,"clean2026":clean26,"g":g,"actions":actions},indent=2))


if __name__=="__main__":raise SystemExit(main())
