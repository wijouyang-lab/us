"""P8.2 cost-model reconciliation."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np, pandas as pd

OUT=Path("data/research/p8_2"); P82=OUT; P8=Path("data/research/p8"); BPS=10.0


def cagr(r):
    r=np.asarray(r,float); return float(np.cumprod(1+r)[-1]**(12/len(r))-1) if len(r) else None


def main():
    out={}
    for method in ("A_RAW","B_EXCLUDE_ALL","C_PER_DATE"):
        df=pd.read_csv(OUT/f"monthly_{method}.csv")
        rows={}
        for s,g in df[df.strategy!="EQUAL_WEIGHT"].groupby("strategy"):
            g=g.sort_values("formation"); turn=g.turnover_two_sided.astype(float)
            rows[s]={"new_cost_bps":float((BPS*turn).mean()),"old_cost_bps_double":float((2*BPS*turn).mean()),
                     "new_cagr":cagr(g.net),"old_cagr":cagr(g.gross-2*BPS/10000*turn),
                     "turnover_total":float(turn.sum()),"months":len(g)}
        out[method]=rows
    etf=pd.read_csv(P82/"etf_strategy_returns.csv")
    er={}
    for s,g in etf.groupby("strategy"):
        old=g.ret + g.cost - 2*BPS/10000  # old had unconditional 2*10bps
        er[s]={"new_cagr":cagr(g.ret),"old_cagr":cagr(old),"mean_new_cost_bps":float(g.cost.mean()*10000),
               "old_cost_bps":20.0,"months":len(g)}
    report={"generated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "formula":{"two_sided_turnover":"|hold XOR prev|/n",
                        "old":"cost=10bps * turnover * 2 (double counted both sides)",
                        "new":"cost=10bps * turnover; turnover already includes additions and removals",
                        "initial":"prev empty -> turnover=1.0 -> one 10bps initial cost"},
            "stock_methods":out,"etf":er,"status":"COST_MODEL_RECONCILED"}
    (OUT/"cost_model_audit.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":raise SystemExit(main())
