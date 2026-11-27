import json, hashlib
from pathlib import Path
import pandas as pd, numpy as np
ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_four")
BASE=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_priority")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_four_out"); OUT.mkdir(exist_ok=True)
# 195 reconciliation
led=pd.read_csv(BASE/"artifacts/priority_candidates_investment_review_v1/candidate_accounting_28000.csv")
old=led[led.status=="DATA_UNAVAILABLE"].copy()
old["old_status"]="DATA_UNAVAILABLE"; old["new_status"]="NOT_EVALUATED"; old["reason"]="NO_EVALUATION_PERFORMED_NOT_A_DATA_CHECK"
old[["ticker","style","old_status","new_status","reason"]].to_csv(OUT/"accounting_195_reconciliation.csv",index=False)
led.loc[led.status=="DATA_UNAVAILABLE","status"]="NOT_EVALUATED"
led.loc[led.status=="NOT_EVALUATED","reason"]="NO_EVALUATION_PERFORMED_NOT_A_DATA_CHECK"
led.to_csv(OUT/"candidate_accounting_28000_corrected.csv",index=False)
# Metrics (SEC USD; TTM from PR638 priority TTM)
tm=pd.read_csv(BASE.parent/"default-workspace/_priority_out/ttm_metrics.csv") if False else pd.read_csv(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_priority_out\ttm_metrics.csv")
tm=tm[tm.ticker.isin(["RELY","FIVE","USLM","FIZZ"])].copy()
# annual / quarter curated from SEC facts
annual={
"RELY":[("FY2024",1264.0,-37.0,111.6),("FY2025",1635.1,67.9,325.1)],
"FIVE":[("FY2025",3876.5,253.6,430.6),("FY2026",4764.1,358.6,586.4)],
"USLM":[("FY2024",317.7,108.8,126.0),("FY2025",372.7,134.3,165.0)],
"FIZZ":[("FY2025",1201.4,186.8,206.7),("FY2026",1180.6,183.6,181.3)],
}
q={"RELY":("Q3 2026",509.8,67.6,None),"FIVE":("Q2 2026",1261.5,221.4,None),"USLM":("Q3 2026",106.2,38.0,None),"FIZZ":("Q1 FY2027",330.7,47.0,None)}
rows=[]
for _,x in tm.iterrows():
 for per,rev,ni,ocf in annual[x.ticker]: rows.append({"ticker":x.ticker,"company":x.company,"period":per,"revenue":rev*1e6,"net_income":ni*1e6,"ocf":ocf*1e6,"fcf":None,"source":"SEC XBRL"})
 per,rev,ni,ocf=q[x.ticker]; rows.append({"ticker":x.ticker,"company":x.company,"period":per,"revenue":rev*1e6,"net_income":ni*1e6,"ocf":ocf,"fcf":None,"source":"SEC 10-Q"})
 rows.append({"ticker":x.ticker,"company":x.company,"period":"TTM","revenue":x.revenue_ttm,"net_income":x.net_income_ttm,"ocf":x.ocf_ttm,"fcf":x.fcf_ttm,"source":"SEC FY+YTD-prior YTD"})
pd.DataFrame(rows).to_csv(OUT/"financial_metrics.csv",index=False)
# Cash quality
cq=[
{"ticker":"RELY","ocf_ttm":409.436e6,"capex_ttm":14.903e6,"fcf_ttm":394.533e6,"sbc_fy":155.1e6,"net_income_ttm":363.73e6,"quality":"P/E distorted by $136M deferred-tax release; FCF before SBC $395M, after SBC ~$239M","flag":"TAX_BENEFIT_NONCASH"},
{"ticker":"FIVE","ocf_ttm":803.48e6,"capex_ttm":204.23e6,"fcf_ttm":599.25e6,"sbc_fy":34.7e6,"net_income_ttm":619.182e6,"quality":"TTM includes $169.5M pre-tax IEEPA tariff refund; normalized net/FCF lower","flag":"ONE_TIME_TARIFF_REFUND"},
{"ticker":"USLM","ocf_ttm":168.863e6,"capex_ttm":70.13e6,"fcf_ttm":98.733e6,"sbc_fy":8.1e6,"net_income_ttm":133.683e6,"quality":"FCF positive but capex elevated; cyclical lime pricing","flag":"CYCLICAL_CAPEX"},
{"ticker":"FIZZ","ocf_ttm":187.015e6,"capex_ttm":25.118e6,"fcf_ttm":161.897e6,"sbc_fy":0.4e6,"net_income_ttm":174.892e6,"quality":"FCF solid; volume -6.4%, price +7.1%; no growth","flag":"VOLUME_DECLINE"}]
pd.DataFrame(cq).to_csv(OUT/"cash_flow_quality.csv",index=False)
# Scenarios
cfg={
"RELY":{"net_debt":-669082000,"shares":214012570,"cur":21.68,"fcf":[200e6,240e6,300e6],"mult":[10,14,18]},
"FIVE":{"net_debt":-561083000,"shares":55054035,"cur":218.09,"fcf":[350e6,470e6,550e6],"mult":[12,18,22]},
"USLM":{"net_debt":-439248000,"shares":28688327,"cur":104.68,"fcf":[70e6,99e6,120e6],"mult":[12,18,22]},
"FIZZ":{"net_debt":-107098000,"shares":93615302,"cur":37.25,"fcf":[130e6,162e6,185e6],"mult":[12,17,20]}}
rows=[]
for t,c in cfg.items():
 for scen,fcf,mult in zip(["Bear","Base","Bull"],c["fcf"],c["mult"]):
  eq=fcf*mult-c["net_debt"]; price=eq/c["shares"]
  rows.append({"ticker":t,"scenario":scen,"fcf":fcf,"ev_fcf_multiple":mult,"net_debt":c["net_debt"],"equity_value":eq,"diluted_shares":c["shares"],"implied_price":price,"current_price":c["cur"],"return_pct":price/c["cur"]-1,"formula":"Equity=FCF*multiple-NetDebt; price=equity/diluted shares"})
pd.DataFrame(rows).to_csv(OUT/"valuation_scenarios.csv",index=False)
# decisions
pd.DataFrame([
{"ticker":"RELY","decision":"WATCH","confidence":"MEDIUM","reason":"FCF strong but P/E 12.8 is not real: $136M deferred-tax release; SBC $155M; AML/regulatory risk","paper":False},
{"ticker":"FIVE","decision":"WATCH","confidence":"MEDIUM","reason":"Comp +14.1% strong, but TTM EPS/FCF includes $169.5M tariff refund; price above base","paper":False},
{"ticker":"USLM","decision":"WATCH","confidence":"MEDIUM","reason":"Quality lime asset, but 22x P/E / 26x EV/FCF at cyclical volumes; no margin of safety","paper":False},
{"ticker":"FIZZ","decision":"WATCH","confidence":"MEDIUM","reason":"Price +7.1% but volume -6.4%; flat sales, margin pressure; 20x P/E","paper":False}]).to_csv(OUT/"investment_decisions.csv",index=False)
# risks
R=pd.DataFrame([
("RELY","REGULATORY","HIGH","AML/remittance licensing"),("RELY","TAX_QUALITY","HIGH","$136M valuation allowance release"),("RELY","SBC","HIGH","$155M SBC"),("RELY","COMPETITION","MEDIUM","remittance price competition"),
("FIVE","TARIFF_REFUND","HIGH","$169.5M one-time benefit"),("FIVE","CONSUMER","MEDIUM","teen discretionary"),("FIVE","INVENTORY","MEDIUM","seasonal/import"),("FIVE","LEASE","MEDIUM","store lease obligations"),
("USLM","CYCLICAL","HIGH","steel/construction demand"),("USLM","REGIONAL","MEDIUM","Texas/regional concentration"),("USLM","CAPEX","MEDIUM","kiln/mine investment"),("USLM","VALUATION","MEDIUM","22x P/E"),
("FIZZ","VOLUME","HIGH","case volume -6.4%"),("FIZZ","BRAND","MEDIUM","LaCroix competition"),("FIZZ","MARGIN","MEDIUM","input/transport costs"),("FIZZ","CONTROL","MEDIUM","family control")],columns=["ticker","risk","level","evidence"])
R.to_csv(OUT/"risk_register.csv",index=False)
# catalysts/sources
pd.DataFrame([{"ticker":t,"catalyst":"next 10-Q","invalidate":"FCF/margin deterioration or one-off reversal"} for t in cfg]).to_csv(OUT/"catalyst_watchlist.csv",index=False)
# source register from PR638
S=pd.read_csv(BASE/"artifacts/priority_candidates_investment_review_v1/source_register.csv"); S=S[S.ticker.isin(cfg)].copy(); S.to_csv(OUT/"source_register.csv",index=False)
print("built",len(led),led.status.value_counts().to_dict(),len(rows))
