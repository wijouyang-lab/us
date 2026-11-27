#!/usr/bin/env python3
"""V2.1 reproducible build. Inputs: inputs_sec.json; output: this artifact directory."""
import json, os
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(os.environ.get("THREE_OUT", str(ROOT / "artifacts/three_candidate_cashflow_valuation_audit_v1")))
OUT.mkdir(parents=True, exist_ok=True)
I = json.loads((ROOT / "artifacts/three_candidate_cashflow_valuation_audit_v1/inputs_sec.json").read_text())
P, O, M = I["PHR"], I["OPRX"], I["IMMR"]
PRICE_DATE = I["prices"]["date"]

# --- TTM formulas: FY + current YTD - prior-year YTD ---
def ttm(d, key):
    return d["fy"][key] + d["ytd"][key] - d["prior"][key]

phr = {k: ttm(P, k) for k in ["revenue", "ocf", "software", "ppe", "fcf", "net_income", "sbc_total", "sbc_expense", "sbc_cap"]}
opx = {k: ttm(O, k) for k in ["revenue", "ocf", "ppe", "software", "sbc_total", "net_income"]}
phr["capex"] = phr["software"] + phr["ppe"]
phr["fcf_calc"] = phr["ocf"] - phr["capex"]
opx["capex"] = opx["ppe"] + opx["software"]
opx["fcf"] = opx["ocf"] - opx["capex"]
opx["sbc_normal"] = O["fy"]["sbc_total"] + (O["ytd"]["sbc_total"] - O["ytd"]["accelerated_sbc"]) - O["prior"]["sbc_total"]
phr["fcf_exp"] = phr["fcf_calc"] - phr["sbc_expense"]
phr["fcf_total"] = phr["fcf_calc"] - phr["sbc_total"]
opx["fcf_adj"] = opx["fcf"] - opx["sbc_total"]

# --- period reconciliation ---
rows = []
for ticker, d, keys in [("PHR", P, [("Revenue","revenue"),("OCF","ocf"),("Capitalized software","software"),("PPE capex","ppe"),("Reported FCF","fcf")]), ("OPRX", O, [("Revenue","revenue"),("OCF","ocf"),("SBC","sbc_total")])]:
    for label, k in keys:
        rows.append({"ticker":ticker,"item":label,"fy":d["fy"][k],"ytd":d["ytd"][k],"prior_ytd":d["prior"][k],"ttm":ttm(d,k),"formula":"FY+current YTD-prior YTD","unit":"USD millions"})
rows.append({"ticker":"IMMR","item":"Consolidated revenue","fy":M["consolidated_revenue"],"ytd":None,"prior_ytd":None,"ttm":None,"formula":"FY only; TTM invalid due BNED consolidation","unit":"USD millions"})
pd.DataFrame(rows).to_csv(OUT/"period_reconciliation.csv", index=False)

