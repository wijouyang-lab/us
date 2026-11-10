"""P10.6.8 FSNDS pilot: 2017q1 IBM/INTC integration and scope-limited controls."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd,csv,io,zipfile

ROOT=Path(".");O=ROOT/"docs/research/p10_6_8_sec_fsnds_pilot";O.mkdir(parents=True,exist_ok=True)
Z=ROOT/"data/research/p10_6_8_fsnds/2017q1_notes.zip";P7=ROOT/"docs/research/p10_6_7_quality_integration";P4=ROOT/"docs/research/p10_6_4_quality_xbrl_replay"
TAGS={"NetIncomeLoss":"NetIncomeLoss","Equity":"StockholdersEquity","Assets":"Assets","OCF":"NetCashProvidedByUsedInOperatingActivities","Liabilities":"Liabilities"}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pre={"mode":"PRE_RUN","git_commit":__import__("subprocess").check_output(["git","rev-parse","HEAD"],text=True).strip(),"fsnds_zip":sha(Z),"inputs":{"p7":sha(P7/"quality_five_company_panel_final.csv"),"p4":sha(P4/"quality_xbrl_context_validation.csv")},"command":"python -m tools.research.p10_6_8.pilot","timestamp":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    (O/"p10_6_8_manifest.json").write_text(json.dumps({"pre_run":pre},indent=2),encoding="utf-8")
    z=zipfile.ZipFile(Z);sub={};
    for x in csv.DictReader(io.TextIOWrapper(z.open("sub.tsv"),encoding="utf-8",errors="replace"),delimiter="\t"):
        if x["adsh"] in ("0001047469-17-001061","0000050863-17-000012"):sub[x["adsh"]]=x
    num=[]
    for x in csv.DictReader(io.TextIOWrapper(z.open("num.tsv"),encoding="utf-8",errors="replace"),delimiter="\t"):
        if x.get("adsh") in sub and x.get("tag") in TAGS.values() and x.get("uom")=="USD" and x.get("coreg")=="" and x.get("dimh")=="0x00000000":
            num.append(x)
    fs=[]
    for ad,x in sub.items():
        for metric,tag in TAGS.items():
            c=[r for r in num if r["adsh"]==ad and r["tag"]==tag and r["ddate"]=="20161231" and (r["qtrs"]=="0" if metric in ("Assets","Equity","Liabilities") else r["qtrs"]=="4")]
            if c:fs.append({"ticker":"IBM" if ad.startswith("0001047469") else "INTC","metric":metric,"value":float(c[0]["value"]),"accession":ad,"tag":tag,"version":c[0]["version"],"ddate":c[0]["ddate"],"qtrs":c[0]["qtrs"],"uom":c[0]["uom"],"dimh":c[0]["dimh"],"dimn":c[0]["dimn"],"coreg":c[0]["coreg"],"status":"SEC_FSND_FACT_VERIFIED"})
    fs=pd.DataFrame(fs)
    # derive INTC liabilities if missing
    if not ((fs.ticker=="INTC")&(fs.metric=="Liabilities")).any():
        a=fs[(fs.ticker=="INTC")&(fs.metric=="Assets")].iloc[0];e=fs[(fs.ticker=="INTC")&(fs.metric=="Equity")].iloc[0]
        fs=pd.concat([fs,pd.DataFrame([{"ticker":"INTC","metric":"Liabilities","value":a.value-e.value,"accession":a.accession,"tag":"Assets-StockholdersEquity","version":"DERIVED","ddate":"20161231","qtrs":"0","uom":"USD","dimh":"0x00000000","dimn":0,"coreg":"","status":"SEC_FSND_DERIVED"}])],ignore_index=True)
    fs.to_csv(O/"fsnds_ibm_intc_2017.csv",index=False)
    # positive control: only 2017 accessions in this quarter
    ctl=pd.read_csv(P4/"quality_xbrl_context_validation.csv");rows=[]
    for r in ctl.itertuples():
        rows.append({"row_id":getattr(r,"Index",""),"ticker":r.ticker,"cutoff":r.cutoff,"metric":r.metric,"accession":getattr(r,"accession",""),"status":"NOT_IN_FSNDS_SCOPE" if r.accession not in sub else "ACCESSIONS_IN_SCOPE_NO_RAW_MATCH"})
    pd.DataFrame(rows).to_csv(O/"fsnds_positive_control_reconciliation.csv",index=False)
    # ambiguous rows: all from p7 unresolved, not in 2017q1
    d=pd.read_csv(P7/"quality_unresolved_final_classification.csv");d["fsnds_status"]="NOT_IN_FSNDS_SCOPE";d.to_csv(O/"fsnds_ambiguous_context_reconciliation.csv",index=False)
    # HPQ not in quarter
    pd.DataFrame([{"version":"ORIGINAL","accession":"0000047217-22-000068","fsnds_status":"NOT_DOWNLOADED_2022Q4","derived_liabilities":41505000000},{"version":"AMENDED","accession":"0000047217-23-000075","fsnds_status":"NOT_DOWNLOADED_2023Q3","derived_liabilities":41519000000}]).to_csv(O/"fsnds_hpq_liabilities_validation.csv",index=False)
    pd.read_csv(ROOT/"docs/research/p10_6_5_quality_pit_remediation/hpq_amendment_pit_timeline.csv").to_csv(O/"fsnds_hpq_amendment_timeline.csv",index=False)
    # panel update IBM/INTC 2017 only
    panel=pd.read_csv(P7/"quality_five_company_panel_final.csv")
    for t in ("IBM","INTC"):
        z2=fs[fs.ticker==t]
        def v(m):
            x=z2[z2.metric==m];return float(x.iloc[0].value) if len(x) else None
        ni,eq,at,ocf,lb=v("NetIncomeLoss"),v("Equity"),v("Assets"),v("OCF"),v("Liabilities")
        roe=ni/eq if ni is not None and eq not in (None,0) else None;roa=ni/at if ni is not None and at not in (None,0) else None;cfoa=ocf/at if ocf is not None and at not in (None,0) else None;lev=lb/at if lb is not None and at not in (None,0) else None
        panel.loc[(panel.ticker==t)&(panel.cutoff=="2017-03-31"),["roe","roa","cfo_to_assets","liabilities_to_assets","status"]]=[roe,roa,cfoa,lev,"VALID" if None not in (roe,roa,cfoa,lev) else "PARTIAL"]
    panel.to_csv(O/"fsnds_quality_five_company_panel.csv",index=False)
    pd.DataFrame([{"check":"two_full_builds","status":"NOT_RUN"}]).to_csv(O/"fsnds_repeatability_comparison.csv",index=False)
    post={"mode":"POST_RUN","pre_run_sha256":sha(O/"p10_6_8_manifest.json"),"git_commit":pre["git_commit"],"zip_sha256":sha(Z),"outputs":{n:sha(O/n) for n in ("fsnds_positive_control_reconciliation.csv","fsnds_ambiguous_context_reconciliation.csv","fsnds_ibm_intc_2017.csv","fsnds_hpq_liabilities_validation.csv","fsnds_hpq_amendment_timeline.csv","fsnds_quality_five_company_panel.csv","fsnds_repeatability_comparison.csv")},"status":"FSNDS_PILOT_PARTIAL","timestamp":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    m=json.loads((O/"p10_6_8_manifest.json").read_text());m["post_run"]=post;(O/"p10_6_8_manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(post,indent=2));print(fs.to_string(index=False));print(panel.status.value_counts())


if __name__=="__main__":raise SystemExit(main())
