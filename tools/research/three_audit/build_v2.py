import pandas as pd, json, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
O=Path(os.environ.get("THREE_OUT", str(ROOT/"artifacts/three_candidate_cashflow_valuation_audit_v1"))); O.mkdir(parents=True,exist_ok=True)
# PHR TTM
phr={"rev":480.591+260.393-233.191,"ocf":78.814+42.250-29.685,"soft":13.296+7.252-7.323,"ppe":11.101+4.802-5.271}
phr["capex"]=phr["soft"]+phr["ppe"]; phr["fcf"]=phr["ocf"]-phr["capex"]
phr["sbc_total"]=68.738+26.009-34.107; phr["sbc_cap"]=1.286+0.580-0.652; phr["sbc_exp"]=67.452+25.429-33.455
phr["fcf_exp"]=phr["fcf"]-phr["sbc_exp"]; phr["fcf_total"]=phr["fcf"]-phr["sbc_total"]
# OPRX
opx={"rev":109.429+61.963-77.190,"ocf":18.715+12.880-11.627,"ppe":0.1+0.068-0.047}
opx["capex"]=opx["ppe"]; opx["fcf"]=opx["ocf"]-opx["capex"]; opx["sbc_total"]=6.962+5.820-5.002; opx["sbc_normal"]=6.962+(5.820-0.588)-5.002; opx["fcf_adj"]=opx["fcf"]-opx["sbc_total"]
# period recon
pd.DataFrame([
{"ticker":"PHR","item":"Revenue","fy":480.591,"ytd":260.393,"prior_ytd":233.191,"ttm":phr["rev"],"formula":"FY+current YTD-prior YTD","unit":"USD millions"},
{"ticker":"PHR","item":"OCF","fy":78.814,"ytd":42.250,"prior_ytd":29.685,"ttm":phr["ocf"],"formula":"FY+current YTD-prior YTD","unit":"USD millions"},
{"ticker":"PHR","item":"Capitalized software","fy":13.296,"ytd":7.252,"prior_ytd":7.323,"ttm":phr["soft"],"formula":"FY+current YTD-prior YTD","unit":"USD millions"},
{"ticker":"PHR","item":"PPE capex","fy":11.101,"ytd":4.802,"prior_ytd":5.271,"ttm":phr["ppe"],"formula":"FY+current YTD-prior YTD","unit":"USD millions"},
{"ticker":"PHR","item":"Reported FCF","fy":54.417,"ytd":30.196,"prior_ytd":17.091,"ttm":phr["fcf"],"formula":"FY+current YTD-prior YTD","unit":"USD millions"},
{"ticker":"OPRX","item":"Revenue","fy":109.429,"ytd":61.963,"prior_ytd":77.190,"ttm":opx["rev"],"formula":"FY+current YTD-prior YTD","unit":"USD millions"},
{"ticker":"OPRX","item":"OCF","fy":18.715,"ytd":12.880,"prior_ytd":11.627,"ttm":opx["ocf"],"formula":"FY+current YTD-prior YTD","unit":"USD millions"},
{"ticker":"OPRX","item":"SBC","fy":6.962,"ytd":5.820,"prior_ytd":5.002,"ttm":opx["sbc_total"],"formula":"FY+current YTD-prior YTD","unit":"USD millions"},
{"ticker":"IMMR","item":"Consolidated revenue","fy":1730.694,"ytd":None,"prior_ytd":None,"ttm":None,"formula":"FY only; TTM invalid due BNED consolidation","unit":"USD millions"}]).to_csv(O/"period_reconciliation.csv",index=False)
# quarterly financials
pd.DataFrame([
{"ticker":"PHR","period":"FY2026","revenue":480.591,"ocf":78.814,"ppe_capex":11.101,"software_capex":13.296,"total_capex":24.397,"fcf":54.417,"source":"10-K FY2026"},
{"ticker":"PHR","period":"H1 2026","revenue":260.393,"ocf":42.250,"ppe_capex":4.802,"software_capex":7.252,"total_capex":12.054,"fcf":30.196,"source":"10-Q 2026-07-31"},
{"ticker":"PHR","period":"H1 2025","revenue":233.191,"ocf":29.685,"ppe_capex":5.271,"software_capex":7.323,"total_capex":12.594,"fcf":17.091,"source":"10-Q 2025-07-31"},
{"ticker":"PHR","period":"TTM","revenue":phr["rev"],"ocf":phr["ocf"],"ppe_capex":phr["ppe"],"software_capex":phr["soft"],"total_capex":phr["capex"],"fcf":phr["fcf"],"source":"FY+ YTD - prior YTD"},
{"ticker":"OPRX","period":"FY2025","revenue":109.429,"ocf":18.715,"ppe_capex":0.1,"software_capex":0.0,"total_capex":0.1,"fcf":18.615,"source":"10-K FY2025"},
{"ticker":"OPRX","period":"9M 2026","revenue":61.963,"ocf":12.880,"ppe_capex":0.068,"software_capex":0.0,"total_capex":0.068,"fcf":12.812,"source":"10-Q 2026-09-30"},
{"ticker":"OPRX","period":"9M 2025","revenue":77.190,"ocf":11.627,"ppe_capex":0.047,"software_capex":0.0,"total_capex":0.047,"fcf":11.580,"source":"10-Q 2025-09-30"},
{"ticker":"OPRX","period":"TTM","revenue":opx["rev"],"ocf":opx["ocf"],"ppe_capex":opx["ppe"],"software_capex":0.0,"total_capex":opx["capex"],"fcf":opx["fcf"],"source":"FY+ YTD - prior YTD"},
{"ticker":"IMMR","period":"FY2026 parent","revenue":15.924,"ocf":None,"ppe_capex":None,"software_capex":None,"total_capex":None,"fcf":None,"source":"10-K FY2026"},
{"ticker":"IMMR","period":"FY2026 BNED","revenue":1714.770,"ocf":None,"ppe_capex":None,"software_capex":None,"total_capex":None,"fcf":None,"source":"10-K FY2026"},
{"ticker":"IMMR","period":"FY2026 consolidated","revenue":1730.694,"ocf":59.1,"ppe_capex":16.2,"software_capex":None,"total_capex":16.2,"fcf":42.9,"source":"10-K FY2026"}]).to_csv(O/"quarterly_financials.csv",index=False)
# fcf reconciliation
pd.DataFrame([
{"ticker":"PHR","reported_ocf":phr["ocf"],"total_capex":phr["capex"],"reported_fcf":phr["fcf"],"expense_sbc":phr["sbc_exp"],"total_sbc":phr["sbc_total"],"fcf_expense_sbc":phr["fcf_exp"],"fcf_total_sbc":phr["fcf_total"],"note":"Capitalized SBC 1.214 is non-cash and not in cash capex; no double deduction; cash-settled SBC UNKNOWN"},
{"ticker":"OPRX","reported_ocf":opx["ocf"],"total_capex":opx["capex"],"reported_fcf":opx["fcf"],"expense_sbc":opx["sbc_total"],"total_sbc":opx["sbc_total"],"fcf_expense_sbc":opx["fcf_adj"],"fcf_total_sbc":opx["fcf_adj"],"note":"9M 2026 includes 0.588 accelerated SBC; normal TTM SBC 7.192"},
{"ticker":"IMMR","reported_ocf":None,"total_capex":None,"reported_fcf":None,"expense_sbc":None,"total_sbc":None,"fcf_expense_sbc":None,"fcf_total_sbc":None,"note":"Consolidated BNED 67.4% NCI; parent FCF not disclosed"}]).to_csv(O/"fcf_reconciliation.csv",index=False)
# SBC history
pd.DataFrame([
{"ticker":"PHR","period":"FY2026","total_sbc":68.738,"expense_sbc":67.452,"capitalized_sbc":1.286,"cash_settled_sbc":None},
{"ticker":"PHR","period":"H1 2026","total_sbc":26.009,"expense_sbc":25.429,"capitalized_sbc":0.580,"cash_settled_sbc":None},
{"ticker":"PHR","period":"H1 2025","total_sbc":34.107,"expense_sbc":33.455,"capitalized_sbc":0.652,"cash_settled_sbc":None},
{"ticker":"PHR","period":"TTM","total_sbc":phr["sbc_total"],"expense_sbc":phr["sbc_exp"],"capitalized_sbc":phr["sbc_cap"],"cash_settled_sbc":None},
{"ticker":"OPRX","period":"FY2025","total_sbc":6.962,"expense_sbc":6.962,"capitalized_sbc":0.0,"cash_settled_sbc":None},
{"ticker":"OPRX","period":"9M 2026","total_sbc":5.820,"expense_sbc":5.820,"capitalized_sbc":0.0,"cash_settled_sbc":None,"accelerated_sbc":0.588},
{"ticker":"OPRX","period":"9M 2025","total_sbc":5.002,"expense_sbc":5.002,"capitalized_sbc":0.0,"cash_settled_sbc":None},
{"ticker":"OPRX","period":"TTM","total_sbc":opx["sbc_total"],"expense_sbc":opx["sbc_total"],"capitalized_sbc":0.0,"cash_settled_sbc":None,"accelerated_sbc_ttm":0.588}]).to_csv(O/"quarterly_sbc_history.csv",index=False)
# capitalized software
pd.DataFrame([
{"ticker":"PHR","fy_software":13.296,"ytd_software":7.252,"prior_ytd_software":7.323,"ttm_software":phr["soft"],"capitalized_sbc_ttm":phr["sbc_cap"],"note":"Capitalized SBC is non-cash; cash capex excludes it; no double deduction"},
{"ticker":"OPRX","fy_software":0.0,"ytd_software":0.0,"prior_ytd_software":0.0,"ttm_software":0.0,"capitalized_sbc_ttm":0.0,"note":"No material capitalized software"},
{"ticker":"IMMR","fy_software":None,"ytd_software":None,"prior_ytd_software":None,"ttm_software":None,"capitalized_sbc_ttm":None,"note":"Not separately attributable due BNED consolidation"}]).to_csv(O/"capitalized_software_reconciliation.csv",index=False)
# ownership
pd.DataFrame([
{"ticker":"IMMR","entity":"Immersion parent","revenue_fy2026":15.924,"ownership":"100%","fcf":"N/A"},
{"ticker":"IMMR","entity":"BNED","revenue_fy2026":1714.770,"ownership":"NCI 67.4%","fcf":"N/A"},
{"ticker":"IMMR","entity":"Consolidated","revenue_fy2026":1730.694,"ownership":"100% consolidated","fcf":42.9},
{"ticker":"PHR","entity":"Phreesia","revenue_ttm":phr["rev"],"ownership":"100%","fcf":phr["fcf"]},
{"ticker":"OPRX","entity":"OptimizeRx","revenue_ttm":opx["rev"],"ownership":"100%","fcf":opx["fcf"]}]).to_csv(O/"fcf_ownership_reconciliation.csv",index=False)
# normalized
pd.DataFrame([
{"ticker":"PHR","reported_fcf":phr["fcf"],"fcf_expense_sbc":phr["fcf_exp"],"fcf_total_sbc":phr["fcf_total"],"normalized_fcf":phr["fcf_total"],"method":"total SBC economic cost"},
{"ticker":"OPRX","reported_fcf":opx["fcf"],"fcf_expense_sbc":opx["fcf_adj"],"fcf_total_sbc":opx["fcf_adj"],"normalized_fcf":opx["fcf_adj"],"method":"total SBC; accelerated 0.588 flagged"},
{"ticker":"IMMR","reported_fcf":None,"fcf_expense_sbc":None,"fcf_total_sbc":None,"normalized_fcf":None,"method":"N/A due consolidation"}]).to_csv(O/"normalized_fcf.csv",index=False)
# scenarios
rows=[]
for scen,fcf,mult in [("Bear",phr["fcf_total"]*0.7,10),("Base",phr["fcf_total"],12),("Bull",phr["fcf_total"]*1.4,15)]:
 eq=fcf*mult+73.494; rows.append({"ticker":"PHR","scenario":scen,"fcf":fcf,"multiple":mult,"net_debt":-73.494,"shares":62.070944,"equity":eq,"price":eq/62.070944,"current":12.09,"return_pct":(eq/62.070944)/12.09-1})