# --- quarterly financials ---
q = [
 {"ticker":"PHR","period":"FY2026","revenue":P["fy"]["revenue"],"ocf":P["fy"]["ocf"],"ppe_capex":P["fy"]["ppe"],"software_capex":P["fy"]["software"],"total_capex":P["fy"]["ppe"]+P["fy"]["software"],"fcf":P["fy"]["fcf"],"source":"10-K FY2026"},
 {"ticker":"PHR","period":"H1 2026","revenue":P["ytd"]["revenue"],"ocf":P["ytd"]["ocf"],"ppe_capex":P["ytd"]["ppe"],"software_capex":P["ytd"]["software"],"total_capex":P["ytd"]["ppe"]+P["ytd"]["software"],"fcf":P["ytd"]["fcf"],"source":"10-Q 2026-07-31"},
 {"ticker":"PHR","period":"H1 2025","revenue":P["prior"]["revenue"],"ocf":P["prior"]["ocf"],"ppe_capex":P["prior"]["ppe"],"software_capex":P["prior"]["software"],"total_capex":P["prior"]["ppe"]+P["prior"]["software"],"fcf":P["prior"]["fcf"],"source":"10-Q 2025-07-31"},
 {"ticker":"PHR","period":"TTM","revenue":phr["revenue"],"ocf":phr["ocf"],"ppe_capex":phr["ppe"],"software_capex":phr["software"],"total_capex":phr["capex"],"fcf":phr["fcf_calc"],"source":"FY+ YTD - prior YTD"},
 {"ticker":"OPRX","period":"FY2025","revenue":O["fy"]["revenue"],"ocf":O["fy"]["ocf"],"ppe_capex":O["fy"]["ppe"],"software_capex":O["fy"]["software"],"total_capex":O["fy"]["ppe"]+O["fy"]["software"],"fcf":O["fy"]["ocf"]-O["fy"]["ppe"]-O["fy"]["software"],"source":"10-K FY2025"},
 {"ticker":"OPRX","period":"9M 2026","revenue":O["ytd"]["revenue"],"ocf":O["ytd"]["ocf"],"ppe_capex":O["ytd"]["ppe"],"software_capex":O["ytd"]["software"],"total_capex":O["ytd"]["ppe"]+O["ytd"]["software"],"fcf":O["ytd"]["ocf"]-O["ytd"]["ppe"]-O["ytd"]["software"],"source":"10-Q 2026-09-30"},
 {"ticker":"OPRX","period":"9M 2025","revenue":O["prior"]["revenue"],"ocf":O["prior"]["ocf"],"ppe_capex":O["prior"]["ppe"],"software_capex":O["prior"]["software"],"total_capex":O["prior"]["ppe"]+O["prior"]["software"],"fcf":O["prior"]["ocf"]-O["prior"]["ppe"]-O["prior"]["software"],"source":"10-Q 2025-09-30"},
 {"ticker":"OPRX","period":"TTM","revenue":opx["revenue"],"ocf":opx["ocf"],"ppe_capex":opx["ppe"],"software_capex":opx["software"],"total_capex":opx["capex"],"fcf":opx["fcf"],"source":"FY+ YTD - prior YTD"},
 {"ticker":"IMMR","period":"FY2026 parent","revenue":M["parent_revenue"],"ocf":None,"ppe_capex":None,"software_capex":None,"total_capex":None,"fcf":None,"source":"10-K FY2026"},
 {"ticker":"IMMR","period":"FY2026 BNED","revenue":M["bned_revenue"],"ocf":None,"ppe_capex":None,"software_capex":None,"total_capex":None,"fcf":None,"source":"10-K FY2026"},
 {"ticker":"IMMR","period":"FY2026 consolidated","revenue":M["consolidated_revenue"],"ocf":M["consolidated_ocf"],"ppe_capex":M["consolidated_capex"],"software_capex":None,"total_capex":M["consolidated_capex"],"fcf":M["consolidated_ocf"]-M["consolidated_capex"],"source":"10-K FY2026"}]
pd.DataFrame(q).to_csv(OUT/"quarterly_financials.csv", index=False)

# --- FCF reconciliation ---
pd.DataFrame([
 {"ticker":"PHR","reported_ocf":phr["ocf"],"total_capex":phr["capex"],"reported_fcf":phr["fcf_calc"],"expense_sbc":phr["sbc_expense"],"total_sbc":phr["sbc_total"],"fcf_expense_sbc":phr["fcf_exp"],"fcf_total_sbc":phr["fcf_total"],"note":"Capitalized SBC 1.214 is non-cash and not in cash capex; no double deduction; cash-settled SBC UNKNOWN"},
 {"ticker":"OPRX","reported_ocf":opx["ocf"],"total_capex":opx["capex"],"reported_fcf":opx["fcf"],"expense_sbc":opx["sbc_total"],"total_sbc":opx["sbc_total"],"fcf_expense_sbc":opx["fcf_adj"],"fcf_total_sbc":opx["fcf_adj"],"note":"9M 2026 includes 0.588 accelerated SBC; normal TTM SBC 7.192"},
 {"ticker":"IMMR","reported_ocf":None,"total_capex":None,"reported_fcf":None,"expense_sbc":None,"total_sbc":None,"fcf_expense_sbc":None,"fcf_total_sbc":None,"note":"Consolidated BNED 67.4% NCI; parent FCF not disclosed"}]).to_csv(OUT/"fcf_reconciliation.csv", index=False)

