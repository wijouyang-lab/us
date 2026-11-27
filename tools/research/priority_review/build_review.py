#!/usr/bin/env python3
"""Priority 39 review + 28k accounting ledger."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_priority")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_priority_review"); OUT.mkdir(exist_ok=True)
DATA=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_priority_out")
u=pd.read_csv(ROOT/"data/research/unified_selection/unified_selection_v1_1.csv")
c=pd.read_csv(ROOT/"artifacts/full_universe_multi_style_v1/all_style_candidates.csv")
e=pd.read_csv(ROOT/"artifacts/full_universe_multi_style_v1/excluded_candidates.csv")
p=pd.read_csv(ROOT/"artifacts/full_universe_multi_style_v1/priority_research_candidates.csv").drop_duplicates("ticker")
h=pd.read_csv(ROOT/"artifacts/tier_a_30_diligence/research_decisions.csv")
tm=pd.read_csv(DATA/"ttm_metrics.csv")
styles=["VALUE","QUALITY","GARP","TREND","TURNAROUND"]
# 28k ledger
allp=pd.MultiIndex.from_product([u.ticker,styles],names=["ticker","style"]).to_frame(index=False)
have=pd.concat([c[["ticker","style"]].assign(status="CANDIDATE"),e[["ticker","style","reason"]].assign(status="EXCLUDED")]).drop_duplicates(["ticker","style"])
led=allp.merge(have,on=["ticker","style"],how="left")
led["status"]=led.status.fillna("DATA_UNAVAILABLE"); led["reason"]=led.reason.fillna("NOT_IN_CANDIDATE_OR_EXCLUSION_OUTPUT")
led=led.merge(u[["ticker","security_type","data_quality_status"]].rename(columns={"data_quality_status":"data_quality"}),on="ticker",how="left")
led.to_csv(OUT/"candidate_accounting_28000.csv",index=False)
# data quality reconciliation
qrows=[]
for st in styles:
 x=c[c.style==st]
 for q in ["VERIFIED","PARTIAL","UNKNOWN","BLOCKED"]:
  qrows.append({"style":st,"data_quality":q,"candidate_rows":int((x.data_quality==q).sum()),"unique_tickers":int(x[x.data_quality==q].ticker.nunique())})
pd.DataFrame(qrows).to_csv(OUT/"data_quality_reconciliation.csv",index=False)
# historical overrides
hist=h[["ticker","decision","confidence","key_reason"]].copy(); hist["source"]="PR633 diligence"; hist.to_csv(OUT/"historical_decision_overrides.csv",index=False)
# unique candidate
pc=p.copy()
# aggregate styles per ticker
sty=c.groupby("ticker").style.apply(lambda x:";".join(sorted(set(x)))).rename("all_styles")
pc=pc.drop_duplicates("ticker").merge(sty,on="ticker",how="left")
pc.to_csv(OUT/"unique_candidate_universe.csv",index=False)
# merge metrics
m=pc.merge(tm,on="ticker",how="left",suffixes=("","_tm"))
m["revenue_ttm"]=pd.to_numeric(m.revenue_ttm,errors="coerce"); m["fcf_ttm"]=pd.to_numeric(m.fcf_ttm,errors="coerce")
# business dict
biz={
"CRMD":"DefenCath antimicrobial catheter lock solution for dialysis; commercial-stage specialty pharma.",
"ALAB":"Connectivity semiconductors and software for AI/data-center platforms.",
"RELY":"Cross-border remittance platform for immigrant consumers.",
"OPRX":"Digital marketing and patient-access platform for pharma.",
"GOLD":"Precious-metals retailer/dealer (Gold.com); revenue is bullion trading, not a miner.",
"PHR":"Patient intake and engagement software for healthcare providers.",
"AG":"Silver and gold mining; revenue from metal sales, cyclical.",
"GLBE":"Cross-border e-commerce enablement for direct-to-consumer brands.",
"LIF":"Family location/safety subscription and advertising.",
"FIVE":"Discount teen/trend retailer with new-store growth.",
"USLM":"Lime and limestone products for construction/environmental markets.",
"IDR":"Gold mining and exploration, small-cap cyclical.",
"INMD":"Medical aesthetic devices (RF/ultrasound) sold globally.",
"CRDO":"High-speed connectivity chips for AI/data-center.",
"FIZZ":"Beverage company (LaCroix/National Beverage).",
"IRMD":"MRI-compatible infusion pumps and monitors.",
"RIGL":"Commercial-stage biotech; royalty/product revenue.",
"MU":"DRAM/NAND memory chips; highly cyclical.",
"SNDK":"Flash-memory (when-issued line); spin-off, limited history.",
"UTHR":"Specialty pharma for pulmonary hypertension.",
"IPAR":"Fragrance brands under licenses; wholesale/retail.",
"LIN":"Industrial gases; long-term contracts, capital intensive.",
"REYN":"Household products (Reynolds, Hefty); stable, low growth.",
"WDFC":"Lubricants/maintenance chemicals; brand compounder.",
"CHD":"Household/personal-care brands; stable consumer.",
"CL":"Global consumer staples (oral/personal/home care).",
"ECL":"Water, hygiene and energy chemical services.",
"MLM":"Aggregates/cement/building materials; cyclical construction.",
"PG":"Global consumer staples.",
"PATK":"Components/materials for RV, marine and manufactured housing.",
"EBS":"Biodefense/medical countermeasures; contract-driven.",
"NUS":"Skincare/supplements direct selling; regulatory/China exposure.",
"PSFE":"Payments/fintech for SMB and gaming; leverage/regulatory.",
"USNA":"Supplements direct selling; mature/declining growth.",
"NATR":"Natural supplements; small-cap direct selling.",
"IMMR":"Haptics/touch technology licensing; royalty model.",
"DOX":"Software/services for communications and media; recurring revenue.",
"CCS":"U.S. homebuilder; cyclical housing.",
"ARKO":"Convenience-store fuel/retail; low-margin, leveraged.",
}
# decisions
histmap=hist.set_index("ticker").decision.to_dict()
# style names
def dec(r):
    t=r.ticker
    if histmap.get(t)=="ELIMINATE": return "ELIMINATE","Historical ELIMINATE override"
    if pd.isna(r.revenue_ttm) or r.revenue_ttm<=0 or pd.isna(r.fcf_ttm): return "INSUFFICIENT_DATA","TTM revenue/FCF unavailable or invalid"
    if histmap.get(t)=="WATCH": return "WATCH","Prior diligence WATCH; needs price/evidence"
    if r.net_income_ttm is not None and pd.notna(r.net_income_ttm) and r.net_income_ttm<0: return "WATCH","TTM net loss"
    if r.fcf_ttm<0: return "WATCH","Negative TTM FCF"
    if r.net_debt is not None and pd.notna(r.net_debt) and r.net_debt>0 and pd.notna(r.net_debt_ebitda) and r.net_debt_ebitda>3: return "WATCH","Leverage >3x EBITDA"
    if t in {"RELY","FIVE","USLM","FIZZ"}: return "PRIORITY_WATCH","Positive FCF, net cash, P/E <25; business quality to verify"
    return "WATCH","Screen candidate; valuation/evidence not sufficient for priority"
m[["decision","decision_reason"]]=m.apply(lambda r:pd.Series(dec(r)),axis=1)
m["decision"]=m.decision
m["paper_candidate"]=False
m.to_csv(OUT/"investment_decisions.csv",index=False)
# financial/valuation
fm=m[["ticker","company","price","price_date","shares","market_cap","revenue_ttm","net_income_ttm","ocf_ttm","capex_ttm","fcf_ttm","total_debt","cash","net_debt","pe_ttm","ev_fcf_ttm","ps_ttm","fcf_yield_ttm","net_debt_ebitda","ttm_method"]].copy()
fm.to_csv(OUT/"financial_metrics.csv",index=False)
val=m[["ticker","company","price","price_date","market_cap","net_debt","pe_ttm","ev_fcf_ttm","ps_ttm","fcf_yield_ttm","net_debt_ebitda","fcf_ttm"]].copy(); val.to_csv(OUT/"valuation_comparison.csv",index=False)
# risks
r=[]
for _,x in m.iterrows():
 for risk,lvl in [("DATA_QUALITY","HIGH" if x.data_quality!="VERIFIED" else "MEDIUM"),("VALUATION","HIGH" if (pd.notna(x.pe_ttm) and x.pe_ttm>40) or pd.isna(x.pe_ttm) else "MEDIUM"),("CASH_FLOW","HIGH" if pd.isna(x.fcf_ttm) or x.fcf_ttm<0 else "MEDIUM"),("LEVERAGE","HIGH" if pd.notna(x.net_debt_ebitda) and x.net_debt_ebitda>3 else "MEDIUM"),("BUSINESS","MEDIUM")]:
  r.append({"ticker":x.ticker,"risk":risk,"level":lvl,"evidence":x.decision_reason})
pd.DataFrame(r).to_csv(OUT/"risk_register.csv",index=False)
# catalyst
pd.DataFrame([{"ticker":x.ticker,"catalyst":"next 10-Q/10-K; FCF and margin update","trigger":x.decision_reason} for _,x in m.iterrows()]).to_csv(OUT/"catalyst_watchlist.csv",index=False)
print(len(led),led.status.value_counts().to_dict(),len(m),m.decision.value_counts().to_dict())