for scen,fcf,mult in [("Bear",opx["fcf_adj"]*0.7,8),("Base",opx["fcf_adj"],12),("Bull",opx["fcf_adj"]*1.4,15)]:
 eq=fcf*mult+8.95; rows.append({"ticker":"OPRX","scenario":scen,"fcf":fcf,"multiple":mult,"net_debt":-8.95,"shares":18.906823,"equity":eq,"price":eq/18.906823,"current":7.31,"return_pct":(eq/18.906823)/7.31-1})
for scen in ["Bear","Base","Bull"]: rows.append({"ticker":"IMMR","scenario":scen,"fcf":None,"multiple":None,"net_debt":None,"shares":None,"equity":None,"price":None,"current":6.55,"return_pct":None})
pd.DataFrame(rows).to_csv(O/"valuation_scenarios.csv",index=False)
# sensitivity
sens=[]
for t,base in [("PHR",phr["fcf_total"]),("OPRX",opx["fcf_adj"])]:
 for delta in [-0.3,-0.15,0,0.15,0.3]:
  f=base*(1+delta); mult=12; eq=f*mult-(-73.494 if t=="PHR" else -8.95); price=eq/(62.070944 if t=="PHR" else 18.906823)
  sens.append({"ticker":t,"fcf_change":delta,"fcf":f,"multiple":mult,"price":price,"return":price/(12.09 if t=="PHR" else 7.31)-1})