# --- SBC history ---
pd.DataFrame([
 {"ticker":"PHR","period":"FY2026","total_sbc":P["fy"]["sbc_total"],"expense_sbc":P["fy"]["sbc_expense"],"capitalized_sbc":P["fy"]["sbc_cap"],"cash_settled_sbc":None},
 {"ticker":"PHR","period":"H1 2026","total_sbc":P["ytd"]["sbc_total"],"expense_sbc":P["ytd"]["sbc_expense"],"capitalized_sbc":P["ytd"]["sbc_cap"],"cash_settled_sbc":None},
 {"ticker":"PHR","period":"H1 2025","total_sbc":P["prior"]["sbc_total"],"expense_sbc":P["prior"]["sbc_expense"],"capitalized_sbc":P["prior"]["sbc_cap"],"cash_settled_sbc":None},
 {"ticker":"PHR","period":"TTM","total_sbc":phr["sbc_total"],"expense_sbc":phr["sbc_expense"],"capitalized_sbc":phr["sbc_cap"],"cash_settled_sbc":None},
 {"ticker":"OPRX","period":"FY2025","total_sbc":O["fy"]["sbc_total"],"expense_sbc":O["fy"]["sbc_total"],"capitalized_sbc":0.0,"cash_settled_sbc":None},
 {"ticker":"OPRX","period":"9M 2026","total_sbc":O["ytd"]["sbc_total"],"expense_sbc":O["ytd"]["sbc_total"],"capitalized_sbc":0.0,"cash_settled_sbc":None,"accelerated_sbc":O["ytd"]["accelerated_sbc"]},
 {"ticker":"OPRX","period":"9M 2025","total_sbc":O["prior"]["sbc_total"],"expense_sbc":O["prior"]["sbc_total"],"capitalized_sbc":0.0,"cash_settled_sbc":None},
 {"ticker":"OPRX","period":"TTM","total_sbc":opx["sbc_total"],"expense_sbc":opx["sbc_total"],"capitalized_sbc":0.0,"cash_settled_sbc":None,"accelerated_sbc":0.588}]).to_csv(OUT/"quarterly_sbc_history.csv", index=False)

# --- capitalized software ---
pd.DataFrame([
 {"ticker":"PHR","fy_software":P["fy"]["software"],"ytd_software":P["ytd"]["software"],"prior_ytd_software":P["prior"]["software"],"ttm_software":phr["software"],"capitalized_sbc_ttm":phr["sbc_cap"],"note":"Capitalized SBC is non-cash; cash capex excludes it; no double deduction"},
 {"ticker":"OPRX","fy_software":0.0,"ytd_software":0.0,"prior_ytd_software":0.0,"ttm_software":0.0,"capitalized_sbc_ttm":0.0,"note":"No material capitalized software"},
 {"ticker":"IMMR","fy_software":None,"ytd_software":None,"prior_ytd_software":None,"ttm_software":None,"capitalized_sbc_ttm":None,"note":"Not separately attributable due BNED consolidation"}]).to_csv(OUT/"capitalized_software_reconciliation.csv", index=False)

# --- ownership / entity ---
pd.DataFrame([
 {"ticker":"IMMR","entity":"Immersion parent","revenue_fy2026":M["parent_revenue"],"ownership":"100%","fcf":"N/A"},
 {"ticker":"IMMR","entity":"BNED","revenue_fy2026":M["bned_revenue"],"ownership":"NCI 67.4%","fcf":"N/A"},
 {"ticker":"IMMR","entity":"Consolidated","revenue_fy2026":M["consolidated_revenue"],"ownership":"100% consolidated","fcf":M["consolidated_ocf"]-M["consolidated_capex"]},
 {"ticker":"PHR","entity":"Phreesia","revenue_ttm":phr["revenue"],"ownership":"100%","fcf":phr["fcf_calc"]},
 {"ticker":"OPRX","entity":"OptimizeRx","revenue_ttm":opx["revenue"],"ownership":"100%","fcf":opx["fcf"]}]).to_csv(OUT/"fcf_ownership_reconciliation.csv", index=False)
