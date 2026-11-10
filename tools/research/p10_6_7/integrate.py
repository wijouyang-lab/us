"""P10.6.7 integrate IBM/INTC 2017 and HPQ liabilities; final five-company panel."""
from __future__ import annotations
import hashlib,json
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd,requests
from lxml import etree

ROOT=Path(".");O=ROOT/"docs/research/p10_6_7_quality_integration";O.mkdir(parents=True,exist_ok=True)
P6=ROOT/"docs/research/p10_6_6_quality_slice_finalization";P1=ROOT/"docs/research/p10_6_1_pit_pilot";UA={"User-Agent":"us-pit-research/1.0 research@example.com"}
CUTOFF=["2017-03-31","2020-03-31","2023-03-31","2026-03-31"]
TAGS={"NetIncomeLoss":["NetIncomeLoss"],"Equity":["StockholdersEquity"],"Assets":["Assets"],"OCF":["NetCashProvidedByUsedInOperatingActivities"],"Liabilities":["Liabilities"]}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(e):
    try:return etree.QName(e).localname
    except Exception:return ""


def parse(url):
    r=requests.get(url,headers=UA,timeout=60);root=etree.fromstring(r.content);ctx={};facts=[]
    for c in root.iter():
        if local(c)=="context":
            cid=c.get("id");ps=pe=inst=None;dims=[]
            for x in c.iter():
                n=local(x)
                if n=="startDate":ps=x.text
                elif n=="endDate":pe=x.text
                elif n=="instant":inst=x.text
                elif n in ("explicitMember","typedMember"):dims.append((x.get("dimension"),x.text))
            ctx[cid]={"start":ps,"end":pe or inst,"instant":inst,"dims":dims}
        elif c.get("contextRef") is not None:facts.append({"c":local(c),"r":c.get("contextRef"),"u":c.get("unitRef"),"v":c.text})
    return ctx,facts,r.content


