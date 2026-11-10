"""P10.6.6 reconcile slice status, recover IBM/INTC sources, add HPQ liabilities."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd,requests
from lxml import etree

ROOT=Path(".");O=ROOT/"docs/research/p10_6_6_quality_slice_finalization";O.mkdir(parents=True,exist_ok=True)
P4=ROOT/"docs/research/p10_6_4_quality_xbrl_replay";P5=ROOT/"docs/research/p10_6_5_quality_pit_remediation";UA={"User-Agent":"us-pit-research/1.0 research@example.com"}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(e):return etree.QName(e).localname


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"inputs":{"p4":sha(P4/"quality_xbrl_context_validation.csv"),"p5":sha(P5/"quality_context_resolution.csv")},"command":"python -m tools.research.p10_6_6.finalize","timestamp":datetime.now(timezone.utc).isoformat(),"timezone":"UTC"}
    (O/"p10_6_6_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    a=pd.read_csv(P4/"quality_xbrl_context_validation.csv");b=pd.read_csv(P5/"quality_context_resolution.csv")
    rec=[]
    for i,(x,y) in enumerate(zip(a.itertuples(),b.itertuples()),1):
        reason="UNCHANGED"
        if x.status!=y.status:
            if y.status=="NOT_APPLICABLE_AFTER_ACQUISITION":reason="XLNX acquired by AMD 2022-02-14"
            else:reason="STATUS_CHANGED"
        rec.append({"row_id":i,"ticker":x.ticker,"cutoff":x.cutoff,"metric":getattr(x,"metric",None),"p46_status":x.status,"p65_status":y.status,"p46_context":getattr(x,"contextRef",None),"p65_context":getattr(y,"contextRef",None),"transition_reason":reason})
    pd.DataFrame(rec).to_csv(O/"quality_row_status_reconciliation.csv",index=False)
    # diagnostics: carry unresolved rows
    diag=[]
    for i,r in enumerate(b.itertuples(),1):
        if r.status=="XBRL_CONTEXT_UNRESOLVED":
            diag.append({"row_id":i,"ticker":r.ticker,"cutoff":r.cutoff,"metric":r.metric,"accession":r.accession,"concept":getattr(r,"concept",None),"candidate_count":getattr(r,"candidate_count",None),"decision":"XBRL_CONTEXT_UNRESOLVED","reason":"no unique consolidated context; segment/duplicate ambiguity"})
    pd.DataFrame(diag).to_csv(O/"quality_context_diagnostics.csv",index=False)
    b.to_csv(O/"quality_historical_lineage_final.csv",index=False)
    # IBM/INTC source recovery metadata + actual instance open
    recs=[]
    for t,c,acc,inst,domain in [("IBM","51143","0001047469-17-001061","ibm-20161231.xml","https://www.sec.gov/Archives/edgar/data/51143/000104746917001061/ibm-20161231.xml"),("INTC","50863","0000050863-17-000012","intc-20161231.xml","https://www.sec.gov/Archives/edgar/data/50863/000005086317000012/intc-20161231.xml")]:
        try:
            r=requests.get(domain,headers=UA,timeout=30);etree.fromstring(r.content);status="SOURCE_RECOVERED"
        except Exception:status="INSTANCE_FOUND_PARSE_FAILED"
        recs.append({"ticker":t,"cik":c,"accession":acc,"instance":inst,"http":getattr(r,"status_code",0),"bytes":len(getattr(r,"content",b"")),"status":status,"integration":"NOT_INTEGRATED_PLACEHOLDER_ROW"})
    pd.DataFrame(recs).to_csv(O/"ibm_intc_source_recovery.csv",index=False)
    # HPQ total liabilities derived from L+SE - equity
    def hpq(acc):
        a=acc.replace("-","");r=requests.get(f"https://www.sec.gov/Archives/edgar/data/47217/{a}/hpq-20221031_htm.xml",headers=UA,timeout=60);root=etree.fromstring(r.content)
        ctx={};facts=[]
        for c in root.iter():
            if local(c)=="context":
                cid=c.get("id");ps=pe=inst=None;dims=[]
                for x in c.iter():
                    n=local(x)
                    if n=="startDate":ps=x.text
                    elif n=="endDate":pe=x.text
                    elif n=="instant":inst=x.text
                    elif n in ("explicitMember","typedMember"):dims.append((x.get("dimension"),x.text))
                ctx[cid]={"start":ps,"end":pe or inst,"dims":dims}
            elif c.get("contextRef") is not None:facts.append({"c":local(c),"r":c.get("contextRef"),"v":c.text})
        def get(tag):
            c=[f for f in facts if f["c"]==tag and f["r"] in ctx and ctx[f["r"]]["end"]=="2022-10-31" and not ctx[f["r"]]["dims"]]
            return c[0] if len(c)==1 else None
        return get("LiabilitiesAndStockholdersEquity"),get("StockholdersEquity")
    o1,e1=hpq("0000047217-22-000068");o2,e2=hpq("0000047217-23-000075")
    def val(x):return float(x["v"]) if x else None
    rows=[{"metric":"TotalLiabilities","original_accession":"0000047217-22-000068","amended_accession":"0000047217-23-000075","original_value":val(o1)-val(e1) if o1 and e1 else None,"amended_value":val(o2)-val(e2) if o2 and e2 else None,"method":"LiabilitiesAndStockholdersEquity - StockholdersEquity","original_context":o1["r"] if o1 else "","amended_context":o2["r"] if o2 else ""}]
    pd.DataFrame(rows).to_csv(O/"hpq_amendment_replay_final.csv",index=False)
    pd.DataFrame([{"check":"two_end_to_end_runs","status":"NOT_RUN","reason":"no second full SEC fetch in this slice"}]).to_csv(O/"quality_repeatability_comparison.csv",index=False)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"p10_6_6_manifest.json"),"git_commit":pre["git_commit"],"outputs":{n:sha(O/n) for n in ("quality_row_status_reconciliation.csv","quality_context_diagnostics.csv","quality_historical_lineage_final.csv","ibm_intc_source_recovery.csv","hpq_amendment_replay_final.csv","quality_repeatability_comparison.csv")},"status":"QUALITY_SLICE_PARTIAL","timestamp":datetime.now(timezone.utc).isoformat()}
    m=json.loads((O/"p10_6_6_manifest.json").read_text());m["post_run"]=post;(O/"p10_6_6_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(post,indent=2));print(pd.DataFrame(rows).to_string(index=False))


if __name__=="__main__":raise SystemExit(main())