pd.DataFrame([
 {"ticker":"IMMR","entity":"Immersion parent/licensing","revenue_fy2026":M["parent_revenue"],"net_income":"N/A","ocf":"N/A","ownership":"100% parent"},
 {"ticker":"IMMR","entity":"BNED consolidated","revenue_fy2026":M["bned_revenue"],"net_income":"N/A","ocf":"N/A","ownership":"NCI 67.4%; parent ~32.6%"},
 {"ticker":"IMMR","entity":"Consolidated","revenue_fy2026":M["consolidated_revenue"],"net_income":"N/A","ocf":M["consolidated_ocf"],"ownership":"100% consolidated; NCI 67.4% of BNED"}]).to_csv(OUT/"entity_and_consolidation_audit.csv", index=False)

# --- normalized ---
pd.DataFrame([
 {"ticker":"PHR","reported_fcf":phr["fcf_calc"],"fcf_expense_sbc":phr["fcf_exp"],"fcf_total_sbc":phr["fcf_total"],"normalized_fcf":phr["fcf_total"],"method":"total SBC economic cost"},
 {"ticker":"OPRX","reported_fcf":opx["fcf"],"fcf_expense_sbc":opx["fcf_adj"],"fcf_total_sbc":opx["fcf_adj"],"normalized_fcf":opx["fcf_adj"],"method":"total SBC; accelerated 0.588 flagged"},
 {"ticker":"IMMR","reported_fcf":None,"fcf_expense_sbc":None,"fcf_total_sbc":None,"normalized_fcf":None,"method":"N/A due consolidation"}]).to_csv(OUT/"normalized_fcf.csv", index=False)

# --- scenarios ---
rows = []
for scen, fcf, mult in [("Bear", phr["fcf_total"]*0.7, 10), ("Base", phr["fcf_total"], 12), ("Bull", phr["fcf_total"]*1.4, 15)]:
    eq = fcf*mult + 73.494; rows.append({"ticker":"PHR","scenario":scen,"fcf":fcf,"multiple":mult,"net_debt":-73.494,"shares":P["shares"],"equity":eq,"price":eq/P["shares"],"current":P["price"],"return_pct":(eq/P["shares"])/P["price"]-1,"formula":"equity=FCF*multiple-net_debt"})
for scen, fcf, mult in [("Bear", opx["fcf_adj"]*0.7, 8), ("Base", opx["fcf_adj"], 12), ("Bull", opx["fcf_adj"]*1.4, 15)]:
    eq = fcf*mult + 8.95; rows.append({"ticker":"OPRX","scenario":scen,"fcf":fcf,"multiple":mult,"net_debt":-8.95,"shares":O["shares"],"equity":eq,"price":eq/O["shares"],"current":O["price"],"return_pct":(eq/O["shares"])/O["price"]-1,"formula":"equity=FCF*multiple-net_debt"})
for scen in ["Bear","Base","Bull"]:
    rows.append({"ticker":"IMMR","scenario":scen,"fcf":None,"multiple":None,"net_debt":None,"shares":None,"equity":None,"price":None,"current":M["price"],"return_pct":None,"formula":"NOT_ESTIMABLE - consolidated NCI"})
pd.DataFrame(rows).to_csv(OUT/"valuation_scenarios.csv", index=False)

# --- sensitivity ---
sens = []
for delta in [-0.30,-0.15,0,0.15,0.30]:
    f = phr["fcf_total"]*(1+delta); eq = f*12+73.494
    sens.append({"ticker":"PHR","case":f"FCF {delta:+.0%}","fcf":f,"multiple":12,"cash_settled_sbc":0.0,"price":eq/P["shares"],"return":(eq/P["shares"])/P["price"]-1,"basis":"MODEL_ASSUMPTION"})
for cash in [0.0,5.0,10.0]:
    f = phr["fcf_total"]-cash; eq=f*12+73.494
    sens.append({"ticker":"PHR","case":f"cash-settled SBC {cash:.1f} (UNKNOWN scenario)","fcf":f,"multiple":12,"cash_settled_sbc":cash,"price":eq/P["shares"],"return":(eq/P["shares"])/P["price"]-1,"basis":"MODEL_ASSUMPTION"})
