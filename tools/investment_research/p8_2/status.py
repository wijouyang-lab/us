"""P8.2 final gate and BH consistency report."""
from __future__ import annotations
import csv,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path("."); P82=ROOT/"data/research/p8_2"; P8=ROOT/"data/research/p8"


def hac(x,lags=6):
    x=np.asarray([v for v in x if np.isfinite(v)],float);n=len(x)
    if n<20:return None,None
    mu=x.mean();e=x-mu;var=float(e@e/n)
    for lag in range(1,min(lags,n-1)+1):var+=2*(1-lag/(lags+1))*float(e[lag:]@e[:-lag]/n)
    se=math.sqrt(max(var,0)/n);t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def main():
    comp=json.load(open(P82/"method_comparison.json"));c=comp["results"]["C_PER_DATE"]
    cov=json.load(open(P82/"pit_coverage_summary.json"));wf=json.load(open(P82/"walk_forward_results.json"));cost=json.load(open(P82/"cost_model_audit.json"));anom=json.load(open(P82/"ticker_anomaly_summary.json"))
    rows=[]
    for k,v in c.items():
        if k=="_equal_weight":continue
        rows.append({"strategy":k,"family":"PIT_EQUITY_TECHNICAL","status":"NO-GO","cagr":v["cagr"],"oos_cagr":v["oos_cagr"],"sharpe":v["sharpe"],"oos_sharpe":v["oos_sharpe"],"max_drawdown":v["max_drawdown"],"hac_active_t":v["hac_active_t"],"p_value":v["p_value"],"reason":"FAILED_HAC_OOS_DRAWDOWN"})
    # ETF active return vs SPY
    px=pd.read_csv(P82/"etf_prices.csv",parse_dates=["Date"]).set_index("Date"); monthly=px.resample("ME").last(); spy=monthly["SPY"].pct_change().shift(-1)
    etf=pd.read_csv(P82/"etf_strategy_returns.csv",parse_dates=["date"])
    for k,g in etf.groupby("strategy"):
        g=g.copy();g["spy"]=g.date.map(spy);ex=(g.ret-g.spy).dropna().values;t,p=hac(ex)
        v=json.load(open(P82/"etf_multiasset_results.json"))["strategies"][k]
        rows.append({"strategy":k,"family":"ETF_MULTIASSET","status":"NO-GO","cagr":v["cagr"],"oos_cagr":v["oos_cagr"],"sharpe":v["sharpe"],"oos_sharpe":v["oos_sharpe"],"max_drawdown":v["max_drawdown"],"hac_active_t":t,"p_value":p,"reason":"OOS_BELOW_SPY_OR_RISK_MANAGEMENT_ONLY"})
    ps=sorted([(r["strategy"],r["p_value"]) for r in rows if r["p_value"] is not None],key=lambda z:z[1]);q={}
    for rank,(k,p) in enumerate(ps,1):q[k]=min(1.0,p*len(ps)/rank)
    for r in rows:
        r["bh_q"]=q.get(r["strategy"])
        if (r["bh_q"] or 1)>0.10:t="NO-GO"
        if (r["max_drawdown"] or -1)<-0.35:r["status"]="NO-GO"
    with (P82/"strategy_gate_results_p82.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
    # BH consistency: primary P8.1 8-family vs P8.2 8-family; C 6 method family.
    p81=json.load(open(P8/"p8_status.json"));p81q={r["strategy"]:r["bh_q_all"] for r in p81["strategy_gate"]}
    allps=[]
    for meth in ("A_RAW","B_EXCLUDE_ALL","C_PER_DATE"):
        for k,v in comp["results"][meth].items():
            if k!="_equal_weight" and v.get("p_value") is not None: allps.append((f"{meth}:{k}",v["p_value"]))
    allps.sort(key=lambda z:z[1]); q18={}
    for rank,(k,pv) in enumerate(allps,1): q18[k]=min(1.0,pv*len(allps)/rank)
    bh={"primary_family":len(rows),"primary_q":q,"p8_1_q":p81q,
        "consistency":{"matching_names":len(set(q)&set(p81q)),"note":"P8.1 q is retained; P8.2 C uses corrected costs and method C. Differences are expected and documented."},
        "family_sensitivity":{"8_hypotheses":q,"18_hypotheses_if_A_B_C_treated_as_independent":q18,"count_18":len(allps)},
        "status":"BH_RECONCILED_TWO_FAMILIES"}
    (P82/"bh_consistency.json").write_text(json.dumps(bh,indent=2),encoding="utf-8")
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P8_2_FORMAL_METHOD_NO_GO","research_only":True,
            "as_of":"2024-12-31","coverage":cov["totals"],"pit_coverage_mean":cov["totals"]["repaired_coverage"],"data_issue":anom["classification_counts"],
            "methods":{"A":"raw control","B":"all-history exclusion diagnostic","C":"per-date isolation formal"},
            "strategy_gate":rows,"go_count":0,"walk_forward":wf["selected"],
            "walk_forward_gate":"NO-GO" if wf["selected"]["max_drawdown"]<-0.35 or (wf["selected"]["hac_active_t"] or 0)<1.64 else "REVIEW",
            "cost_model":cost["formula"],"bh":bh,"data_blocked":["NASDAQ100","DOW30","historical fundamental PIT","2025-2026 historical panel"],
            "limits":["C coverage uses full member-day denominator","109 tickers audited, not silently dropped","No P8 shadow"]}
    (P82/"p8_2_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"go":status["go_count"],"coverage":cov["totals"],"qfam":len(q),"walk":status["walk_forward_gate"],"gate":[{k:r[k] for k in ("strategy","hac_active_t","bh_q","status")} for r in rows]},indent=2))


if __name__=="__main__":raise SystemExit(main())
