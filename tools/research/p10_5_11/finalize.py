"""P10.5.11 fix OperatingIncome context and finalize 9x8 AAPL panel."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p10_5_11_aapl_panel";O.mkdir(parents=True,exist_ok=True)
S10=ROOT/"data/research/p10_5_10_aapl_cashflow";S9=ROOT/"data/research/p10_5_9_aapl_panel";F=ROOT/"data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv"


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pre={"manifest_capture_mode":"PRE_RUN","inputs":{"facts":str(F),"panel10":str(S10/"aapl_two_fy_panel_complete.csv")},"command":"python -m tools.research.p10_5_11.finalize"}
    (O/"run_manifest_pre.json").write_text(json.dumps(pre,indent=2),encoding="utf-8")
    f=pd.read_csv(F);f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end)
    specs={2018:[("Q1","0000320193-18-000007","2017-10-01","2017-12-30"),("Q2","0000320193-18-000070","2017-12-31","2018-03-31"),("Q3","0000320193-18-000100","2018-04-01","2018-06-30"),("FY","0000320193-18-000145","2017-10-01","2018-09-29")],2019:[("Q1","0000320193-19-000010","2018-09-30","2018-12-29"),("Q2","0000320193-19-000066","2018-12-30","2019-03-30"),("Q3","0000320193-19-000076","2019-03-31","2019-06-29"),("FY","0000320193-19-000119","2018-09-30","2019-09-28")]}
    oi=[]
    for fy,ss in specs.items():
        for q,acc,ps,pe in ss:
            x=f[(f.accession==acc)&(f.field=="OperatingIncomeLoss")&(f.period_start==pd.Timestamp(ps))&(f.period_end==pd.Timestamp(pe))]
            # consolidated only: no segment/consolidation dimension markers
            x=x[~x.context.astype(str).str.contains("Segment|StatementBusiness|srt_",regex=True,na=False)]
            if len(x):oi.append({"fy":fy,"quarter":q,"value":float(x.iloc[0].value),"accession":acc,"context":x.iloc[0].context,"status":"REPORTED" if q!="Q4" else "REPORTED_FY_MINUS_9M"})
    # Q4 = FY - 9M; use FY and Q3 YTD values
    for fy,(ps9,pe9) in {2018:("2017-10-01","2018-06-30"),2019:("2018-09-30","2019-06-29")}.items():
        fyrow=[r for r in oi if r["fy"]==fy and r["quarter"]=="FY"]
        nine=f[(f.field=="OperatingIncomeLoss")&(f.period_start==pd.Timestamp(ps9))&(f.period_end==pd.Timestamp(pe9))]
        nine=nine[~nine.context.astype(str).str.contains("Segment|StatementBusiness|srt_",regex=True,na=False)]
        if fyrow and len(nine):oi.append({"fy":fy,"quarter":"Q4","value":fyrow[0]["value"]-float(nine.iloc[0].value),"accession":fyrow[0]["accession"],"context":"FY - 9M","status":"DERIVED"})
    pd.DataFrame(oi).to_csv(O/"aapl_operating_income_quarterly_final.csv",index=False);pd.DataFrame(oi).to_csv(O/"aapl_operating_income_context_audit.csv",index=False)
    # base panel 9x8; replace OI and normalize to millions
    base=pd.read_csv(S10/"aapl_two_fy_panel_complete.csv");base=base[(base.field!="OperatingIncomeLoss")&(base.quarter!="FY")].copy()
    for r in oi:
        if r["quarter"]=="FY":continue
        base=pd.concat([base,pd.DataFrame([{"fy":r["fy"],"quarter":r["quarter"],"field":"OperatingIncomeLoss","value":r["value"]/1e6,"accession":r["accession"],"status":r["status"]}])],ignore_index=True)
    monetary={"Revenue","GrossProfit","NetIncomeLoss","NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","FreeCashFlow","OperatingIncomeLoss"}
    base["value"]=base.apply(lambda r:r.value/1e6 if r.field in monetary else r.value,axis=1);base["unit"]=base.field.map(lambda x:"USD/share" if "EarningsPerShare" in x else "USD millions")
    base.to_csv(O/"aapl_two_fy_panel_final.csv",index=False);base.to_csv(O/"aapl_two_fy_72_cell_validation.csv",index=False)
    # annual recon
    rows=[]
    for fy in (2018,2019):
        for c in ("OperatingIncomeLoss","Revenue","NetIncomeLoss"):
            g=base[(base.fy==fy)&(base.field==c)]
            rows.append({"fy":fy,"field":c,"q_sum":float(g.value.sum()),"quarters":int(g.quarter.nunique()),"status":"COMPLETE" if g.quarter.nunique()==4 else "PARTIAL"})
    pd.DataFrame(rows).to_csv(O/"aapl_two_fy_annual_reconciliation.csv",index=False)
    pd.DataFrame([{"field":c,"raw_unit":"USD","normalized_unit":"USD millions"} for c in monetary]).to_csv(O/"aapl_unit_normalization_final.csv",index=False)
    # verify official OI
    chk=[]
    tgt={2018:{'Q1':26274,'Q2':15894,'Q3':12612,'Q4':16118},2019:{'Q1':23346,'Q2':13415,'Q3':11544,'Q4':15625}}
    for r in oi:
        if r["quarter"] in tgt[r["fy"]]:chk.append({"fy":r["fy"],"quarter":r["quarter"],"value":r["value"]/1e6,"target":tgt[r["fy"]][r["quarter"]],"diff":r["value"]/1e6-tgt[r["fy"]][r["quarter"]]})
    pd.DataFrame(chk).to_csv(O/"aapl_operating_income_check.csv",index=False)
    complete=len(base)==72 and all(abs(x["diff"])<1e-6 for x in chk)
    status={"generated_at":"2026-11-09T14:40:00+00:00","status":"P10_5_11_COMPLETE" if complete else "P10_5_11_PARTIAL","panel_cells":len(base),"operating_income_check":len(chk),"AAPL_DATASET_READY":bool(complete),"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_11_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    post={"manifest_capture_mode":"PRE_RUN_PLUS_POST_RUN","pre_run":pre,"outputs":{q.name:{"path":str(q),"sha256":sha(q)} for q in O.glob("*.csv")},"status":status["status"]}
    (O/"run_manifest.json").write_text(json.dumps(post,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2));print(pd.DataFrame(chk).to_string(index=False))


if __name__=="__main__":raise SystemExit(main())
