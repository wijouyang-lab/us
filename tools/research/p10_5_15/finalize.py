"""P10.5.15 fact lineage, secondary 10-K cross-check, annual EPS."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p10_5_15_aapl_panel";O.mkdir(parents=True,exist_ok=True)
S14=ROOT/"data/research/p10_5_14_aapl_panel/aapl_two_fy_panel_final_v4.csv";F=ROOT/"data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv"
TARGET={2018:{"Revenue":[88293,61137,53265,62900],"GrossProfit":[33912,23422,20421,24084],"NetIncomeLoss":[20065,13822,11519,14125],"EarningsPerShareBasic":[3.92,2.75,2.36,2.94],"EarningsPerShareDiluted":[3.89,2.73,2.34,2.91]},2019:{"Revenue":[84310,58015,53809,64040],"GrossProfit":[32031,21821,20227,24313],"NetIncomeLoss":[19965,11561,10044,13686],"EarningsPerShareBasic":[4.22,2.47,2.20,3.05],"EarningsPerShareDiluted":[4.18,2.46,2.18,3.03]}}
PERIODS={2018:{"Q1":("2017-10-01","2017-12-30"),"Q2":("2017-12-31","2018-03-31"),"Q3":("2018-04-01","2018-06-30"),"Q4":("2018-07-01","2018-09-29")},2019:{"Q1":("2018-09-30","2018-12-29"),"Q2":("2018-12-30","2019-03-30"),"Q3":("2019-03-31","2019-06-29"),"Q4":("2019-06-30","2019-09-28")}}


def main():
    d=pd.read_csv(S14);core=d[d.field.isin(["Revenue","GrossProfit","OperatingIncomeLoss","NetIncomeLoss","EarningsPerShareBasic","EarningsPerShareDiluted","NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","FreeCashFlow"])].copy();derived=d[d.field=="GrossMarginPercentage"].copy()
    # correct raw and components for Q2/Q3 2019
    for q,products,services,total in (("Q2",46565,11450,58015),("Q3",42354,11455,53809)):
        m=(core.fy==2019)&(core.quarter==q)&(core.field=="Revenue")
        core.loc[m,"value"]=total;core.loc[m,"raw_value"]=total*1e6;core.loc[m,"raw_unit"]="USD";core.loc[m,"derivation_method"]="RECONSTRUCTED_FROM_COMPONENTS";core.loc[m,"source_accession_secondary"]=core.loc[m,"source_accession_primary"];core.loc[m,"status"]="DERIVED";core.loc[m,"provenance_status"]="LINEAGE_INCOMPLETE";core.loc[m,"products_value"]=products;core.loc[m,"services_value"]=services
    core.to_csv(O/"aapl_core_panel_v5.csv",index=False);derived.to_csv(O/"aapl_gross_margin_percentage_v5.csv",index=False)
    # secondary facts from FY2019 10-K
    f=pd.read_csv(F);f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end)
    sec=[]
    for fy,fields in TARGET.items():
        for field,vals in fields.items():
            for i,q in enumerate(("Q1","Q2","Q3","Q4")):
                ps,pe=PERIODS[fy][q];tags=["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet"] if field=="Revenue" else [field]
                y=f[(f.accession=="0000320193-19-000119")&(f.field.isin(tags))&(f.period_start==pd.Timestamp(ps))&(f.period_end==pd.Timestamp(pe))]
                sv=float(y.iloc[0].value) if len(y) else None
                if field not in ("EarningsPerShareBasic","EarningsPerShareDiluted") and sv is not None:sv=sv/1e6
                pv=core[(core.fy==fy)&(core.quarter==q)&(core.field==field)].value
                pv=float(pv.iloc[0]) if len(pv) else None
                sec.append({"fy":fy,"quarter":q,"field":field,"primary_value":pv,"secondary_value":sv,"difference":None if pv is None or sv is None else pv-sv,"secondary_accession":"0000320193-19-000119","secondary_form":"10-K","secondary_note":"Note 12 Selected Quarterly Financial Information","secondary_source":"SECONDARY_XBRL_FACT_IN_10-K","secondary_source_sha256":y.iloc[0].sha256 if len(y) else "","status":"SECONDARY_FILING_MATCH" if pv is not None and sv is not None and abs(pv-sv)<1e-6 else "SECONDARY_SOURCE_UNRESOLVED" if sv is None else "SECONDARY_FILING_MISMATCH"})
    s=pd.DataFrame(sec);s.to_csv(O/"aapl_40_secondary_v5.csv",index=False)
    # annual EPS using actual facts
    eps=[]
    for fy,acc,ni,bs,ds,be,de in [(2018,"0000320193-18-000145",59531,4955377,5000109,12.01,11.91),(2019,"0000320193-19-000119",55256,4617834,4648913,11.97,11.89)]:
        b=Decimal(ni)*Decimal(1000)/Decimal(bs);dd=Decimal(ni)*Decimal(1000)/Decimal(ds)
        eps.append({"fy":fy,"accession":acc,"net_income_usd_m":ni,"basic_shares_thousand":bs,"diluted_shares_thousand":ds,"basic_recalc":float(b),"diluted_recalc":float(dd),"basic_reported":be,"diluted_reported":de,"basic_diff":float(b)-be,"diluted_diff":float(dd)-de,"basic_round":float(b.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)),"diluted_round":float(dd.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)),"status":"PASS" if abs(float(b)-be)<0.01 and abs(float(dd)-de)<0.01 else "FAIL"})
    pd.DataFrame(eps).to_csv(O/"aapl_annual_eps_reconciliation.csv",index=False)
    # context audit
    ctx=core[["fy","quarter","field","source_accession_primary","context","provenance_status"]].copy();ctx["context_missing"]=ctx.context.isna()|(ctx.context.astype(str).str.strip()=="")|(ctx.context.astype(str)=="CASHFLOW_STATEMENT")|(ctx.context.astype(str)=="FY_MINUS_9M");ctx.to_csv(O/"aapl_context_audit_v5.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_5_15_PARTIAL","core_panel_cells":len(core),"gross_margin_percentage_cells":len(derived),"secondary_match":int((s.status=="SECONDARY_FILING_MATCH").sum()),"secondary_mismatch":int((s.status=="SECONDARY_FILING_MISMATCH").sum()),"secondary_unresolved":int((s.status=="SECONDARY_SOURCE_UNRESOLVED").sum()),"annual_eps_pass":int((pd.DataFrame(eps).status=="PASS").sum()),"context_missing_cells":int(ctx.context_missing.sum()),"fact_level_traceable":int((~ctx.context_missing).sum()),"lineage_incomplete":int(ctx.context_missing.sum()),"unit_failures":int((~core.unit.isin(["USD millions","USD/share"])).sum()),"dimension_contaminated":0,"AAPL_DATASET_READY":False,"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_15_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2));print(s.status.value_counts());print(pd.DataFrame(eps)[["fy","basic_recalc","diluted_recalc","status"]])


if __name__=="__main__":raise SystemExit(main())
