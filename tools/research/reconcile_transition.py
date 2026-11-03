#!/usr/bin/env python3
"""Reconcile PR438 Transition NAV and rebuild with sleeve accounting."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

CONFIG="w25_c10_all_legs"; START="2007-05-30"; END="2026-10-30"; C=10/10000


def load(t,p):
    d=pd.read_csv(p); c={x.lower().replace(" ","_"):x for x in d.columns}
    o=pd.DataFrame({"Date":pd.to_datetime(d[c["date"]],utc=True).dt.tz_convert(None).dt.normalize(),
                    "Open":pd.to_numeric(d[c["open"]],errors="coerce"),
                    "Close":pd.to_numeric(d[c["close"]],errors="coerce"),
                    "AdjClose":pd.to_numeric(d[c["adj_close"]],errors="coerce"),
                    "Dividends":pd.to_numeric(d[c["dividends"]],errors="coerce").fillna(0)}).dropna()
    o["AdjOpen"]=o.Open*o.AdjClose/o.Close
    return o.sort_values("Date").set_index("Date")


def rebuild(frame_q,frame_b,cal,ledger,adjusted=True,initial_cost=False):
    """Sleeve accounting matching PR438: 25% strategy sleeve + 75% reserve."""
    op = "AdjOpen" if adjusted else "Open"
    cl = "AdjClose" if adjusted else "Close"
    reserve=(1-0.25)*50000/float(frame_b.loc[cal[0],op])
    sleeve=0.25*50000/float(frame_b.loc[cal[0],op])
    q_units=0.0; cash=0.0
    entries={pd.Timestamp(r.entry):r for _,r in ledger.iterrows()}
    exits={pd.Timestamp(r.exit):r for _,r in ledger.iterrows()}
    rows=[]
    for d in cal:
        # dividends on raw accounting only; adjusted prices already include them
        if not adjusted:
            div_b=float(frame_b.Dividends.loc[d]); div_q=float(frame_q.Dividends.loc[d])
            if div_b>0: cash += (sleeve+reserve)*div_b
            if q_units>0 and div_q>0: cash += q_units*div_q
        if d in exits and q_units>0:
            qpx=float(frame_q.loc[d,op]); gross=q_units*qpx
            net=gross*(1-C); q_units=0
            # buy sleeve BIL with net (cost 10bps)
            bpx=float(frame_b.loc[d,op]); sleeve=(net*(1-C)+cash)/bpx; cash=0
        if d in entries and q_units==0:
            bpx=float(frame_b.loc[d,op]); value=sleeve*bpx+cash; cash=0
            # sell BIL and buy QQQ, each 10bps
            q_units=(value*(1-C)*(1-C))/float(frame_q.loc[d,op]); sleeve=0
        if q_units>0: strat=q_units*float(frame_q.loc[d,cl])
        else: strat=sleeve*float(frame_b.loc[d,cl])
        nav=strat+reserve*float(frame_b.loc[d,cl])+cash
        rows.append({"date":d,"nav":nav,"strategy":strat,"reserve":reserve*float(frame_b.loc[d,cl])})
    return pd.DataFrame(rows).set_index("date")


def run(data_dir:Path,out:Path):
    q=load("QQQ",data_dir/"QQQ.csv"); b=load("BIL",data_dir/"BIL.csv")
    cal=b.index[(b.index>=pd.Timestamp(START))&(b.index<=pd.Timestamp(END))]
    q=q.reindex(cal); b=b.reindex(cal)
    daily=pd.read_csv(data_dir/"transition_daily_nav.csv"); daily=daily[daily.config==CONFIG].copy()
    daily["date"]=pd.to_datetime(daily.date); daily=daily.set_index("date").reindex(cal)
    ledger=pd.read_csv(data_dir/"transition_trade_ledger.csv"); ledger=ledger[ledger.config==CONFIG]
    adj=rebuild(q,b,cal,ledger,adjusted=True)
    raw=rebuild(q,b,cal,ledger,adjusted=False)
    # normalized comparison
    adjn=adj.nav/adj.nav.iloc[0]; rawn=raw.nav/raw.nav.iloc[0]; orig=daily.nav/ daily.nav.iloc[0]
    cmp=pd.DataFrame({"original":orig,"rebuild_adj":adjn,"rebuild_raw":rawn})
    cmp["adj_minus_orig"]=cmp.rebuild_adj-cmp.original
    cmp["raw_minus_orig"]=cmp.rebuild_raw-cmp.original
    cmp.to_csv(out/"transition_nav_reconciliation.csv")
    summary={"max_abs_adj_diff":float(cmp.adj_minus_orig.abs().max()),
             "mean_abs_adj_diff":float(cmp.adj_minus_orig.abs().mean()),
             "max_abs_raw_diff":float(cmp.raw_minus_orig.abs().max()),
             "mean_abs_raw_diff":float(cmp.raw_minus_orig.abs().mean()),
             "final_original":float(orig.iloc[-1]),"final_adj":float(adjn.iloc[-1]),"final_raw":float(rawn.iloc[-1]),
             "vol_original":float(orig.pct_change(fill_method=None).std(ddof=1)*np.sqrt(252)),
             "vol_adj":float(adjn.pct_change(fill_method=None).std(ddof=1)*np.sqrt(252)),
             "vol_raw":float(rawn.pct_change(fill_method=None).std(ddof=1)*np.sqrt(252))}
    (out/"reconciliation.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",type=Path,default=Path("data/research/transition_risk_match"))
    ap.add_argument("--out",type=Path,default=Path("docs/research/transition_risk_match")); a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True); run(a.data_dir,a.out)
