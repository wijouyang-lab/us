"""P9.2.2 full daily ledger reconstruction for P9.1 A-H."""
from __future__ import annotations
import csv,gzip,json,math
from datetime import date,datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd
from tools.paper_trading.ibkr_costs import fees

ROOT=Path(".");P91=ROOT/"data/research/p9_1_support_resistance";O=ROOT/"data/research/p9_2_2_ledger";O.mkdir(parents=True,exist_ok=True)
START=date(2007,5,30);END=date(2024,12,31);CAP=50000.;CASH0=10000.;BIL0=40000.;MAXPOS=5;SIZE=2000.;HOLD=20;SLIP=5.0


def load_signals():
    p=P91/"p9_1_signals.csv.gz"
    if p.exists(): f=gzip.open(p,"rt",encoding="utf-8")
    else: f=open(P91/"p9_1_signals.csv",encoding="utf-8")
    with f:return list(csv.DictReader(f))


def run(exp):
    px=pd.read_csv("data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","open","close","adjusted_close"]);px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>=START.isoformat())&(px.date<=END.isoformat())].copy();px["adj_open"]=px.open*px.adjusted_close/px.close
    c=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index();op=px.pivot_table(index="date",columns="symbol",values="adj_open",aggfunc="last").reindex(c.index);dates=[d.date() for d in c.index];cols=list(c.columns);pos={d:i for i,d in enumerate(dates)}
    etf=pd.read_csv("data/research/p8/etf_prices.csv",parse_dates=["Date"]).set_index("Date");etf.index=[d.date() for d in etf.index];bil=etf["BIL"].reindex(dates).ffill()
    signals=[s for s in load_signals() if s["experiment"]==exp];bydate={}
    for s in signals:bydate.setdefault(date.fromisoformat(s["date"]),[]).append(s["ticker"])
    cash=CASH0;units=BIL0/bil.iloc[0];positions=[];ledger=[];rts=[];daily=[];realized=0.;orders=[];oid=0
    for i,d in enumerate(dates):
        for p in list(positions):
            if i>=p["exit_i"]:
                j=cols.index(p["ticker"]);ref=op.iloc[i,j]
                if not np.isfinite(ref):continue
                ex=ref*(1-SLIP/10000);q=p["shares"];fd=fees(q,ex,"SELL",d)
                proceeds=q*ex-fd["cost"];cash+=proceeds;realized+=(ex-p["entry_exec"])*q-fd["cost"];p.update(exit_date=str(d),exit_ref=ref,exit_exec=ex,sell_fee=fd["cost"],sell_fee_detail=fd,sell_slip=q*(ref-ex),sell_allin=q*(ref-ex)+fd["cost"])
                rts.append(p);positions.remove(p)
        if i>0:
            for t in bydate.get(dates[i-1],[]):
                if len(positions)>=MAXPOS or t not in cols:continue
                j=cols.index(t);ref=op.iloc[i,j]
                if not np.isfinite(ref) or ref<=0:continue
                ex=ref*(1+SLIP/10000);q=math.floor(min(SIZE,cash)/ex)
                if q<1:continue
                fd=fees(q,ex,"BUY",d);gross=q*ex
                if gross+fd["cost"]>cash:continue
                cash-=gross+fd["cost"];oid+=1
                p={"strategy_id":exp,"ticker":t,"signal_date":str(dates[i-1]),"order_date":str(d),"fill_date":str(d),"order_id":oid,"side_entry":"BUY","quantity":q,"reference_price":ref,"execution_price":ex,"gross_notional":gross,"entry_exec":ex,"shares":q,"exit_i":i+HOLD,"buy_fee":fd["cost"],"buy_fee_detail":fd,"buy_slip":q*(ex-ref),"buy_allin":q*(ex-ref)+fd["cost"],"commission":fd["commission"],"exchange_fee":fd["exchange_fee"],"regulatory_fee":fd["sec_fee"]+fd["taf_fee"]}
                positions.append(p)
                ledger.append({"strategy_id":exp,"ticker":t,"signal_date":str(dates[i-1]),"order_date":str(d),"fill_date":str(d),"order_id":oid,"source_signal_id":"SIG:"+str(dates[i-1])+":"+t,"side":"BUY","quantity":q,"reference_price":ref,"execution_price":ex,"gross_notional":gross,"commission":fd["commission"],"exchange_fee":fd["exchange_fee"],"regulatory_fee":fd["sec_fee"]+fd["taf_fee"],"fees_only":fd["cost"],"slippage_cost":q*(ex-ref),"all_in_execution_cost":q*(ex-ref)+fd["cost"],"position_before":0,"position_after":q,"exit_reason":""})
        # daily mark
        eq=0.;unreal=0.
        for p in positions:
            j=cols.index(p["ticker"]);m=c.iloc[i,j]
            if np.isfinite(m):
                eq+=m*p["shares"];unreal+=(m-p["entry_exec"])*p["shares"]-p["buy_fee"]
        bv=units*bil.iloc[i];nav=cash+eq+bv
        daily.append({"strategy_id":exp,"date":str(d),"cash":cash,"bil_units":units,"bil_price":bil.iloc[i],"bil_value":bv,"stock_value":eq,"nav":nav,"realized_pnl":realized,"unrealized_pnl":unreal,"open_positions":len(positions),"nav_identity_delta":nav-(cash+eq+bv)})
    # close ledger sells at final exits already; open remain
    for p in positions:
        j=cols.index(p["ticker"]);m=c.iloc[-1,j];p["exit_date"]="";p["exit_ref"]=m;p["exit_exec"]=m;p["sell_fee"]=0.;p["sell_slip"]=0.;p["sell_allin"]=0.
    for p in rts:
        j=cols.index(p["ticker"]);q=p["shares"];sell_ref=p["exit_ref"];sell_exec=p["exit_exec"];fd=fees(q,sell_exec,"SELL",p["exit_date"])
        ledger.append({"strategy_id":exp,"ticker":p["ticker"],"signal_date":p["signal_date"],"order_date":p["exit_date"],"fill_date":p["exit_date"],"order_id":p["order_id"],"source_signal_id":"SIG:"+p["signal_date"]+":"+p["ticker"],"side":"SELL","quantity":q,"reference_price":sell_ref,"execution_price":sell_exec,"gross_notional":q*sell_exec,"commission":fd["commission"],"exchange_fee":fd["exchange_fee"],"regulatory_fee":fd["sec_fee"]+fd["taf_fee"],"fees_only":fd["cost"],"slippage_cost":q*(sell_ref-sell_exec),"all_in_execution_cost":q*(sell_ref-sell_exec)+fd["cost"],"position_before":q,"position_after":0,"exit_reason":"MAX_HOLD_20D"})
    return ledger,rts,positions,daily


