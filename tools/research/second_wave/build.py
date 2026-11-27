import pandas as pd, json, hashlib
from pathlib import Path
ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_second")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_second_out"); OUT.mkdir(exist_ok=True)
T=['ALAB','OPRX','PHR','LIF','IDR','CRDO','IRMD','SNDK','UTHR','IPAR','LIN','REYN','CHD','CL','ECL','MLM','PG','PATK','EBS','NUS','USNA','NATR','IMMR','CCS','ARKO']
tm=pd.read_csv(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_priority_out\ttm_metrics.csv"); d=tm[tm.ticker.isin(T)].copy()
p=pd.read_csv(ROOT/"artifacts/priority_candidates_investment_review_v1/investment_decisions.csv"); d=d.merge(p[["ticker","all_styles","data_quality"]],on="ticker",how="left")
uni=pd.read_csv(ROOT/"data/research/unified_selection/unified_selection_v1_1.csv"); d=d.merge(uni[["ticker","industry"]],on="ticker",how="left")
d["base_multiple"]=16.0
d["base_fcf"]=d.fcf_ttm
d["base_price"]=(d.base_fcf*d.base_multiple-d.net_debt)/d.shares
d["base_return"]=d.base_price/d.price-1
# normalized audit flags
def flag(r):
 f=[]
 if pd.isna(r.fcf_ttm): f.append("FCF_NA")
 elif r.fcf_ttm<0: f.append("FCF_NEGATIVE")
 if pd.notna(r.revenue_ttm) and r.revenue_ttm>0 and pd.notna(r.fcf_ttm) and r.fcf_ttm>r.revenue_ttm: f.append("FCF_GT_REVENUE_SUSPECT")
 if pd.notna(r.net_income_ttm) and r.net_income_ttm<0: f.append("GAAP_LOSS")
 if r.ticker=="SNDK": f.append("DATA_OUTLIER")
 if r.ticker in ("EBS","USNA","NUS"): f.append("ONE_TIME_OR_LOSS_RISK")
 return ";".join(f)
d["normalized_flags"]=d.apply(flag,axis=1)
d["shortlist"]=d.ticker.isin(["IMMR","OPRX","PHR","NATR"])
d["decision"]="WATCH"; d.loc[~d.shortlist,"decision"]="WATCH"; d["review_status"]=d.shortlist.map({True:"SECOND_WAVE_RESEARCH",False:"REJECT"})
d.to_csv(OUT/"candidate_universe.csv",index=False)
fm=d[["ticker","company","price","price_date","shares","market_cap","revenue_ttm","net_income_ttm","ocf_ttm","capex_ttm","fcf_ttm","total_debt","cash","net_debt","pe_ttm","ev_fcf_ttm","fcf_yield_ttm","net_debt_ebitda","ttm_method"]].copy(); fm.to_csv(OUT/"financial_metrics.csv",index=False)
val=d[["ticker","company","price","price_date","market_cap","net_debt","pe_ttm","ev_fcf_ttm","ps_ttm","fcf_yield_ttm","base_price","base_return","normalized_flags","review_status"]].copy(); val.to_csv(OUT/"valuation_comparison.csv",index=False)
d[["ticker","fcf_ttm","revenue_ttm","fcf_yield_ttm","normalized_flags","review_status"]].to_csv(OUT/"normalized_fcf_audit.csv",index=False)
# scenarios for 4
cfg={"IMMR":{"mult":[10,12,14],"fcf":[50e6,61e6,70e6],"name":"Haptics licensing; FCF may include litigation/royalty timing"},
"OPRX":{"mult":[12,14,16],"fcf":[16e6,20e6,24e6],"name":"Healthcare marketing platform; microcap/customer concentration"},
"PHR":{"mult":[12,16,20],"fcf":[65e6,81e6,95e6],"name":"Patient intake SaaS; GAAP profit low, FCF stronger"},
"NATR":{"mult":[10,12,14],"fcf":[8e6,10.5e6,13e6],"name":"Supplements; small-cap, low growth"}}
rows=[]
for t,c in cfg.items():
 r=d[d.ticker==t].iloc[0]
 for scen,m,fcf in zip(["Bear","Base","Bull"],c["mult"],c["fcf"]):
  eq=fcf*m-r.net_debt; price=eq/r.shares
  rows.append({"ticker":t,"scenario":scen,"fcf":fcf,"multiple":m,"net_debt":r.net_debt,"shares":r.shares,"equity":eq,"price":price,"current":r.price,"return_pct":price/r.price-1,"assumption":c["name"]})
pd.DataFrame(rows).to_csv(OUT/"valuation_scenarios.csv",index=False)
# peer comparison
peer=d.groupby("industry").agg(n=("ticker","size"),median_pe=("pe_ttm","median"),median_evfcf=("ev_fcf_ttm","median")).reset_index()
peer.to_csv(OUT/"peer_comparison.csv",index=False)
# risk
risk=d[["ticker","normalized_flags","review_status","data_quality"]].copy(); risk["risk"]="SEE_FLAGS"; risk.to_csv(OUT/"risk_register.csv",index=False)
# sources
s=pd.read_csv(ROOT/"artifacts/priority_candidates_investment_review_v1/source_register.csv"); s=s[s.ticker.isin(T)]; s.to_csv(OUT/"source_register.csv",index=False)
print(len(d),d.shortlist.sum(),pd.DataFrame(rows)[["ticker","scenario","price"]].to_string(index=False))
