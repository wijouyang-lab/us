"""P8.2.2 status: event-time E, invalid NAV, complete member-day partition."""
from __future__ import annotations
import csv,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandas as pd

O=Path("data/research/p8_2_2");P82=Path("data/research/p8_2")


def hac(x,lags=6):
    x=np.asarray([v for v in x if np.isfinite(v)],float);n=len(x)
    if n<20:return None,None
    mu=x.mean();e=x-mu;v=float(e@e/n)
    for l in range(1,min(lags,n-1)+1):v+=2*(1-l/(lags+1))*float(e[l:]@e[:-l]/n)
    se=math.sqrt(max(v,0)/n);t=mu/se if se else None
    from math import erf,sqrt
    return t,(2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if t is not None else None)


def main():
    e=json.load(open(O/"event_time_results.json"));wf=json.load(open(O/"walk_forward_results.json"));ms=json.load(open(O/"member_day_status_summary.json"));ev=json.load(open(O/"event_time_policy.json"));anom=json.load(open(O/"anomaly_classification.json"))
    rows=[]
    for k,v in e["results"].items():
        rows.append({"strategy":k,"family":"PIT_EQUITY_TECHNICAL","status":"NO-GO","cagr_valid_subset":v["cagr"],"oos_cagr_valid_subset":v["oos_cagr"],"sharpe_valid_subset":v["sharpe"],"max_drawdown_valid_subset":v["max_drawdown"],"valid_months":v["valid_months"],"invalid_months":v["invalid_months"],"hac_active_t":v["hac_active_t"],"p_value":v["p_value"],"nav_complete":False,"reason":"INVALID_MONTHS_REMAIN_IN_CALENDAR"})
    # ETF primary (P8.2 corrected costs) for family consistency.
    p82=json.load(open(P82/"p8_2_status.json"))
    for r in p82["strategy_gate"]:
        if r["family"]=="ETF_MULTIASSET":
            rows.append({"strategy":r["strategy"],"family":"ETF_MULTIASSET","status":"NO-GO","cagr_valid_subset":r["cagr"],"oos_cagr_valid_subset":r["oos_cagr"],"sharpe_valid_subset":r["sharpe"],"max_drawdown_valid_subset":r["max_drawdown"],"valid_months":None,"invalid_months":0,"hac_active_t":r["hac_active_t"],"p_value":r["p_value"],"nav_complete":True,"reason":"RISK_MANAGEMENT_ONLY"})
    ps=sorted([(r["strategy"],r["p_value"]) for r in rows if r["p_value"] is not None],key=lambda z:z[1]);q={}
    for rank,(k,p) in enumerate(ps,1):q[k]=min(1.0,p*len(ps)/rank)
    for r in rows:r["bh_q"]=q.get(r["strategy"])
    with (O/"strategy_gate_results_p822.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
    bh={"primary_family":len(ps),"primary_q":q,"note":"6 event-time equity + 2 ETF; all no-go"}
    for r in rows:
        r["cagr"]=r.get("cagr_valid_subset");r["oos_cagr"]=r.get("oos_cagr_valid_subset");r["sharpe"]=r.get("sharpe_valid_subset");r["max_drawdown"]=r.get("max_drawdown_valid_subset");r["bh_q_all"]=r.get("bh_q")
    denom=ms["denominator"];pit=ms["statuses"]["VALID_VERIFIED_TRADABLE"]/denom if denom else None
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P8_2_2_AUDIT_COMPLETE_NO_GO","research_only":True,"as_of":"2024-12-31",
            "member_day_partition":ms,"anomaly_counts":anom["counts"],"event_time_policy":ev,"pit_coverage_mean":pit,
            "strategy_gate":rows,"go_count":0,
            "nav_status":"INCOMPLETE_FOR_EQUITY_STRATEGIES" if any(r["invalid_months"] for r in rows if r["family"]=="PIT_EQUITY_TECHNICAL") else "COMPLETE",
            "walk_forward":wf["selected"],"walk_forward_gate":"NO-GO" if (wf["selected"]["max_drawdown"] or -1)<-0.35 or (wf["selected"]["hac_active_t"] or 0)<1.64 else "REVIEW",
            "invalid_month_handling":"calendar retained; invalid months None/UNPRICEABLE; metrics are valid-subset only; no zero-return fill; no complete-NAV claim",
            "bh":bh,"data_blocked":["NASDAQ100","DOW30","historical fundamental PIT","2025-2026 historical panel"],
            "limits":["Full NAV is not available for affected months","P8 shadow not launched"]}
    (O/"p8_2_2_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"status":status["status"],"go":0,"partition_sum":ms["sum"],"nav":status["nav_status"],"wf":status["walk_forward_gate"],"gate":[{k:r[k] for k in ("strategy","hac_active_t","valid_months","invalid_months","bh_q")} for r in rows]},indent=2))


if __name__=="__main__":raise SystemExit(main())
