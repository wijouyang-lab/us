"""P10.6.4 vertical slice: raw XBRL context verification for five cohort names."""
from __future__ import annotations
import hashlib,json
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd,requests
from lxml import etree

ROOT=Path(".");O=ROOT/"docs/research/p10_6_4_quality_xbrl_replay";O.mkdir(parents=True,exist_ok=True)
UA={"User-Agent":"us-pit-research/1.0 research@example.com"}
CUTOFF=["2017-03-31","2020-03-31","2023-03-31","2026-03-31"]
PICK=[("AAPL","320193"),("IBM","51143"),("INTC","50863"),("XLNX","743988"),("HPQ","47217")]
TAGS={"NetIncomeLoss":["NetIncomeLoss"],"Equity":["StockholdersEquity"],"Assets":["Assets"],"OCF":["NetCashProvidedByUsedInOperatingActivities"],"Liabilities":["Liabilities"]}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(e):return etree.QName(e).localname


def latest10k(cik,cutoff):
    d=requests.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",headers=UA,timeout=30).json();f=d["filings"]["recent"]
    for i in range(len(f["form"])):
        if f["form"][i]=="10-K" and f["filingDate"][i]<=cutoff:return f["accessionNumber"][i],f["filingDate"][i]
    return None,None


def parse_instance(acc):
    a=acc.replace("-","");idx=requests.get(f"https://www.sec.gov/Archives/edgar/data/{''}/{a}/index.json",headers=UA,timeout=30)
    # CIK path differs; caller fills
    return a


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"cohort_sha":sha("docs/research/p10_6_3_quality_expansion/quality_peer_cohort.csv"),"picks":PICK,"command":"python -m tools.research.p10_6_4.verify","timestamp":datetime.now(timezone.utc).isoformat(),"timezone":"UTC"}
    (O/"quality_replay_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    rows=[];filings=[]
    for ticker,cik in PICK:
        for cutoff in CUTOFF:
            acc,filed=latest10k(cik,cutoff)
            if not acc:rows.append({"ticker":ticker,"cutoff":cutoff,"status":"SOURCE_FILE_MISSING"});continue
            a=acc.replace("-","");idx=requests.get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{a}/index.json",headers=UA,timeout=30).json()
            names=[x["name"] for x in idx["directory"]["item"] if x["name"].endswith(".xml") and not any(s in x["name"] for s in ("_cal.xml","_def.xml","_lab.xml","_pre.xml","FilingSummary"))]
            inst=next((n for n in names if n.startswith("aapl-") or n.endswith("_htm.xml")),names[0] if names else None)
            if not inst:rows.append({"ticker":ticker,"cutoff":cutoff,"accession":acc,"status":"INSTANCE_UNRESOLVED"});continue
            url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{a}/{inst}";r=requests.get(url,headers=UA,timeout=60);root=etree.fromstring(r.content)
            ctx={};facts=[]
            for c in root.iter():
                if local(c)=="context":
                    cid=c.get("id");ps=pe=None;dims=[]
                    for x in c.iter():
                        n=local(x)
                        if n=="startDate":ps=x.text
                        elif n=="endDate":pe=x.text
                        elif n=="instant":pe=x.text
                        elif n in ("explicitMember","typedMember"):dims.append((x.get("dimension"),x.text))
                    ctx[cid]={"start":ps,"end":pe,"dims":dims}
                elif c.get("contextRef") is not None:facts.append({"concept":local(c),"contextRef":c.get("contextRef"),"unit":c.get("unitRef"),"value":c.text})
            filings.append({"ticker":ticker,"cutoff":cutoff,"accession":acc,"filed":filed,"instance":inst,"sha256":hashlib.sha256(r.content).hexdigest(),"contexts":len(ctx),"facts":len(facts)})
            for metric,tags in TAGS.items():
                cand=[x for x in facts if x["concept"] in tags and x["contextRef"] in ctx and not ctx[x["contextRef"]]["dims"]]
                # annual or instant period check
                cand=[x for x in cand if (metric in ("Assets","Equity","Liabilities") and ctx[x["contextRef"]]["start"] is None) or (metric not in ("Assets","Equity","Liabilities") and ctx[x["contextRef"]]["start"] and 340<=(date.fromisoformat(ctx[x["contextRef"]]["end"])-date.fromisoformat(ctx[x["contextRef"]]["start"])).days<=380)]
                if cand:
                    maxend=max(ctx[x["contextRef"]]["end"] for x in cand)
                    cand=[x for x in cand if ctx[x["contextRef"]]["end"]==maxend]
                rows.append({"ticker":ticker,"cutoff":cutoff,"metric":metric,"accession":acc,"filed":filed,"instance":inst,"concept":cand[0]["concept"] if len(cand)==1 else "","contextRef":cand[0]["contextRef"] if len(cand)==1 else "","start":ctx[cand[0]["contextRef"]]["start"] if len(cand)==1 else "","end":ctx[cand[0]["contextRef"]]["end"] if len(cand)==1 else "","unit":cand[0]["unit"] if len(cand)==1 else "","raw_value":cand[0]["value"] if len(cand)==1 else "","candidate_count":len(cand),"status":"XBRL_CONTEXT_VERIFIED" if len(cand)==1 else "XBRL_CONTEXT_UNRESOLVED"})
    pd.DataFrame(rows).to_csv(O/"quality_xbrl_context_validation.csv",index=False);pd.DataFrame(filings).to_csv(O/"quality_vertical_filings.csv",index=False)
    # amendment timeline metadata only
    amend=[{"company":"HPQ","original_10K":"0000047217-22-000068","original_filed":"2022-12-06","amended_10K":"0000047217-23-000075","amended_filed":"2023-09-11","status":"AMENDMENT_REPLAY_UNRESOLVED","reason":"financial-fact change not parsed in this slice"}]
    pd.DataFrame(amend).to_csv(O/"quality_amendment_replay.csv",index=False)
    # lineage copy from P10.6.3 for context rows? build minimal
    pd.DataFrame(rows).to_csv(O/"quality_historical_lineage_v2.csv",index=False)
    ok=sum(1 for r in rows if r["status"]=="XBRL_CONTEXT_VERIFIED");total=len(rows)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"quality_replay_manifest.json"),"git_commit":pre["git_commit"],"outputs":{n:sha(O/n) for n in ("quality_xbrl_context_validation.csv","quality_vertical_filings.csv","quality_amendment_replay.csv","quality_historical_lineage_v2.csv")},"rows":total,"verified":ok,"status":"XBRL_VERTICAL_SLICE_PASS" if ok==total else "XBRL_VERTICAL_SLICE_PARTIAL","timestamp":datetime.now(timezone.utc).isoformat()}
    m=json.loads((O/"quality_replay_manifest.json").read_text());m["post_run"]=post;(O/"quality_replay_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(post,indent=2))


if __name__=="__main__":raise SystemExit(main())
