"""P10.6.5 fix XLNX lifecycle and replay HPQ 10-K/A financial changes."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd,requests
from lxml import etree

ROOT=Path(".");O=ROOT/"docs/research/p10_6_5_quality_pit_remediation";O.mkdir(parents=True,exist_ok=True)
P4=ROOT/"docs/research/p10_6_4_quality_xbrl_replay";UA={"User-Agent":"us-pit-research/1.0 research@example.com"}
TAGS={"NetIncomeLoss":["NetIncomeLoss"],"Equity":["StockholdersEquity"],"Assets":["Assets"],"OCF":["NetCashProvidedByUsedInOperatingActivities"],"Liabilities":["Liabilities"]}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(e):return etree.QName(e).localname


def parse_hpq(acc):
    a=acc.replace("-","");r=requests.get(f"https://www.sec.gov/Archives/edgar/data/47217/{a}/hpq-20221031_htm.xml",headers=UA,timeout=60);root=etree.fromstring(r.content)
    ctx={};facts=[]
    for c in root.iter():
        if local(c)=="context":
            cid=c.get("id");ps=pe=None;dims=[];inst=None
            for x in c.iter():
                n=local(x)
                if n=="startDate":ps=x.text
                elif n=="endDate":pe=x.text
                elif n=="instant":inst=x.text
                elif n in ("explicitMember","typedMember"):dims.append((x.get("dimension"),x.text))
            ctx[cid]={"start":ps,"end":pe or inst,"instant":inst,"dims":dims}
        elif c.get("contextRef") is not None:facts.append({"concept":local(c),"contextRef":c.get("contextRef"),"unit":c.get("unitRef"),"value":c.text})
    out={}
    for metric,tags in TAGS.items():
        cand=[f for f in facts if f["concept"] in tags and f["contextRef"] in ctx and not ctx[f["contextRef"]]["dims"]]
        if metric in ("Assets","Equity","Liabilities"):cand=[f for f in cand if ctx[f["contextRef"]]["instant"]]
        else:cand=[f for f in cand if ctx[f["contextRef"]]["start"] and ctx[f["contextRef"]]["end"] and 340<=(datetime.fromisoformat(ctx[f["contextRef"]]["end"])-datetime.fromisoformat(ctx[f["contextRef"]]["start"])).days<=380]
        # FY2022 end 2022-10-31
        cand=[f for f in cand if ctx[f["contextRef"]]["end"]=="2022-10-31"]
        if len(cand)==1:out[metric]=cand[0]
        elif len(cand)>1:
            vals={f["value"] for f in cand};out[metric]=cand[0] if len(vals)==1 else {"ambiguous":len(cand)}
    return out,r.content


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"inputs":{"p4":sha(P4/"quality_xbrl_context_validation.csv")},"command":"python -m tools.research.p10_6_5.remediate","timestamp":datetime.now(timezone.utc).isoformat(),"timezone":"UTC"}
    (O/"p10_6_5_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    d=pd.read_csv(P4/"quality_xbrl_context_validation.csv")
    # reclassify XLNX after acquisition
    d.loc[(d.ticker=="XLNX")&(d.cutoff.isin(["2023-03-31","2026-03-31"])),"status"]="NOT_APPLICABLE_AFTER_ACQUISITION"
    d.to_csv(O/"quality_context_resolution.csv",index=False);d.to_csv(O/"quality_xbrl_lineage_v3.csv",index=False)
    # XLNX lifecycle
    life=[{"event":"AMD-Xilinx acquisition closed","event_date":"2022-02-14","form":"8-K","accession":"0001104659-22-021762","detail":"Xilinx common shares converted into AMD consideration"},{"event":"Xilinx 25-NSE","event_date":"2022-02-14","form":"25-NSE","accession":"0001354457-22-000131","detail":"exchange delisting"},{"cutoff":"2017-03-31","applicable":True},{"cutoff":"2020-03-31","applicable":True},{"cutoff":"2023-03-31","applicable":False},{"cutoff":"2026-03-31","applicable":False}]
    pd.DataFrame(life).to_csv(O/"xlnx_acquisition_lifecycle.csv",index=False)
    # HPQ replay
    orig,oc=parse_hpq("0000047217-22-000068");amend,ac=parse_hpq("0000047217-23-000075");rows=[]
    for m in TAGS:
        o=orig.get(m);a=amend.get(m)
        ov=float(o["value"]) if isinstance(o,dict) and "value" in o else None;av=float(a["value"]) if isinstance(a,dict) and "value" in a else None
        rows.append({"metric":m,"original_accession":"0000047217-22-000068","amended_accession":"0000047217-23-000075","original_value":ov,"amended_value":av,"difference":None if ov is None or av is None else av-ov,"pct_change":None if not ov else (av-ov)/ov,"original_context":o.get("contextRef") if isinstance(o,dict) else "","amended_context":a.get("contextRef") if isinstance(a,dict) else "","status":"AMENDED_FACT" if ov!=av else "UNCHANGED"})
    h=pd.DataFrame(rows);h.to_csv(O/"hpq_10k_original_vs_amended.csv",index=False)
    # PIT timeline
    t=[]
    for date,label,use in (("2023-09-08","before amendment","ORIGINAL"),("2023-09-11","amendment filing date","ORIGINAL_CONSERVATIVE"),("2023-09-12","next session","AMENDED")):
        for r in h.itertuples():t.append({"date":date,"label":label,"metric":r.metric,"value":r.original_value if use!="AMENDED" else r.amended_value,"version":use})
    pd.DataFrame(t).to_csv(O/"hpq_amendment_pit_timeline.csv",index=False)
    pd.DataFrame([{"check":"second_full_five_name_build","status":"NOT_RUN","reason":"scope limited to remediation"}]).to_csv(O/"quality_repeatability_comparison.csv",index=False)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"p10_6_5_manifest.json"),"git_commit":pre["git_commit"],"outputs":{n:sha(O/n) for n in ("quality_context_resolution.csv","quality_xbrl_lineage_v3.csv","xlnx_acquisition_lifecycle.csv","hpq_10k_original_vs_amended.csv","hpq_amendment_pit_timeline.csv","quality_repeatability_comparison.csv")},"status":"QUALITY_SLICE_PARTIAL","timestamp":datetime.now(timezone.utc).isoformat()}
    m=json.loads((O/"p10_6_5_manifest.json").read_text());m["post_run"]=post;(O/"p10_6_5_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(post,indent=2));print(h.to_string(index=False))


if __name__=="__main__":raise SystemExit(main())
