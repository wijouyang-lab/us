"""P9.2.3 reproducibility framework and independent ledger reconciliation."""
from __future__ import annotations
import hashlib,json,math,platform,subprocess
from datetime import date,datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(".");P=ROOT/"data/research/p9_2_2_ledger";O=ROOT/"data/research/p9_2_3_reproducibility";O.mkdir(parents=True,exist_ok=True)


def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()


def git(*args):
    return subprocess.check_output(["git",*args],text=True).strip()


class MiniLedger:
    """Small independent cash/position ledger for tests."""
    def __init__(self,cash=50000.0):self.cash=cash;self.pos={};self.realized=0.0;self.fees=0.0;self.slip=0.0;self.orders=[];self.cost={}
    def buy(self,ticker,q,ref,ex,fee=0.0):
        q=int(q);self.cash-=q*ex+fee;self.pos[ticker]=self.pos.get(ticker,0)+q;self.fees+=fee;self.slip+=q*(ex-ref);self.cost[ticker]=self.cost.get(ticker,0)+q*ex+fee;self.orders.append({"side":"BUY","ticker":ticker,"q":q,"ref":ref,"ex":ex,"fee":fee})
    def sell(self,ticker,q,ref,ex,fee=0.0):
        q=int(q)
        if self.pos.get(ticker,0)<q:raise ValueError("unmatched sell")
        self.pos[ticker]-=q;self.cash+=q*ex-fee;self.fees+=fee;self.slip+=q*(ref-ex);self.orders.append({"side":"SELL","ticker":ticker,"q":q,"ref":ref,"ex":ex,"fee":fee})
    def nav(self,prices):
        return self.cash+sum(q*prices.get(t,0) for t,q in self.pos.items())


def independent_reconcile():
    led=pd.read_csv(P/"trade_ledger_final.csv",dtype={"ticker":str});daily=pd.read_csv(P/"daily_nav_reconciliation.csv",dtype={"strategy_id":str})
    px=pd.read_csv("data/research/pit_data/finsaber_prices_raw.csv",usecols=["date","symbol","adjusted_close"]);px["date"]=pd.to_datetime(px.date);px["symbol"]=px.symbol.str.upper();px=px[(px.date>=date(2007,5,30).isoformat())&(px.date<=date(2024,12,31).isoformat())]
    close=px.pivot_table(index="date",columns="symbol",values="adjusted_close",aggfunc="last").sort_index();close.index=[d.date() for d in close.index]
    etf=pd.read_csv("data/research/p8/etf_prices.csv",parse_dates=["Date"]).set_index("Date");etf.index=[d.date() for d in etf.index];bil=etf["BIL"].ffill().dropna()
    out=[];details=[];unmatched=0
    for strat,g in led.groupby("strategy_id"):
        orders=g.sort_values(["fill_date","order_id"]).to_dict("records");od={}
        for x in orders:od.setdefault(date.fromisoformat(x["fill_date"]),[]).append(x)
        cash=10000.;units=40000./bil.iloc[0];positions={};realized=0.;last_ex={};unmatched_s=0
        for row in daily[daily.strategy_id==strat].itertuples():
            d=date.fromisoformat(row.date)
            for o in od.get(d,[]):
                q=int(o["quantity"])
                if o["side"]=="BUY":cash-=q*o["execution_price"]+o["fees_only"];positions[o["ticker"]]=positions.get(o["ticker"],0)+q;last_ex[o["ticker"]]=o["execution_price"]
                else:
                    if positions.get(o["ticker"],0)<q:unmatched_s+=1
                    positions[o["ticker"]]=positions.get(o["ticker"],0)-q;cash+=q*o["execution_price"]-o["fees_only"];realized+=(o["execution_price"]-last_ex.get(o["ticker"],o["execution_price"]))*q-o["fees_only"]
            stock=0.
            for t,q in positions.items():
                if q>0 and d in close.index and t in close.columns:stock+=q*close.loc[d,t]
            nav=cash+stock+units*float(bil.get(d,np.nan))
            diff=nav-row.nav;details.append({"strategy_id":strat,"date":str(d),"saved_nav":row.nav,"independent_nav":nav,"difference":diff,"cash":cash,"stock_value":stock,"bil_value":units*float(bil.get(d,np.nan))})
        out.append({"strategy_id":strat,"days":len(daily[daily.strategy_id==strat]),"max_abs_nav_diff":max(abs(x["difference"]) for x in details if x["strategy_id"]==strat),"mean_abs_nav_diff":float(np.nanmean([abs(x["difference"]) for x in details if x["strategy_id"]==strat])),"unmatched_sells":unmatched_s,"end_cash":cash,"end_bil_units":units,"open_positions":sum(1 for q in positions.values() if q>0),"open_shares":sum(q for q in positions.values() if q>0)})
    pd.DataFrame(out).to_csv(O/"ledger_independent_reconciliation.csv",index=False);pd.DataFrame(details).to_csv(O/"ledger_independent_daily.csv",index=False)
    return out