def metric(ctx,facts,tag,metric):
    cand=[f for f in facts if f["c"]==tag and f["r"] in ctx and not ctx[f["r"]]["dims"]]
    if metric in ("Assets","Equity","Liabilities"):cand=[f for f in cand if ctx[f["r"]]["instant"]=="2016-12-31"]
    else:cand=[f for f in cand if ctx[f["r"]]["start"] and ctx[f["r"]]["end"] and ctx[f["r"]]["start"].startswith("2016-01") and ctx[f["r"]]["end"]=="2016-12-31"]
    if len(cand)==1:return cand[0]
    return None


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"inputs":{"p6":sha(P6/"quality_historical_lineage_final.csv"),"p1":sha(P1/"pit_reconstruction_results.csv")},"command":"python -m tools.research.p10_6_7.integrate","timestamp":datetime.now(timezone.utc).isoformat(),"timezone":"UTC"}
    (O/"p10_6_7_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    ints=[]
    for t,c,url in [("IBM","51143","https://www.sec.gov/Archives/edgar/data/51143/000104746917001061/ibm-20161231.xml"),("INTC","50863","https://www.sec.gov/Archives/edgar/data/50863/000005086317000012/intc-20161231.xml")]:
        ctx,facts,content=parse(url)
        for m,tags in TAGS.items():
            f=metric(ctx,facts,tags[0],m)
            ints.append({"ticker":t,"cutoff":"2017-03-31","metric":m,"value":float(f["v"]) if f else None,"accession":"0001047469-17-001061" if t=="IBM" else "0000050863-17-000012","instance":url.rsplit("/",1)[-1],"concept":f["c"] if f else "","contextRef":f["r"] if f else "","start":ctx[f["r"]]["start"] if f else "","end":ctx[f["r"]]["end"] if f else "","unit":f["u"] if f else "","status":"FACT_LEVEL_VERIFIED" if f else "FACT_NOT_FOUND","lineage":"SOURCE_RECOVERED_AND_FACTS_INTEGRATED" if f else "SOURCE_RECOVERED_PENDING_FACT_INTEGRATION"})
    pd.DataFrame(ints).to_csv(O/"ibm_intc_2017_quality_integration.csv",index=False)
    # HPQ liabilities via identity
    def hpq(acc):
        ctx,facts,content=parse(f"https://www.sec.gov/Archives/edgar/data/47217/{acc.replace('-','')}/hpq-20221031_htm.xml")
        def get(tag):
            c=[f for f in facts if f["c"]==tag and f["r"] in ctx and ctx[f["r"]]["end"]=="2022-10-31" and not ctx[f["r"]]["dims"]]
            return c[0] if c else None
        a=get("Assets");e=get("StockholdersEquity")
        return a,e
    h=[];vals={}
    for acc in ("0000047217-22-000068","0000047217-23-000075"):
        a,e=hpq(acc);av=float(a["v"]) if a else None;ev=float(e["v"]) if e else None
        vals[acc]=(av,ev,av-ev if av is not None and ev is not None else None,a,e)
        h.append({"version":"ORIGINAL" if "22-000068" in acc else "AMENDED","accession":acc,"assets":av,"equity":ev,"total_liabilities":av-ev if av is not None and ev is not None else None,"assets_context":a["r"] if a else "","equity_context":e["r"] if e else "","status":"DERIVED_FORMULA_VERIFIED" if av is not None and ev is not None and a["r"]==e["r"] else "XBRL_CONTEXT_UNRESOLVED"})
    pd.DataFrame(h).to_csv(O/"hpq_total_liabilities_final.csv",index=False)
    # unresolved classification
    d=pd.read_csv(P6/"quality_context_diagnostics.csv");cls=[]
    for r in d.itertuples():
        if getattr(r,"decision","")!="XBRL_CONTEXT_UNRESOLVED":continue
        n=r.candidate_count
        cat="NO_CONSOLIDATED_FACT" if n==0 else "MULTIPLE_CONSOLIDATED_CANDIDATES" if n>1 else "OTHER_UNRESOLVED"
        cls.append({"row_id":r.row_id,"ticker":r.ticker,"cutoff":r.cutoff,"metric":r.metric,"candidate_count":n,"final_class":cat,"affects_quality":True,"next_step":"manual PRE inspection" if cat=="MULTIPLE_CONSOLIDATED_CANDIDATES" else "source unavailable"})
    pd.DataFrame(cls).to_csv(O/"quality_unresolved_final_classification.csv",index=False)
    # final 5-company panel from P10.6.1 raw
    base=pd.read_csv(P1/"pit_reconstruction_results.csv");panel=[]
    for t in ("AAPL","IBM","INTC","XLNX","HPQ"):
        for cutoff in CUTOFF:
            if t=="XLNX" and cutoff in ("2023-03-31","2026-03-31"):
                panel.append({"ticker":t,"cutoff":cutoff,"roe":None,"roa":None,"cfo_to_assets":None,"liabilities_to_assets":None,"status":"NOT_APPLICABLE_AFTER_ACQUISITION"});continue
            x=base[(base.ticker==t)&(base.cutoff==cutoff)]
            def v(m):
                y=x[x.metric==m];return float(y.iloc[0].value) if len(y) else None
            ni=v("NetIncomeLoss");eq=v("Equity");at=v("Assets");ocf=v("OCF");lb=v("Liabilities")
            if t in ("IBM","INTC") and cutoff=="2017-03-31":
                z=pd.DataFrame(ints);z=z[(z.ticker==t)&(z.cutoff==cutoff)]
                def vv(m):
                    y=z[z.metric==m];return float(y.iloc[0].value) if len(y) and pd.notna(y.iloc[0].value) else None
                ni,eq,at,ocf,lb=vv("NetIncomeLoss"),vv("Equity"),vv("Assets"),vv("OCF"),vv("Liabilities")
            roe=ni/eq if ni is not None and eq not in (None,0) else None;roa=ni/at if ni is not None and at not in (None,0) else None;cfoa=ocf/at if ocf is not None and at not in (None,0) else None;lev=lb/at if lb is not None and at not in (None,0) else None
            panel.append({"ticker":t,"cutoff":cutoff,"roe":roe,"roa":roa,"cfo_to_assets":cfoa,"liabilities_to_assets":lev,"status":"VALID" if None not in (roe,roa,cfoa,lev) else "PARTIAL"})
    pd.DataFrame(panel).to_csv(O/"quality_five_company_panel_final.csv",index=False)
    pd.DataFrame([{"check":"two_full_builds","status":"NOT_RUN"}]).to_csv(O/"quality_repeatability_final.csv",index=False)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"p10_6_7_manifest.json"),"git_commit":pre["git_commit"],"outputs":{n:sha(O/n) for n in ("ibm_intc_2017_quality_integration.csv","hpq_total_liabilities_final.csv","quality_unresolved_final_classification.csv","quality_five_company_panel_final.csv","quality_repeatability_final.csv")},"status":"QUALITY_SLICE_PARTIAL","timestamp":datetime.now(timezone.utc).isoformat()}
    m=json.loads((O/"p10_6_7_manifest.json").read_text());m["post_run"]=post;(O/"p10_6_7_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(post,indent=2));print(pd.DataFrame(h).to_string(index=False));print(pd.DataFrame(ints).groupby("ticker").status.value_counts().to_string())


if __name__=="__main__":raise SystemExit(main())