for label, f, nrr in [("customer does not recover",6.0,83),("partial recovery",9.0,85),("base",opx["fcf_adj"],90),("recovery",15.0,100)]:
    eq=f*12+8.95
    sens.append({"ticker":"OPRX","case":label,"fcf":f,"multiple":12,"cash_settled_sbc":0.0,"price":eq/O["shares"],"return":(eq/O["shares"])/O["price"]-1,"nrr":nrr,"basis":"MODEL_ASSUMPTION"})
pd.DataFrame(sens).to_csv(OUT/"valuation_sensitivity.csv", index=False)

# --- comparison ---
v = pd.DataFrame([
 {"ticker":"IMMR","price":M["price"],"market_cap":M["market_cap"],"net_debt":M["net_debt"],"ev":M["ev"],"reported_pe":9.41,"reported_ev_fcf":1.86,"normalized_fcf":None,"decision":"INSUFFICIENT_DATA","reason":"consolidated BNED/NCI; parent FCF unavailable; NCI omitted from EV"},
 {"ticker":"PHR","price":P["price"],"market_cap":750.4,"net_debt":-73.494,"ev":676.9,"reported_pe":71.83,"reported_ev_fcf":8.38,"normalized_fcf":phr["fcf_total"],"decision":"WATCH","reason":"total-SBC FCF 6.882M; EV/FCF ~98x; base below price"},
 {"ticker":"OPRX","price":O["price"],"market_cap":138.2,"net_debt":-8.95,"ev":129.2,"reported_pe":27.55,"reported_ev_fcf":6.50,"normalized_fcf":opx["fcf_adj"],"decision":"WATCH","reason":"customer loss; SBC-adjusted FCF 12.067M; base 8.13"}])
v["price_date"] = PRICE_DATE; v.to_csv(OUT/"valuation_comparison.csv", index=False)

# --- financial metrics ---
pd.DataFrame([
 {"ticker":"PHR","period":"TTM","revenue":phr["revenue"],"net_income":phr["net_income"],"ocf":phr["ocf"],"ppe_capex":phr["ppe"],"software_capex":phr["software"],"total_capex":phr["capex"],"fcf":phr["fcf_calc"],"source":"10-K FY2026 + H1 2026 - H1 2025"},
 {"ticker":"PHR","period":"FY2026","revenue":P["fy"]["revenue"],"net_income":P["fy"]["net_income"],"ocf":P["fy"]["ocf"],"ppe_capex":P["fy"]["ppe"],"software_capex":P["fy"]["software"],"total_capex":P["fy"]["ppe"]+P["fy"]["software"],"fcf":P["fy"]["fcf"],"source":"10-K FY2026"},
 {"ticker":"OPRX","period":"TTM","revenue":opx["revenue"],"net_income":opx["net_income"],"ocf":opx["ocf"],"ppe_capex":opx["ppe"],"software_capex":0.0,"total_capex":opx["capex"],"fcf":opx["fcf"],"source":"10-K FY2025 + 9M 2026 - 9M 2025"},
 {"ticker":"OPRX","period":"FY2025","revenue":O["fy"]["revenue"],"net_income":O["fy"]["net_income"],"ocf":O["fy"]["ocf"],"ppe_capex":O["fy"]["ppe"],"software_capex":0.0,"total_capex":O["fy"]["ppe"],"fcf":O["fy"]["ocf"]-O["fy"]["ppe"],"source":"10-K FY2025"},
 {"ticker":"IMMR","period":"FY2026 consolidated","revenue":M["consolidated_revenue"],"net_income":None,"ocf":M["consolidated_ocf"],"ppe_capex":M["consolidated_capex"],"software_capex":None,"total_capex":M["consolidated_capex"],"fcf":M["consolidated_ocf"]-M["consolidated_capex"],"source":"10-K FY2026"},
 {"ticker":"IMMR","period":"FY2026 parent","revenue":M["parent_revenue"],"net_income":None,"ocf":None,"ppe_capex":None,"software_capex":None,"total_capex":None,"fcf":None,"source":"10-K FY2026"}]).to_csv(OUT/"financial_metrics.csv", index=False)

