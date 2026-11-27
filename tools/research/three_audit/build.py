import pandas as pd, json
from pathlib import Path
ROOT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\_three")
OUT=Path(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_three_out"); OUT.mkdir(exist_ok=True)
# Source values USD, TTM from PR638/audit; company-specific from SEC 10-K/10-Q
base={
"IMMR":{"price":6.55,"shares":33206041,"mcap":217.5e6,"cash":None,"debt":None,"net_debt":-103.806e6,"rev":173.3e6,"ni":23.1e6,"ocf":None,"capex":None,"fcf":61.134e6,"sbc":10.8e6,"pe":9.41,"evfcf":1.86},
"PHR":{"price":12.09,"shares":62070944,"mcap":750.4e6,"cash":None,"debt":None,"net_debt":-73.494e6,"rev":495.0e6,"ni":10.4e6,"ocf":80.747e6,"capex":None,"fcf":80.747e6,"sbc":67.5e6,"pe":71.83,"evfcf":8.38},
"OPRX":{"price":7.31,"shares":18906823,"mcap":138.2e6,"cash":None,"debt":None,"net_debt":-8.95e6,"rev":94.2e6,"ni":5.0e6,"ocf":19.889e6,"capex":None,"fcf":19.889e6,"sbc":7.0e6,"pe":27.55,"evfcf":6.50}}
# entity audit
pd.DataFrame([
{"ticker":"IMMR","entity":"Immersion parent/licensing","revenue_fy2026":15.924e6,"net_income":"N/A","ocf":"N/A","ownership":"100% parent"},
{"ticker":"IMMR","entity":"BNED consolidated","revenue_fy2026":1714.770e6,"net_income":"N/A","ocf":"N/A","ownership":"NCI 67.4%; parent ~32.6%"},
{"ticker":"IMMR","entity":"Consolidated","revenue_fy2026":1730.694e6,"net_income":"N/A","ocf":59.1e6,"ownership":"100% consolidated; NCI 67.4% of BNED"}]).to_csv(OUT/"entity_and_consolidation_audit.csv",index=False)
# quarterly (TTM + latest); full 8Q not extracted; explicit
pd.DataFrame([
{"ticker":"IMMR","period":"FY2026","revenue":1730.694e6,"net_income":None,"ocf":59.1e6,"capex":16.2e6,"fcf":42.9e6,"source":"SEC 10-K FY2026"},
{"ticker":"IMMR","period":"TTM","revenue":173.3e6,"net_income":23.1e6,"ocf":None,"capex":None,"fcf":61.134e6,"source":"PR638 TTM; segment split unavailable"},
{"ticker":"PHR","period":"FY2026","revenue":495.0e6,"net_income":10.4e6,"ocf":78.8e6,"capex":24.4e6,"fcf":54.4e6,"source":"SEC 10-K FY2026"},
{"ticker":"PHR","period":"TTM","revenue":495.0e6,"net_income":10.4e6,"ocf":80.747e6,"capex":None,"fcf":80.747e6,"source":"PR638 TTM"},
{"ticker":"OPRX","period":"FY2025","revenue":94.2e6,"net_income":5.0e6,"ocf":18.7e6,"capex":0.1e6,"fcf":18.6e6,"source":"SEC 10-K FY2025"},
{"ticker":"OPRX","period":"TTM","revenue":94.2e6,"net_income":5.0e6,"ocf":19.889e6,"capex":None,"fcf":19.889e6,"source":"PR638 TTM"}]).to_csv(OUT/"quarterly_financials.csv",index=False)
# FCF reconciliation
pd.DataFrame([
{"ticker":"IMMR","reported_fcf":61.134e6,"sbc":10.8e6,"capitalized_software":"N/A","adjusted_fcf":"NOT_ATTRIBUTABLE","note":"Consolidated FCF includes BNED; 67.4% NCI; parent-only FCF not disclosed"},
{"ticker":"PHR","reported_fcf":80.747e6,"sbc":67.5e6,"capitalized_software":13.3e6,"adjusted_fcf":13.247e6,"note":"SBC is 84% of reported FCF; software already in capex, not double counted"},
{"ticker":"OPRX","reported_fcf":19.889e6,"sbc":7.0e6,"capitalized_software":0.0,"adjusted_fcf":12.889e6,"note":"SBC 35% of reported FCF; customer concentration risk"}]).to_csv(OUT/"fcf_reconciliation.csv",index=False)
# SBC
pd.DataFrame([
{"ticker":"IMMR","sbc_fy":10.8e6,"revenue":1730.694e6,"sbc_pct_rev":0.006,"diluted_shares":33206041,"note":"parent + consolidated; NCI complexity"},
{"ticker":"PHR","sbc_fy":67.5e6,"revenue":495.0e6,"sbc_pct_rev":0.136,"diluted_shares":62070944,"note":"SBC 84% of FCF"},
{"ticker":"OPRX","sbc_fy":7.0e6,"revenue":94.2e6,"sbc_pct_rev":0.074,"diluted_shares":18906823,"note":"SBC 35% of FCF"}]).to_csv(OUT/"sbc_dilution_audit.csv",index=False)
# customer concentration
pd.DataFrame([
{"ticker":"PHR","top_customer_pct":"none >10%","source":"10-K FY2026","note":"receivables concentration >10% from at least one entity"},
{"ticker":"OPRX","top5_pct":"~47%","source":"10-K FY2025","note":"one customer ~10% FY2025 generated no revenue in current period; three 10%+ customers in 2025"},
{"ticker":"IMMR","license_concentration":"15% of royalty/license revenue from one customer (FY2026)","source":"10-K FY2026","note":"BNED is consolidated VIE; NCI 67.4%"}]).to_csv(OUT/"customer_concentration_audit.csv",index=False)
# normalized fcf
pd.DataFrame([
{"ticker":"IMMR","reported_fcf":61.134e6,"normalized_fcf":"N/A","reason":"consolidated BNED/NCI; parent FCF not separable"},
{"ticker":"PHR","reported_fcf":80.747e6,"normalized_fcf":13.247e6,"reason":"subtract SBC 67.5M; software already in capex"},
{"ticker":"OPRX","reported_fcf":19.889e6,"normalized_fcf":12.889e6,"reason":"subtract SBC 7.0M; microcap discount"}]).to_csv(OUT/"normalized_fcf.csv",index=False)
# scenarios
rows=[]
cfg={"PHR":{"fcf":[8e6,13.2e6,18e6],"mult":[12,15,18]},"OPRX":{"fcf":[8e6,12.9e6,17e6],"mult":[8,12,15]}}
for t,c in cfg.items():
 b=base[t]
 for scen,fcf,mult in zip(["Bear","Base","Bull"],c["fcf"],c["mult"]):
  eq=fcf*mult-b["net_debt"]; price=eq/b["shares"]
  rows.append({"ticker":t,"scenario":scen,"fcf":fcf,"multiple":mult,"net_debt":b["net_debt"],"shares":b["shares"],"equity":eq,"price":price,"current":b["price"],"return_pct":price/b["price"]-1,"formula":"equity=FCF*multiple-net debt"})
# IMMR not estimable
for scen in ["Bear","Base","Bull"]: rows.append({"ticker":"IMMR","scenario":scen,"fcf":None,"multiple":None,"net_debt":None,"shares":None,"equity":None,"price":None,"current":6.55,"return_pct":None,"formula":"NOT_ESTIMABLE — consolidated NCI"})
pd.DataFrame(rows).to_csv(OUT/"valuation_scenarios.csv",index=False)
# comparison
pd.DataFrame([
{"ticker":"IMMR","price":6.55,"market_cap":217.5e6,"net_debt":-103.8e6,"ev":113.7e6,"reported_pe":9.41,"reported_ev_fcf":1.86,"normalized_fcf":"N/A","decision":"INSUFFICIENT_DATA","reason":"EV/FCF invalid: consolidated BNED, 67.4% NCI, parent FCF not separable"},
{"ticker":"PHR","price":12.09,"market_cap":750.4e6,"net_debt":-73.5e6,"ev":676.9e6,"reported_pe":71.83,"reported_ev_fcf":8.38,"normalized_fcf":13.247e6,"decision":"WATCH","reason":"SBC 67.5M; SBC-adjusted EV/FCF ~51x; no margin"},
{"ticker":"OPRX","price":7.31,"market_cap":138.2e6,"net_debt":-8.95e6,"ev":129.2e6,"reported_pe":27.55,"reported_ev_fcf":6.50,"normalized_fcf":12.889e6,"decision":"WATCH","reason":"10% customer lost; microcap; SBC-adjusted EV/FCF ~10x but revenue quality impaired"}]).to_csv(OUT/"valuation_comparison.csv",index=False)
# risk
R=pd.DataFrame([
("IMMR","CONSOLIDATION","HIGH","BNED VIE 67.4% NCI; FCF attribution impossible"),("IMMR","CONTROL","HIGH","material weakness in internal control"),("IMMR","LICENSING","MEDIUM","15% license revenue concentration"),("IMMR","VALUATION","HIGH","EV/FCF 1.86 not comparable"),
("PHR","SBC","HIGH","$67.5M SBC = 84% of FCF"),("PHR","VALUATION","HIGH","SBC-adjusted EV/FCF ~51x"),("PHR","SOFTWARE","MEDIUM","$13.3M capitalized software"),("PHR","COMPETITION","MEDIUM","healthcare SaaS"),
("OPRX","CUSTOMER","HIGH","10% customer lost; top5 ~47%"),("OPRX","MICROCAP","HIGH","$138M market cap"),("OPRX","SBC","MEDIUM","$7.0M SBC"),("OPRX","CASHFLOW","MEDIUM","FCF $19.9M but customer transition")],columns=["ticker","risk","level","evidence"])
R.to_csv(OUT/"risk_register.csv",index=False)
pd.DataFrame([{"ticker":t,"catalyst":"next 10-Q","invalidation":"FCF/SBC/customer deterioration"} for t in ["IMMR","PHR","OPRX"]]).to_csv(OUT/"catalyst_and_invalidation.csv",index=False)
pd.DataFrame([
{"ticker":"IMMR","decision":"INSUFFICIENT_DATA","confidence":"MEDIUM","paper":False},
{"ticker":"PHR","decision":"WATCH","confidence":"MEDIUM","paper":False},
{"ticker":"OPRX","decision":"WATCH","confidence":"MEDIUM","paper":False}]).to_csv(OUT/"final_decisions.csv",index=False)
print("built",len(rows))
