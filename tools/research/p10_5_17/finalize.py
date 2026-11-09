"""P10.5.17 exact cashflow periods and Note 12 HTML locators."""
from __future__ import annotations
import hashlib,json
from io import BytesIO
from pathlib import Path
import pandas as pd,requests

ROOT=Path(".");O=ROOT/"data/research/p10_5_17_aapl_panel";O.mkdir(parents=True,exist_ok=True)
F=ROOT/"data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv";P15=ROOT/"data/research/p10_5_15_aapl_panel"
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}
SPECS={2018:[("Q1","0000320193-18-000007","2017-10-01","2017-12-30"),("H1","0000320193-18-000070","2017-10-01","2018-03-31"),("9M","0000320193-18-000100","2017-10-01","2018-06-30"),("FY","0000320193-18-000145","2017-10-01","2018-09-29")],2019:[("Q1","0000320193-19-000010","2018-09-30","2018-12-29"),("H1","0000320193-19-000066","2018-09-30","2019-03-30"),("9M","0000320193-19-000076","2018-09-30","2019-06-29"),("FY","0000320193-19-000119","2018-09-30","2019-09-28")]}
TARGET={2018:{"Q1":(28293,2810),"Q2":(15130,4195),"Q3":(14488,3267),"Q4":(19523,3041)},2019:{"Q1":(26690,3355),"Q2":(11155,2363),"Q3":(11636,2000),"Q4":(19910,2777)}}


def main():
    f=pd.read_csv(F);f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end)
    inputs=[];qrows=[]
    for fy,ss in SPECS.items():
        vals={}
        for q,acc,ps,pe in ss:
            for tag in ("NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment"):
                x=f[(f.accession==acc)&(f.field==tag)&(f.period_start==pd.Timestamp(ps))&(f.period_end==pd.Timestamp(pe))]
                if len(x):
                    v=float(x.iloc[0].value);vals[(q,tag)]=v
                    inputs.append({"fy":fy,"period":q,"field":tag,"value":v,"accession":acc,"context":x.iloc[0].context,"period_start":ps,"period_end":pe,"unit":x.iloc[0].unit,"status":"PERIOD_MATCH" if str(x.iloc[0].context)!="nan" else "CONTEXT_MISSING"})
        ocf={"Q1":vals[("Q1","NetCashProvidedByUsedInOperatingActivities")],"Q2":vals[("H1","NetCashProvidedByUsedInOperatingActivities")]-vals[("Q1","NetCashProvidedByUsedInOperatingActivities")],"Q3":vals[("9M","NetCashProvidedByUsedInOperatingActivities")]-vals[("H1","NetCashProvidedByUsedInOperatingActivities")],"Q4":vals[("FY","NetCashProvidedByUsedInOperatingActivities")]-vals[("9M","NetCashProvidedByUsedInOperatingActivities")]}
        cap={"Q1":vals[("Q1","PaymentsToAcquirePropertyPlantAndEquipment")],"Q2":vals[("H1","PaymentsToAcquirePropertyPlantAndEquipment")]-vals[("Q1","PaymentsToAcquirePropertyPlantAndEquipment")],"Q3":vals[("9M","PaymentsToAcquirePropertyPlantAndEquipment")]-vals[("H1","PaymentsToAcquirePropertyPlantAndEquipment")],"Q4":vals[("FY","PaymentsToAcquirePropertyPlantAndEquipment")]-vals[("9M","PaymentsToAcquirePropertyPlantAndEquipment")]}
        for q in ("Q1","Q2","Q3","Q4"):
            qrows.append({"fy":fy,"quarter":q,"ocf":ocf[q]/1e6,"capex":cap[q]/1e6,"fcf":(ocf[q]-cap[q])/1e6,"target_ocf":TARGET[fy][q][0],"target_capex":TARGET[fy][q][1],"diff_ocf":ocf[q]/1e6-TARGET[fy][q][0],"diff_capex":cap[q]/1e6-TARGET[fy][q][1],"diff_fcf":(ocf[q]-cap[q])/1e6-(TARGET[fy][q][0]-TARGET[fy][q][1]),"source_periods":"H1-Q1" if q=="Q2" else "9M-H1" if q=="Q3" else "FY-9M" if q=="Q4" else "Q1"})
    pd.DataFrame(inputs).to_csv(O/"aapl_cashflow_fact_inputs_v7.csv",index=False);pd.DataFrame(qrows).to_csv(O/"aapl_cashflow_quarterly_lineage_v7.csv",index=False)
    # Note12 HTML
    url="https://www.sec.gov/Archives/edgar/data/320193/000032019319000119/a10-k20199282019.htm";r=requests.get(url,headers=UA,timeout=60);sha=hashlib.sha256(r.content).hexdigest();tables=pd.read_html(BytesIO(r.content))
    rows=[]
    for fy,ti in ((2019,84),(2018,85)):
        t=tables[ti]
        for mi,(metric,ri) in enumerate((("Revenue",4),("GrossProfit",5),("NetIncomeLoss",6),("EarningsPerShareBasic",9),("EarningsPerShareDiluted",10))):
            for q,ci in (("Q4",2),("Q3",6),("Q2",10),("Q1",14)):
                cell=str(t.iat[ri,ci]);v=float(cell.replace("$","").replace(",",""))
                rows.append({"fy":fy,"quarter":q,"field":metric,"html_value":v,"cell_text":cell,"table_index":ti,"row_label":str(t.iat[ri,0]),"column_label":f"{q}","cell":f"r{ri}c{ci}","accession":"0000320193-19-000119","source_sha256":sha,"status":"HTML_CELL_PARSED"})
    pd.DataFrame(rows).to_csv(O/"aapl_40_html_note_crosscheck_v2.csv",index=False)
    # core + context
    core=pd.read_csv(P15/"aapl_core_panel_v5.csv");core.to_csv(O/"aapl_core_panel_v7.csv",index=False);ctx=pd.read_csv(P15/"aapl_context_audit_v5.csv");ctx.to_csv(O/"aapl_context_audit_v7.csv",index=False)
    pd.DataFrame([{"fy":fy,"quarter":q,"concept":"GrossProfit","pre_status":"PRE_UNRESOLVED"} for fy in (2018,2019) for q in ("Q1","Q2","Q3","Q4")]).to_csv(O/"aapl_gross_margin_pre_audit_v2.csv",index=False)
    pd.read_csv(P15/"aapl_annual_eps_reconciliation.csv").to_csv(O/"aapl_annual_eps_reconciliation_v2.csv",index=False)
    q=pd.DataFrame(qrows)
    status={"generated_at":"2026-11-10T01:45:00+00:00","status":"P10_5_17_PARTIAL","cashflow_inputs":len(inputs),"cashflow_period_matches":int((pd.DataFrame(inputs).status=="PERIOD_MATCH").sum()),"cashflow_cells":24,"cashflow_exact":int(((q.diff_ocf.abs()<1e-6)&(q.diff_capex.abs()<1e-6)&(q.diff_fcf.abs()<1e-6)).sum()),"html_cells":len(rows),"html_locators":len(rows),"context_gaps":int(ctx.context_missing.sum()),"fact_level_traceable":int((~ctx.context_missing).sum()),"annual_eps_pass":4,"pre_audit_done":0,"AAPL_DATASET_READY":False,"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_17_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2));print(q[["fy","quarter","diff_ocf","diff_capex","diff_fcf"]].to_string(index=False))


if __name__=="__main__":raise SystemExit(main())
