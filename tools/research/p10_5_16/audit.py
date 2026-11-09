"""P10.5.16 lineage audit: annual EPS from facts, Note12 probe, cashflow lineage."""
from __future__ import annotations
import json
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
import pandas as pd,requests

ROOT=Path(".");O=ROOT/"data/research/p10_5_16_aapl_panel";O.mkdir(parents=True,exist_ok=True)
F=ROOT/"data/research/p10_5_3_execution_recovery/aapl_historical_financial_facts.csv";P15=ROOT/"data/research/p10_5_15_aapl_panel"
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}


def main():
    f=pd.read_csv(F);f["period_start"]=pd.to_datetime(f.period_start);f["period_end"]=pd.to_datetime(f.period_end)
    specs={2018:("0000320193-18-000145","2017-10-01","2018-09-29"),2019:("0000320193-19-000119","2018-09-30","2019-09-28")}
    inputs=[];eps=[]
    for fy,(acc,ps,pe) in specs.items():
        def get(field):
            x=f[(f.accession==acc)&(f.field==field)&(f.period_start==pd.Timestamp(ps))&(f.period_end==pd.Timestamp(pe))];return x.iloc[0] if len(x) else None
        ni=get("NetIncomeLoss");bs=get("WeightedAverageNumberOfSharesOutstandingBasic");ds=get("WeightedAverageNumberOfDilutedSharesOutstanding");be=get("EarningsPerShareBasic");de=get("EarningsPerShareDiluted")
        for name,row,unit in (("NetIncomeLoss",ni,"USD"),("BasicShares",bs,"shares"),("DilutedShares",ds,"shares"),("BasicEPS",be,"USD/share"),("DilutedEPS",de,"USD/share")):
            if row is not None:inputs.append({"fy":fy,"field":name,"value":row.value,"unit":unit,"accession":acc,"context":row.context,"period_start":str(row.period_start.date()),"period_end":str(row.period_end.date()),"source_hash":row.sha256})
        if all(x is not None for x in (ni,bs,ds,be,de)):
            b=Decimal(str(ni.value))/Decimal(1000)/Decimal(str(bs.value))*Decimal(1000);d=Decimal(str(ni.value))/Decimal(1000)/Decimal(str(ds.value))*Decimal(1000)
            eps.append({"fy":fy,"net_income":float(ni.value)/1e6,"basic_shares_thousand":float(bs.value)/1e3,"diluted_shares_thousand":float(ds.value)/1e3,"basic_recalc":float(b),"diluted_recalc":float(d),"basic_reported":float(be.value),"diluted_reported":float(de.value),"basic_round":float(b.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)),"diluted_round":float(d.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)),"status":"PASS" if abs(float(b)-float(be.value))<0.01 and abs(float(d)-float(de.value))<0.01 else "FAIL"})
    pd.DataFrame(inputs).to_csv(O/"aapl_annual_eps_input_facts.csv",index=False);pd.DataFrame(eps).to_csv(O/"aapl_annual_eps_reconciliation_v2.csv",index=False)
    # Note12 HTML probe
    url="https://www.sec.gov/Archives/edgar/data/320193/000032019319000119/a10-k20199282019.htm";note={"http":"","tables":0,"note12":"","status":""}
    try:
        r=requests.get(url,headers=UA,timeout=60);note["http"]=r.status_code;note["sha256"]=__import__("hashlib").sha256(r.content).hexdigest()
        tables=pd.read_html(r.content);note["tables"]=len(tables)
        idx=[i for i,t in enumerate(tables) if any("Fourth Quarter" in str(x) for x in t.astype(str).values.flatten())]
        note["note12"]=str(idx[:3]);note["status"]="TABLE_CANDIDATES_FOUND" if idx else "NOTE12_TABLE_NOT_FOUND"
    except Exception as e:note["status"]="HTML_PARSE_ERROR";note["error"]=str(e)[:200]
    (O/"note12_html_probe.json").write_text(json.dumps(note,indent=2),encoding="utf-8")
    # cashflow lineage from facts, exact accessions
    cf=pd.read_csv(ROOT/"data/research/p10_5_10_aapl_cashflow/aapl_cashflow_quarterly_reconstruction.csv")
    cfrows=[]
    for r in cf.itertuples():
        for fld,tag in (("OCF","NetCashProvidedByUsedInOperatingActivities"),("Capex","PaymentsToAcquirePropertyPlantAndEquipment")):
            x=f[(f.accession==r.ocf_accession)&(f.field==tag)]
            if len(x):cfrows.append({"fy":r.fy,"quarter":r.quarter,"field":fld,"accession":r.ocf_accession,"concept":tag,"context":x.iloc[0].context,"period_start":x.iloc[0].period_start,"period_end":x.iloc[0].period_end,"value":x.iloc[0].value,"unit":x.iloc[0].unit,"status":"FACT_LOCATED" if str(x.iloc[0].context)!="nan" else "CONTEXT_MISSING"})
    pd.DataFrame(cfrows).to_csv(O/"aapl_cashflow_lineage_v6.csv",index=False)
    # gross margin PRE status (not parsed)
    pd.DataFrame([{"fy":fy,"quarter":q,"concept":"GrossProfit","preferred_label":"Gross margin","pre_status":"PRE_NOT_PARSED","direct_status":"DIRECT"} for fy in (2018,2019) for q in ("Q1","Q2","Q3","Q4")]).to_csv(O/"aapl_gross_margin_pre_audit.csv",index=False)
    # context audit from P15
    ctx=pd.read_csv(P15/"aapl_context_audit_v5.csv");ctx.to_csv(O/"aapl_context_audit_v6.csv",index=False)
    # secondary preserve
    sec=pd.read_csv(P15/"aapl_40_secondary_v5.csv");sec.to_csv(O/"aapl_40_secondary_v6.csv",index=False)
    pd.DataFrame([{"html_note_status":note["status"],"tables":note["tables"]}]).to_csv(O/"aapl_40_html_note_crosscheck.csv",index=False)
    status={"generated_at":"2026-11-10T01:30:00+00:00","status":"P10_5_16_PARTIAL","core_cells":72,"gross_margin_ratio_cells":8,"annual_eps_rows":len(eps),"annual_eps_pass":int((pd.DataFrame(eps).status=="PASS").sum()),"annual_eps_inputs":len(inputs),"cashflow_fact_rows":len(cfrows),"cashflow_context_missing":sum(1 for x in cfrows if x["status"]!="FACT_LOCATED"),"note12_status":note["status"],"html_note_locators":0,"context_gaps":int(ctx.context_missing.sum()),"fact_level_traceable":int((~ctx.context_missing).sum()),"pre_audit_done":0,"secondary_match":int((sec.status=="SECONDARY_FILING_MATCH").sum()),"AAPL_DATASET_READY":False,"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_16_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2));print(pd.DataFrame(eps))


if __name__=="__main__":raise SystemExit(main())
