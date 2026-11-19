"""P8.2.1 final gate with event-time D and full OHLCV coverage."""
from __future__ import annotations
import csv,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p8_2_1";P82=ROOT/"data/research/p8_2"


def hac(x,lags=6):
    x=np.asarray([v for v in x if np.isfinite(v)],float);n=len(x)
    if n<20:return None,None
    mu=x.mean();e=x-mu;v=float(e@e/n)
    for l in range(1,min(lags,n-1)+1):v+=2*(1-l/(lags+1))*float(e[l:]@e[:-l]/n)
    se=math.sqrt(max(v,0)/n);t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def main():
    d=json.load(open(O/"event_time_results.json"));cov=json.load(open(O/"ohlcv_coverage_summary.json"));wf=json.load(open(O/"walk_forward_results.json"));comp=json.load(open(P82/"method_comparison.json"));anom=json.load(open(O/"anomaly_classification.json"))
    rows=[]
    for k,v in d["results"].items():
        rows.append({"strategy":k,"family":"PIT_EQUITY_TECHNICAL","status":"NO-GO","cagr":v["cagr"],"oos_cagr":v["oos_cagr"],"sharpe":v["sharpe"],"oos_sharpe":v["oos_sharpe"],"max_drawdown":v["max_drawdown"],"hac_active_t":v["hac_active_t"],"p_value":v["p_value"],"reason":"FAILED_ACTIVE_HAC_OR_DRAWDOWN"})
    p82=json.load(open(P82/"p8_2_status.json"))
    for r in p82["strategy_gate"]:
        if r["family"]=="ETF_MULTIASSET": rows.append({**r,"reason":"RISK_MANAGEMENT_ONLY"})
    ps=sorted([(r["strategy"],r["p_value"]) for r in rows if r["p_value"] is not None],key=lambda z:z[1]);q={}
    for rank,(k,p) in enumerate(ps,1):q[k]=min(1.0,p*len(ps)/rank)
    for r in rows:
        r["bh_q"]=q.get(r["strategy"])
        if (r["bh_q"] or 1)>0.10:r["status"]="NO-GO"
    with (O/"strategy_gate_results_p821.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
    # BH sensitivity: 4 data methods x 6 equity methods; ETF only primary.
    allps=[]
    for meth in ("A_RAW","B_EXCLUDE_ALL","C_PER_DATE"):
        for k,v in comp["results"][meth].items():
            if k!="_equal_weight" and v.get("p_value") is not None:allps.append((f"{meth}:{k}",v["p_value"]))
    for k,v in d["results"].items(): allps.append((f"D_EVENT_TIME:{k}",v["p_value"]))
    allps.sort(key=lambda z:z[1]);q24={}
    for rank,(k,p) in enumerate(allps,1):q24[k]=min(1.0,p*len(allps)/rank)
    bh={"primary_family":len(ps),"primary_q":q,"sensitivity_family":len(allps),"sensitivity_q":q24,
        "counts":{"primary":len(ps),"data_method_sensitivity":len(allps)},
        "note":"A/B/C/D are data-method sensitivity, not independent alpha strategies; both families reported."}
    fw=pd.read_csv(O/"factor_window_audit.csv")
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P8_2_1_EVENT_TIME_NO_GO","research_only":True,
            "as_of":"2024-12-31","coverage":cov["totals"],"pit_coverage_mean":cov["totals"]["verified_tradable_coverage"],"coverage_policy":cov["policy"],
            "anomaly_counts":anom["counts"],"factor_rows":len(fw),"strategy_gate":rows,"go_count":0,
            "walk_forward":wf["selected"],"walk_forward_gate":"NO-GO" if wf["selected"]["max_drawdown"]<-0.35 or (wf["selected"]["hac_active_t"] or 0)<1.64 else "REVIEW",
            "switch_events":len(wf["switches"]),"invalid_months":d["invalid_months"],"invalid_exposure_mean":d["invalid_exposure"],
            "lookahead":{"old_C":"uses future anomaly dates to decide holdings","new_D":"only known anomalies at formation; future anomalies mark DATA_INVALID, not selection"},
            "bh":bh,"data_blocked":["NASDAQ100","DOW30","historical fundamental PIT","2025-2026 historical panel"],
            "limits":["D has 48 strategy-month DATA_INVALID observations; reported, not zero-filled","No P8 shadow"]}
    (O/"p8_2_1_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    (O/"bh_consistency.json").write_text(json.dumps(bh,indent=2),encoding="utf-8")
    print(json.dumps({"go":0,"coverage":cov["totals"],"invalid":d["invalid_months"],"wf":status["walk_forward_gate"],"gate":[{k:r[k] for k in ("strategy","hac_active_t","bh_q","status")} for r in rows]},indent=2))


if __name__=="__main__":raise SystemExit(main())
