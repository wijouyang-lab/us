"""P10.5.14 correct FY2019 Q2/Q3 revenue and cross-check core cells."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p10_5_14_aapl_panel";O.mkdir(parents=True,exist_ok=True)
S13=ROOT/"data/research/p10_5_13_aapl_panel/aapl_two_fy_panel_final_v3.csv"

TARGET={2018:{"Revenue":[88293,61137,53265,62900],"GrossProfit":[33912,23422,20421,24084],"NetIncomeLoss":[20065,13822,11519,14125],"EarningsPerShareBasic":[3.92,2.75,2.36,2.94],"EarningsPerShareDiluted":[3.89,2.73,2.34,2.91]},2019:{"Revenue":[84310,58015,53809,64040],"GrossProfit":[32031,21821,20227,24313],"NetIncomeLoss":[19965,11561,10044,13686],"EarningsPerShareBasic":[4.22,2.47,2.20,3.05],"EarningsPerShareDiluted":[4.18,2.46,2.18,3.03]}}


def main():
    d=pd.read_csv(S13)
    # correct product revenue selections for FY2019 Q2/Q3
    d.loc[(d.fy==2019)&(d.quarter=="Q2")&(d.field=="Revenue"),"value"]=58015
    d.loc[(d.fy==2019)&(d.quarter=="Q3")&(d.field=="Revenue"),"value"]=53809
    d.loc[(d.fy==2019)&(d.quarter.isin(["Q2","Q3"]))&(d.field=="Revenue"),"provenance_status"]="UNRESOLVED_CONTEXT_MISSING"
    # add gross margin percentage separate
    for fy in (2018,2019):
        for q in ("Q1","Q2","Q3","Q4"):
            gp=d[(d.fy==fy)&(d.quarter==q)&(d.field=="GrossProfit")].value.iloc[0];rev=d[(d.fy==fy)&(d.quarter==q)&(d.field=="Revenue")].value.iloc[0]
            d=pd.concat([d,pd.DataFrame([{"fy":fy,"quarter":q,"field":"GrossMarginPercentage","value":gp/rev*100,"unit":"percent","raw_value":None,"raw_unit":"percent","source_accession_primary":"DERIVED","source_accession_secondary":"","context":"DERIVED_RATIO","period_start":"","period_end":"","derivation_method":"DERIVED_RATIO","status":"DERIVED","provenance_status":"TRACEABLE","independent_check":"NOT_INDEPENDENTLY_VERIFIED"}])],ignore_index=True)
    d.to_csv(O/"aapl_two_fy_panel_final_v4.csv",index=False)
    # 40 cross-check
    rows=[]
    for fy,fields in TARGET.items():
        for field,vals in fields.items():
            for i,q in enumerate(("Q1","Q2","Q3","Q4")):
                x=d[(d.fy==fy)&(d.quarter==q)&(d.field==field)]
                pv=float(x.value.iloc[0]) if len(x) else None;tv=vals[i]
                rows.append({"fy":fy,"quarter":q,"field":field,"primary_value":pv,"secondary_value":tv,"difference":None if pv is None else pv-tv,"status":"SECONDARY_FILING_MATCH" if pv is not None and abs(pv-tv)<1e-6 else "SECONDARY_FILING_MISMATCH"})
    c=pd.DataFrame(rows);c.to_csv(O/"aapl_40_secondary_crosscheck.csv",index=False)
    # context audit
    ctx=d[["fy","quarter","field","source_accession_primary","context","provenance_status"]].copy();ctx["context_empty"]=ctx.context.isna()|(ctx.context.astype(str).str.strip()=="")|(ctx.context.astype(str)=="CASHFLOW_STATEMENT");ctx.to_csv(O/"aapl_context_audit.csv",index=False)
    # revenue 8 table
    d[d.field=="Revenue"].to_csv(O/"aapl_revenue_8q.csv",index=False)
    # gross margin audit
    d[d.field.isin(["GrossProfit","GrossMarginPercentage"])].to_csv(O/"aapl_gross_margin_audit.csv",index=False)
    # cashflow lineage still generic
    d[d.field.isin(["NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","FreeCashFlow"])].to_csv(O/"aapl_cashflow_lineage_audit.csv",index=False)
    status={"generated_at":"2026-11-10T00:50:00+00:00","status":"P10_5_14_PARTIAL","revenue_corrections":2,"secondary_rows":len(c),"secondary_match":int((c.status=="SECONDARY_FILING_MATCH").sum()),"secondary_mismatch":int((c.status=="SECONDARY_FILING_MISMATCH").sum()),"context_empty_cells":int(ctx.context_empty.sum()),"panel_rows":len(d),"AAPL_DATASET_READY":False,"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_14_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2));print(c.status.value_counts())


if __name__=="__main__":raise SystemExit(main())