pd.DataFrame(sens).to_csv(O/"valuation_sensitivity.csv",index=False)
# comparison
pd.DataFrame([
{"ticker":"IMMR","price":6.55,"market_cap":217.5,"net_debt":-103.8,"ev":113.7,"reported_pe":9.41,"reported_ev_fcf":1.86,"normalized_fcf":None,"decision":"INSUFFICIENT_DATA","reason":"consolidated BNED/NCI; EV/FCF invalid; NCI omitted"},
{"ticker":"PHR","price":12.09,"market_cap":750.4,"net_debt":-73.5,"ev":676.9,"reported_pe":71.83,"reported_ev_fcf":8.38,"normalized_fcf":phr["fcf_total"],"decision":"WATCH","reason":"total-SBC FCF 6.9M; EV/FCF ~98x; base below price"},
{"ticker":"OPRX","price":7.31,"market_cap":138.2,"net_debt":-8.95,"ev":129.2,"reported_pe":27.55,"reported_ev_fcf":6.50,"normalized_fcf":opx["fcf_adj"],"decision":"WATCH","reason":"customer loss; SBC-adjusted FCF 12.1M; base 8.1"}]).to_csv(O/"valuation_comparison.csv",index=False)
# risk/cat/source/decisions
pd.DataFrame([("IMMR","CONSOLIDATION","HIGH","BNED NCI 67.4%; parent FCF unavailable"),("IMMR","VALUATION","HIGH","EV/FCF 1.86 invalid"),("PHR","SBC","HIGH","total SBC 60.6M vs FCF 67.5M"),("PHR","VALUATION","HIGH","SBC-adjusted EV/FCF ~98x"),("OPRX","CUSTOMER","HIGH","10% customer zero current; NRR 121->83"),("OPRX","MICROCAP","HIGH","$138M market cap")],columns=["ticker","risk","level","evidence"]).to_csv(O/"risk_register.csv",index=False)
pd.DataFrame([{"ticker":t,"catalyst":"next 10-Q","invalidate":"SBC/FCF/customer deterioration"} for t in ["IMMR","PHR","OPRX"]]).to_csv(O/"catalyst_and_invalidation.csv",index=False)
pd.DataFrame([{"ticker":"IMMR","decision":"INSUFFICIENT_DATA","paper":False},{"ticker":"PHR","decision":"WATCH","paper":False},{"ticker":"OPRX","decision":"WATCH","paper":False}]).to_csv(O/"final_decisions.csv",index=False)
print(phr,opx)