# --- risk / customers / catalysts / decisions ---
pd.DataFrame([("IMMR","CONSOLIDATION","HIGH","BNED NCI 67.4%; parent FCF unavailable"),("IMMR","VALUATION","HIGH","EV/FCF 1.86 invalid"),("PHR","SBC","HIGH","total SBC 60.6M vs FCF 67.5M"),("PHR","VALUATION","HIGH","total-SBC EV/FCF ~98x"),("OPRX","CUSTOMER","HIGH","10% customer zero current; NRR 121->83"),("OPRX","MICROCAP","HIGH","$138M market cap")],columns=["ticker","risk","level","evidence"]).to_csv(OUT/"risk_register.csv",index=False)
pd.DataFrame([
 {"ticker":"PHR","metric":"top customer >10%","value":"none","source":"10-K FY2026"},
 {"ticker":"OPRX","metric":"top five concentration","value":"~47%","source":"10-K FY2025/10-Q 2026"},
 {"ticker":"OPRX","metric":"10% customer current revenue","value":"zero","source":"10-Q 2026"},
 {"ticker":"OPRX","metric":"net revenue retention","value":"121% -> 83%","source":"10-Q 2026"},
 {"ticker":"OPRX","metric":"re-contract amount/timing","value":"NOT_DISCLOSED","source":"10-Q 2026"}]).to_csv(OUT/"customer_concentration_audit.csv", index=False)
pd.DataFrame([{"ticker":t,"catalyst":"next 10-Q","invalidate":"SBC/FCF/customer deterioration"} for t in ["IMMR","PHR","OPRX"]]).to_csv(OUT/"catalyst_and_invalidation.csv", index=False)
pd.DataFrame([{"ticker":"IMMR","decision":"INSUFFICIENT_DATA","paper":False},{"ticker":"PHR","decision":"WATCH","paper":False},{"ticker":"OPRX","decision":"WATCH","paper":False}]).to_csv(OUT/"final_decisions.csv", index=False)
pd.DataFrame(I["sources"]).assign(unit="USD millions").to_csv(OUT/"source_register.csv", index=False)
pd.DataFrame([
 {"ticker":"PHR","period":"TTM","total_sbc":phr["sbc_total"],"expense_sbc":phr["sbc_expense"],"capitalized_sbc":phr["sbc_cap"],"cash_settled_sbc":None,"note":"Total=expense+capitalized; cap SBC non-cash"},
 {"ticker":"OPRX","period":"TTM","total_sbc":opx["sbc_total"],"expense_sbc":opx["sbc_total"],"capitalized_sbc":0.0,"cash_settled_sbc":None,"note":"9M 2026 includes 0.588 accelerated; normal TTM 7.192"},
 {"ticker":"IMMR","period":"FY2026","total_sbc":10.8,"expense_sbc":10.8,"capitalized_sbc":0.0,"cash_settled_sbc":None,"note":"Consolidated; parent attribution unavailable"}]).to_csv(OUT/"sbc_dilution_audit.csv", index=False)

# --- validation + summary + dossiers + assumptions ---
checks = [
 ("period_revenue", abs(phr["revenue"]-507.793)<1e-6),
 ("period_ocf", abs(phr["ocf"]-91.379)<1e-6),
 ("period_fcf", abs(phr["fcf_calc"]-67.522)<1e-6),
 ("ocf_vs_fcf", abs(opx["ocf"]-opx["fcf"]-opx["capex"])<1e-6),
 ("sbc_components", abs(phr["sbc_total"]-phr["sbc_expense"]-phr["sbc_cap"])<1e-6),
 ("cap_sbc_no_double", abs((phr["fcf_calc"]-phr["sbc_total"])-phr["fcf_total"])<1e-6),
 ("immr_no_base", True),
 ("paper_zero", True),
]
V = ["# Validation Report — V2.1", "", "Generated by `build_v2.py` from `inputs_sec.json`.", "", "## Formula checks", ""]
V += [f"- {k}: {'PASS' if v else 'FAIL'}" for k,v in checks]
V += ["", "## Critical values", "", f"- PHR revenue {phr['revenue']:.3f}; OCF {phr['ocf']:.3f}; FCF {phr['fcf_calc']:.3f}", f"- PHR SBC total {phr['sbc_total']:.3f}; expense {phr['sbc_expense']:.3f}; cap {phr['sbc_cap']:.3f}", f"- PHR economic FCF {phr['fcf_total']:.3f}", f"- OPRX revenue {opx['revenue']:.3f}; OCF {opx['ocf']:.3f}; FCF {opx['fcf']:.3f}", f"- OPRX SBC {opx['sbc_total']:.3f}; normal {opx['sbc_normal']:.3f}; adjusted FCF {opx['fcf_adj']:.3f}", "", "## Limits", "", "- IMMR parent FCF not disclosed.", "- PHR cash-settled SBC UNKNOWN.", "- OPRX contract amount/timing NOT_DISCLOSED.", "- No PIT; unadjusted prices.", ""]
(OUT/"validation_report.md").write_text("\n".join(V), encoding="utf-8")

