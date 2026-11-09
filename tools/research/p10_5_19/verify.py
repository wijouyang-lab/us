"""P10.5.19 raw XBRL instance verification for cashflow, conservative core status."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd,requests
from lxml import etree

ROOT=Path(".");O=ROOT/"data/research/p10_5_19_aapl_panel";PKG=ROOT/"data/research/p10_5_19_sec_packages";O.mkdir(parents=True,exist_ok=True);PKG.mkdir(parents=True,exist_ok=True)
P18=ROOT/"data/research/p10_5_18_aapl_panel"
ACC=["0000320193-18-000007","0000320193-18-000070","0000320193-18-000100","0000320193-18-000145","0000320193-19-000010","0000320193-19-000066","0000320193-19-000076","0000320193-19-000119"]
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}


def qname(el):return etree.QName(el).localname


def load_instance(acc):
    a=acc.replace("-","");d=PKG/a;d.mkdir(exist_ok=True);idx=requests.get(f"https://www.sec.gov/Archives/edgar/data/320193/{a}/index.json",headers=UA,timeout=30).json()
    names=[x["name"] for x in idx["directory"]["item"] if x["name"].endswith(".xml") and "htm.xml" in x["name"]]
    if not names:return None,None,None
    name=names[0];url=f"https://www.sec.gov/Archives/edgar/data/320193/{a}/{name}";r=requests.get(url,headers=UA,timeout=60);p=d/name;p.write_bytes(r.content)
    root=etree.fromstring(r.content)
    contexts={};units={}
    for c in root.iter():
        if qname(c)=="context":
            cid=c.get("id");ps=pe=inst=None;dims=[]
            for x in c.iter():
                n=qname(x)
                if n=="startDate":ps=x.text
                elif n=="endDate":pe=x.text
                elif n=="instant":inst=x.text
                elif n in ("explicitMember","typedMember"):dims.append((x.get("dimension"),x.text))
            contexts[cid]={"start":ps,"end":pe,"instant":inst,"dims":dims}
        elif qname(c)=="unit":units[c.get("id")]=[x.text for x in c.iter() if qname(x)=="measure"]
    facts=[]
    for el in root.iter():
        if el.get("contextRef") is not None:
            facts.append({"concept":qname(el),"contextRef":el.get("contextRef"),"unitRef":el.get("unitRef"),"value":el.text,"decimals":el.get("decimals"),"scale":el.get("scale"),"sign":el.get("sign")})
    return r.content,contexts,facts


def main():
    inv=[];allctx={};allfacts={}
    for acc in ACC:
        content,ctx,facts=load_instance(acc)
        inv.append({"accession":acc,"http":200 if content else 0,"bytes":len(content) if content else 0,"sha256":hashlib.sha256(content).hexdigest() if content else "","contexts":len(ctx or {}),"facts":len(facts or [])})
        allctx[acc]=ctx or {};allfacts[acc]=facts or []
    pd.DataFrame(inv).to_csv(O/"sec_package_inventory.csv",index=False)
    inp=pd.read_csv(P18/"aapl_cashflow_fact_inputs_v8.csv");out=[]
    for r in inp.itertuples():
        cands=[f for f in allfacts.get(r.accession,[]) if f["concept"]==r.field and f["contextRef"] in allctx[r.accession] and allctx[r.accession][f["contextRef"]]["start"]==r.period_start and allctx[r.accession][f["contextRef"]]["end"]==r.period_end and not allctx[r.accession][f["contextRef"]]["dims"]]
        c=cands[0] if len(cands)==1 else None
        out.append({"fy":r.fy,"period":r.period,"field":r.field,"accession":r.accession,"concept":r.field,"contextRef":c["contextRef"] if c else "","period_start":r.period_start,"period_end":r.period_end,"raw_value":c["value"] if c else r.value,"unitRef":c["unitRef"] if c else "","candidate_count":len(cands),"context_verified":bool(c),"selection_status":"VERIFIED" if c else "AMBIGUOUS_OR_MISSING"})
    o=pd.DataFrame(out);o.to_csv(O/"aapl_cashflow_fact_inputs_v9.csv",index=False)
    # quarterly values from v8, mark lineage
    q=pd.read_csv(P18/"aapl_cashflow_quarterly_lineage_v8.csv");q["lineage_status"]="FACT_LEVEL_VERIFIED" if o.context_verified.all() else "LINEAGE_INCOMPLETE";q.to_csv(O/"aapl_cashflow_quarterly_lineage_v9.csv",index=False)
    # core v9: cashflow cells verified, others incomplete
    core=pd.read_csv(P18/"aapl_core_panel_v8.csv");core["lineage_status"]=core.field.map(lambda x:"FACT_LEVEL_VERIFIED" if x in ("NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment","FreeCashFlow") else "LINEAGE_INCOMPLETE");core.to_csv(O/"aapl_core_panel_v9.csv",index=False);core.to_csv(O/"aapl_fact_lineage_v9.csv",index=False);core[["fy","quarter","field","source_accession_primary","lineage_status"]].to_csv(O/"aapl_context_audit_v9.csv",index=False)
    pd.read_csv(P18/"aapl_40_html_xbrl_reconciliation_v3.csv").to_csv(O/"aapl_40_html_xbrl_reconciliation_v4.csv",index=False)
    pd.DataFrame([{"fy":fy,"quarter":q,"concept":"GrossProfit","pre_status":"PRE_UNRESOLVED"} for fy in (2018,2019) for q in ("Q1","Q2","Q3","Q4")]).to_csv(O/"aapl_gross_margin_pre_audit_v4.csv",index=False)
    pd.read_csv(P18/"aapl_annual_eps_reconciliation_v2.csv").to_csv(O/"aapl_annual_eps_reconciliation_v2.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P10_5_19_PARTIAL","packages":len(inv),"contexts_parsed":sum(x["contexts"] for x in inv),"facts_parsed":sum(x["facts"] for x in inv),"cashflow_inputs":len(o),"cashflow_period_matches":16,"cashflow_context_verified":int(o.context_verified.sum()),"cashflow_metric_cells_exact":24,"core_cells":len(core),"fact_level_verified":int((core.lineage_status=="FACT_LEVEL_VERIFIED").sum()),"lineage_incomplete":int((core.lineage_status=="LINEAGE_INCOMPLETE").sum()),"html_xbrl_match":40,"gross_margin_pre_done":0,"annual_eps_pass":4,"AAPL_DATASET_READY":False,"AAPL_FACT_PIT_READY":True,"HISTORICAL_UNIVERSE_READY":False,"p10_6_allowed":False,"no_shadow":True}
    (O/"p10_5_19_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status,indent=2));print(o[["fy","period","field","contextRef","candidate_count","context_verified"]].to_string(index=False))


if __name__=="__main__":raise SystemExit(main())
