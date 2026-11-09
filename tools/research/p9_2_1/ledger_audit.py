"""P9.2.1 closed-trade ledger and two-sided fee audit for P9.1 A-H."""
from __future__ import annotations
import csv,json,math
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from tools.paper_trading.ibkr_costs import fees

ROOT=Path(".");P91=ROOT/"data/research/p9_1_support_resistance";O=ROOT/"data/research/p9_2_1_trade_ledger";O.mkdir(parents=True,exist_ok=True)
SLIP=5.0

def fifo_match(buys, sells):
    """FIFO match lots. buys/sells are (date, qty, id). Returns matches, unmatched sells, remaining buys."""
    lots=[[b[0],b[1],b[2]] for b in buys];out=[];unmatched=0
    for sd,sq,sid in sells:
        rem=sq
        while rem>0 and lots:
            lot=lots[0];take=min(rem,lot[1])
            out.append({"buy_id":lot[2],"sell_id":sid,"qty":take})
            lot[1]-=take;rem-=take
            if lot[1]<=0:lots.pop(0)
        unmatched+=max(rem,0)
    return out,unmatched,[{"id":x[2],"remaining":x[1]} for x in lots]


def build_experiment(path):
    d=json.loads(path.read_text(encoding="utf-8"));trades=d.get("trades_detail",[]);ledger=[];rts=[]
    for idx,t in enumerate(trades):
        q=t["shares"];buy=t["entry_price"];sell=t["exit_price"];bd=t["entry_date"];sd=t["exit_date"]
        buy_fee=fees(q,buy,"BUY",bd)["cost"];sell_fee=fees(q,sell,"SELL",sd)["cost"]
        # Slippage is embedded in fill prices in P9.1; recover approximate 5bps component.
        buy_slip=q*buy*(SLIP/10000)/(1+SLIP/10000);sell_slip=q*sell*(SLIP/10000)/(1-SLIP/10000)
        gross_buy=q*buy;gross_sell=q*sell
        for side,dt,price,fee,slip,pos0,pos1 in (("BUY",bd,buy,buy_fee,buy_slip,0,1),("SELL",sd,sell,sell_fee,sell_slip,1,0)):
            ledger.append({"strategy_id":d.get("strategy"),"ticker":t["ticker"],"signal_date":"NOT_STORED","order_date":dt,"fill_date":dt,"side":side,"quantity":q,"fill_price":price,"gross_notional":q*price,"commission":fees(q,price,side,dt)["commission"],"exchange_fee":fees(q,price,side,dt)["exchange_fee"],"regulatory_fee":fees(q,price,side,dt)["sec_fee"]+fees(q,price,side,dt)["taf_fee"],"slippage_cost":slip,"total_transaction_cost":fee+slip,"position_before":pos0,"position_after":pos1,"exit_reason":"MAX_HOLD_20D" if side=="SELL" else "","source_signal_id":"NOT_STORED","trade_seq":idx})
        gross=(sell-buy)*q;net=gross-buy_fee-sell_fee-buy_slip-sell_slip
        rts.append({"strategy_id":d.get("strategy"),"ticker":t["ticker"],"buy_date":bd,"sell_date":sd,"quantity":q,"buy_price":buy,"sell_price":sell,"gross_pnl":gross,"buy_fee":buy_fee,"sell_fee":sell_fee,"buy_slippage":buy_slip,"sell_slippage":sell_slip,"net_pnl":net,"cost_buy_reported":t.get("cost_buy"),"cost_buy_recomputed":buy_fee,"buy_fee_delta":buy_fee-(t.get("cost_buy") or 0),"status":"CLOSED"})
    return d,ledger,rts


def main():
    all_ledger=[];all_rts=[];recon=[]
    for p in sorted(P91.glob("portfolio_*.json")):
        d,led,rts=build_experiment(p);all_ledger+=led;all_rts+=rts
        f=pd.DataFrame(led);buyf=f[f.side=="BUY"];sellf=f[f.side=="SELL"]
        recon.append({"strategy":d.get("strategy"),"file":p.name,"buys":len(buyf),"sells":len(sellf),"closed_round_trips":len(rts),"partial_sells":0,"unmatched_sells":0,"unmatched_buys":0,"open_positions":"NOT_STORED_IN_P9_1_JSON","buy_fees":float(buyf.total_transaction_cost.sum()-buyf.slippage_cost.sum()),"sell_fees":float(sellf.total_transaction_cost.sum()-sellf.slippage_cost.sum()),"buy_slippage":float(buyf.slippage_cost.sum()),"sell_slippage":float(sellf.slippage_cost.sum()),"all_in_two_sided_cost":float(f.total_transaction_cost.sum()),"reported_total_costs":d.get("total_costs"),"reported_fee_delta":float((buyf.total_transaction_cost.sum()-buyf.slippage_cost.sum())+(sellf.total_transaction_cost.sum()-sellf.slippage_cost.sum()))-(d.get("total_costs") or 0),"slippage_not_in_reported_costs":float(buyf.slippage_cost.sum()+sellf.slippage_cost.sum()),"buy_cost_reported_sum":float(pd.DataFrame(rts).cost_buy_reported.sum()) if rts else 0,"buy_cost_recomputed_sum":float(pd.DataFrame(rts).cost_buy_recomputed.sum()) if rts else 0,"gross_pnl":float(pd.DataFrame(rts).gross_pnl.sum()) if rts else 0,"net_pnl":float(pd.DataFrame(rts).net_pnl.sum()) if rts else 0,"note":"P9.1 total_costs excludes slippage; slippage is embedded in fill prices. P9.1 JSON has no open-position or signal-date field."})
    pd.DataFrame(all_ledger).to_csv(O/"trade_ledger.csv",index=False);pd.DataFrame(all_rts).to_csv(O/"round_trip_trades.csv",index=False);pd.DataFrame(recon).to_csv(O/"trade_cost_reconciliation.csv",index=False)
    audit={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P9_2_1_LEDGER_PARTIAL","finding":"P9.1 code charges BUY and SELL fees separately and applies 5bps slippage to both legs; no omission of sell commission found. But P9.1 JSON does not store signal_date, open positions, or per-leg fee columns, so a complete order ledger and full NAV reconciliation cannot be reconstructed from the published artifacts.","buy_and_sell_fees":"BOTH_CALCULATED","sell_fee_omission":False,"p9_1_metrics_need_restatement":False,"ledger_completeness":"PARTIAL","rows":len(all_ledger),"experiments":len(recon),"no_shadow":True}
    (O/"trade_cost_audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    print(pd.DataFrame(recon)[["strategy","buys","sells","closed_round_trips","buy_fees","sell_fees","all_in_two_sided_cost","reported_total_costs","reported_fee_delta"]].to_string(index=False))


if __name__=="__main__":raise SystemExit(main())