def build_manifest():
    inputs={"price":"data/research/pit_data/finsaber_prices_raw.csv","membership":"data/research/historical_universe/sp500_daily.csv","signals":"data/research/p9_1_support_resistance/p9_1_signals.csv.gz","cost_model":"tools/paper_trading/ibkr_costs.py","config":"tools/research/p9_2_2/ledger_final.py"}
    outputs=["trade_ledger_final.csv","round_trip_trades_final.csv","open_positions_final.csv","daily_nav_reconciliation.csv","all_in_cost_reconciliation.csv"]
    lock=next((x for x in ("uv.lock","requirements.txt","pyproject.toml") if Path(x).exists()),None)
    m={"experiment_id":"P9_2_2_A_LEVEL_TOUCH_REPLAY","strategy_id":"A_LEVEL_TOUCH","git_commit_sha":git("rev-parse","HEAD"),"git_dirty_status":bool(git("status","--porcelain")),"source_diff_hash":hashlib.sha256(git("diff").encode()).hexdigest(),"python_version":platform.python_version(),"dependency_lock_hash":sha(lock) if lock else None,"data_sources":{k:{"path":v,"sha256":sha(v)} for k,v in inputs.items()},"cost_model_version":"IBKR_PRO_TIERED_2026_11","start_date":"2007-05-30","end_date":"2024-12-31","parameters":{"start":"2007-05-30","end":"2024-12-31","cash":50000,"equity_budget":10000,"max_positions":5,"hold_days":20,"slippage_bps_per_side":5},"calendar":"NYSE sessions from price panel","timezone":"America/New_York","execution_rule":"signal at close t; fill at next open with 5bps adverse slippage","command":"python -m tools.research.p9_2_2.ledger_final","random_seed":0,"initial_capital":50000.0,"outputs":{x:{"path":str(P/x),"sha256":sha(P/x)} for x in outputs},"status":"REPRODUCIBLE_IF_INPUT_HASHES_MATCH"}
    (O/"run_manifest_example.json").write_text(json.dumps(m,indent=2),encoding="utf-8");return m


def main():
    rec=independent_reconcile();m=build_manifest()
    audit={"generated_at":datetime.now(timezone.utc).isoformat(),"p9_1":{"status":"P9_1_ORIGINAL_RESULT_NOT_REPRODUCIBLE","reported":"CAGR/MaxDD retained as historical reported values","reason":"P9.1 original price input was not committed with an immutable SHA-256; exact signal/data version cannot be proven; P9.2.2 replay order counts differ"},"p9_2_2":{"independent_reconciliation":rec,"status":"INDEPENDENT_RECONCILIATION_PASS" if all(np.isfinite(r["max_abs_nav_diff"]) and r["max_abs_nav_diff"]<1e-6 for r in rec) else "INDEPENDENT_RECONCILIATION_PARTIAL"},"framework":{"manifest":"run_manifest_example.json","schema":"run_manifest.schema.json","required_outputs":["run_manifest.json","data_manifest.json","signal_log.csv","trade_ledger.csv","round_trip_trades.csv","open_positions.csv","daily_nav.csv","cost_reconciliation.csv","performance_metrics.json","run_status.json"]},"no_shadow":True}
    (O/"reproducibility_audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    print(json.dumps(audit,indent=2))


if __name__=="__main__":raise SystemExit(main())