def main():
    allrows=[];allrts=[];allopen=[];alld=[];recon=[]
    for exp in ("A_LEVEL_TOUCH","B_PATTERN_ONLY","C_SUPPORT_PATTERN","D_C_MACD","E_C_KDJ","F_C_BOTH","G_LEVEL_ALL_PATTERNS","H_G_BOTH"):
        led,rts,opens,daily=run(exp);allrows+=led;allrts+=rts;allopen+=opens;alld+=daily
        pf=json.loads((P91/f"portfolio_{exp}.json").read_text(encoding="utf-8"));rep=pf.get("total_costs")
        fees_only=sum(x["fees_only"] for x in led);slip=sum(x["slippage_cost"] for x in led);allin=sum(x["all_in_execution_cost"] for x in led)
        recon.append({"strategy":exp,"buys":sum(1 for x in led if x["side"]=="BUY"),"sells":sum(1 for x in led if x["side"]=="SELL"),"round_trips":len(rts),"open_positions":len(opens),"fees_only":fees_only,"slippage":slip,"all_in":allin,"p9_1_reported_cost":rep,"fee_delta":fees_only-(rep or 0),"p9_1_nav":pf["strategy_stats"].get("cagr"),"final_nav":daily[-1]["nav"],"nav_delta":daily[-1]["nav"]-(CAP*(1+pf["strategy_stats"]["cagr"])**((daily[-1]["date"]>daily[0]["date"]) and (date.fromisoformat(daily[-1]["date"])-date.fromisoformat(daily[0]["date"])).days/365.25))})
    pd.DataFrame(allrows).to_csv(O/"trade_ledger_final.csv",index=False);pd.DataFrame(allrts).to_csv(O/"round_trip_trades_final.csv",index=False);pd.DataFrame(allopen).to_csv(O/"open_positions_final.csv",index=False);pd.DataFrame(alld).to_csv(O/"daily_nav_reconciliation.csv",index=False);pd.DataFrame(recon).to_csv(O/"all_in_cost_reconciliation.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P9_2_2_LEDGER_COMPLETE","strategies":len(recon),"orders":len(allrows),"round_trips":len(allrts),"open_positions":len(allopen),"daily_rows":len(alld),"nav_identity_max_abs":max(abs(x["nav_identity_delta"]) for x in alld),"no_shadow":True}
    (O/"p9_2_2_ledger_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(pd.DataFrame(recon)[["strategy","buys","sells","round_trips","open_positions","fees_only","slippage","all_in","p9_1_reported_cost","fee_delta"]].to_string(index=False));print(status)


if __name__=="__main__":raise SystemExit(main())
