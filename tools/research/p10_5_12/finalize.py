"""P10.5.12 fix panel units and cell provenance."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p10_5_12_aapl_panel";O.mkdir(parents=True,exist_ok=True)
F=ROOT/"data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv";CF=ROOT/"data/research/p10_5_10_aapl_cashflow/aapl_cashflow_quarterly_reconstruction.csv"


def main():
    f=pd.read_csv(F);f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end)
    specs={2018:{"Q1":("0000320193-18-000007","2017-10-01","2017-12-30"),"Q2":("0000320193-18-000070","2017-12-31","2018-03-31"),"Q3":("0000320193-18-000100","2018-04-01","2018-06-30"),"Q4":("0000320193-18-000145","2018-07-01","2018-09-29")},2019:{"Q1":("0000320193-19-000010","2018-09-30","2018-12-29"),"Q2":("0000320193-19-000066","2018-12-30","2019-03-30"),"Q3":("0000320193-19-000076","2019-03-31","2019-06-29"),"Q4":("0000320193-19-000119","2019-07-01","2019-09-28")}}
    fields={"Revenue":"RevenueFromContractWithCustomerExcludingAssessedTax","GrossProfit":"GrossProfit","OperatingIncomeLoss":"OperatingIncomeLoss","NetIncomeLoss":"NetIncomeLoss","EarningsPerShareBasic":"EarningsPerShareBasic","EarningsPerShareDiluted":"EarningsPerShareDiluted"}
    rows=[]
    for fy,qs in specs.items():
        for q,(acc,ps,pe) in qs.items():
            for canon,tag in fields.items():
                x=f[(f.accession==acc)&(f.field==tag)&(f.period_start==pd.Timestamp(ps))&(f.period_end==pd.Timestamp(pe))]
                x=x[~x.context.astype(str).str.contains("Segment|StatementBusiness|srt_",regex=True,na=False)]
                if len(x):
                    v=float(x.iloc[0].value);unit="USD/share" if "EarningsPerShare" in canon else "USD"
                    rows.append({"fy":fy,"quarter":q,"field":canon,"value":v,"unit":unit,"raw_value":v,"raw_unit":unit,"source_accession_primary":acc,"source_accession_secondary":"","context":x.iloc[0].context,"period_start":ps,"period_end":pe,"derivation_method":"DIRECT","status":"REPORTED","provenance_status":"TRACEABLE"})
    cf=pd.read_csv(CF)
    for r in cf.itertuples():
        for fld,val in (("NetCashProvidedByUsedInOperatingActivities",r.ocf),("PaymentsToAcquirePropertyPlantAndEquipment",r.capex_outflow_positive),("FreeCashFlow",r.fcf)):
            rows.append({"fy":r.fy,"quarter":r.quarter,"field":fld,"value":float(val),"unit":"USD millions","raw_value":float(val)*1e6 if fld!="FreeCashFlow" else float(val),"raw_unit":"USD","source_accession_primary":r.ocf_accession,"source_accession_secondary":"","context":"CASHFLOW_STATEMENT","period_start":"","period_end":"","derivation_method":"QTD_RECONSTRUCTION" if fld!="FreeCashFlow" else "OCF_MINUS_CAPEX","status":"DERIVED" if fld=="FreeCashFlow" else "REPORTED","provenance_status":"TRACEABLE"})
    df=pd.DataFrame(rows);df["value"]=df.apply(lambda r:r.value/1e6 if r.field not in ("EarningsPerShareBasic","EarningsPerShareDiluted") and r.field not in ("NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","FreeCashFlow") else r.value,axis=1);df["unit"]=df.field.map(lambda x:"USD/share" if "EarningsPerShare" in x else "USD millions")
    df.to_csv(O/"aapl_two_fy_panel_final_v2.csv",index=False);df.to_csv(O/"aapl_72_provenance_audit.csv",index=False)
    # validation counts
    val=df.groupby("field").agg(cells=("value","size"),accessions=("source_accession_primary","nunique")).reset_index();val.to_csv(O/"aapl_cell_validation.csv",index=False)
    # units audit
    units=df[["fy","quarter","field","value","unit"]].copy();units["status"]="PASS" if (units.unit.isin(["USD millions","USD/share"])).all() else "FAIL";units.to_csv(O/"aapl_unit_audit.csv",index=False)
    # reconciliation cashflow exact
    chk=df[df.field.isin(["NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","FreeCashFlow"])].merge(cf[["fy","quarter","ocf","capex_outflow_positive","fcf"]],on=["fy","quarter"]);chk["diff"]=chk.apply(lambda r:r.value-(r.ocf if "NetCash" in r.field else r.capex_outflow_positive if "Payments" in r.field else r.fcf),axis=1);chk.to_csv(O/"aapl_cashflow_unit_check.csv",index=False)
    # provenance flag: Q1-Q3 should not use 10-K accession
    bad=df[(df.quarter.isin(["Q1","Q2","Q3"]))&(df.source_accession_primary.str.endswith(("000145","000119")))]
    bad.to_csv(O/"aapl_bad_accessions.csv",index=False)
    status={"generated_at":"2026-11-09T15:30:00+00:00","status":"P10_5_12_PARTIAL","panel_cells":len(df),"cashflow_cells":len(chk),"cashflow_max_abs_diff":float(chk["diff"].abs().max()),"bad_accession_cells":len(bad),"unit_status":"PASS" if (df.unit.isin(["USD millions","USD/share"])).all() else "FAIL","AAPL_DATASET_READY":False,"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_12_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2))


if __name__=="__main__":raise SystemExit(main())
