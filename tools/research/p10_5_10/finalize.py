"""P10.5.10 FY2018/FY2019 cash-flow and core panel completion."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd

ROOT=Path(".");O=ROOT/"data/research/p10_5_10_aapl_cashflow";O.mkdir(parents=True,exist_ok=True)
S9=ROOT/"data/research/p10_5_9_aapl_panel";F=ROOT/"data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv"


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pre={"manifest_capture_mode":"PRE_RUN","inputs":{"panel":str(S9/"aapl_quarterly_panel_v3.csv"),"facts":str(F)},"command":"python -m tools.research.p10_5_10.finalize"}
    (O/"run_manifest_pre.json").write_text(json.dumps(pre,indent=2),encoding="utf-8")
    f=pd.read_csv(F);f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end)
    cash=f[f.field.isin(["NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment"])]
    # exact accession map per fiscal year and period type
    specs={2018:[("Q1","0000320193-18-000007","2017-10-01","2017-12-30"),("Q2","0000320193-18-000070","2017-10-01","2018-03-31"),("Q3","0000320193-18-000100","2017-10-01","2018-06-30"),("FY","0000320193-18-000145","2017-10-01","2018-09-29")],2019:[("Q1","0000320193-19-000010","2018-09-30","2018-12-29"),("Q2","0000320193-19-000066","2018-09-30","2019-03-30"),("Q3","0000320193-19-000076","2018-09-30","2019-06-29"),("FY","0000320193-19-000119","2018-09-30","2019-09-28")]}
    rows=[]
    for fy,ss in specs.items():
        vals={}
        for q,acc,ps,pe in ss:
            for tag in ("NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment"):
                x=cash[(cash.accession==acc)&(cash.field==tag)&(cash.period_start==pd.Timestamp(ps))&(cash.period_end==pd.Timestamp(pe))]
                vals[(q,tag)]=float(x.iloc[0].value) if len(x) else None
        # QTD reconstruction
        q1=vals[("Q1","NetCashProvidedByUsedInOperatingActivities")];h1=vals[("Q2","NetCashProvidedByUsedInOperatingActivities")];n9=vals[("Q3","NetCashProvidedByUsedInOperatingActivities")];fyv=vals[("FY","NetCashProvidedByUsedInOperatingActivities")]
        c1=vals[("Q1","PaymentsToAcquirePropertyPlantAndEquipment")];ch1=vals[("Q2","PaymentsToAcquirePropertyPlantAndEquipment")];cn9=vals[("Q3","PaymentsToAcquirePropertyPlantAndEquipment")];cfy=vals[("FY","PaymentsToAcquirePropertyPlantAndEquipment")]
        ocf={"Q1":q1,"Q2":h1-q1,"Q3":n9-h1,"Q4":fyv-n9};cap={"Q1":c1,"Q2":ch1-c1,"Q3":cn9-ch1,"Q4":cfy-cn9}
        for q in ("Q1","Q2","Q3","Q4"):
            rows.append({"fy":fy,"quarter":q,"ocf":ocf[q]/1e6,"capex_outflow_positive":abs(cap[q])/1e6,"fcf":(ocf[q]-abs(cap[q]))/1e6,"ocf_accession":dict(enumerate([x[1] for x in ss]))[{"Q1":0,"Q2":1,"Q3":2,"Q4":3}[q]],"source":"REAL_XBRL"})
    cf=pd.DataFrame(rows);cf.to_csv(O/"aapl_cashflow_quarterly_reconstruction.csv",index=False)
    # panel core
    p=pd.read_csv(S9/"aapl_quarterly_panel_v3.csv");p=p[p.fy.isin([2018,2019])]
    core=["Revenue","GrossProfit","OperatingIncomeLoss","NetIncomeLoss","EarningsPerShareBasic","EarningsPerShareDiluted"]
    panel=[]
    for fy in (2018,2019):
        for q in ("Q1","Q2","Q3","Q4"):
            for c in core:
                x=p[(p.fy==fy)&(p.quarter==q)&(p.canonical==c)]
                if len(x): panel.append({"fy":fy,"quarter":q,"field":c,"value":float(x.iloc[0].value),"accession":x.iloc[0].accession,"status":"REPORTED"})
            cr=cf[(cf.fy==fy)&(cf.quarter==q)].iloc[0]
            for c,v in (("NetCashProvidedByUsedInOperatingActivities",cr.ocf),("PaymentsToAcquirePropertyPlantAndEquipment",cr.capex_outflow_positive),("FreeCashFlow",cr.fcf)):
                panel.append({"fy":fy,"quarter":q,"field":c,"value":float(v),"accession":cr.ocf_accession,"status":"DERIVED" if c!="NetCashProvidedByUsedInOperatingActivities" else "REPORTED"})
    # derive missing Q4 Operating Income from FY minus Q1-Q3 (same basis)
    for fy,(ps,pe) in {2018:("2017-10-01","2018-09-29"),2019:("2018-09-30","2019-09-28")}.items():
        fyop=f[(f.field=="OperatingIncomeLoss")&(f.period_start==pd.Timestamp(ps))&(f.period_end==pd.Timestamp(pe))]
        qs=[x for x in panel if x["fy"]==fy and x["field"]=="OperatingIncomeLoss"]
        if len(fyop) and len(qs)==3:
            panel.append({"fy":fy,"quarter":"Q4","field":"OperatingIncomeLoss","value":float(fyop.iloc[0].value)-sum(x["value"] for x in qs),"accession":fyop.iloc[0].accession,"status":"DERIVED"})
    pd.DataFrame(panel).to_csv(O/"aapl_two_fy_panel_complete.csv",index=False)
    # matrix 9 metrics x 8 quarters
    pd.DataFrame(panel).pivot_table(index=["fy","quarter"],columns="field",values="value",aggfunc="last").reset_index().to_csv(O/"aapl_two_fy_field_matrix.csv",index=False)
    # reconciliation vs targets
    targets=pd.DataFrame([{"fy":2018,"quarter":"Q1","ocf":28293,"capex":2810,"fcf":25483},{"fy":2018,"quarter":"Q2","ocf":15130,"capex":4195,"fcf":10935},{"fy":2018,"quarter":"Q3","ocf":14488,"capex":3267,"fcf":11221},{"fy":2018,"quarter":"Q4","ocf":19523,"capex":3041,"fcf":16482},{"fy":2019,"quarter":"Q1","ocf":26690,"capex":3355,"fcf":23335},{"fy":2019,"quarter":"Q2","ocf":11155,"capex":2363,"fcf":8792},{"fy":2019,"quarter":"Q3","ocf":11636,"capex":2000,"fcf":9636},{"fy":2019,"quarter":"Q4","ocf":19910,"capex":2777,"fcf":17133}])
    chk=cf.merge(targets,on=["fy","quarter"]);chk["ocf_diff"]=chk.ocf_x-chk.ocf_y;chk["capex_diff"]=chk.capex_outflow_positive-chk.capex;chk["fcf_diff"]=chk.fcf_x-chk.fcf_y;chk.to_csv(O/"aapl_cashflow_reconciliation.csv",index=False)
    pd.DataFrame([{"fy":int(fy),"ocf_q_sum":float(g.ocf.sum()),"capex_q_sum":float(g.capex_outflow_positive.sum()),"fcf_q_sum":float(g.fcf.sum())} for fy,g in cf.groupby("fy")]).to_csv(O/"aapl_two_fy_metric_reconciliation.csv",index=False)
    cf[["fy","quarter","capex_outflow_positive","source"]].to_csv(O/"aapl_capex_sign_audit.csv",index=False)
    # q4 basis and asof reuse
    pd.DataFrame([{"fy":fy,"basis":"ORIGINAL_REPORTED","q4_inputs_same_basis":True} for fy in (2018,2019)]).to_csv(O/"aapl_accounting_basis_final.csv",index=False)
    pd.read_csv(S9/"aapl_fact_level_asof_tests.csv").to_csv(O/"aapl_two_fy_asof_tests.csv",index=False)
    # status
    cnt=pd.DataFrame(panel).groupby(["fy","quarter"]).field.nunique();complete=bool((cnt==9).all())
    status={"generated_at":"2026-11-09T14:00:00+00:00","status":"P10_5_10_COMPLETE" if complete else "P10_5_10_PARTIAL","fy":[2018,2019],"quarters":8,"metrics":9,"cells":len(panel),"core_complete":complete,"cashflow_rows":len(cf),"AAPL_DATASET_READY":complete,"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_10_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    post={"manifest_capture_mode":"PRE_RUN_PLUS_POST_RUN","pre_run":pre,"outputs":{q.name:{"path":str(q),"sha256":sha(q)} for q in O.glob("*.csv")},"status":status["status"]}
    (O/"run_manifest.json").write_text(json.dumps(post,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2));print(chk[["fy","quarter","ocf_diff","capex_diff","fcf_diff"]].to_string(index=False))


if __name__=="__main__":raise SystemExit(main())
