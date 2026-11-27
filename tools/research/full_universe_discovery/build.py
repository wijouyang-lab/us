#!/usr/bin/env python3
"""Full-universe multi-style discovery V1 from existing FS2/Unified data."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_discovery")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_discovery_out"); OUT.mkdir(exist_ok=True)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

u=pd.read_csv(ROOT/"data/research/unified_selection/unified_selection_v1_1.csv")
fs2=pd.read_csv(ROOT/"data/research/fs2/composite_candidates_v1.csv")[["ticker","valid_days","adv20_usd","corporate_action_status"]]
u=u.drop(columns=[c for c in ["valid_days","adv20_usd","corporate_action_status"] if c in u.columns]).merge(fs2,on="ticker",how="left",suffixes=("","_fs2"))
v=pd.read_csv(ROOT/"data/universe/selection/value_rankings.csv")[["ticker","market_cap"]].drop_duplicates("ticker")
u=u.merge(v,on="ticker",how="left")
u["peer_group"]=u.security_type.fillna("UNKNOWN")+"|"+u.industry.fillna("UNCLASSIFIED")
u["peer_n"]=u.groupby("peer_group").ticker.transform("size")
u["is_common"]=u.security_type.isin(["COMMON","ADR"])
u["ca_ok"]=~u.corporate_action_status.eq("CORPORATE_ACTION_REVIEW").fillna(False)
u["liq_ok"]=u.adv20_usd.fillna(0)>=2_000_000
u["base_eligible"]=u.is_common & u.tradability_status.eq("ELIGIBLE_FOR_RESEARCH") & u.ca_ok & u.liq_ok
u["peer_n"]=u.groupby("peer_group").base_eligible.transform("sum")
u["eligible"]=u.base_eligible & (u.peer_n>=20)
def dq(r):
    if not r.is_common: return "BLOCKED"
    if not r.ca_ok: return "BLOCKED"
    if not r.liq_ok: return "PARTIAL"
    if r.dimension_coverage==4 and r.peer_n>=20: return "VERIFIED"
    if r.dimension_coverage>=2: return "PARTIAL"
    return "UNKNOWN"
u["data_quality"]=u.apply(dq,axis=1)
# trend peer percentile, special financial excluded from standard trend? Keep, but flagged
u["trend_peer_pct"]=u.groupby("peer_group").trend_pct.rank(pct=True)
u["special_financial"]=u.industry.isin(["BANKS","INSURANCE","REIT","OTHER_FINANCIALS"])
# style candidate masks
styles={
 "VALUE": (u.value_pct>=0.80),
 "QUALITY": (u.quality_pct>=0.80),
 "GARP": (u.garp_pct>=0.80),
 "TREND": (u.trend_peer_pct>=0.80) & (u.ret60>0),
 "TURNAROUND": pd.Series(False,index=u.index),
}
cand=[]; exc=[]
for st,mask in styles.items():
    sub=u[u.eligible & mask & ~u.special_financial].copy()
    # special financials excluded from standard multiples; for VALUE/QUALITY they remain separately, not mixed
    sub["style"]=st
    sub["style_score"]=sub[{"VALUE":"value_pct","QUALITY":"quality_pct","GARP":"garp_pct","TREND":"trend_peer_pct","TURNAROUND":"trend_peer_pct"}[st]]
    sub["style_rank"]=sub.style_score.rank(ascending=False,method="first")
    cand.append(sub)
    bad=u[u.eligible & ~mask]
    exc.append(pd.DataFrame({"ticker":bad.ticker,"style":st,"reason":"STYLE_THRESHOLD_NOT_MET"}))
    bad2=u[~u.eligible]
    exc.append(pd.DataFrame({"ticker":bad2.ticker,"style":st,"reason":"BASE_ELIGIBILITY_FAILED"}))
c=pd.concat(cand,ignore_index=True) if cand else pd.DataFrame()
if len(c):
    c["risk_flags"]=""
    c.loc[c.fcf_yield.fillna(0)<0,"risk_flags"]+="NEGATIVE_FCF;"
    c.loc[c.special_financial,"risk_flags"]+="SPECIAL_FINANCIAL_EXCLUDED;"
    c["tier"]="RESEARCH"
    c.loc[(c.data_quality!="VERIFIED")|(c.style_score<0.80),"tier"]="WATCH"
    c.loc[c.data_quality=="BLOCKED","tier"]="REJECT"
    c["style_rank"]=c.groupby("style").style_score.rank(ascending=False,method="first")
    for st in c.style.unique():
        idx=c[(c.style==st)&(c.data_quality=="VERIFIED")&(c.style_score>=0.90)].nsmallest(10,"style_rank").index
        c.loc[idx,"tier"]="PRIORITY_RESEARCH"
    c=c.sort_values(["style","tier","style_rank"])
    c["peer_percentile"]=c.style_score
    c["data_confidence"]=c.data_quality
    c["exclusion_reason"]=""
    drop=[x for x in c.columns if 'composite' in x or x in ('research_rank','legacy_research_rank','research_group','research_status')]
    c=c.drop(columns=drop)
else: c=pd.DataFrame()
# all candidates long
c.to_csv(OUT/"all_style_candidates.csv",index=False)
for st,fn in [("VALUE","value_candidates.csv"),("QUALITY","quality_candidates.csv"),("GARP","garp_candidates.csv"),("TREND","trend_candidates.csv"),("TURNAROUND","turnaround_candidates.csv")]:
    x=c[c.style==st] if len(c) else pd.DataFrame()
    x.to_csv(OUT/fn,index=False)
pd.concat(exc,ignore_index=True).drop_duplicates().to_csv(OUT/"excluded_candidates.csv",index=False)
pr=c[c.tier=="PRIORITY_RESEARCH"].copy() if len(c) else pd.DataFrame()
pr.to_csv(OUT/"priority_research_candidates.csv",index=False)
# universe coverage
cov=pd.DataFrame([
 {"metric":"total_tickers","value":len(u)},
 {"metric":"COMMON","value":int((u.security_type=="COMMON").sum())},
 {"metric":"ADR","value":int((u.security_type=="ADR").sum())},
 {"metric":"other","value":int((~u.is_common).sum())},
 {"metric":"price_liquidity_20d","value":int(u.adv20_usd.notna().sum())},
 {"metric":"adv20_2m_plus","value":int(u.liq_ok.sum())},
 {"metric":"market_cap_available","value":int(u.market_cap.notna().sum())},
 {"metric":"verified","value":int((u.data_quality=="VERIFIED").sum())},
 {"metric":"partial","value":int((u.data_quality=="PARTIAL").sum())},
 {"metric":"blocked","value":int((u.data_quality=="BLOCKED").sum())},
 {"metric":"unknown","value":int((u.data_quality=="UNKNOWN").sum())},
 {"metric":"corporate_action_review","value":int((u.corporate_action_status=="CORPORATE_ACTION_REVIEW").sum())}])
cov.to_csv(OUT/"universe_coverage.csv",index=False)
# risk register
risks=[]
for _,r in c.iterrows():
    for f in [x for x in str(r.risk_flags).split(";") if x]: risks.append({"ticker":r.ticker,"style":r.style,"risk_flag":f,"evidence":"derived from FS2/unified fields"})
pd.DataFrame(risks).to_csv(OUT/"risk_register.csv",index=False)
# source register
src=pd.DataFrame([
 {"source":"FS2 composite_candidates_v1.csv","path":"data/research/fs2/composite_candidates_v1.csv","sha256":sha(ROOT/"data/research/fs2/composite_candidates_v1.csv"),"as_of":"2026-11-25"},
 {"source":"Unified Selection v1.1","path":"data/research/unified_selection/unified_selection_v1_1.csv","sha256":sha(ROOT/"data/research/unified_selection/unified_selection_v1_1.csv"),"as_of":"2026-11-05 / 2026-11-25"},
 {"source":"FS2 value rankings","path":"data/universe/selection/value_rankings.csv","sha256":sha(ROOT/"data/universe/selection/value_rankings.csv"),"as_of":"2026-11-05"}])
src.to_csv(OUT/"source_register.csv",index=False)
print("candidates",len(c),c.style.value_counts().to_dict() if len(c) else {}, "priority",len(pr))
print("dq",u.data_quality.value_counts().to_dict())