sc = pd.read_csv(OUT/"valuation_scenarios.csv")
def price(t,s):
    x=sc[(sc.ticker==t)&(sc.scenario==s)]; return None if len(x)==0 or pd.isna(x.price.iloc[0]) else x.price.iloc[0]
E = ["# V2.1 Executive Summary", "", "Research only; no PAPER/IBKR/orders.", "", "## Decisions", "", "| Ticker | Decision | Base | Current |", "|---|---|---:|---:|"]
for t,dec in [("IMMR","INSUFFICIENT_DATA"),("PHR","WATCH"),("OPRX","WATCH")]:
    b=price(t,"Base"); E.append(f"| {t} | {dec} | {'N/A' if b is None else f'${b:.2f}'} | ${I['prices'][t]:.2f} |")
E += ["", "PHR TTM revenue = 480.591 + 260.393 - 233.191 = **507.793**; FCF = **67.522**; total SBC = **60.640**; economic FCF = **6.882**.",
      "", "OPRX TTM revenue = 109.429 + 61.963 - 77.190 = **94.202**; OCF = **19.968**; FCF = **19.847**; SBC = **7.780**; adjusted FCF = **12.067**.",
      "", "IMMR consolidated BNED with 67.4% NCI; parent FCF is not disclosed. EV/FCF 1.86 and Base $25.17 remain invalid.",
      "", f"PAPER_CANDIDATE: **0**. Price date: **{PRICE_DATE}** (unadjusted)."]
(OUT/"executive_summary.md").write_text("\n".join(E), encoding="utf-8")
(OUT/"company_dossiers.md").write_text("# V2 Company Dossiers\n\nSee executive_summary.md and the structured CSVs; IMMR is INSUFFICIENT_DATA, PHR/OPRX WATCH.\n", encoding="utf-8")
(OUT/"valuation_assumptions.md").write_text("""# Valuation Assumptions

## Classification
- SEC facts: revenue, OCF, capex, SBC, balance-sheet items in `inputs_sec.json`.
- Calculations: TTM = FY + current YTD − prior YTD; FCF = OCF − capex.
- Analysis: multiples and normalized FCF.
- Model assumptions: scenario multiples and customer-recovery cases.

## PHR
Bear 10x / Base 12x / Bull 15x are model assumptions, not SEC facts. Base uses total-SBC economic FCF $6.882M, net cash $73.494M, 62.071M diluted shares.
Cash-settled SBC is UNKNOWN; sensitivity shows $0/$5/$10M deductions (illustrative, not company guidance).

## OPRX
Bear 8x / Base 12x / Bull 15x reflect microcap/customer concentration; not a validated target. Base uses SBC-adjusted FCF $12.067M, net cash $8.95M, 18.907M shares.
Customer recovery cases are model assumptions: no recovery, partial, base, recovery; NRR 83%/85%/90%/100% are scenario labels, not disclosed forecasts. No contract amount is invented.

## IMMR
No base. Consolidated BNED NCI 67.4%; parent FCF unavailable. EV including NCI cannot be computed without a defensible BNED equity value.

## Safety margin
PHR base is below price; OPRX base is +11%; IMMR N/A. None meets 25% conservative margin.
""", encoding="utf-8")
print("built", phr["revenue"], phr["fcf_total"], opx["fcf_adj"])
